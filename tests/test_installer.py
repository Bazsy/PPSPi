from __future__ import annotations

import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_alternate_root_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "rootfs"
            boot = root / "boot" / "firmware"
            boot.mkdir(parents=True)
            config_txt = boot / "config.txt"
            cmdline_txt = boot / "cmdline.txt"
            config_txt.write_text("# existing\ndtparam=audio=on\n", encoding="utf-8")
            cmdline_txt.write_text(
                "console=serial0,115200 console=tty1 root=PARTUUID=test rw\n", encoding="utf-8"
            )
            command = [
                "bash",
                str(PROJECT_ROOT / "scripts" / "install.sh"),
                "--root",
                str(root),
                "--skip-packages",
            ]
            first = subprocess.run(command, capture_output=True, check=False, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            installed_config = (root / "etc" / "ppstime" / "ppstime.env").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                stat.S_IMODE((root / "etc" / "ppstime" / "ppstime.env").stat().st_mode),
                0o644,
            )
            installed_boot = config_txt.read_text(encoding="utf-8")
            backups_after_first = sorted(boot.glob("*.ppstime-*.bak"))

            second = subprocess.run(command, capture_output=True, check=False, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                (root / "etc" / "ppstime" / "ppstime.env").read_text(encoding="utf-8"),
                installed_config,
            )
            self.assertEqual(config_txt.read_text(encoding="utf-8"), installed_boot)
            self.assertEqual(sorted(boot.glob("*.ppstime-*.bak")), backups_after_first)
            self.assertEqual(installed_boot.count("# BEGIN PPSPi managed configuration"), 1)
            self.assertIn("dtparam=audio=on", installed_boot)
            self.assertNotIn("console=serial0", cmdline_txt.read_text(encoding="utf-8"))
            self.assertTrue((root / "usr" / "local" / "sbin" / "ppstime-status").is_symlink())
            backup_link = root / "usr" / "local" / "sbin" / "ppstime-backup"
            self.assertTrue(backup_link.is_symlink())
            self.assertEqual(backup_link.readlink(), Path("/usr/lib/ppstime/ppstime-backup"))
            self.assertTrue((root / "usr" / "lib" / "ppstime" / "ppstime-backup").is_file())
            health_link = root / "usr" / "local" / "sbin" / "ppstime-health"
            self.assertTrue(health_link.is_symlink())
            self.assertEqual(health_link.readlink(), Path("/usr/lib/ppstime/ppstime-health"))
            self.assertTrue((root / "usr" / "lib" / "ppstime" / "ppstime-health").is_file())
            self.assertTrue((root / "etc" / "ppstime" / "health-transition.d").is_dir())
            health_service = (
                root / "etc" / "systemd" / "system" / "ppstime-healthcheck.service"
            ).read_text(encoding="utf-8")
            self.assertIn("RuntimeDirectory=ppstime", health_service)
            self.assertIn("RuntimeDirectoryPreserve=yes", health_service)
            self.assertIn("ProtectSystem=strict", health_service)
            health_timer = (
                root / "etc" / "systemd" / "system" / "ppstime-healthcheck.timer"
            ).read_text(encoding="utf-8")
            self.assertIn("OnUnitActiveSec=2min", health_timer)
            self.assertEqual(
                (root / "etc" / "modules-load.d" / "ppstime.conf").read_text(
                    encoding="utf-8"
                ),
                "# PPSPi exposes I2C bus devices for hardware validation and diagnostics.\n"
                "i2c-dev\n",
            )


if __name__ == "__main__":
    unittest.main()
