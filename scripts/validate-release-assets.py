#!/usr/bin/env python3
"""Validate the exact four PPSPi assets before attaching them to a release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHUNK_SIZE = 1024 * 1024


class ValidationError(ValueError):
    """Raised when release assets do not satisfy the publication contract."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path.name} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise ValidationError(f"cannot read {path.name}: {exc}") from exc
    return digest.hexdigest()


def expected_asset_names(version: str) -> tuple[str, str, str, str]:
    image = f"ppspi-{version}-raspios-trixie-arm64.img.xz"
    return (
        image,
        f"{image}.sha256",
        "build-info.json",
        f"ppspi-{version}-raspios-trixie-arm64.rpi-imager-manifest",
    )


def validate_release_assets(
    directory: Path,
    *,
    version: str,
    tag: str,
    repository: str,
    expected_commit: str,
) -> dict[str, Any]:
    """Validate names, checksums, metadata, and Imager release URL."""

    if not SEMVER_RE.fullmatch(version):
        raise ValidationError(f"version is not semantic versioning: {version}")
    if tag != f"v{version}":
        raise ValidationError(f"tag {tag} does not match version {version}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValidationError(f"invalid repository name: {repository}")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValidationError("expected commit must be a lowercase 40-character SHA-1")
    if not directory.is_dir():
        raise ValidationError(f"asset directory not found: {directory}")

    expected_names = expected_asset_names(version)
    actual_names = sorted(path.name for path in directory.iterdir() if path.is_file())
    if actual_names != sorted(expected_names):
        raise ValidationError(
            "release asset set mismatch: expected "
            + ", ".join(sorted(expected_names))
            + "; found "
            + ", ".join(actual_names)
        )

    image_name, checksum_name, build_info_name, manifest_name = expected_names
    image_path = directory / image_name
    image_size = image_path.stat().st_size
    if image_size <= 0:
        raise ValidationError("release image is empty")
    image_sha256 = sha256_file(image_path)

    checksum_fields = (directory / checksum_name).read_text(encoding="utf-8").split()
    if len(checksum_fields) != 2:
        raise ValidationError("checksum file must contain one SHA-256 and filename")
    checksum_sha256, checksum_filename = checksum_fields
    if not SHA256_RE.fullmatch(checksum_sha256):
        raise ValidationError("checksum file does not contain a lowercase SHA-256")
    if checksum_filename.lstrip("*") != image_name:
        raise ValidationError("checksum filename does not match release image")
    if checksum_sha256 != image_sha256:
        raise ValidationError("checksum does not match release image")

    build_info = load_json(directory / build_info_name)
    required_build_info = {
        "project_version": version,
        "git_commit": expected_commit,
        "raspberry_pi_os_release": "trixie",
        "architecture": "arm64",
        "default_profile": "uputronics-gps-rtc-hat",
    }
    for key, expected_value in required_build_info.items():
        if build_info.get(key) != expected_value:
            raise ValidationError(
                f"build-info {key} is {build_info.get(key)!r}, expected {expected_value!r}"
            )

    manifest = load_json(directory / manifest_name)
    os_list = manifest.get("os_list")
    if not isinstance(os_list, list) or len(os_list) != 1 or not isinstance(os_list[0], dict):
        raise ValidationError("manifest must contain exactly one OS entry")
    entry = os_list[0]
    expected_url = (
        f"https://github.com/{repository}/releases/download/{tag}/{image_name}"
    )
    expected_manifest = {
        "url": expected_url,
        "image_download_size": image_size,
        "image_download_sha256": image_sha256,
        "init_format": "cloudinit-rpi",
        "devices": ["pi4-64bit"],
        "architecture": "armv8",
        "website": f"https://github.com/{repository}",
    }
    for key, expected_value in expected_manifest.items():
        if entry.get(key) != expected_value:
            raise ValidationError(
                f"manifest {key} is {entry.get(key)!r}, expected {expected_value!r}"
            )
    extract_sha256 = entry.get("extract_sha256")
    extract_size = entry.get("extract_size")
    if not isinstance(extract_sha256, str) or not SHA256_RE.fullmatch(extract_sha256):
        raise ValidationError("manifest extract_sha256 is missing or invalid")
    if not isinstance(extract_size, int) or extract_size <= 0:
        raise ValidationError("manifest extract_size is missing or invalid")

    return {
        "version": version,
        "tag": tag,
        "repository": repository,
        "git_commit": expected_commit,
        "image": image_name,
        "image_size": image_size,
        "image_sha256": image_sha256,
        "extract_size": extract_size,
        "extract_sha256": extract_sha256,
        "assets": list(expected_names),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate_release_assets(
            args.directory,
            version=args.version,
            tag=args.tag,
            repository=args.repository,
            expected_commit=args.expected_commit,
        )
    except (OSError, ValidationError) as exc:
        print(f"PPSPi release asset validation error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "PPSPi release assets validated: "
            f"{result['tag']} {result['image_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
