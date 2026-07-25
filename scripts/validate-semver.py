#!/usr/bin/env python3
"""Validate one PPSPi version using the runtime's strict SemVer rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import semantic_version_is_valid  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    args = parser.parse_args()
    if not semantic_version_is_valid(args.version):
        parser.error(f"invalid semantic version: {args.version!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
