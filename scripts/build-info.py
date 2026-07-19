#!/usr/bin/env python3
"""Generate canonical PPSPi build metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-version", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--build-date-utc", required=True)
    parser.add_argument("--pi-gen-commit", required=True)
    parser.add_argument("--os-release", default="trixie")
    parser.add_argument("--architecture", default="arm64")
    parser.add_argument("--default-profile", default="uputronics-gps-rtc-hat")
    args = parser.parse_args()
    payload = {
        "project_version": args.project_version,
        "git_commit": args.git_commit,
        "build_date_utc": args.build_date_utc,
        "pi_gen_commit": args.pi_gen_commit,
        "raspberry_pi_os_release": args.os_release,
        "architecture": args.architecture,
        "default_profile": args.default_profile,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())