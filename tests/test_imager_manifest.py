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
GENERATOR = PROJECT_ROOT / "scripts" / "generate-imager-manifest.py"
VERSION = "0.1.0"
IMAGE_NAME = f"ppspi-{VERSION}-raspios-trixie-arm64.img.xz"


class ImagerManifestTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, bytes]:
        raw_image = b"PPSPi synthetic disk image\n" * 128
        image = root / IMAGE_NAME
        image.write_bytes(lzma.compress(raw_image, format=lzma.FORMAT_XZ))
        build_info = root / "build-info.json"
        build_info.write_text(
            json.dumps(
                {
                    "project_version": VERSION,
                    "git_commit": "a" * 40,
                    "build_date_utc": "2026-07-19T12:34:56Z",
                    "pi_gen_commit": "b" * 40,
                    "raspberry_pi_os_release": "trixie",
                    "architecture": "arm64",
                    "default_profile": "uputronics-gps-rtc-hat",
                }
            ),
            encoding="utf-8",
        )
        return image, build_info, raw_image

    def generate(
        self, image: Path, build_info: Path, output: Path, image_url: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(GENERATOR),
            "--image",
            str(image),
            "--build-info",
            str(build_info),
            "--output",
            str(output),
        ]
        if image_url is not None:
            command.extend(["--image-url", image_url])
        return subprocess.run(command, capture_output=True, check=False, text=True)

    def test_local_manifest_matches_imager_2_schema_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, raw_image = self.make_fixture(root)
            output = root / "ppspi-local.rpi-imager-manifest"
            process = self.generate(image, build_info, output)
            self.assertEqual(process.returncode, 0, process.stderr)

            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(set(manifest), {"imager", "os_list"})
            self.assertEqual(len(manifest["os_list"]), 1)
            entry = manifest["os_list"][0]
            required = {
                "name",
                "description",
                "icon",
                "url",
                "extract_size",
                "extract_sha256",
                "image_download_size",
                "image_download_sha256",
                "release_date",
                "init_format",
                "devices",
                "architecture",
                "capabilities",
            }
            self.assertTrue(required.issubset(entry))
            self.assertEqual(entry["url"], image.resolve().as_uri())
            self.assertEqual(entry["image_download_size"], image.stat().st_size)
            self.assertEqual(
                entry["image_download_sha256"], hashlib.sha256(image.read_bytes()).hexdigest()
            )
            self.assertEqual(entry["extract_size"], len(raw_image))
            self.assertEqual(entry["extract_sha256"], hashlib.sha256(raw_image).hexdigest())
            self.assertEqual(entry["release_date"], "2026-07-19")
            self.assertEqual(entry["init_format"], "cloudinit-rpi")
            self.assertEqual(entry["devices"], ["pi4-64bit"])
            self.assertEqual(entry["architecture"], "armv8")
            self.assertEqual(entry["capabilities"], [])

            device = manifest["imager"]["devices"][0]
            self.assertEqual(device["name"], "Raspberry Pi 4 Model B")
            self.assertEqual(device["tags"], ["pi4-64bit"])
            self.assertEqual(device["architecture"], "armv8")
            self.assertEqual(device["capabilities"], [])

            serialized = output.read_text(encoding="utf-8").lower()
            for forbidden in ("password", "passwd", "authorized_keys", "private_key", "wifi"):
                self.assertNotIn(forbidden, serialized)

    def test_release_manifest_uses_explicit_https_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, _ = self.make_fixture(root)
            output = root / "release.rpi-imager-manifest"
            image_url = (
                "https://github.com/Bazsy/PPSPi/releases/download/v0.1.0/"
                "ppspi-0.1.0-raspios-trixie-arm64.img.xz"
            )
            process = self.generate(image, build_info, output, image_url)
            self.assertEqual(process.returncode, 0, process.stderr)
            entry = json.loads(output.read_text(encoding="utf-8"))["os_list"][0]
            self.assertEqual(entry["url"], image_url)

    def test_rejects_unsafe_image_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, _ = self.make_fixture(root)
            process = self.generate(
                image, build_info, root / "bad.rpi-imager-manifest", "javascript:alert(1)"
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("absolute file, HTTP, or HTTPS URL", process.stderr)

    def test_rejects_image_url_for_different_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, _ = self.make_fixture(root)
            process = self.generate(
                image,
                build_info,
                root / "bad.rpi-imager-manifest",
                "https://example.invalid/ppspi-wrong.img.xz",
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("URL filename must match build metadata", process.stderr)

    def test_rejects_corrupt_xz_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, _ = self.make_fixture(root)
            image.write_bytes(b"not an xz stream")
            process = self.generate(image, build_info, root / "bad.rpi-imager-manifest")
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("cannot decompress image", process.stderr)

    def test_rejects_non_trixie_build_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, build_info, _ = self.make_fixture(root)
            metadata = json.loads(build_info.read_text(encoding="utf-8"))
            metadata["raspberry_pi_os_release"] = "bookworm"
            build_info.write_text(json.dumps(metadata), encoding="utf-8")
            process = self.generate(image, build_info, root / "bad.rpi-imager-manifest")
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("must identify Raspberry Pi OS Trixie", process.stderr)


if __name__ == "__main__":
    unittest.main()
