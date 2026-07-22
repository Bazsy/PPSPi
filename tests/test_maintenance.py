from __future__ import annotations

import importlib.machinery
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PROJECT_ROOT / "files" / "ppstime"
MAINTENANCE_COMMAND = CORE_PATH / "ppstime-maintenance"
sys.path.insert(0, str(CORE_PATH))

from ppstime_core import (
    config_to_env,
    load_config,
    render_maintenance_timer,
    render_unattended_upgrades,
)


def load_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ppstime_maintenance", str(MAINTENANCE_COMMAND))
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


class MaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(PROJECT_ROOT, environ={})

    def args(self, root: Path) -> Namespace:
        config = root / "ppstime.env"
        config.write_text(config_to_env(self.config), encoding="utf-8")
        boot_id = root / "boot-id"
        boot_id.write_text("boot-one\n", encoding="ascii")
        return Namespace(
            config=config,
            state_file=root / "os-update-state.json",
            reboot_state=root / "reboot-pending.json",
            post_boot_state=root / "maintenance-post-boot.json",
            boot_id_file=boot_id,
            reboot_required=root / "reboot-required",
            lock_file=root / "maintenance.lock",
            package_lock_files=[
                root / "apt-archives-lock",
                root / "apt-lists-lock",
                root / "dpkg-lock",
                root / "dpkg-lock-frontend",
            ],
            package_lock_timeout=1.0,
            update_command=["update"],
            upgrade_command=["upgrade"],
            audit_command=["audit"],
            tracking_command=["tracking"],
            rtc_command=["rtc"],
            reboot_command=["reboot"],
            deep_test_command=["deep"],
            health_command=["health"],
            allow_non_root=True,
        )

    def completed(
        self, code: int = 0, stdout: str = "", stderr: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], code, stdout, stderr)

    def test_rendered_security_policy_and_weekly_timer(self) -> None:
        policy = render_unattended_upgrades(self.config)
        self.assertIn("#clear Unattended-Upgrade::Allowed-Origins;", policy)
        self.assertIn("#clear Unattended-Upgrade::Origins-Pattern;", policy)
        self.assertIn("${distro_codename}-security", policy)
        self.assertNotIn('${distro_codename}-updates', policy)
        self.assertNotIn('codename=${distro_codename},label=Debian";', policy)
        self.assertNotIn("origin=Raspbian", policy)
        self.assertNotIn("origin=Raspberry Pi Foundation", policy)
        self.assertIn('Automatic-Reboot "false"', policy)
        timer = render_maintenance_timer(self.config)
        self.assertIn("OnCalendar=Sun *-*-* 04:00:00 UTC", timer)
        self.assertIn("RandomizedDelaySec=30min", timer)

        all_updates = dict(self.config, OS_UPDATE_SCOPE="all")
        policy = render_unattended_upgrades(all_updates)
        self.assertIn('${distro_codename}-updates', policy)
        self.assertIn("origin=Raspbian", policy)

    def test_success_without_reboot_records_state(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            with patch.object(module, "run_command", return_value=self.completed()):
                result = module.run_maintenance(args)
            self.assertEqual(result, 0)
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["result"], "SUCCESS")
            self.assertFalse(state["reboot_required"])
            self.assertEqual(state["last_success_utc"], state["last_check_utc"])
            self.assertFalse(args.reboot_state.exists())

    def test_failed_upgrade_preserves_last_success(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.state_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "last_check_utc": "2026-07-21T00:00:00Z",
                        "last_success_utc": "2026-07-21T00:00:00Z",
                        "result": "SUCCESS",
                        "reboot_required": False,
                    }
                ),
                encoding="utf-8",
            )

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                return self.completed(1 if command[0] == "upgrade" else 0)

            with patch.object(module, "run_command", side_effect=run), self.assertRaisesRegex(
                module.MaintenanceError, "unattended-upgrade"
            ):
                module.run_maintenance(args)
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["result"], "FAILED")
            self.assertEqual(state["last_success_utc"], "2026-07-21T00:00:00Z")

    def test_required_reboot_saves_rtc_and_records_boot_id(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_required.touch()
            calls: list[str] = []

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                calls.append(command[0])
                if command[0] == "tracking":
                    return self.completed(stdout="Leap status     : Normal\n")
                return self.completed()

            with patch.object(module, "run_command", side_effect=run):
                result = module.run_maintenance(args)
            self.assertEqual(result, 0)
            self.assertEqual(
                calls,
                ["update", "upgrade", "audit", "tracking", "rtc", "audit", "reboot"],
            )
            marker = json.loads(args.reboot_state.read_text(encoding="utf-8"))
            self.assertEqual(marker["requested_boot_id"], "boot-one")
            self.assertEqual(marker["reason"], "os_reboot_required")
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertTrue(state["reboot_required"])

    def test_required_reboot_defers_when_unsynchronized(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_required.touch()

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                if command[0] == "tracking":
                    return self.completed(stdout="Leap status     : Not synchronised\n")
                return self.completed()

            with patch.object(module, "run_command", side_effect=run), self.assertRaisesRegex(
                module.MaintenanceError, "deferred"
            ):
                module.run_maintenance(args)
            self.assertFalse(args.reboot_state.exists())

    def test_post_boot_acknowledges_only_changed_boot_id(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_state.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reason": "os_reboot_required",
                        "requested_utc": "2026-07-22T12:00:00Z",
                        "requested_boot_id": "boot-one",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(
                module, "run_command", return_value=self.completed()
            ), self.assertRaisesRegex(module.MaintenanceError, "current boot"):
                module.post_boot(args)
            self.assertTrue(args.reboot_state.exists())

            args.boot_id_file.write_text("boot-two\n", encoding="ascii")
            args.state_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "last_check_utc": "2026-07-22T12:00:00Z",
                        "last_success_utc": "2026-07-22T12:00:00Z",
                        "result": "SUCCESS",
                        "reboot_required": True,
                    }
                ),
                encoding="utf-8",
            )
            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                if command[0] == "deep":
                    return self.completed(stdout='{"ok":true}\n')
                if command[0] == "health":
                    return self.completed(
                        stdout='{"state":"HEALTHY_PPS","host_state":"HEALTHY"}\n'
                    )
                return self.completed()

            with patch.object(module, "run_command", side_effect=run):
                self.assertEqual(module.post_boot(args), 0)
            self.assertFalse(args.reboot_state.exists())
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertFalse(state["reboot_required"])
            evidence = json.loads(args.post_boot_state.read_text(encoding="utf-8"))
            self.assertEqual(evidence["reason"], "os_reboot_required")
            self.assertEqual(evidence["completed_boot_id"], "boot-two")
            self.assertTrue(evidence["deep_test_ok"])
            self.assertEqual(evidence["timing_state"], "HEALTHY_PPS")

    def test_second_audit_failure_records_failed_state(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_required.touch()
            audit_count = 0

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                nonlocal audit_count
                if command[0] == "tracking":
                    return self.completed(stdout="Leap status     : Normal\n")
                if command[0] == "audit":
                    audit_count += 1
                    return self.completed(stdout="broken\n" if audit_count == 2 else "")
                return self.completed()

            with patch.object(module, "run_command", side_effect=run), self.assertRaisesRegex(
                module.MaintenanceError, "audit"
            ):
                module.run_maintenance(args)
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["result"], "FAILED")
            self.assertIsNone(state["last_success_utc"])
            self.assertFalse(args.reboot_state.exists())

    def test_reboot_launch_exception_removes_marker_and_records_failure(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_required.touch()

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                if command[0] == "tracking":
                    return self.completed(stdout="Leap status     : Normal\n")
                if command[0] == "reboot":
                    raise module.MaintenanceError("cannot run reboot: timed out")
                return self.completed()

            with patch.object(module, "run_command", side_effect=run), self.assertRaisesRegex(
                module.MaintenanceError, "timed out"
            ):
                module.run_maintenance(args)
            self.assertFalse(args.reboot_state.exists())
            state = json.loads(args.state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["result"], "FAILED")

    def test_state_write_failure_after_marker_removes_marker(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.reboot_required.touch()
            original_atomic = module.atomic_json

            def atomic(path: Path, payload: dict[str, object], mode: int = 0o644) -> None:
                if path == args.state_file and args.reboot_state.exists():
                    raise OSError("simulated state write failure")
                original_atomic(path, payload, mode)

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                if command[0] == "tracking":
                    return self.completed(stdout="Leap status     : Normal\n")
                return self.completed()

            with patch.object(module, "atomic_json", side_effect=atomic), patch.object(
                module, "run_command", side_effect=run
            ), self.assertRaisesRegex(OSError, "simulated"):
                module.run_maintenance(args)
            self.assertFalse(args.reboot_state.exists())

    def test_disabled_updates_do_not_run_commands(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.args(root)
            config = dict(self.config, OS_UPDATES_ENABLED="false")
            args.config.write_text(config_to_env(config), encoding="utf-8")
            with patch.object(module, "run_command") as run:
                self.assertEqual(module.run_maintenance(args), 0)
            run.assert_not_called()

    def test_package_lock_timeout_is_bounded(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "dpkg-lock"
            with patch.object(
                module.fcntl, "lockf", side_effect=BlockingIOError
            ), patch.object(module.time, "monotonic", side_effect=[0.0, 1.0]), patch.object(
                module.time, "sleep"
            ), self.assertRaisesRegex(
                module.MaintenanceError, "timed out"
            ), module.acquire_package_locks([lock_path], 0.5):
                self.fail("unreachable")

    def test_post_boot_failure_records_evidence_and_clears_marker(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            args = self.args(Path(temporary))
            args.boot_id_file.write_text("boot-two\n", encoding="ascii")
            args.reboot_state.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reason": "os_reboot_required",
                        "requested_utc": "2026-07-22T12:00:00Z",
                        "requested_boot_id": "boot-one",
                    }
                ),
                encoding="utf-8",
            )

            def run(command: list[str], timeout: int = 0) -> subprocess.CompletedProcess[str]:
                if command[0] == "deep":
                    return self.completed(1, stdout='{"ok":false}\n')
                if command[0] == "health":
                    return self.completed(
                        stdout='{"state":"UNSYNCHRONIZED","host_state":"WARNING"}\n'
                    )
                return self.completed()

            with patch.object(module, "run_command", side_effect=run), self.assertRaisesRegex(
                module.MaintenanceError, "deep health"
            ):
                module.post_boot(args)
            self.assertFalse(args.reboot_state.exists())
            evidence = json.loads(args.post_boot_state.read_text(encoding="utf-8"))
            self.assertFalse(evidence["deep_test_ok"])
            self.assertEqual(evidence["timing_state"], "UNSYNCHRONIZED")
            self.assertEqual(evidence["host_state"], "WARNING")


if __name__ == "__main__":
    unittest.main()
