from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import (
    ConfigError,
    load_config,
    remove_serial_console,
    render_boot_block,
    update_managed_block,
)


class BootConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(PROJECT_ROOT, environ={})
        self.block = render_boot_block(self.config)

    def test_managed_block_is_idempotent_and_preserves_unrelated_lines(self) -> None:
        original = "# Raspberry Pi settings\ndtparam=audio=on\n"
        once = update_managed_block(original, self.block)
        twice = update_managed_block(once, self.block)
        self.assertEqual(once, twice)
        self.assertIn("dtparam=audio=on", once)
        self.assertEqual(once.count("dtoverlay=pps-gpio"), 1)
        self.assertEqual(
            once.count("dtoverlay=i2c-rtc,rv3028,backup-switchover-mode=3"), 1
        )

    def test_managed_block_replaces_previous_values(self) -> None:
        old_block = self.block.replace("gpiopin=18", "gpiopin=4")
        existing = f"gpu_mem=16\n\n{old_block}\n"
        updated = update_managed_block(existing, self.block)
        self.assertNotIn("gpiopin=4", updated)
        self.assertIn("gpu_mem=16", updated)

    def test_malformed_markers_are_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            update_managed_block("# BEGIN PPSPi managed configuration\n", self.block)

    def test_only_serial_console_is_removed(self) -> None:
        cmdline = "console=serial0,115200 console=tty1 root=PARTUUID=abc rw quiet\n"
        updated = remove_serial_console(cmdline)
        self.assertNotIn("console=serial0", updated)
        self.assertIn("console=tty1", updated)
        self.assertIn("root=PARTUUID=abc", updated)
        self.assertEqual(updated.count("\n"), 1)

    def test_disabled_rtc_backup_mode_omits_overlay_parameter(self) -> None:
        config = dict(self.config, RTC_BACKUP_SWITCH_MODE="0")
        block = render_boot_block(config)
        self.assertIn("dtoverlay=i2c-rtc,rv3028\n", block)
        self.assertNotIn("backup-switchover-mode", block)


if __name__ == "__main__":
    unittest.main()
