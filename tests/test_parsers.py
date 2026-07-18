from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "stratum1"
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import (
    parse_chrony_clients,
    parse_chrony_sources,
    parse_gpsd_json,
    parse_ppstest,
)


class ParserTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_chrony_sources_selected_pps(self) -> None:
        sources = parse_chrony_sources(self.fixture("chronyc-sources.txt"))
        selected = next(source for source in sources if source["state"] == "*")
        self.assertEqual(selected["name"], "PPS")

    def test_client_count(self) -> None:
        self.assertEqual(parse_chrony_clients(self.fixture("chronyc-clients.txt")), 4)

    def test_gps_fix_and_satellites(self) -> None:
        gps = parse_gpsd_json(self.fixture("gpspipe.txt"), device="/dev/serial0")
        self.assertEqual(gps["fix"], "3D")
        self.assertEqual(gps["satellites_used"], 4)
        self.assertEqual(gps["reported_baud"], 115200)

    def test_real_ppstest_sequence_format(self) -> None:
        self.assertTrue(parse_ppstest(self.fixture("ppstest.txt")))
        self.assertFalse(parse_ppstest("source 0 - assert 1.0, sequence: 1\n"))


if __name__ == "__main__":
    unittest.main()