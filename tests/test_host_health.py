from __future__ import annotations

import importlib.machinery
import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST_HEALTH_COMMAND = PROJECT_ROOT / "files" / "ppstime" / "ppstime-host-health"
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))


def load_host_health_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "ppstime_host_health", str(HOST_HEALTH_COMMAND)
    )
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


def healthy_payload() -> dict[str, object]:
    filesystem = {
        "available": True,
        "available_bytes": 8_000_000,
        "available_percent": 80.0,
        "inode_available_percent": 75.0,
        "read_only": False,
        "error": None,
    }
    return {
        "filesystems": {"root": dict(filesystem), "boot": dict(filesystem)},
        "temperature_celsius": 52.5,
        "throttling": {"available": True, "flags": 0, "active": [], "error": None},
        "root_filesystem_errors": 0,
        "updates": {
            "status": "SUCCESS",
            "last_check_utc": "2026-07-22T12:00:00Z",
            "last_success_utc": "2026-07-22T12:00:00Z",
            "success_age_seconds": 0.0,
            "reboot_required": False,
            "error": None,
        },
    }


class HostHealthTests(unittest.TestCase):
    def test_classifies_healthy_warning_and_critical(self) -> None:
        module = load_host_health_module()
        payload = healthy_payload()
        self.assertEqual(module.classify_host(payload), ("HEALTHY", []))

        warning = healthy_payload()
        warning["filesystems"]["root"]["available_percent"] = 10.0
        warning["temperature_celsius"] = 76.0
        warning["throttling"]["flags"] = 1 << 18
        warning["updates"]["reboot_required"] = True
        state, reasons = module.classify_host(warning)
        self.assertEqual(state, "WARNING")
        self.assertEqual(
            reasons,
            [
                "root_disk_low",
                "temperature_high",
                "throttling_occurred",
                "update_reboot_required",
            ],
        )

        critical = healthy_payload()
        critical["filesystems"]["boot"]["inode_available_percent"] = 4.0
        critical["temperature_celsius"] = 90.0
        critical["throttling"]["flags"] = 1 << 0
        critical["root_filesystem_errors"] = 2
        state, reasons = module.classify_host(critical)
        self.assertEqual(state, "CRITICAL")
        self.assertEqual(
            reasons,
            [
                "boot_inodes_critical",
                "temperature_critical",
                "throttling_active",
                "root_filesystem_errors",
            ],
        )

    def test_missing_update_marker_is_reported_without_degrading_host(self) -> None:
        module = load_host_health_module()
        with tempfile.TemporaryDirectory() as temporary:
            updates = module.read_update_state(
                Path(temporary) / "missing.json",
                datetime(2026, 7, 22, 12, tzinfo=timezone.utc),
            )
        self.assertEqual(updates["status"], "UNKNOWN")
        payload = healthy_payload()
        payload["updates"] = updates
        self.assertEqual(module.classify_host(payload), ("HEALTHY", []))

    def test_update_marker_age_failure_and_invalid_schema(self) -> None:
        module = load_host_health_module()
        now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "last_check_utc": "2026-07-22T11:00:00Z",
                        "last_success_utc": "2026-07-14T11:00:00Z",
                        "result": "FAILED",
                        "reboot_required": True,
                    }
                ),
                encoding="utf-8",
            )
            updates = module.read_update_state(path, now)
            self.assertEqual(updates["status"], "FAILED")
            self.assertEqual(updates["success_age_seconds"], 8 * 24 * 3600 + 3600)
            payload = healthy_payload()
            payload["updates"] = updates
            state, reasons = module.classify_host(payload)
            self.assertEqual(state, "CRITICAL")
            self.assertEqual(
                reasons,
                [
                    "update_success_stale_critical",
                    "update_check_failed",
                    "update_reboot_required",
                ],
            )

            path.write_text('{"schema_version":true}\n', encoding="utf-8")
            invalid = module.read_update_state(path, now)
            self.assertEqual(invalid["status"], "UNKNOWN")
            self.assertEqual(invalid["error"], "schema")

    def test_filesystem_percentages_and_read_only(self) -> None:
        module = load_host_health_module()
        fake = SimpleNamespace(
            f_bavail=25,
            f_blocks=100,
            f_frsize=4096,
            f_favail=30,
            f_files=100,
            f_flag=getattr(module.os, "ST_RDONLY", 1),
        )
        with patch.object(module.os, "statvfs", return_value=fake):
            result = module.filesystem_status(Path("/"))
        self.assertEqual(result["available_bytes"], 25 * 4096)
        self.assertEqual(result["available_percent"], 25.0)
        self.assertEqual(result["inode_available_percent"], 30.0)
        self.assertTrue(result["read_only"])

    def test_temperature_and_throttling_parsers(self) -> None:
        module = load_host_health_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            other = root / "thermal_zone0"
            other.mkdir()
            (other / "type").write_text("gpu-thermal\n", encoding="ascii")
            (other / "temp").write_text("60000\n", encoding="ascii")
            cpu = root / "thermal_zone1"
            cpu.mkdir()
            (cpu / "type").write_text("cpu-thermal\n", encoding="ascii")
            (cpu / "temp").write_text("55250\n", encoding="ascii")
            self.assertEqual(module.read_temperature(root), 55.25)

        parsed = module.parse_throttled("throttled=0x50005\n")
        self.assertEqual(parsed["flags"], 0x50005)
        self.assertEqual(
            parsed["active"],
            ["under_voltage_now", "throttled_now", "under_voltage_occurred", "throttling_occurred"],
        )
        with self.assertRaisesRegex(module.HostHealthError, "invalid"):
            module.parse_throttled("not throttled")

    def test_ext4_error_counter_uses_root_mount_device_only(self) -> None:
        module = load_host_health_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mountinfo = root / "mountinfo"
            mountinfo.write_text(
                "36 25 179:2 / / rw,relatime - ext4 /dev/mmcblk0p2 rw\n"
                "37 25 179:1 / /boot/firmware rw,relatime - vfat /dev/mmcblk0p1 rw\n",
                encoding="utf-8",
            )
            device = root / "devices" / "mmcblk0p2"
            device.mkdir(parents=True)
            sys_dev = root / "sys-dev"
            sys_dev.mkdir()
            (sys_dev / "179:2").symlink_to(device, target_is_directory=True)
            sys_ext4 = root / "sys-ext4" / "mmcblk0p2"
            sys_ext4.mkdir(parents=True)
            (sys_ext4 / "errors_count").write_text("3\n", encoding="ascii")
            self.assertEqual(
                module.read_ext4_errors(mountinfo, sys_dev, root / "sys-ext4"),
                3,
            )

    def test_boot_path_requires_actual_mount(self) -> None:
        module = load_host_health_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            boot = root / "boot" / "firmware"
            boot.mkdir(parents=True)
            mountinfo = root / "mountinfo"
            mountinfo.write_text(
                "36 25 179:2 / / rw,relatime - ext4 /dev/mmcblk0p2 rw\n",
                encoding="utf-8",
            )
            self.assertIsNone(module.find_boot_path([boot], mountinfo))
            mountinfo.write_text(
                "36 25 179:2 / / rw,relatime - ext4 /dev/mmcblk0p2 rw\n"
                f"37 25 179:1 / {boot} rw,relatime - vfat /dev/mmcblk0p1 rw\n",
                encoding="utf-8",
            )
            self.assertEqual(module.find_boot_path([boot], mountinfo), boot)

    def test_update_marker_rejects_missing_success_future_and_bad_order(self) -> None:
        module = load_host_health_module()
        now = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        base = {
            "schema_version": 1,
            "last_check_utc": "2026-07-22T11:00:00Z",
            "last_success_utc": "2026-07-22T11:00:00Z",
            "result": "SUCCESS",
            "reboot_required": False,
        }
        scenarios = {
            "missing_success": dict(base, last_success_utc=None),
            "future_check": dict(base, last_check_utc="2099-01-01T00:00:00Z"),
            "future_success": dict(base, last_success_utc="2099-01-01T00:00:00Z"),
            "bad_order": dict(
                base,
                last_check_utc="2026-07-22T10:00:00Z",
                last_success_utc="2026-07-22T11:00:00Z",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "updates.json"
            for expected_error, payload in scenarios.items():
                with self.subTest(expected_error=expected_error):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    result = module.read_update_state(path, now)
                    self.assertEqual(result["status"], "UNKNOWN")
                    expected = (
                        expected_error
                        if expected_error == "missing_success"
                        else "timestamp_order"
                    )
                    self.assertEqual(result["error"], expected)

    def test_fixture_validation_rejects_nonfinite_and_malformed_values(self) -> None:
        module = load_host_health_module()
        payload = healthy_payload()
        payload["temperature_celsius"] = math.nan
        with self.assertRaisesRegex(module.HostHealthError, "finite"):
            module.validate_fixture(payload)

        payload = healthy_payload()
        payload["throttling"]["flags"] = True
        with self.assertRaisesRegex(module.HostHealthError, "non-negative integer"):
            module.validate_fixture(payload)

    def test_threshold_configuration_is_closed_and_ordered(self) -> None:
        module = load_host_health_module()
        defaults = module.validate_thresholds(module.DEFAULT_THRESHOLDS)
        self.assertEqual(defaults["disk_warning_percent"], 15.0)
        invalid = dict(module.DEFAULT_THRESHOLDS)
        invalid["disk_critical_percent"] = 20.0
        with self.assertRaisesRegex(module.HostHealthError, "disk thresholds"):
            module.validate_thresholds(invalid)
        invalid = dict(module.DEFAULT_THRESHOLDS)
        invalid["unexpected"] = 1
        with self.assertRaisesRegex(module.HostHealthError, "keys do not match"):
            module.validate_thresholds(invalid)

    def test_cli_human_and_json_fixture_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "host.json"
            fixture.write_text(json.dumps(healthy_payload()), encoding="utf-8")
            json_result = subprocess.run(
                [
                    sys.executable,
                    str(HOST_HEALTH_COMMAND),
                    "--fixture-json",
                    str(fixture),
                    "--json",
                    "--now",
                    "2026-07-22T12:00:00Z",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(json_result.returncode, 0, json_result.stderr)
            payload = json.loads(json_result.stdout)
            self.assertEqual(payload["state"], "HEALTHY")
            self.assertEqual(payload["reasons"], [])

            human_result = subprocess.run(
                [
                    sys.executable,
                    str(HOST_HEALTH_COMMAND),
                    "--fixture-json",
                    str(fixture),
                    "--now",
                    "2026-07-22T12:00:00Z",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(human_result.returncode, 0, human_result.stderr)
            self.assertIn("State: HEALTHY", human_result.stdout)
            self.assertIn("Temperature: 52.5 C", human_result.stdout)


if __name__ == "__main__":
    unittest.main()
