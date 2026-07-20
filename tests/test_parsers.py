from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "stratum1"
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import (
    parse_chrony_clients,
    parse_chrony_sources,
    parse_gpsd_json,
    parse_ppstest,
    pps_sysfs_active,
    read_pps_sequence,
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

    def test_gps_parser_keeps_valid_sky_among_empty_reports(self) -> None:
        records = "\n".join(
            (
                '{"class":"TPV","device":"/dev/serial0","mode":3}',
                '{"class":"SKY","device":"/dev/serial0","uSat":7}',
                '{"class":"SKY","device":"/dev/serial0","uSat":0}',
                '{"class":"TPV","device":"/dev/other","mode":1}',
            )
        )
        gps = parse_gpsd_json(records, device="/dev/serial0")
        self.assertEqual(gps["fix"], "3D")
        self.assertEqual(gps["satellites_used"], 7)

    def test_unprivileged_pps_sysfs_sequence_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pps_dir = Path(temporary) / "pps0"
            pps_dir.mkdir()
            assert_file = pps_dir / "assert"
            assert_file.write_text("1784549927.999872511#467\n", encoding="ascii")

            def advance_sequence(_: float) -> None:
                assert_file.write_text("1784549928.999872272#468\n", encoding="ascii")

            self.assertEqual(
                read_pps_sequence("/dev/pps0", sysfs_root=Path(temporary)), 467
            )
            with patch("ppstime_core.time.sleep", side_effect=advance_sequence):
                self.assertTrue(
                    pps_sysfs_active("/dev/pps0", sysfs_root=Path(temporary))
                )

            with patch("ppstime_core.time.sleep"):
                self.assertFalse(
                    pps_sysfs_active("/dev/pps0", sysfs_root=Path(temporary))
                )

            assert_file.write_text("malformed\n", encoding="ascii")
            self.assertIsNone(
                read_pps_sequence("/dev/pps0", sysfs_root=Path(temporary))
            )
            self.assertFalse(
                pps_sysfs_active("/dev/not-pps", sysfs_root=Path(temporary))
            )


if __name__ == "__main__":
    unittest.main()