#!/usr/bin/env python3
"""Build and minisign a deterministic PPSPi application-only update."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_update import (  # noqa: E402
    canonical_json,
    compatibility_series,
    parse_version,
    source_payload_files,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_archive(source_root: Path, archive: Path) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    with (
        archive.open("xb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT
        ) as handle,
    ):
        for source, destination, mode in source_payload_files(source_root):
            data = source.read_bytes()
            info = tarfile.TarInfo(destination)
            info.size = len(data)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            handle.addfile(info, io.BytesIO(data))
            payload.append(
                {
                    "path": destination,
                    "size": len(data),
                    "sha256": sha256_bytes(data),
                    "mode": mode,
                }
            )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", default="Bazsy/PPSPi")
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--secret-key", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--minisign", default="minisign")
    args = parser.parse_args()
    try:
        parse_version(args.version)
        if not args.secret_key.is_file():
            raise ValueError("minisign secret key file does not exist")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        archive = args.output_dir / f"ppspi-{args.version}-application.tar.gz"
        archive.unlink(missing_ok=True)
        payload = build_archive(args.source_root.resolve(), archive)
        manifest = {
            "schema_version": 1,
            "project": "PPSPi",
            "repository": args.repository,
            "version": args.version,
            "git_commit": args.git_commit,
            "compatibility_series": compatibility_series(args.version),
            "platform": {"architecture": "arm64", "os_release": "trixie"},
            "archive": {
                "filename": archive.name,
                "size": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            },
            "payload": payload,
        }
        manifest_path = archive.with_name(f"{archive.name}.manifest.json")
        manifest_path.write_bytes(canonical_json(manifest))
        signature = manifest_path.with_name(f"{manifest_path.name}.minisig")
        signature.unlink(missing_ok=True)
        result = subprocess.run(
            [
                args.minisign,
                "-HSm",
                str(manifest_path),
                "-s",
                str(args.secret_key),
                "-x",
                str(signature),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not signature.is_file():
            raise ValueError("minisign failed to create the application manifest signature")
        for path in (archive, manifest_path, signature):
            print(path)
        return 0
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"PPSPi application package error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
