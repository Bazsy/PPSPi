from __future__ import annotations

import copy
import importlib.machinery
import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_COMMAND = PROJECT_ROOT / "files" / "ppstime" / "ppstime-health"
DIAGNOSTICS_COMMAND = PROJECT_ROOT / "files" / "ppstime" / "ppstime-diagnostics"
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))


def load_health_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ppstime_health", str(HEALTH_COMMAND))
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


def load_diagnostics_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "ppstime_diagnostics", str(DIAGNOSTICS_COMMAND)
    )
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


def healthy_status() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile": "uputronics-gps-rtc-hat",
        "gps": {
            "device": "/dev/serial0",
            "configured_baud": 115200,
            "reported_baud": 115200,
            "serial": "OK",
            "service": "ACTIVE",
            "fix": "3D",
            "satellites_used": 15,
        },
        "pps": {
            "device": "/dev/pps0",
            "exists": True,
            "pulses": "ACTIVE",
        },
        "rtc": {
            "device": "/dev/rtc0",
            "status": "OK",
            "time": "2026-07-22 12:00:00 UTC",
        },
        "chrony": {
            "state": "SYNCHRONIZED",
            "selected_source": "PPS",
            "stratum": 1,
            "system_offset_seconds": "+0.000000007",
            "root_dispersion_seconds": "0.000560501",
        },
        "ntp_clients": 1,
    }


class HealthTests(unittest.TestCase):
    def run_update(
        self,
        root: Path,
        status: dict[str, Any],
        now: str,
        *,
        hook_dir: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        status_path = root / "status.json"
        state_path = root / "health-state.json"
        status_path.write_text(json.dumps(status), encoding="utf-8")
        command = [
            sys.executable,
            str(HEALTH_COMMAND),
            "--update",
            "--state-file",
            str(state_path),
            "--status-json",
            str(status_path),
            "--confirmations",
            "2",
            "--now",
            now,
            "--monotonic-seconds",
            str(datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp()),
        ]
        if hook_dir is not None:
            command.extend(["--hook-dir", str(hook_dir)])
        process = subprocess.run(command, capture_output=True, check=False, text=True)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return process, state

    def test_classifies_all_health_states(self) -> None:
        scenarios: dict[str, tuple[dict[str, Any], list[str]]] = {}

        healthy = healthy_status()
        scenarios["HEALTHY_PPS"] = (healthy, [])

        fallback = copy.deepcopy(healthy)
        fallback["chrony"]["selected_source"] = "192.0.2.1"
        fallback["chrony"]["stratum"] = 2
        fallback["pps"]["pulses"] = "INACTIVE"
        scenarios["NETWORK_FALLBACK"] = (
            fallback,
            ["selected_source=other", "pps_inactive", "stratum=2"],
        )

        unsynchronized = copy.deepcopy(healthy)
        unsynchronized["chrony"]["state"] = "NOT SYNCHRONIZED"
        unsynchronized["chrony"]["selected_source"] = None
        unsynchronized["chrony"]["stratum"] = None
        scenarios["UNSYNCHRONIZED"] = (
            unsynchronized,
            ["chrony_not_synchronized"],
        )

        hardware_error = copy.deepcopy(healthy)
        hardware_error["gps"]["serial"] = "MISSING"
        hardware_error["gps"]["service"] = "INACTIVE"
        hardware_error["pps"]["exists"] = False
        hardware_error["rtc"]["status"] = "UNAVAILABLE"
        scenarios["HARDWARE_ERROR"] = (
            hardware_error,
            [
                "gps_serial_missing",
                "gpsd_inactive",
                "pps_device_missing",
                "rtc_unavailable",
            ],
        )

        for expected_state, (status, expected_reasons) in scenarios.items():
            with self.subTest(expected_state=expected_state), tempfile.TemporaryDirectory() as tmp:
                process, state = self.run_update(
                    Path(tmp), status, "2026-07-22T12:00:00Z"
                )
                process, state = self.run_update(
                    Path(tmp), status, "2026-07-22T12:01:00Z"
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(state["state"], expected_state)
                self.assertEqual(state["last_observation"]["reasons"], expected_reasons)

    def test_hysteresis_duration_hook_order_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hook_dir = root / "hooks"
            hook_dir.mkdir(mode=0o700)
            hook_log = root / "hooks.log"
            for name in ("10-first", "20-second"):
                hook = hook_dir / name
                hook.write_text(
                    "#!/usr/bin/env python3\n"
                    "import os\n"
                    "from pathlib import Path\n"
                    f"path = Path({str(hook_log)!r})\n"
                    "with path.open('a', encoding='utf-8') as stream:\n"
                    f"    stream.write({name!r} + '|' + os.environ['PPSTIME_HEALTH_FROM'] "
                    "+ '|' + os.environ['PPSTIME_HEALTH_TO'] + '|' "
                    "+ os.environ['PPSTIME_HEALTH_PREVIOUS_DURATION_SECONDS'] + '|' "
                    "+ os.environ['PPSTIME_HEALTH_REASONS'] + '\\n')\n",
                    encoding="utf-8",
                )
                hook.chmod(0o700)

            healthy = healthy_status()
            first, state = self.run_update(
                root,
                healthy,
                "2026-07-22T12:00:00Z",
                hook_dir=hook_dir,
            )
            self.assertIn("confirmation=1/2", first.stdout)
            self.assertEqual(state["state"], "UNKNOWN")
            self.assertFalse(hook_log.exists())

            second, state = self.run_update(
                root,
                healthy,
                "2026-07-22T12:01:00Z",
                hook_dir=hook_dir,
            )
            self.assertIn("from=UNKNOWN to=HEALTHY_PPS", second.stdout)
            self.assertEqual(state["state"], "HEALTHY_PPS")
            self.assertFalse(hook_log.exists())

            fallback = copy.deepcopy(healthy)
            fallback["chrony"]["selected_source"] = "192.0.2.1"
            fallback["chrony"]["stratum"] = 2
            fallback["pps"]["pulses"] = "INACTIVE"
            self.run_update(
                root,
                fallback,
                "2026-07-22T12:02:00Z",
                hook_dir=hook_dir,
            )
            transition, state = self.run_update(
                root,
                fallback,
                "2026-07-22T12:03:00Z",
                hook_dir=hook_dir,
            )
            self.assertIn("previous_duration_seconds=120", transition.stdout)
            self.assertEqual(state["state"], "NETWORK_FALLBACK")

            self.run_update(
                root,
                healthy,
                "2026-07-22T12:04:00Z",
                hook_dir=hook_dir,
            )
            recovery, state = self.run_update(
                root,
                healthy,
                "2026-07-22T12:05:00Z",
                hook_dir=hook_dir,
            )
            self.assertIn("previous_duration_seconds=120", recovery.stdout)
            self.assertEqual(state["state"], "HEALTHY_PPS")
            lines = hook_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                lines,
                [
                    "10-first|HEALTHY_PPS|NETWORK_FALLBACK|120|"
                    "selected_source=other,pps_inactive,stratum=2",
                    "20-second|HEALTHY_PPS|NETWORK_FALLBACK|120|"
                    "selected_source=other,pps_inactive,stratum=2",
                    "10-first|NETWORK_FALLBACK|HEALTHY_PPS|120|",
                    "20-second|NETWORK_FALLBACK|HEALTHY_PPS|120|",
                ],
            )

    def test_confirmed_degraded_startup_runs_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hook_dir = root / "hooks"
            hook_dir.mkdir(mode=0o700)
            hook_log = root / "hook.log"
            hook = hook_dir / "10-log"
            hook.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "from pathlib import Path\n"
                f"Path({str(hook_log)!r}).write_text("
                "os.environ['PPSTIME_HEALTH_FROM'] + '>' + "
                "os.environ['PPSTIME_HEALTH_TO'], encoding='utf-8')\n",
                encoding="utf-8",
            )
            hook.chmod(0o700)
            degraded = healthy_status()
            degraded["chrony"]["state"] = "NOT SYNCHRONIZED"
            process, state = self.run_update(
                root,
                degraded,
                "2026-07-22T12:00:00Z",
                hook_dir=hook_dir,
            )
            process, state = self.run_update(
                root,
                degraded,
                "2026-07-22T12:01:00Z",
                hook_dir=hook_dir,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(state["state"], "UNSYNCHRONIZED")
            self.assertEqual(hook_log.read_text(encoding="utf-8"), "UNKNOWN>UNSYNCHRONIZED")

    def test_unsafe_hook_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hook_dir = root / "hooks"
            hook_dir.mkdir(mode=0o700)
            unsafe_hook = hook_dir / "10-unsafe"
            unsafe_hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            unsafe_hook.chmod(0o777)
            degraded = healthy_status()
            degraded["chrony"]["state"] = "NOT SYNCHRONIZED"
            process, _ = self.run_update(
                root,
                degraded,
                "2026-07-22T12:00:00Z",
                hook_dir=hook_dir,
            )
            process, _ = self.run_update(
                root,
                degraded,
                "2026-07-22T12:01:00Z",
                hook_dir=hook_dir,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("unsafe hook ignored: 10-unsafe", process.stdout)

    def test_timed_out_hook_kills_its_process_group(self) -> None:
        module = load_health_module()
        module.HOOK_TIMEOUT_SECONDS = 0.1
        module.HOOK_TOTAL_BUDGET_SECONDS = 0.05
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hook_dir = root / "hooks"
            hook_dir.mkdir(mode=0o700)
            child_pid_path = root / "child.pid"
            hook = hook_dir / "10-slow"
            hook.write_text(
                "#!/usr/bin/env python3\n"
                "import subprocess\n"
                "import time\n"
                "from pathlib import Path\n"
                "child = subprocess.Popen(['sleep', '30'])\n"
                f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='ascii')\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            hook.chmod(0o700)
            second_hook = hook_dir / "20-never-runs"
            second_hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            second_hook.chmod(0o700)
            transition = {
                "from": "HEALTHY_PPS",
                "to": "NETWORK_FALLBACK",
                "at": "2026-07-22T12:00:00Z",
                "previous_duration_seconds": 120,
                "reasons": ["pps_inactive"],
            }
            warnings = module.run_hooks(hook_dir, transition)
            self.assertEqual(
                warnings,
                ["hook 10-slow timed out", "total hook time budget exhausted"],
            )
            child_pid = int(child_pid_path.read_text(encoding="ascii"))
            process_stat = Path(f"/proc/{child_pid}/stat")
            if process_stat.exists():
                self.assertEqual(process_stat.read_text(encoding="ascii").split()[2], "Z")

    def test_malformed_state_and_collection_failure_never_fail_service_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "health-state.json"
            state_path.write_text("{}\n", encoding="utf-8")
            status_path = root / "status.json"
            status_path.write_text(json.dumps(healthy_status()), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(HEALTH_COMMAND),
                    "--update",
                    "--state-file",
                    str(state_path),
                    "--status-json",
                    str(status_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("health state keys do not match schema", process.stdout)
            self.assertEqual(state_path.read_text(encoding="utf-8"), "{}\n")

            missing_state = root / "missing-state.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(HEALTH_COMMAND),
                    "--update",
                    "--state-file",
                    str(missing_state),
                    "--status-json",
                    str(root / "missing-status.json"),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("status fixture not found", process.stdout)
            self.assertFalse(missing_state.exists())

    def test_json_human_and_prometheus_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_update(root, healthy_status(), "2026-07-22T12:00:00Z")
            self.run_update(root, healthy_status(), "2026-07-22T12:01:00Z")
            common = [
                "--state-file",
                str(root / "health-state.json"),
                "--now",
                "2026-07-22T12:02:00Z",
                "--monotonic-seconds",
                str(datetime.fromisoformat("2026-07-22T12:02:00+00:00").timestamp()),
            ]
            json_result = subprocess.run(
                [sys.executable, str(HEALTH_COMMAND), "--json", *common],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(json_result.returncode, 0, json_result.stderr)
            payload = json.loads(json_result.stdout)
            self.assertEqual(payload["state"], "HEALTHY_PPS")
            self.assertEqual(payload["state_duration_seconds"], 60)

            human_result = subprocess.run(
                [sys.executable, str(HEALTH_COMMAND), *common],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(human_result.returncode, 0, human_result.stderr)
            self.assertIn("State:              HEALTHY_PPS", human_result.stdout)
            self.assertIn("State duration:     60 seconds", human_result.stdout)

            metrics_result = subprocess.run(
                [sys.executable, str(HEALTH_COMMAND), "--prometheus", *common],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(metrics_result.returncode, 0, metrics_result.stderr)
            self.assertIn(
                'ppstime_health_state{state="UNKNOWN"} 0', metrics_result.stdout
            )
            self.assertIn(
                'ppstime_health_state{state="HEALTHY_PPS"} 1', metrics_result.stdout
            )
            self.assertIn(
                'ppstime_health_state{state="NETWORK_FALLBACK"} 0',
                metrics_result.stdout,
            )
            self.assertIn("ppstime_health_state_duration_seconds 60", metrics_result.stdout)

    def test_health_state_file_mode_is_world_readable_and_non_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_update(root, healthy_status(), "2026-07-22T12:00:00Z")
            _, state = self.run_update(root, healthy_status(), "2026-07-22T12:01:00Z")
            state_path = root / "health-state.json"
            self.assertEqual(state_path.stat().st_mode & 0o777, 0o644)
            serialized = json.dumps(state).lower()
            for forbidden in ("password", "secret", "token", "private_key"):
                self.assertNotIn(forbidden, serialized)

    def test_boolean_numeric_fields_and_impossible_pending_count_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid_status = healthy_status()
            invalid_status["chrony"]["stratum"] = True
            status_path = root / "status.json"
            state_path = root / "health-state.json"
            status_path.write_text(json.dumps(invalid_status), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(HEALTH_COMMAND),
                    "--update",
                    "--state-file",
                    str(state_path),
                    "--status-json",
                    str(status_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("stratum must be an integer or null", process.stdout)
            self.assertFalse(state_path.exists())

            invalid_state = {
                "schema_version": 1,
                "state": "UNKNOWN",
                "state_since": None,
                "state_since_monotonic_seconds": None,
                "pending_state": "HEALTHY_PPS",
                "pending_count": 2,
                "last_checked_at": None,
                "last_observation": None,
                "last_transition": None,
            }
            invalid_state["pending_state"] = "HEALTHY_PPS"
            invalid_state["pending_count"] = 2
            state_path.write_text(json.dumps(invalid_state), encoding="utf-8")
            status_path.write_text(json.dumps(healthy_status()), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(HEALTH_COMMAND),
                    "--update",
                    "--state-file",
                    str(state_path),
                    "--status-json",
                    str(status_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("invalid pending count", process.stdout)

    def test_nonfinite_clock_timestamp_and_unknown_state_keys_are_rejected(self) -> None:
        module = load_health_module()
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaisesRegex(
                module.HealthError, "finite non-negative"
            ):
                module.requested_monotonic(value)

        state = module.empty_state()
        state["state"] = "HEALTHY_PPS"
        state["state_since"] = True
        state["state_since_monotonic_seconds"] = 1.0
        with self.assertRaisesRegex(module.HealthError, "must be a string"):
            module.validate_state(state)

        state = module.empty_state()
        state["unexpected_secret"] = "must not pass through diagnostics"
        with self.assertRaisesRegex(module.HealthError, "keys do not match schema"):
            module.validate_state(state)

    def test_diagnostics_health_state_is_valid_json(self) -> None:
        module = load_diagnostics_module()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "health-state.json"
            module.run_command = lambda command, timeout: SimpleNamespace(
                returncode=0,
                stdout='{"state":"HEALTHY_PPS"}\n',
                stderr="",
            )
            module.write_health_state(output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {
                "state": "HEALTHY_PPS"
            })


if __name__ == "__main__":
    unittest.main()
