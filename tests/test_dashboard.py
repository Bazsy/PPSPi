from __future__ import annotations

import errno
import fcntl
import http.client
import importlib.machinery
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = PROJECT_ROOT / "files" / "ppstime"
DASHBOARD_COMMAND = CORE_ROOT / "ppstime-dashboard"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "dashboard" / "health.json"
DEGRADED_FIXTURES = (
    PROJECT_ROOT / "tests" / "fixtures" / "dashboard" / "degraded-scenarios.json"
)
sys.path.insert(0, str(CORE_ROOT))

from ppstime_core import (
    ConfigError,
    config_to_env,
    load_config,
    migrate_dashboard_defaults,
    validate_config,
)
from ppstime_update import UpdateError, safe_payload_path, source_payload_files


def load_dashboard() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ppstime_dashboard", str(DASHBOARD_COMMAND))
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


def load_configure_profile() -> ModuleType:
    command = PROJECT_ROOT / "scripts" / "configure-profile.py"
    loader = importlib.machinery.SourceFileLoader("configure_profile", str(command))
    module = ModuleType(loader.name)
    module.__file__ = str(command)
    loader.exec_module(module)
    return module


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_dashboard()
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.config = load_config(PROJECT_ROOT, environ={})

    def test_enabled_private_defaults_and_invalid_configuration(self) -> None:
        self.assertEqual(self.config["DASHBOARD_ENABLED"], "true")
        self.assertEqual(self.config["DASHBOARD_BIND"], "0.0.0.0")
        self.assertEqual(
            self.config["DASHBOARD_ALLOWED_CIDRS"],
            "127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
        )
        self.assertEqual(self.config["DASHBOARD_PORT"], "8080")
        self.assertEqual(self.config["DASHBOARD_RETENTION_HOURS"], "168")
        invalid = (
            {"DASHBOARD_ENABLED": "yes"},
            {"DASHBOARD_BIND": "localhost"},
            {"DASHBOARD_BIND": "::"},
            {"DASHBOARD_BIND": "8.8.8.8", "DASHBOARD_ALLOWED_CIDRS": "8.8.8.8/32"},
            {"DASHBOARD_BIND": "192.168.2.2", "DASHBOARD_ALLOWED_CIDRS": "192.168.1.0/24"},
            {"DASHBOARD_ALLOWED_CIDRS": "0.0.0.0/0"},
            {"DASHBOARD_ALLOWED_CIDRS": "169.254.0.0/16"},
            {"DASHBOARD_ALLOWED_CIDRS": "192.168.1.1/24"},
            {"DASHBOARD_PORT": "80"},
            {"DASHBOARD_PORT": "65536"},
            {"DASHBOARD_RETENTION_HOURS": "0"},
            {"DASHBOARD_RETENTION_HOURS": "721"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                validate_config(dict(self.config, **changes))
        validate_config(
            dict(
                self.config,
                DASHBOARD_ENABLED="true",
                DASHBOARD_BIND="192.168.1.20",
                DASHBOARD_ALLOWED_CIDRS="192.168.1.0/24",
            )
        )

    def test_exact_v020_defaults_migrate_but_custom_settings_are_preserved(self) -> None:
        legacy = dict(
            self.config,
            DASHBOARD_ENABLED="false",
            DASHBOARD_BIND="127.0.0.1",
            DASHBOARD_ALLOWED_CIDRS="127.0.0.1/32",
        )
        self.assertEqual(migrate_dashboard_defaults(legacy), self.config)
        customized = dict(legacy, DASHBOARD_PORT="8081")
        self.assertEqual(migrate_dashboard_defaults(customized), customized)

    def test_configuration_regeneration_migrates_v020_dashboard_defaults(self) -> None:
        legacy = dict(
            self.config,
            DASHBOARD_ENABLED="false",
            DASHBOARD_BIND="127.0.0.1",
            DASHBOARD_ALLOWED_CIDRS="127.0.0.1/32",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            boot = root / "boot/firmware"
            boot.mkdir(parents=True)
            (boot / "config.txt").write_text("# boot\n", encoding="utf-8")
            (boot / "cmdline.txt").write_text("root=test rw\n", encoding="utf-8")
            config = root / "etc/ppstime/ppstime.env"
            config.parent.mkdir(parents=True)
            config.write_text(config_to_env(legacy), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts/configure-profile.py"),
                    "--source-root",
                    str(PROJECT_ROOT),
                    "--root",
                    str(root),
                    "--config",
                    str(config),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            migrated = self.module.load_dashboard_config(config)
        self.assertEqual(migrated, self.config)

    def test_configuration_regeneration_prepares_held_updater_lock(self) -> None:
        module = load_configure_profile()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc_root = root / "proc"
            parent = proc_root / "123"
            parent.mkdir(parents=True)
            (parent / "cmdline").write_bytes(
                b"python3\0/usr/lib/ppstime/ppstime-update\0apply\0"
            )
            lock_path = root / "run/lock/ppstime-maintenance.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("", encoding="ascii")
            os.chmod(lock_path, 0o600)
            with lock_path.open("rb") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertTrue(
                    module.prepare_dashboard_update_lock(
                        root,
                        proc_root=proc_root,
                        parent_pid=123,
                    )
                )
                self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(ConfigError, "not held"):
                module.prepare_dashboard_update_lock(
                    root,
                    proc_root=proc_root,
                    parent_pid=123,
                )
            (parent / "cmdline").write_bytes(
                b"python3\0/usr/lib/ppstime/not-the-updater\0ppstime-update\0"
            )
            self.assertFalse(
                module.prepare_dashboard_update_lock(
                    root,
                    proc_root=proc_root,
                    parent_pid=123,
                )
            )

    def test_closed_projection_excludes_raw_and_identifying_fields(self) -> None:
        payload = json.loads(json.dumps(self.fixture))
        payload["last_observation"]["reasons"] = ["selected_source=other", "secret=value"]
        payload["last_host_observation"]["summary"]["updates"]["error"] = "/private/path"
        sample = self.module.sanitize_health(
            payload, datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(set(sample), set(self.module.SAMPLE_KEYS))
        serialized = json.dumps(sample)
        for forbidden in (
            "reason",
            "secret",
            "private",
            "/dev/",
            "serial",
            "profile",
            "client",
            "available_bytes",
        ):
            self.assertNotIn(forbidden, serialized.lower())
        self.assertEqual(sample["timing_state"], "HEALTHY_PPS")
        self.assertEqual(sample["root_available_percent"], 42.25)
        self.assertEqual(sample["boot_available_percent"], 63.5)
        self.assertEqual(sample["temperature_celsius"], 48.75)
        self.assertEqual(sample["satellites_used"], 15)
        self.assertEqual(sample["system_offset_seconds"], 0.000000007)
        self.assertEqual(sample["root_dispersion_seconds"], 0.000560501)

    def test_projection_rejects_extra_keys_and_out_of_range_values(self) -> None:
        payload = json.loads(json.dumps(self.fixture))
        payload["unexpected"] = "raw passthrough"
        with self.assertRaisesRegex(self.module.DashboardError, "keys"):
            self.module.sanitize_health(payload, datetime.now(timezone.utc))

    def test_unavailable_collectors_null_stale_metrics_and_keep_safe_transition(self) -> None:
        payload = json.loads(json.dumps(self.fixture))
        payload["timing_collection_available"] = False
        payload["host_collection_available"] = False
        payload["last_transition"] = {
            "from": "HEALTHY_PPS",
            "to": "UNSYNCHRONIZED",
            "at": "2026-07-25T11:59:00Z",
            "previous_duration_seconds": 3600,
            "reasons": ["private=value"],
        }
        payload["last_host_observation"]["summary"] = {"error": "private"}
        sample = self.module.sanitize_health(
            payload, datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        )
        for key in (
            "gps_fix",
            "satellites_used",
            "pps_pulses",
            "rtc_available",
            "stratum",
            "system_offset_seconds",
            "root_dispersion_seconds",
            "temperature_celsius",
            "throttled_flags",
        ):
            self.assertIsNone(sample[key], key)
        transition = json.loads(sample["timing_transition"])
        self.assertEqual(
            transition,
            {
                "from": "HEALTHY_PPS",
                "to": "UNSYNCHRONIZED",
                "at": "2026-07-25T11:59:00Z",
            },
        )
        self.assertNotIn("private", sample["timing_transition"])

    def test_committed_degraded_scenarios_use_only_sample_schema(self) -> None:
        scenarios = json.loads(DEGRADED_FIXTURES.read_text(encoding="utf-8"))
        self.assertEqual(
            {scenario["name"] for scenario in scenarios},
            {
                "network-fallback",
                "timing-collector-unavailable",
                "host-warning",
                "hardware-error",
            },
        )
        for scenario in scenarios:
            self.assertTrue(set(scenario) - {"name"} < set(self.module.SAMPLE_KEYS))
        payload = json.loads(json.dumps(self.fixture))
        payload["last_host_observation"]["summary"]["temperature_celsius"] = 1000
        with self.assertRaisesRegex(self.module.DashboardError, "range"):
            self.module.sanitize_health(payload, datetime.now(timezone.utc))
        payload = json.loads(json.dumps(self.fixture))
        payload["last_observation"]["summary"]["stratum"] = 17
        with self.assertRaisesRegex(self.module.DashboardError, "range"):
            self.module.sanitize_health(payload, datetime.now(timezone.utc))

    def test_sqlite_history_is_bounded_and_readable_without_wal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "dashboard.sqlite3"
            start = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
            for index in range(40):
                sample = self.module.sanitize_health(
                    self.fixture, start + timedelta(minutes=index * 2)
                )
                self.module.write_sample(database, sample, retention_hours=1)
            connection = sqlite3.connect(database)
            try:
                count = connection.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                connection.close()
            self.assertLessEqual(count, 32)
            self.assertEqual(journal_mode, "delete")
            source = DASHBOARD_COMMAND.read_text(encoding="utf-8")
            self.assertIn("PRAGMA max_page_count={DATABASE_MAX_PAGES}", source)
            self.assertFalse(database.with_name(f"{database.name}-wal").exists())
            latest, samples = self.module.read_history(
                database, 1, int((start + timedelta(minutes=78)).timestamp())
            )
            self.assertIsNotNone(latest)
            self.assertLessEqual(len(samples), 32)
            self.assertLessEqual(database.stat().st_size, self.module.MAX_DATABASE_BYTES)

    def test_rate_limiter_has_burst_and_recovery(self) -> None:
        limiter = self.module.RateLimiter()
        self.assertTrue(all(limiter.allow("127.0.0.1", now=0.0) for _ in range(20)))
        self.assertFalse(limiter.allow("127.0.0.1", now=0.0))
        self.assertTrue(limiter.allow("127.0.0.1", now=2.0))

    def test_read_side_rejects_corrupted_persisted_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "dashboard.sqlite3"
            now = datetime.now(timezone.utc).replace(microsecond=0)
            sample = self.module.sanitize_health(self.fixture, now)
            self.module.write_sample(database, sample, retention_hours=24)
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "UPDATE samples SET timing_state = ?", ("<script>raw</script>",)
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaisesRegex(self.module.DashboardError, "timing_state"):
                self.module.read_history(database, 24, int(now.timestamp()))

    def test_peer_cidr_is_checked_from_socket_address(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = self.module.DashboardServer(
                ("127.0.0.1", 0),
                self.module.DashboardHandler,
                allowed_networks=(self.module.ipaddress.ip_network("127.0.0.1/32"),),
                database=Path(temporary) / "db",
                asset_root=PROJECT_ROOT / "files" / "dashboard",
            )
            try:
                self.assertTrue(server.verify_request(None, ("127.0.0.1", 1)))
                self.assertFalse(server.verify_request(None, ("127.0.0.2", 1)))
                self.assertFalse(server.verify_request(None, ("not-an-ip", 1)))
                server.rate_limiter = self.module.RateLimiter()
                self.assertTrue(
                    all(server.verify_request(None, ("127.0.0.1", 1)) for _ in range(20))
                )
                self.assertFalse(server.verify_request(None, ("127.0.0.1", 1)))
            finally:
                server.server_close()

    def test_server_exits_after_atomic_runtime_file_replacement(self) -> None:
        for watched_name in ("ppstime.env", "ppstime-dashboard"):
            with self.subTest(path=watched_name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                watched = root / watched_name
                watched.write_text("old\n", encoding="utf-8")
                server = self.module.DashboardServer(
                    ("127.0.0.1", 0),
                    self.module.DashboardHandler,
                    allowed_networks=(
                        self.module.ipaddress.ip_network("127.0.0.1/32"),
                    ),
                    database=root / "db",
                    asset_root=PROJECT_ROOT / "files" / "dashboard",
                    watched_paths=(watched,),
                )
                failures: list[BaseException] = []

                def serve(
                    active_server: object = server,
                    captured_failures: list[BaseException] = failures,
                ) -> None:
                    try:
                        active_server.serve_forever(poll_interval=0.01)
                    except BaseException as exc:  # noqa: BLE001 - capture thread result
                        captured_failures.append(exc)

                thread = threading.Thread(target=serve, daemon=True)
                try:
                    thread.start()
                    replacement = root / "replacement"
                    replacement.write_text("restored\n", encoding="utf-8")
                    os.replace(replacement, watched)
                    thread.join(timeout=2)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(len(failures), 1)
                    self.assertIsInstance(failures[0], self.module.DashboardError)
                    self.assertIn("runtime file changed", str(failures[0]))
                finally:
                    server.shutdown()
                    server.server_close()

    def test_server_restarts_immediately_after_serving_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "dashboard.sqlite3"
            self.module.write_sample(
                database,
                self.module.sanitize_health(self.fixture, datetime.now(timezone.utc)),
                retention_hours=24,
            )
            server = self.module.DashboardServer(
                ("127.0.0.1", 0),
                self.module.DashboardHandler,
                allowed_networks=(self.module.ipaddress.ip_network("127.0.0.1/32"),),
                database=database,
                asset_root=PROJECT_ROOT / "files" / "dashboard",
            )
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
                    client.sendall(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
                    response = b""
                    while chunk := client.recv(4096):
                        response += chunk
                self.assertTrue(response.startswith(b"HTTP/1.0 200 OK\r\n"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            replacement = self.module.DashboardServer(
                ("127.0.0.1", port),
                self.module.DashboardHandler,
                allowed_networks=(self.module.ipaddress.ip_network("127.0.0.1/32"),),
                database=database,
                asset_root=PROJECT_ROOT / "files" / "dashboard",
            )
            replacement.server_close()

    def test_preflight_retries_only_address_in_use(self) -> None:
        attempts = [
            OSError(errno.EADDRINUSE, "Address already in use"),
            None,
        ]

        class Probe:
            def setsockopt(self, *args: object) -> None:
                pass

            def bind(self, address: tuple[str, int]) -> None:
                self_address = address
                del self_address
                failure = attempts.pop(0)
                if failure is not None:
                    raise failure

            def close(self) -> None:
                pass

        with (
            mock.patch.object(self.module.socket, "socket", side_effect=(Probe(), Probe())),
            mock.patch.object(self.module.time, "sleep") as sleep,
        ):
            self.module.preflight(self.config, timeout=1.0, interval=0.1)
        sleep.assert_called_once()

        with (
            mock.patch.object(
                self.module.socket,
                "socket",
                return_value=Probe(),
            ),
            mock.patch.object(
                Probe,
                "bind",
                side_effect=OSError(errno.EACCES, "Permission denied"),
            ),
            self.assertRaisesRegex(self.module.DashboardError, "Permission denied"),
        ):
            self.module.preflight(self.config, timeout=1.0, interval=0.1)

    def test_server_waits_for_updater_lock_and_watches_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "maintenance.lock"
            lock_path.write_text("", encoding="ascii")
            server = mock.Mock()
            with lock_path.open("rb") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release(_: float) -> None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

                with mock.patch.object(self.module.time, "sleep", side_effect=release):
                    self.module.wait_for_maintenance_lock(
                        server, lock_path, interval=0.01
                    )
            server.service_actions.assert_called_once_with()

    def test_maintenance_lock_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("", encoding="ascii")
            lock = root / "maintenance.lock"
            lock.symlink_to(target)
            with self.assertRaisesRegex(self.module.DashboardError, "cannot read"):
                self.module.wait_for_maintenance_lock(mock.Mock(), lock)

    def test_systemd_open_file_requires_exact_named_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "maintenance.lock"
            lock.write_text("", encoding="ascii")
            with lock.open("rb") as stream:
                descriptor = os.dup(stream.fileno())
                try:
                    with (
                        mock.patch.dict(
                            os.environ,
                            {
                                "LISTEN_PID": str(os.getpid()),
                                "LISTEN_FDS": "1",
                                "LISTEN_FDNAMES": "maintenance-lock",
                            },
                            clear=False,
                        ),
                        mock.patch.object(
                            self.module,
                            "SYSTEMD_FD_START",
                            descriptor,
                        ),
                    ):
                        inherited = self.module.systemd_open_file("maintenance-lock")
                    self.assertIsNotNone(inherited)
                    os.close(inherited)
                finally:
                    os.close(descriptor)
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "LISTEN_PID": str(os.getpid()),
                        "LISTEN_FDS": "1",
                        "LISTEN_FDNAMES": "wrong-name",
                    },
                    clear=False,
                ),
                self.assertRaisesRegex(self.module.DashboardError, "unavailable"),
            ):
                self.module.systemd_open_file("maintenance-lock")

    def test_http_get_head_headers_methods_ranges_and_exact_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "dashboard.sqlite3"
            sample = self.module.sanitize_health(self.fixture, datetime.now(timezone.utc))
            self.module.write_sample(database, sample, retention_hours=168)
            server = self.module.DashboardServer(
                ("127.0.0.1", 0),
                self.module.DashboardHandler,
                allowed_networks=(self.module.ipaddress.ip_network("127.0.0.1/32"),),
                database=database,
                asset_root=PROJECT_ROOT / "files" / "dashboard",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                connection.request("GET", "/api/v1/dashboard?hours=24")
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                payload = json.loads(body)
                self.assertEqual(
                    set(payload),
                    {"schema_version", "generated_at", "range_hours", "latest", "samples"},
                )
                self.assertEqual(payload["range_hours"], 24)
                self.assertEqual(payload["latest"]["satellites_used"], 15)
                self.assertEqual(payload["latest"]["rtc_available"], True)
                self.assertIn("default-src 'self'", response.getheader("Content-Security-Policy"))
                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
                self.assertEqual(response.getheader("Referrer-Policy"), "no-referrer")
                self.assertEqual(response.getheader("Connection"), "close")

                connection.request("HEAD", "/dashboard.css")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"")
                self.assertGreater(int(response.getheader("Content-Length")), 0)

                for method in (
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "OPTIONS",
                    "TRACE",
                    "PROPFIND",
                ):
                    connection.request(method, "/api/v1/dashboard")
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 405, method)
                    self.assertEqual(response.getheader("Allow"), "GET, HEAD")
                    self.assertEqual(response.getheader("X-Frame-Options"), "DENY")

                for target in (
                    "/api/v1/dashboard?hours=2",
                    "/api/v1/dashboard?hours=24&extra=1",
                    "/api/v1/dashboard?hours=168&hours=24",
                ):
                    connection.request("GET", target)
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 400, target)

                connection.request(
                    "GET",
                    "/api/v1/dashboard?hours=24",
                    body=b"forbidden",
                    headers={"Content-Length": "9"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 400)

                connection.request("GET", "/api/v1/dashboard?hours=720")
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["range_hours"], 720)

                for target in ("/../etc/passwd", "/dashboard.css?raw=1", "/admin"):
                    connection.request("GET", target)
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 404, target)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_static_assets_are_local_exact_and_without_external_requests(self) -> None:
        asset_root = PROJECT_ROOT / "files" / "dashboard"
        self.assertEqual(
            {path.name for path in asset_root.iterdir()},
            {"index.html", "dashboard.css", "dashboard.js", "ppspi.svg"},
        )
        content = "\n".join(
            path.read_text(encoding="utf-8") for path in asset_root.iterdir()
        ).lower()
        for forbidden in ("https://", "//cdn", "<form", "websocket", "fetch(\"http"):
            self.assertNotIn(forbidden, content)
        self.assertEqual(content.count("http://"), 2)
        self.assertEqual(content.count("http://www.w3.org/2000/svg"), 2)
        source = DASHBOARD_COMMAND.read_text(encoding="utf-8")
        self.assertIn("Never log client addresses, paths, or query strings", source)
        self.assertNotIn("self.client_address[0]}", source)
        javascript = (asset_root / "dashboard.js").read_text(encoding="utf-8")
        self.assertGreaterEqual(
            javascript.count("timing_collection_available === true"), 7
        )
        self.assertGreaterEqual(
            javascript.count("host_collection_available === true"), 4
        )
        self.assertIn("renderLatest(null);", javascript)
        self.assertIn("const flush = () =>", javascript)
        self.assertIn("if (!Number.isFinite(number))", javascript)
        self.assertIn('byId("chart-legend")', javascript)
        self.assertIn('[[30, "On"], [210, "Off"]]', javascript)
        self.assertIn("if (!values.length)", javascript)

    def test_chart_scales_distinguish_numeric_ranges_and_units(self) -> None:
        javascript = PROJECT_ROOT / "files" / "dashboard" / "dashboard.js"
        script = f"""
const chart = require({json.dumps(str(javascript))});
const result = {{
    low: chart.buildScale([2, 3], {{includeZero: true, integer: true}}),
    high: chart.buildScale([10, 15], {{includeZero: true, integer: true}}),
    constant: chart.buildScale([55, 55], {{}}),
    precision: chart.formatAxisTick(12.5, {{unit: 'µs'}}, 0),
    health: chart.formatAxisTick(3, {{labels: ['Error', 'Unsync', 'Fallback', 'Healthy']}}, 3),
    root: chart.oneDecimal(83.89193159775925, '%'),
    boot: chart.oneDecimal(85.2154380826185, '%'),
    temperature: chart.oneDecimal(53.556, '°C'),
    missing: chart.oneDecimal(null, '%'),
    nan: chart.oneDecimal(NaN, '%'),
    infinity: chart.oneDecimal(Infinity, '%'),
    text: chart.oneDecimal('53.556', '°C'),
    boolean: chart.oneDecimal(false, '%'),
}};
console.log(JSON.stringify(result));
"""
        result = subprocess.run(
            ["node", "--eval", script],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["low"]["ticks"], [0, 1, 2, 3])
        self.assertEqual(payload["high"]["ticks"], [0, 5, 10, 15])
        self.assertLess(payload["constant"]["minimum"], 55)
        self.assertGreater(payload["constant"]["maximum"], 55)
        self.assertEqual(payload["precision"], "12.5 µs")
        self.assertEqual(payload["health"], "Healthy")
        self.assertEqual(payload["root"], "83.9%")
        self.assertEqual(payload["boot"], "85.2%")
        self.assertEqual(payload["temperature"], "53.6°C")
        self.assertEqual(payload["missing"], "—")
        self.assertEqual(payload["nan"], "—")
        self.assertEqual(payload["infinity"], "—")
        self.assertEqual(payload["text"], "—")
        self.assertEqual(payload["boolean"], "—")

    def test_raw_socket_request_and_header_bounds_apply_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "dashboard.sqlite3"
            self.module.write_sample(
                database,
                self.module.sanitize_health(self.fixture, datetime.now(timezone.utc)),
                retention_hours=24,
            )
            server = self.module.DashboardServer(
                ("127.0.0.1", 0),
                self.module.DashboardHandler,
                allowed_networks=(self.module.ipaddress.ip_network("127.0.0.1/32"),),
                database=database,
                asset_root=PROJECT_ROOT / "files" / "dashboard",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def status(request: bytes) -> int:
                with socket.create_connection(
                    ("127.0.0.1", server.server_port), timeout=3
                ) as client:
                    client.sendall(request)
                    response = client.recv(4096)
                return int(response.split(b" ", 2)[1])

            try:
                self.assertEqual(
                    status(b"GET /" + b"x" * 3000 + b" HTTP/1.0\r\n\r\n"),
                    414,
                )
                self.assertEqual(
                    status(b"GET / HTTP/1.0\r\nX-Large: " + b"x" * 9000 + b"\r\n\r\n"),
                    431,
                )
                many_headers = b"".join(
                    f"X-{index}: x\r\n".encode("ascii") for index in range(40)
                )
                self.assertEqual(
                    status(b"GET / HTTP/1.0\r\n" + many_headers + b"\r\n"),
                    431,
                )
                self.assertEqual(
                    status(
                        b"POST /api/v1/dashboard HTTP/1.0\r\n"
                        b"Transfer-Encoding: chunked\r\n\r\n"
                    ),
                    400,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_systemd_units_separate_sampling_and_http_privileges(self) -> None:
        systemd = PROJECT_ROOT / "files" / "systemd"
        server = (systemd / "ppstime-dashboard.service").read_text(encoding="utf-8")
        sampler = (systemd / "ppstime-dashboard-sample.service").read_text(encoding="utf-8")
        timer = (systemd / "ppstime-dashboard-sample.timer").read_text(encoding="utf-8")
        self.assertIn("ExecStartPre=/usr/lib/ppstime/ppstime-dashboard preflight", server)
        self.assertIn("ExecStart=/usr/lib/ppstime/ppstime-dashboard serve", server)
        self.assertIn(
            "OpenFile=/run/lock/ppstime-maintenance.lock:maintenance-lock:read-only",
            server,
        )
        self.assertIn("DynamicUser=true", server)
        self.assertIn("ProtectSystem=strict", server)
        self.assertIn("CapabilityBoundingSet=", server)
        self.assertIn("RestrictAddressFamilies=AF_INET AF_INET6", server)
        self.assertNotIn("StateDirectory=", server)
        self.assertIn("ExecStart=/usr/lib/ppstime/ppstime-dashboard sample", sampler)
        self.assertIn("PrivateNetwork=true", sampler)
        self.assertNotIn("DynamicUser=true", sampler)
        self.assertIn("ReadWritePaths=/var/lib/ppstime-dashboard", sampler)
        self.assertNotIn("ReadWritePaths=", server)
        self.assertIn("Wants=ppstime-dashboard.service", timer)
        self.assertIn("OnUnitActiveSec=2min", timer)

    def test_signed_payload_inventory_contains_exact_dashboard_files(self) -> None:
        payload = {destination for _, destination, _ in source_payload_files(PROJECT_ROOT)}
        expected = {
            "usr/lib/ppstime/ppstime-dashboard",
            "usr/share/ppstime/dashboard/index.html",
            "usr/share/ppstime/dashboard/dashboard.css",
            "usr/share/ppstime/dashboard/dashboard.js",
            "usr/share/ppstime/dashboard/ppspi.svg",
            "etc/systemd/system/ppstime-dashboard.service",
            "etc/systemd/system/ppstime-dashboard-sample.service",
            "etc/systemd/system/ppstime-dashboard-sample.timer",
            "usr/lib/tmpfiles.d/ppstime.conf",
        }
        self.assertTrue(expected.issubset(payload))
        self.assertEqual(
            {path for path in payload if path.startswith("usr/share/ppstime/dashboard/")},
            {path for path in expected if path.startswith("usr/share/ppstime/dashboard/")},
        )
        for path in expected:
            self.assertEqual(safe_payload_path(path), path)
        with self.assertRaises(UpdateError):
            safe_payload_path("usr/share/ppstime/dashboard/admin.html")

    def test_installer_inventory_and_configuration_apply_reconcile_units(self) -> None:
        installer = (PROJECT_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("ppstime-dashboard; do", installer)
        self.assertIn("/usr/share/ppstime/dashboard", installer)
        self.assertIn("DASHBOARD_ENABLED=true", installer)
        self.assertIn("ppstime-dashboard-sample.timer", installer)
        config_command = (CORE_ROOT / "ppstime-config").read_text(encoding="utf-8")
        self.assertIn('"ppstime-dashboard.service"', config_command)
        self.assertIn('"ppstime-dashboard-sample.timer"', config_command)

    def test_config_fixture_can_be_written_canonically(self) -> None:
        enabled = dict(self.config)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ppstime.env"
            path.write_text(config_to_env(enabled), encoding="utf-8")
            loaded = self.module.load_dashboard_config(path)
        self.assertEqual(loaded["DASHBOARD_ENABLED"], "true")


if __name__ == "__main__":
    unittest.main()
