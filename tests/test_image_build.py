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
    def test_pi_gen_pin_is_official_trixie_arm64_revision(self) -> None:
        pin = (PROJECT_ROOT / "pi-gen" / "PI_GEN_COMMIT").read_text(
            encoding="utf-8"
        )
        self.assertEqual(pin.strip(), "ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5")

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

    def test_rtc_runtime_dependencies_are_in_both_install_paths(self) -> None:
        install_script = (PROJECT_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        image_packages = (
            PROJECT_ROOT / "pi-gen" / "stage-pps-pi" / "00-packages" / "00-packages"
        ).read_text(encoding="utf-8")
        image_validator = (PROJECT_ROOT / "scripts" / "validate-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("util-linux-extra", install_script)
        self.assertIn("util-linux-extra", image_packages.split())
        self.assertIn("/usr/sbin/hwclock", image_validator)
        self.assertIn("/etc/modules-load.d/ppstime.conf", image_validator)

    def test_image_removes_only_missing_cloud_init_module(self) -> None:
        stage_script = (
            PROJECT_ROOT / "pi-gen" / "stage-pps-pi" / "01-install" / "00-run.sh"
        ).read_text(encoding="utf-8")
        image_validator = (PROJECT_ROOT / "scripts" / "validate-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("import cloudinit.config.cc_netplan_nm_patch", stage_script)
        self.assertIn("netplan_nm_patch", image_validator)

    def test_active_profile_is_non_secret_and_world_readable(self) -> None:
        configure_script = (PROJECT_ROOT / "scripts" / "configure-profile.py").read_text(
            encoding="utf-8"
        )
        config_tool = (PROJECT_ROOT / "files" / "ppstime" / "ppstime-config").read_text(
            encoding="utf-8"
        )
        image_validator = (PROJECT_ROOT / "scripts" / "validate-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("(config_to_env(config), 0o644)", configure_script)
        self.assertIn("mode=0o644", config_tool)
        self.assertIn("/etc/ppstime/ppstime.env", image_validator)

    def test_image_requires_gpsd_coarse_clock_socket(self) -> None:
        image_validator = (PROJECT_ROOT / "scripts" / "validate-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "refclock SOCK /run/chrony.clk.serial0.sock refid GPS",
            image_validator,
        )
        self.assertIn("allow 127.0.0.1/32", image_validator)
        self.assertIn("allow ::1/128", image_validator)

    def test_selector_ignores_intermediate_lite_image(self) -> None:
        selector = load_selector()
        with tempfile.TemporaryDirectory() as temporary:
            deploy_dir = Path(temporary)
            final_image = deploy_dir / (
                "image_2026-07-18-ppspi-0.1.0-dev-raspios-trixie-arm64.img.xz"
            )
            lite_image = deploy_dir / (
                "image_2026-07-18-ppspi-0.1.0-dev-raspios-trixie-arm64-lite.img.xz"
            )
            final_image.touch()
            lite_image.touch()
            selected = selector.select_image(
                deploy_dir, "ppspi-0.1.0-dev-raspios-trixie-arm64"
            )
        self.assertEqual(selected, final_image.resolve())

    def test_selector_rejects_multiple_final_images(self) -> None:
        selector = load_selector()
        with tempfile.TemporaryDirectory() as temporary:
            deploy_dir = Path(temporary)
            for date in ("2026-07-18", "2026-07-19"):
                (deploy_dir / f"image_{date}-ppspi-0.1.0-dev-raspios-trixie-arm64.img.xz").touch()
            with self.assertRaisesRegex(ValueError, "found 2"):
                selector.select_image(deploy_dir, "ppspi-0.1.0-dev-raspios-trixie-arm64")

    def test_workflow_installs_pi_gen_host_emulation(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-image.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("binfmt-support qemu-user-binfmt", workflow)
        self.assertNotIn("binfmt-support qemu-user-static", workflow)
        self.assertIn(
            "docker/setup-qemu-action@96fe6ef7f33517b61c61be40b68a1882f3264fb8",
            workflow,
        )
        self.assertIn(
            "image: docker.io/tonistiigi/binfmt@sha256:"
            "400a4873b838d1b89194d982c45e5fb3cda4593fbfd7e08a02e76b03b21166f0",
            workflow,
        )
        self.assertIn("platforms: arm64", workflow)
        self.assertIn("reset: true", workflow)
        self.assertIn("/proc/sys/fs/binfmt_misc/qemu-aarch64", workflow)
        self.assertIn("grep --extended-regexp '^flags:.*F'", workflow)

    def test_build_targets_trixie_with_native_cloud_init(self) -> None:
        build_script = (PROJECT_ROOT / "scripts" / "build-image.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("RELEASE='trixie'", build_script)
        self.assertIn("ENABLE_CLOUD_INIT=1", build_script)
        self.assertNotIn("RELEASE='bookworm'", build_script)

    def test_workflow_names_trixie_artifacts(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-image.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Raspberry Pi OS Trixie arm64", workflow)
        self.assertIn("ppspi-${{ inputs.version }}-trixie-arm64", workflow)
        self.assertNotIn("bookworm-arm64", workflow)

    def test_workflow_validates_built_image_before_upload(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-image.yml").read_text(
            encoding="utf-8"
        )
        validation = "./scripts/validate-image.sh artifacts/*.img.xz"
        manifest = "scripts/generate-imager-manifest.py"
        self.assertIn(validation, workflow)
        self.assertIn(manifest, workflow)
        self.assertLess(workflow.index(validation), workflow.index(manifest))
        self.assertLess(workflow.index(manifest), workflow.index("Upload test image"))

    def test_release_workflow_generates_versioned_imager_manifest(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("binfmt-support qemu-user-binfmt", workflow)
        self.assertIn(
            "docker/setup-qemu-action@96fe6ef7f33517b61c61be40b68a1882f3264fb8",
            workflow,
        )
        self.assertIn("/proc/sys/fs/binfmt_misc/qemu-aarch64", workflow)
        self.assertIn("releases/download/${TAG_NAME}/ppspi-${VERSION}", workflow)
        self.assertIn('--image-url "${image_url}"', workflow)


if __name__ == "__main__":
    unittest.main()