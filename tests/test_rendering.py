from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import load_config, render_chrony, render_gpsd


class RenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(PROJECT_ROOT, environ={})

    def test_chrony_separates_gps_label_and_pps_precision(self) -> None:
        rendered = render_chrony(self.config)
        self.assertIn("refclock SOCK /run/chrony.clk.serial0.sock refid GPS", rendered)
        self.assertIn("delay 0.2 noselect", rendered)
        self.assertIn("refclock PPS /dev/pps0 refid PPS lock GPS", rendered)
        self.assertIn("dpoll 0 precision 1e-7", rendered)
        self.assertNotIn("dpoll 0 prefer", rendered)
        self.assertIn("pool pool.ntp.org iburst maxsources 4", rendered)
        self.assertIn("maxclockerror 200", rendered)
        self.assertIn("maxdistance 0.1", rendered)
        self.assertIn("allow 10.0.0.0/8", rendered)
        self.assertIn("allow 172.16.0.0/12", rendered)
        self.assertIn("allow 192.168.0.0/16", rendered)
        self.assertIn("allow fc00::/7", rendered)
        self.assertIn("allow 127.0.0.1/32", rendered)
        self.assertIn("allow ::1/128", rendered)
        self.assertEqual(rendered.count("\nallow "), 6)
        self.assertNotIn("allow 0/0", rendered)
        self.assertNotIn("allow fe80::/10", rendered)

    def test_falling_edge_uses_chrony_and_overlay_options(self) -> None:
        config = dict(self.config, PPS_ASSERT_EDGE="falling")
        rendered = render_chrony(config)
        self.assertIn("refclock PPS /dev/pps0:clear", rendered)

    def test_gpsd_opens_devices_at_start_without_hotplug(self) -> None:
        rendered = render_gpsd(self.config)
        self.assertIn('GPSD_OPTIONS="-n -s 115200"', rendered)
        self.assertIn('DEVICES="/dev/serial0 /dev/pps0"', rendered)
        self.assertIn('USBAUTO="false"', rendered)


if __name__ == "__main__":
    unittest.main()