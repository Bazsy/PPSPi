#!/usr/bin/env python3
"""Summarize a PPSPi 24-hour observation log and flag operational anomalies."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MINIMUM_DURATION_SECONDS = 24 * 60 * 60
MINIMUM_SAMPLE_COVERAGE = 0.95


def parse_timestamp(value: str) -> datetime:
    """Parse one UTC timestamp emitted by the observation logger."""

    for pattern in ("%Y-%m-%dT%H:%M:%SZ", "%Y%m%dT%H%M%SZ"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"invalid UTC timestamp: {value}")


def optional_float(value: str) -> float | None:
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def numeric_summary(values: list[float], *, rms: bool = False) -> dict[str, float] | None:
    """Return stable summary statistics, or None when no values were captured."""

    if not values:
        return None
    result = {
        "samples": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
    }
    if rms:
        result["rms"] = math.sqrt(statistics.fmean(value * value for value in values))
        result["max_absolute"] = max(abs(value) for value in values)
    if len(values) > 1:
        result["standard_deviation"] = statistics.pstdev(values)
    else:
        result["standard_deviation"] = 0.0
    return result


def percentage(numerator: int, denominator: int) -> float | None:
    return 100.0 * numerator / denominator if denominator else None


def read_marker(path: Path, name: str) -> datetime | None:
    """Read a compact UTC marker such as start_utc from an observation file."""

    if not path.is_file():
        return None
    prefix = f"{name}="
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(prefix):
            return parse_timestamp(line.removeprefix(prefix).strip())
    return None


def read_json_section(path: Path, start_marker: str, end_marker: str) -> dict[str, Any] | None:
    """Read one JSON object bounded by exact section markers."""

    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        start = lines.index(start_marker) + 1
        end = lines.index(end_marker, start)
    except ValueError:
        return None
    try:
        value = json.loads("\n".join(lines[start:end]))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def resolve_input(input_path: Path) -> tuple[Path, Path | None, Path | None]:
    """Resolve samples, identity, and final files from a file or directory input."""

    if input_path.is_dir():
        samples = input_path / "samples.tsv"
        identity = input_path / "identity.txt"
        final = input_path / "final.txt"
    else:
        samples = input_path
        identity = None
        final = None
    if not samples.is_file():
        raise FileNotFoundError(f"observation samples not found: {samples}")
    return samples, identity, final


def analyze_observation(input_path: Path) -> dict[str, Any]:
    """Parse one observation and return a JSON-serializable summary."""

    samples_path, identity_path, final_path = resolve_input(input_path)
    sample_times: list[datetime] = []
    temperatures: list[float] = []
    tracking: list[dict[str, Any]] = []
    pps_sources: list[dict[str, Any]] = []
    gnss: list[dict[str, Any]] = []
    pps_sequences: list[tuple[datetime, int]] = []
    power_states: list[tuple[datetime, str]] = []
    services: dict[str, list[dict[str, Any]]] = {"chrony": [], "gpsd": []}
    failed_units: list[int] = []
    malformed_lines = 0

    for raw_line in samples_path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = raw_line.split("\t")
        if not fields:
            continue
        kind = fields[0]
        try:
            if kind == "SAMPLE" and len(fields) >= 4:
                timestamp = parse_timestamp(fields[2])
                sample_times.append(timestamp)
                temperature = optional_float(fields[3])
                if temperature is not None:
                    temperatures.append(temperature / 1000.0)
            elif kind == "TRACKING" and len(fields) >= 3:
                timestamp = parse_timestamp(fields[1])
                values = next(csv.reader([fields[2]]))
                if len(values) < 14:
                    malformed_lines += 1
                    continue
                tracking.append(
                    {
                        "timestamp": timestamp,
                        "reference_id": values[0],
                        "source": values[1],
                        "stratum": int(values[2]),
                        "system_offset": float(values[4]),
                        "last_offset": float(values[5]),
                        "reported_rms_offset": float(values[6]),
                        "frequency": float(values[7]),
                        "skew": float(values[9]),
                        "root_delay": float(values[10]),
                        "root_dispersion": float(values[11]),
                        "leap": values[13],
                    }
                )
            elif kind == "SOURCE" and len(fields) >= 3:
                timestamp = parse_timestamp(fields[1])
                values = next(csv.reader([fields[2]]))
                if len(values) < 10:
                    malformed_lines += 1
                    continue
                if values[2] == "PPS":
                    pps_sources.append(
                        {
                            "timestamp": timestamp,
                            "symbol": values[0] + values[1],
                            "reach": values[5],
                            "last_rx": values[6],
                            "adjusted_offset": float(values[7]),
                            "measured_offset": float(values[8]),
                            "error": float(values[9]),
                        }
                    )
            elif kind == "GNSS" and len(fields) >= 3:
                timestamp = parse_timestamp(fields[1])
                payload = json.loads(fields[2])
                payload["timestamp"] = timestamp
                gnss.append(payload)
            elif kind == "PPS_ASSERT" and len(fields) >= 3:
                timestamp = parse_timestamp(fields[1])
                match = re.search(r"#([0-9]+)\s*$", fields[2])
                if match:
                    pps_sequences.append((timestamp, int(match.group(1))))
            elif kind == "POWER" and len(fields) >= 3:
                power_states.append((parse_timestamp(fields[1]), fields[2].strip()))
            elif kind == "SERVICE" and len(fields) >= 5:
                timestamp = parse_timestamp(fields[1])
                name = fields[2]
                if name in services:
                    services[name].append(
                        {
                            "timestamp": timestamp,
                            "state": fields[3],
                            "restarts": int(fields[4]),
                        }
                    )
            elif kind == "FAILED_UNITS" and len(fields) >= 3:
                failed_units.append(int(fields[2]))
        except (ValueError, json.JSONDecodeError):
            malformed_lines += 1

    if not sample_times:
        raise ValueError("observation contains no valid SAMPLE records")

    start = read_marker(identity_path, "start_utc") if identity_path else None
    end = read_marker(final_path, "end_utc") if final_path else None
    final_deep_test = (
        read_json_section(final_path, "[final-deep-test]", "[failed-units]")
        if final_path
        else None
    )
    completed = end is not None
    start = start or min(sample_times)
    effective_end = end or max(sample_times)
    duration_seconds = max(0.0, (effective_end - start).total_seconds())
    expected_samples = max(1.0, duration_seconds / 60.0)
    sample_coverage = min(100.0, 100.0 * len(sample_times) / expected_samples)

    selected_pps = sum(item["source"] == "PPS" for item in tracking)
    stratum_one = sum(item["stratum"] == 1 for item in tracking)
    normal_leap = sum(item["leap"] == "Normal" for item in tracking)
    pps_selected = sum(item["symbol"] == "#*" for item in pps_sources)
    pps_reach_zero = sum(item["reach"] == "0" for item in pps_sources)
    pps_last_rx = [
        value
        for item in pps_sources
        if (value := optional_float(item["last_rx"])) is not None
    ]

    sequence_pairs = list(zip(pps_sequences, pps_sequences[1:], strict=False))
    advancing_sequences = sum(current[1] != previous[1] for previous, current in sequence_pairs)
    frozen_sequences = len(sequence_pairs) - advancing_sequences

    service_summary: dict[str, Any] = {}
    for name, entries in services.items():
        service_summary[name] = {
            "samples": len(entries),
            "inactive_samples": sum(item["state"] != "active" for item in entries),
            "maximum_restart_count": max((item["restarts"] for item in entries), default=None),
        }

    transitions: list[dict[str, str]] = []
    previous_source: str | None = None
    for item in tracking:
        if item["source"] != previous_source:
            transitions.append(
                {
                    "timestamp": item["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source": item["source"],
                }
            )
            previous_source = item["source"]

    anomalies: list[str] = []
    if completed and duration_seconds < MINIMUM_DURATION_SECONDS:
        anomalies.append(
            f"completed duration is {duration_seconds / 3600:.2f} hours, below 24 hours"
        )
    if completed and not final_deep_test:
        anomalies.append("final deep-test result is missing or malformed")
    elif completed and final_deep_test.get("ok") is not True:
        anomalies.append("final deep test did not pass")
    if completed and sample_coverage < 100.0 * MINIMUM_SAMPLE_COVERAGE:
        anomalies.append(f"sample coverage is only {sample_coverage:.2f}%")
    if completed:
        minimum_minute_records = MINIMUM_SAMPLE_COVERAGE * len(sample_times)
        minute_records = {
            "tracking": len(tracking),
            "PPS source": len(pps_sources),
            "PPS assert": len(pps_sequences),
            "failed-unit": len(failed_units),
            "chrony service": len(services["chrony"]),
            "gpsd service": len(services["gpsd"]),
        }
        for name, count in minute_records.items():
            if count < minimum_minute_records:
                anomalies.append(f"{name} record coverage is incomplete ({count} records)")
        minimum_five_minute_records = MINIMUM_SAMPLE_COVERAGE * len(sample_times) / 5.0
        if len(gnss) < minimum_five_minute_records:
            anomalies.append(f"GNSS record coverage is incomplete ({len(gnss)} records)")
        if len(power_states) < minimum_five_minute_records:
            anomalies.append(f"power record coverage is incomplete ({len(power_states)} records)")
    if tracking and selected_pps != len(tracking):
        count = len(tracking) - selected_pps
        anomalies.append(f"PPS was not the tracked source in {count} samples")
    if tracking and stratum_one != len(tracking):
        anomalies.append(f"Stratum was not 1 in {len(tracking) - stratum_one} samples")
    if tracking and normal_leap != len(tracking):
        anomalies.append(f"leap status was not Normal in {len(tracking) - normal_leap} samples")
    if pps_sources and pps_selected != len(pps_sources):
        anomalies.append(f"PPS was not #* in {len(pps_sources) - pps_selected} source samples")
    if pps_reach_zero:
        anomalies.append(f"PPS reach was zero in {pps_reach_zero} source samples")
    if frozen_sequences:
        anomalies.append(f"PPS assert sequence did not advance in {frozen_sequences} intervals")
    for name, summary in service_summary.items():
        if summary["inactive_samples"]:
            anomalies.append(f"{name} was inactive in {summary['inactive_samples']} samples")
        if summary["maximum_restart_count"] not in (None, 0):
            anomalies.append(f"{name} restart count reached {summary['maximum_restart_count']}")
    maximum_failed_units = max(failed_units, default=0)
    if maximum_failed_units:
        anomalies.append(f"failed unit count reached {maximum_failed_units}")
    nonzero_power = [state for _, state in power_states if state != "throttled=0x0"]
    if nonzero_power:
        anomalies.append(f"nonzero throttling state appeared in {len(nonzero_power)} samples")
    non_3d = sum(int(item.get("mode", 0) or 0) != 3 for item in gnss)
    if non_3d:
        anomalies.append(f"GNSS mode was not 3D in {non_3d} samples")
    missing_gnss_pps = sum(int(item.get("pps_reports", 0) or 0) == 0 for item in gnss)
    if malformed_lines:
        anomalies.append(f"{malformed_lines} observation records were malformed")

    status = "IN_PROGRESS"
    if completed:
        status = "FAIL" if anomalies else "PASS"

    system_offsets = [item["system_offset"] for item in tracking]
    pps_offsets = [item["measured_offset"] for item in pps_sources]
    used_satellites = [
        float(item["satellites_used"])
        for item in gnss
        if isinstance(item.get("satellites_used"), int | float)
    ]
    hdop = [
        float(item["hdop"])
        for item in gnss
        if isinstance(item.get("hdop"), int | float)
    ]
    pdop = [
        float(item["pdop"])
        for item in gnss
        if isinstance(item.get("pdop"), int | float)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "completed": completed,
        "input": str(samples_path),
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_utc": effective_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration_seconds,
        "duration_hours": duration_seconds / 3600.0,
        "sample_count": len(sample_times),
        "sample_coverage_percent": sample_coverage,
        "tracking": {
            "samples": len(tracking),
            "pps_selected_samples": selected_pps,
            "pps_selected_percent": percentage(selected_pps, len(tracking)),
            "stratum_one_percent": percentage(stratum_one, len(tracking)),
            "normal_leap_percent": percentage(normal_leap, len(tracking)),
            "source_transitions": transitions,
        },
        "timing": {
            "system_offset_seconds": numeric_summary(system_offsets, rms=True),
            "pps_offset_seconds": numeric_summary(pps_offsets, rms=True),
            "root_dispersion_seconds": numeric_summary(
                [item["root_dispersion"] for item in tracking]
            ),
            "frequency_ppm": numeric_summary([item["frequency"] for item in tracking]),
            "skew_ppm": numeric_summary([item["skew"] for item in tracking]),
            "temperature_c": numeric_summary(temperatures),
        },
        "pps": {
            "source_samples": len(pps_sources),
            "selected_samples": pps_selected,
            "selected_percent": percentage(pps_selected, len(pps_sources)),
            "reach_zero_samples": pps_reach_zero,
            "maximum_last_rx_seconds": max(pps_last_rx, default=None),
            "assert_samples": len(pps_sequences),
            "assert_intervals": len(sequence_pairs),
            "advancing_intervals": advancing_sequences,
            "frozen_intervals": frozen_sequences,
            "assert_availability_percent": percentage(advancing_sequences, len(sequence_pairs)),
        },
        "gnss": {
            "samples": len(gnss),
            "mode_3d_percent": percentage(len(gnss) - non_3d, len(gnss)),
            "satellites_used": numeric_summary(used_satellites),
            "hdop": numeric_summary(hdop),
            "pdop": numeric_summary(pdop),
            "captures_with_pps": len(gnss) - missing_gnss_pps,
        },
        "services": service_summary,
        "maximum_failed_unit_count": maximum_failed_units,
        "final_deep_test_ok": final_deep_test.get("ok") if final_deep_test else None,
        "power": {
            "samples": len(power_states),
            "nonzero_throttling_samples": len(nonzero_power),
        },
        "malformed_record_count": malformed_lines,
        "anomalies": anomalies,
    }


def format_value(value: float | None, unit: str = "") -> str:
    return "N/A" if value is None else f"{value:.9g}{unit}"


def render_human(summary: dict[str, Any]) -> str:
    """Render a concise review-oriented report."""

    timing = summary["timing"]
    offsets = timing["system_offset_seconds"] or {}
    pps_offsets = timing["pps_offset_seconds"] or {}
    dispersion = timing["root_dispersion_seconds"] or {}
    temperature = timing["temperature_c"] or {}
    gnss = summary["gnss"]
    satellites = gnss["satellites_used"] or {}
    hdop = gnss["hdop"] or {}
    samples = (
        f"{summary['sample_count']} "
        f"({summary['sample_coverage_percent']:.2f}% coverage)"
    )
    pps_selected = format_value(summary["tracking"]["pps_selected_percent"], "%")
    pps_availability = format_value(summary["pps"]["assert_availability_percent"], "%")
    dispersion_range = (
        f"{format_value(dispersion.get('min'), ' s')} .. "
        f"{format_value(dispersion.get('max'), ' s')}"
    )
    temperature_range = (
        f"{format_value(temperature.get('min'), ' C')} .. "
        f"{format_value(temperature.get('max'), ' C')}"
    )
    satellite_range = (
        f"{format_value(satellites.get('min'))} .. "
        f"{format_value(satellites.get('max'))}"
    )
    hdop_range = f"{format_value(hdop.get('min'))} .. {format_value(hdop.get('max'))}"
    deep_test = {
        True: "PASS",
        False: "FAIL",
        None: "N/A",
    }[summary["final_deep_test_ok"]]
    lines = [
        "PPSPi observation summary",
        "--------------------------",
        f"Status:                    {summary['status']}",
        f"Window:                    {summary['start_utc']} to {summary['end_utc']}",
        f"Duration:                  {summary['duration_hours']:.3f} hours",
        f"Samples:                   {samples}",
        f"PPS selected:              {pps_selected}",
        f"PPS reach-zero samples:    {summary['pps']['reach_zero_samples']}",
        f"PPS assert availability:   {pps_availability}",
        f"3D GNSS captures:          {format_value(gnss['mode_3d_percent'], '%')}",
        f"System offset mean:        {format_value(offsets.get('mean'), ' s')}",
        f"System offset RMS:         {format_value(offsets.get('rms'), ' s')}",
        f"System offset max abs:     {format_value(offsets.get('max_absolute'), ' s')}",
        f"PPS offset mean:           {format_value(pps_offsets.get('mean'), ' s')}",
        f"PPS offset std dev:        {format_value(pps_offsets.get('standard_deviation'), ' s')}",
        f"Root dispersion range:     {dispersion_range}",
        f"Temperature range:         {temperature_range}",
        f"Satellites used range:     {satellite_range}",
        f"HDOP range:                {hdop_range}",
        f"Failed units (maximum):    {summary['maximum_failed_unit_count']}",
        f"Final deep test:           {deep_test}",
        f"Throttling anomalies:      {summary['power']['nonzero_throttling_samples']}",
        "Source transitions:",
    ]
    lines.extend(
        f"  {transition['timestamp']} -> {transition['source']}"
        for transition in summary["tracking"]["source_transitions"]
    )
    lines.append("Anomalies:")
    if summary["anomalies"]:
        lines.extend(f"  - {anomaly}" for anomaly in summary["anomalies"])
    elif summary["completed"]:
        lines.append("  none")
    else:
        lines.append("  observation is still in progress")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path, help="observation directory or samples.tsv")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero unless a completed observation passes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = analyze_observation(args.observation)
    except (OSError, ValueError) as exc:
        print(f"PPSPi observation analysis error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_human(summary))
    return 1 if args.strict and summary["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
