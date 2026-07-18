#!/usr/bin/env python3
"""Select exactly one final PPSPi image from a pi-gen deploy directory."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SAFE_IMAGE_NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")


def select_image(deploy_dir: Path, image_name: str) -> Path:
    """Return the exact final image and reject missing or ambiguous output."""

    if not SAFE_IMAGE_NAME.fullmatch(image_name):
        raise ValueError(f"unsafe image name: {image_name!r}")
    if not deploy_dir.is_dir():
        raise ValueError(f"deploy directory does not exist: {deploy_dir}")

    expected_pattern = f"image_*-{image_name}.img.xz"
    candidates = sorted(path for path in deploy_dir.glob(expected_pattern) if path.is_file())
    if len(candidates) != 1:
        available = sorted(path.name for path in deploy_dir.glob("*.img.xz") if path.is_file())
        available_text = ", ".join(available) if available else "none"
        raise ValueError(
            f"expected exactly one {expected_pattern!r}; found {len(candidates)}; "
            f"available images: {available_text}"
        )
    return candidates[0].resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-dir", type=Path, required=True)
    parser.add_argument("--image-name", required=True)
    args = parser.parse_args()
    try:
        print(select_image(args.deploy_dir, args.image_name))
    except ValueError as exc:
        print(f"PPSPi image selection error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())