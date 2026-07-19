#!/usr/bin/env python3
"""Generate Raspberry Pi Imager 2.x metadata for a PPSPi image."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
CHUNK_SIZE = 1024 * 1024
OS_ICON = "https://downloads.raspberrypi.com/raspios_armhf/Raspberry_Pi_OS_(32-bit).png"
DEVICE_ICON = "https://downloads.raspberrypi.com/imager/icons/RPi_4.png"


def die(message: str) -> None:
    raise SystemExit(f"PPSPi Imager manifest error: {message}")


def load_build_info(path: Path) -> tuple[str, str]:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        die(f"cannot read build metadata: {error}")

    required = {
        "project_version",
        "build_date_utc",
        "raspberry_pi_os_release",
        "architecture",
    }
    missing = sorted(required - metadata.keys())
    if missing:
        die("missing build metadata: " + ", ".join(missing))

    version = metadata["project_version"]
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        die("build metadata project_version is not valid semantic versioning")
    if metadata["raspberry_pi_os_release"] != "trixie":
        die("build metadata must identify Raspberry Pi OS Trixie")
    if metadata["architecture"] != "arm64":
        die("build metadata must identify arm64")

    build_date = metadata["build_date_utc"]
    if not isinstance(build_date, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", build_date
    ):
        die("build_date_utc must use YYYY-MM-DDTHH:MM:SSZ")
    return version, build_date[:10]


def inspect_image(path: Path) -> tuple[int, str, int, str]:
    compressed_hash = hashlib.sha256()
    try:
        with path.open("rb") as compressed:
            while chunk := compressed.read(CHUNK_SIZE):
                compressed_hash.update(chunk)
    except OSError as error:
        die(f"cannot read image: {error}")

    extracted_hash = hashlib.sha256()
    extracted_size = 0
    try:
        with lzma.open(path, "rb") as image:
            while chunk := image.read(CHUNK_SIZE):
                extracted_hash.update(chunk)
                extracted_size += len(chunk)
    except (OSError, lzma.LZMAError) as error:
        die(f"cannot decompress image: {error}")

    if extracted_size == 0:
        die("decompressed image is empty")
    return (
        path.stat().st_size,
        compressed_hash.hexdigest(),
        extracted_size,
        extracted_hash.hexdigest(),
    )


def validate_image_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    if parsed.scheme == "file" and parsed.path:
        return value
    die("image URL must be an absolute file, HTTP, or HTTPS URL")


def build_manifest(
    *,
    version: str,
    release_date: str,
    image_url: str,
    download_size: int,
    download_sha256: str,
    extract_size: int,
    extract_sha256: str,
) -> dict[str, object]:
    os_name = f"PPSPi {version} (Raspberry Pi OS Trixie, 64-bit)"
    return {
        "imager": {
            "default_os": os_name,
            "devices": [
                {
                    "name": "Raspberry Pi 4 Model B",
                    "description": "The supported PPSPi target",
                    "icon": DEVICE_ICON,
                    "tags": ["pi4-64bit"],
                    "matching_type": "inclusive",
                    "architecture": "armv8",
                    "capabilities": [],
                }
            ],
        },
        "os_list": [
            {
                "name": os_name,
                "description": "GPS/PPS-synchronised Stratum-1 NTP appliance",
                "icon": OS_ICON,
                "url": image_url,
                "extract_size": extract_size,
                "extract_sha256": extract_sha256,
                "image_download_size": download_size,
                "image_download_sha256": download_sha256,
                "release_date": release_date,
                "init_format": "cloudinit-rpi",
                "devices": ["pi4-64bit"],
                "architecture": "armv8",
                "capabilities": [],
                "website": "https://github.com/Bazsy/PPSPi",
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="PPSPi .img.xz file")
    parser.add_argument(
        "--build-info", type=Path, required=True, help="Matching PPSPi build-info.json"
    )
    parser.add_argument(
        "--image-url",
        help="Image URL stored in the manifest (default: absolute file URI for --image)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path (default: beside the image with .rpi-imager-manifest suffix)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image = args.image.resolve()
    if not image.is_file():
        die(f"image not found: {args.image}")
    if not image.name.endswith(".img.xz"):
        die("image must use the .img.xz format")
    if not args.build_info.is_file():
        die(f"build metadata not found: {args.build_info}")

    version, release_date = load_build_info(args.build_info)
    expected_name = f"ppspi-{version}-raspios-trixie-arm64.img.xz"
    if image.name != expected_name:
        die(f"image filename must match build metadata: {expected_name}")

    image_url = validate_image_url(args.image_url or image.as_uri())
    if Path(urlparse(image_url).path).name != expected_name:
        die(f"image URL filename must match build metadata: {expected_name}")
    download_size, download_sha256, extract_size, extract_sha256 = inspect_image(image)
    manifest = build_manifest(
        version=version,
        release_date=release_date,
        image_url=image_url,
        download_size=download_size,
        download_sha256=download_sha256,
        extract_size=extract_size,
        extract_sha256=extract_sha256,
    )

    output = args.output
    if output is None:
        output = image.with_name(image.name.removesuffix(".img.xz") + ".rpi-imager-manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
    ) as temporary:
        temporary.write(json.dumps(manifest, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, output)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
