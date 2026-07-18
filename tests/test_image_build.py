from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_selector() -> ModuleType:
    selector_path = PROJECT_ROOT / "scripts" / "select-image.py"
    spec = importlib.util.spec_from_file_location("select_image", selector_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {selector_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImageBuildTests(unittest.TestCase):
    def test_pi_gen_docker_config_uses_c_option(self) -> None:
        build_script = (PROJECT_ROOT / "scripts" / "build-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("./build-docker.sh -c config-ppspi", build_script)
        self.assertNotIn("./build-docker.sh config-ppspi", build_script)

    def test_pi_gen_skips_intermediate_stage2_image(self) -> None:
        build_script = (PROJECT_ROOT / "scripts" / "build-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('touch "${checkout_dir}/stage2/SKIP_IMAGES"', build_script)

    def test_selector_ignores_intermediate_lite_image(self) -> None:
        selector = load_selector()
        with tempfile.TemporaryDirectory() as temporary:
            deploy_dir = Path(temporary)
            final_image = deploy_dir / (
                "image_2026-07-18-ppspi-0.1.0-dev-raspios-bookworm-arm64.img.xz"
            )
            lite_image = deploy_dir / (
                "image_2026-07-18-ppspi-0.1.0-dev-raspios-bookworm-arm64-lite.img.xz"
            )
            final_image.touch()
            lite_image.touch()
            selected = selector.select_image(
                deploy_dir, "ppspi-0.1.0-dev-raspios-bookworm-arm64"
            )
        self.assertEqual(selected, final_image.resolve())

    def test_selector_rejects_multiple_final_images(self) -> None:
        selector = load_selector()
        with tempfile.TemporaryDirectory() as temporary:
            deploy_dir = Path(temporary)
            for date in ("2026-07-18", "2026-07-19"):
                (deploy_dir / f"image_{date}-ppspi-0.1.0-dev-raspios-bookworm-arm64.img.xz").touch()
            with self.assertRaisesRegex(ValueError, "found 2"):
                selector.select_image(deploy_dir, "ppspi-0.1.0-dev-raspios-bookworm-arm64")

    def test_workflow_installs_pi_gen_host_emulation(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-image.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("binfmt-support qemu-user-static", workflow)


if __name__ == "__main__":
    unittest.main()