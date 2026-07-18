from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PROJECT_ROOT / "files" / "ppstime"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "stratum1"
sys.path.insert(0, str(CORE_PATH))

from ppstime_core import config_to_env, load_config


class StatusTests(unittest.TestCase):
    def run_status(self, config_path: Path, fixture_dir: Path) -> dict[str, object]:
        process = subprocess.run(
            [
                sys.executable,
                str(CORE_PATH / "ppstime-status"),
                "--json",
                "--config",
                str(config_path),
                "--fixture-dir",
                str(fixture_dir),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_successful_stratum_one_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "ppstime.env"
            config_path.write_text(
                config_to_env(load_config(PROJECT_ROOT, environ={})), encoding="utf-8"
            )
            status = self.run_status(config_path, FIXTURES)
        self.assertEqual(status["gps"]["fix"], "3D")
        self.assertEqual(status["gps"]["configured_baud"], 115200)
        self.assertEqual(status["gps"]["reported_baud"], 115200)
        self.assertEqual(status["pps"]["pulses"], "ACTIVE")
        self.assertEqual(status["rtc"]["status"], "OK")
        self.assertEqual(status["chrony"]["state"], "SYNCHRONIZED")
        self.assertEqual(status["chrony"]["selected_source"], "PPS")
        self.assertEqual(status["chrony"]["stratum"], 1)
        self.assertEqual(status["chrony"]["system_offset_seconds"], "+0.000002100")
        self.assertEqual(status["ntp_clients"], 4)

    def test_network_fallback_and_inactive_pps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_dir = root / "fixtures"
            shutil.copytree(FIXTURES, fixture_dir)
            (fixture_dir / "chronyc-sources.txt").write_text(
                (FIXTURES / "chronyc-sources.txt")
                .read_text(encoding="utf-8")
                .replace("#* PPS", "#? PPS")
                .replace("^+ 192.0.2.1", "^* 192.0.2.1"),
                encoding="utf-8",
            )
            (fixture_dir / "ppstest.txt").write_text("timeout waiting for PPS\n", encoding="utf-8")
            config_path = root / "ppstime.env"
            config_path.write_text(
                config_to_env(load_config(PROJECT_ROOT, environ={})), encoding="utf-8"
            )
            status = self.run_status(config_path, fixture_dir)
        self.assertEqual(status["chrony"]["selected_source"], "192.0.2.1")
        self.assertEqual(status["pps"]["pulses"], "INACTIVE")

    def test_required_degraded_states(self) -> None:
        scenarios = {
            "missing_serial": (
                lambda fixture: (fixture / "device-state.json").write_text(
                    '{"gps_device": false, "pps_device": true, "rtc_device": true}\n',
                    encoding="utf-8",
                ),
                lambda status: self.assertEqual(status["gps"]["serial"], "MISSING"),
            ),
            "gps_without_fix": (
                lambda fixture: (fixture / "gpspipe.txt").write_text(
                    '{"class":"TPV","mode":1}\n{"class":"SKY","satellites":[]}\n',
                    encoding="utf-8",
                ),
                lambda status: self.assertEqual(status["gps"]["fix"], "NO FIX"),
            ),
            "gps_fix_without_pps": (
                lambda fixture: (fixture / "ppstest.txt").write_text(
                    "timeout waiting for PPS\n", encoding="utf-8"
                ),
                lambda status: self.assertEqual(status["pps"]["pulses"], "INACTIVE"),
            ),
            "pps_active_chrony_unsynchronized": (
                lambda fixture: (fixture / "chronyc-tracking.txt").write_text(
                    (FIXTURES / "chronyc-tracking.txt")
                    .read_text(encoding="utf-8")
                    .replace("Leap status     : Normal", "Leap status     : Not synchronised"),
                    encoding="utf-8",
                ),
                lambda status: self.assertEqual(
                    status["chrony"]["state"], "NOT SYNCHRONIZED"
                ),
            ),
            "rtc_unavailable": (
                lambda fixture: (fixture / "device-state.json").write_text(
                    '{"gps_device": true, "pps_device": true, "rtc_device": false}\n',
                    encoding="utf-8",
                ),
                lambda status: self.assertEqual(status["rtc"]["status"], "UNAVAILABLE"),
            ),
        }
        for name, (mutate, assertion) in scenarios.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture_dir = root / "fixtures"
                shutil.copytree(FIXTURES, fixture_dir)
                mutate(fixture_dir)
                config_path = root / "ppstime.env"
                config_path.write_text(
                    config_to_env(load_config(PROJECT_ROOT, environ={})), encoding="utf-8"
                )
                assertion(self.run_status(config_path, fixture_dir))

    def test_deep_validation_command_with_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "ppstime.env"
            config_path.write_text(
                config_to_env(load_config(PROJECT_ROOT, environ={})), encoding="utf-8"
            )
            boot_path = root / "config.txt"
            boot_path.write_text(
                "enable_uart=1\n"
                "dtoverlay=pps-gpio,gpiopin=18\n"
                "dtoverlay=i2c-rtc,rv3028\n",
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(CORE_PATH / "ppstime-test"),
                    "--json",
                    "--config",
                    str(config_path),
                    "--fixture-dir",
                    str(FIXTURES),
                    "--boot-config",
                    str(boot_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])

    def test_deep_validation_rejects_reported_baud_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_dir = root / "fixtures"
            shutil.copytree(FIXTURES, fixture_dir)
            gpspipe = fixture_dir / "gpspipe.txt"
            gpspipe.write_text(
                gpspipe.read_text(encoding="utf-8").replace('"bps":115200', '"bps":9600'),
                encoding="utf-8",
            )
            config_path = root / "ppstime.env"
            config_path.write_text(
                config_to_env(load_config(PROJECT_ROOT, environ={})), encoding="utf-8"
            )
            boot_path = root / "config.txt"
            boot_path.write_text(
                "enable_uart=1\n"
                "dtoverlay=pps-gpio,gpiopin=18\n"
                "dtoverlay=i2c-rtc,rv3028\n",
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(CORE_PATH / "ppstime-test"),
                    "--json",
                    "--config",
                    str(config_path),
                    "--fixture-dir",
                    str(fixture_dir),
                    "--boot-config",
                    str(boot_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        result = json.loads(process.stdout)
        baud_check = next(check for check in result["checks"] if check["name"] == "gps_baud")
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(result["ok"])
        self.assertEqual(baud_check["status"], "FAIL")
        self.assertEqual(baud_check["message"], "configured=115200, reported=9600")


if __name__ == "__main__":
    unittest.main()