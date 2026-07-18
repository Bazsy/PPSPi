from __future__ import annotations

import hashlib
import json
import lzma
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_build_info_and_release_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "source.img.xz"
            raw_image = b"PPSPi synthetic image fixture\n" * 32
            image.write_bytes(lzma.compress(raw_image, format=lzma.FORMAT_XZ))
            build_info = root / "build-info.json"
            metadata_process = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "build-info.py"),
                    "--output",
                    str(build_info),
                    "--project-version",
                    "0.1.0",
                    "--git-commit",
                    "a" * 40,
                    "--build-date-utc",
                    "2026-07-18T12:00:00Z",
                    "--pi-gen-commit",
                    "b" * 40,
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(metadata_process.returncode, 0, metadata_process.stderr)
            output = root / "artifacts"
            package_process = subprocess.run(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts" / "package-release.sh"),
                    "--image",
                    str(image),
                    "--build-info",
                    str(build_info),
                    "--version",
                    "v0.1.0",
                    "--output-dir",
                    str(output),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(package_process.returncode, 0, package_process.stderr)
            artifact = output / "ppspi-0.1.0-raspios-bookworm-arm64.img.xz"
            checksum = artifact.with_suffix(artifact.suffix + ".sha256")
            self.assertTrue(artifact.exists())
            self.assertTrue(checksum.exists())
            expected_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.assertEqual(checksum.read_text(encoding="utf-8").split()[0], expected_hash)
            metadata = json.loads((output / "build-info.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["project_version"], "0.1.0")
            self.assertEqual(metadata["architecture"], "arm64")
            self.assertEqual(metadata["default_profile"], "uputronics-gps-rtc-hat")


if __name__ == "__main__":
    unittest.main()