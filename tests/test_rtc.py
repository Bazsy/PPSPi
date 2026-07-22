from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import config_to_env, load_config


class RtcCommandTests(unittest.TestCase):
    def run_restore(
        self, hwclock_stderr: str, hwclock_exit: int
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            hwclock = bin_dir / "hwclock"
            hwclock.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' {hwclock_stderr!r} >&2\n"
                f"exit {hwclock_exit}\n",
                encoding="utf-8",
            )
            hwclock.chmod(0o755)

            config = load_config(PROJECT_ROOT, environ={})
            config["RTC_DEVICE"] = "/dev/null"
            config_path = root / "ppstime.env"
            config_path.write_text(config_to_env(config), encoding="utf-8")

            environment = dict(os.environ)
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            return subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "files" / "ppstime" / "ppstime-rtc"),
                    "restore",
                    "--config",
                    str(config_path),
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )

    def test_uninitialized_rtc_is_a_successful_restore_skip(self) -> None:
        process = self.run_restore(
            "hwclock: ioctl(RTC_RD_NAME) to /dev/rtc0 to read the time failed: Invalid argument",
            1,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("hardware clock is uninitialized", process.stderr)

    def test_other_restore_errors_remain_failures(self) -> None:
        process = self.run_restore("hwclock: read failed: Input/output error", 1)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Input/output error", process.stderr)

    def test_generic_invalid_argument_remains_a_failure(self) -> None:
        process = self.run_restore("hwclock: invalid option: Invalid argument", 1)
        self.assertEqual(process.returncode, 1)
        self.assertNotIn("hardware clock is uninitialized", process.stderr)

    def test_successful_restore_remains_successful(self) -> None:
        process = self.run_restore("", 0)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("RTC restore completed", process.stdout)

    def run_required_save(
        self,
        *,
        synchronized: bool = True,
        device: str = "/dev/null",
        hwclock_exit: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            chronyc = bin_dir / "chronyc"
            leap = "Normal" if synchronized else "Not synchronised"
            chronyc.write_text(
                f"#!/bin/sh\nprintf '%s\\n' 'Leap status     : {leap}'\n",
                encoding="utf-8",
            )
            chronyc.chmod(0o755)
            hwclock = bin_dir / "hwclock"
            hwclock.write_text(
                f"#!/bin/sh\nexit {hwclock_exit}\n",
                encoding="utf-8",
            )
            hwclock.chmod(0o755)
            config = load_config(PROJECT_ROOT, environ={})
            config["RTC_DEVICE"] = device
            config_path = root / "ppstime.env"
            config_path.write_text(config_to_env(config), encoding="utf-8")
            environment = dict(os.environ)
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            return subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "files" / "ppstime" / "ppstime-rtc"),
                    "save",
                    "--required",
                    "--config",
                    str(config_path),
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )

    def test_required_save_fails_when_unsynchronized(self) -> None:
        process = self.run_required_save(synchronized=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("not synchronized", process.stderr)

    def test_required_save_fails_when_device_missing(self) -> None:
        process = self.run_required_save(device="/dev/ppstime-missing-rtc")
        self.assertEqual(process.returncode, 1)
        self.assertIn("unavailable", process.stderr)

    def test_required_save_fails_on_hwclock_error(self) -> None:
        process = self.run_required_save(hwclock_exit=1)
        self.assertEqual(process.returncode, 1)

    def test_required_save_succeeds_after_real_write(self) -> None:
        process = self.run_required_save()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("RTC save completed", process.stdout)


if __name__ == "__main__":
    unittest.main()
