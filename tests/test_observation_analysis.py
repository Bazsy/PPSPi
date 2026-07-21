from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_analyzer() -> ModuleType:
    path = PROJECT_ROOT / "scripts" / "analyze-observation.py"
    spec = importlib.util.spec_from_file_location("analyze_observation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_healthy_observation(root: Path) -> None:
    start = datetime(2026, 7, 21, tzinfo=timezone.utc)
    (root / "identity.txt").write_text(
        "start_utc=20260721T000000Z\n", encoding="utf-8"
    )
    (root / "final.txt").write_text(
        "end_utc=20260722T000000Z\n"
        "[final-deep-test]\n"
        '{"checks":[],"ok":true}\n'
        "[failed-units]\n",
        encoding="utf-8",
    )
    lines: list[str] = []
    for index in range(1440):
        current = start + timedelta(minutes=index)
        current_timestamp = timestamp(current)
        system_offset = 0.000001 if index % 2 == 0 else -0.000001
        pps_offset = 0.0000002 if index % 2 == 0 else -0.0000002
        lines.extend(
            (
                f"SAMPLE\t{index + 1}\t{current_timestamp}\t50000",
                "TRACKING\t"
                f"{current_timestamp}\t50505300,PPS,1,1784575713.0,"
                f"{system_offset},0.0,0.000001,19.0,0.0,0.1,"
                "0.000000001,0.0002,1.0,Normal",
                "SOURCE\t"
                f"{current_timestamp}\t#,*,PPS,0,0,377,0,0.0,"
                f"{pps_offset},0.000000101",
                f"PPS_ASSERT\t{current_timestamp}\t1784575713.0#{1000 + index}",
                f"POWER\t{current_timestamp}\tthrottled=0x0",
                f"SERVICE\t{current_timestamp}\tchrony\tactive\t0",
                f"SERVICE\t{current_timestamp}\tgpsd\tactive\t0",
                f"FAILED_UNITS\t{current_timestamp}\t0",
            )
        )
        if index % 5 == 0:
            lines.append(
                f"GNSS\t{current_timestamp}\t"
                + json.dumps(
                    {
                        "mode": 3,
                        "satellites_visible": 26,
                        "satellites_used": 16,
                        "nonzero_signal": 19,
                        "max_signal": 49.0,
                        "gdop": 1.5,
                        "hdop": 0.7,
                        "pdop": 1.3,
                        "eph": 1.2,
                        "epv": 1.5,
                        "pps_reports": 2,
                    },
                    separators=(",", ":"),
                )
            )
    (root / "samples.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


class ObservationAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analyzer = load_analyzer()

    def test_complete_healthy_observation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_healthy_observation(root)
            summary = self.analyzer.analyze_observation(root)

        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(summary["completed"])
        self.assertEqual(summary["duration_hours"], 24.0)
        self.assertEqual(summary["sample_count"], 1440)
        self.assertEqual(summary["tracking"]["pps_selected_percent"], 100.0)
        self.assertEqual(summary["pps"]["assert_availability_percent"], 100.0)
        self.assertEqual(summary["pps"]["reach_zero_samples"], 0)
        self.assertEqual(summary["gnss"]["mode_3d_percent"], 100.0)
        self.assertAlmostEqual(summary["timing"]["system_offset_seconds"]["mean"], 0.0)
        self.assertAlmostEqual(
            summary["timing"]["system_offset_seconds"]["rms"], 0.000001
        )
        self.assertEqual(summary["services"]["chrony"]["maximum_restart_count"], 0)
        self.assertEqual(summary["maximum_failed_unit_count"], 0)
        self.assertEqual(summary["anomalies"], [])

    def test_in_progress_file_uses_sample_timestamp_column(self) -> None:
        content = (
            "SAMPLE\t1\t2026-07-21T08:48:24Z\t49000\n"
            "SAMPLE\t2\t2026-07-21T08:49:24Z\t50000\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "samples.tsv"
            path.write_text(content, encoding="utf-8")
            summary = self.analyzer.analyze_observation(path)

        self.assertEqual(summary["status"], "IN_PROGRESS")
        self.assertFalse(summary["completed"])
        self.assertEqual(summary["start_utc"], "2026-07-21T08:48:24Z")
        self.assertEqual(summary["end_utc"], "2026-07-21T08:49:24Z")
        self.assertEqual(summary["sample_count"], 2)

    def test_completed_anomalies_fail(self) -> None:
        start = datetime(2026, 7, 21, tzinfo=timezone.utc)
        second = start + timedelta(minutes=1)
        lines = [
            f"SAMPLE\t1\t{timestamp(start)}\t50000",
            f"SAMPLE\t2\t{timestamp(second)}\t51000",
            f"TRACKING\t{timestamp(start)}\t"
            "C0000201,network,2,0,0.01,0.01,0.01,20,0,2,"
            "0.01,0.02,64,Not synchronised",
            f"SOURCE\t{timestamp(start)}\t#,-,PPS,0,0,0,120,0.0,0.001,0.000000101",
            f"PPS_ASSERT\t{timestamp(start)}\t1.0#10",
            f"PPS_ASSERT\t{timestamp(second)}\t1.0#10",
            f"GNSS\t{timestamp(start)}\t{{\"mode\":2,\"satellites_used\":3,\"pps_reports\":0}}",
            f"POWER\t{timestamp(start)}\tthrottled=0x50000",
            f"SERVICE\t{timestamp(start)}\tchrony\tinactive\t1",
            f"SERVICE\t{timestamp(start)}\tgpsd\tactive\t0",
            f"FAILED_UNITS\t{timestamp(start)}\t1",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "identity.txt").write_text(
                "start_utc=20260721T000000Z\n", encoding="utf-8"
            )
            (root / "final.txt").write_text(
                "end_utc=20260722T000000Z\n"
                "[final-deep-test]\n"
                '{"checks":[],"ok":false}\n'
                "[failed-units]\n",
                encoding="utf-8",
            )
            (root / "samples.tsv").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            summary = self.analyzer.analyze_observation(root)

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["pps"]["frozen_intervals"], 1)
        self.assertEqual(summary["pps"]["reach_zero_samples"], 1)
        self.assertEqual(summary["services"]["chrony"]["inactive_samples"], 1)
        self.assertEqual(summary["services"]["chrony"]["maximum_restart_count"], 1)
        self.assertEqual(summary["maximum_failed_unit_count"], 1)
        self.assertEqual(summary["power"]["nonzero_throttling_samples"], 1)
        self.assertFalse(summary["final_deep_test_ok"])
        self.assertIn("final deep test did not pass", summary["anomalies"])
        self.assertTrue(any("PPS was not #*" in item for item in summary["anomalies"]))
        self.assertTrue(any("PPS reach was zero" in item for item in summary["anomalies"]))
        self.assertTrue(any("GNSS mode was not 3D" in item for item in summary["anomalies"]))

    def test_completed_missing_required_records_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "identity.txt").write_text(
                "start_utc=20260721T000000Z\n", encoding="utf-8"
            )
            (root / "final.txt").write_text(
                "end_utc=20260722T000000Z\n", encoding="utf-8"
            )
            (root / "samples.tsv").write_text(
                "SAMPLE\t1\t2026-07-21T00:00:00Z\t50000\n",
                encoding="utf-8",
            )
            summary = self.analyzer.analyze_observation(root)

        self.assertEqual(summary["status"], "FAIL")
        self.assertTrue(
            any("tracking record coverage is incomplete" in item for item in summary["anomalies"])
        )
        self.assertTrue(
            any("GNSS record coverage is incomplete" in item for item in summary["anomalies"])
        )
        self.assertIn("final deep-test result is missing or malformed", summary["anomalies"])


if __name__ == "__main__":
    unittest.main()
