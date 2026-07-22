from __future__ import annotations

import importlib.machinery
import io
import json
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PROJECT_ROOT / "files" / "ppstime"
BACKUP_COMMAND = CORE_PATH / "ppstime-backup"
sys.path.insert(0, str(CORE_PATH))

from ppstime_core import config_to_env, load_config, parse_env_file


def load_backup_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ppstime_backup", str(BACKUP_COMMAND))
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


class BackupTests(unittest.TestCase):
    model = "Raspberry Pi 4 Model B Rev 1.5"

    def write_config(self, path: Path, **changes: str) -> dict[str, str]:
        config = load_config(PROJECT_ROOT, environ={})
        config.update(changes)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config_to_env(config), encoding="utf-8")
        return config

    def write_build_info(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "project_version": "0.2.0-dev",
                    "git_commit": "1" * 40,
                    "raspberry_pi_os_release": "trixie",
                    "architecture": "arm64",
                    "default_profile": "uputronics-gps-rtc-hat",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def export_archive(
        self,
        root: Path,
        *,
        name: str = "backup.tar.gz",
        changes: dict[str, str] | None = None,
    ) -> tuple[Path, dict[str, str]]:
        config_path = root / f"{name}.env"
        config = self.write_config(config_path, **(changes or {}))
        build_info = root / f"{name}.build-info.json"
        self.write_build_info(build_info)
        archive = root / name
        process = subprocess.run(
            [
                sys.executable,
                str(BACKUP_COMMAND),
                "export",
                "--config",
                str(config_path),
                "--build-info",
                str(build_info),
                "--model",
                self.model,
                "--output",
                str(archive),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return archive, config

    def install_alternate_root(self, root: Path) -> None:
        boot = root / "boot" / "firmware"
        boot.mkdir(parents=True)
        (boot / "config.txt").write_text("# original\ndtparam=audio=on\n", encoding="utf-8")
        (boot / "cmdline.txt").write_text(
            "console=tty1 root=PARTUUID=test rw\n", encoding="utf-8"
        )
        process = subprocess.run(
            [
                "bash",
                str(PROJECT_ROOT / "scripts" / "install.sh"),
                "--root",
                str(root),
                "--skip-packages",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    def restore_command(
        self,
        archive: Path,
        root: Path,
        action: str,
        *,
        configure_command: Path | None = None,
    ) -> list[str]:
        return [
            sys.executable,
            str(BACKUP_COMMAND),
            "restore",
            str(archive),
            "--root",
            str(root),
            "--source-root",
            str(PROJECT_ROOT),
            "--configure-command",
            str(configure_command or PROJECT_ROOT / "scripts" / "configure-profile.py"),
            "--model",
            self.model,
            action,
        ]

    def test_export_archive_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, config = self.export_archive(root)
            self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
            with tarfile.open(archive, "r:gz") as handle:
                members = {member.name: member for member in handle.getmembers()}
            self.assertEqual(set(members), {"manifest.json", "ppstime.env"})
            self.assertEqual(members["manifest.json"].mode, 0o644)
            self.assertEqual(members["ppstime.env"].mode, 0o600)
            self.assertTrue(all(member.isfile() for member in members.values()))

            process = subprocess.run(
                [sys.executable, str(BACKUP_COMMAND), "inspect", str(archive), "--json"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            manifest = json.loads(process.stdout)
            self.assertEqual(manifest["profile"], config["PPSTIME_PROFILE"])
            self.assertEqual(manifest["hardware_model"], self.model)
            self.assertEqual(manifest["project_version"], "0.2.0-dev")
            self.assertEqual(manifest["git_commit"], "1" * 40)
            self.assertEqual(len(manifest["config_sha256"]), 64)

    def test_archive_rejects_tampering_extra_members_and_boolean_schema(self) -> None:
        module = load_backup_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self.export_archive(root)
            with tarfile.open(archive, "r:gz") as source:
                manifest = source.extractfile("manifest.json").read()
                config = source.extractfile("ppstime.env").read()

            tampered = root / "tampered.tar.gz"
            with tarfile.open(tampered, "w:gz") as target:
                for name, content in (
                    ("manifest.json", manifest),
                    ("ppstime.env", config + b"# changed\n"),
                ):
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    target.addfile(info, fileobj=__import__("io").BytesIO(content))
            with self.assertRaisesRegex(module.BackupError, "SHA-256"):
                module.read_archive(tampered)

            extra = root / "extra.tar.gz"
            with tarfile.open(extra, "w:gz") as target:
                for name, content in (
                    ("manifest.json", manifest),
                    ("ppstime.env", config),
                    ("unexpected", b"nope"),
                ):
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    target.addfile(info, fileobj=__import__("io").BytesIO(content))
            with self.assertRaisesRegex(module.BackupError, "exactly"):
                module.read_archive(extra)

            manifest_payload = json.loads(manifest)
            manifest_payload["schema_version"] = True
            with self.assertRaisesRegex(module.BackupError, "schema version"):
                module.validate_manifest(manifest_payload)

    def test_pre_host_and_maintenance_backup_migrates_to_current_defaults(self) -> None:
        module = load_backup_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, current_config = self.export_archive(root)
            with tarfile.open(archive, "r:gz") as source:
                manifest = json.loads(source.extractfile("manifest.json").read())
                config_text = source.extractfile("ppstime.env").read().decode("utf-8")
            legacy_lines = [
                line
                for line in config_text.splitlines()
                if not line.startswith(("HOST_", "OS_"))
            ]
            legacy_config = ("\n".join(legacy_lines) + "\n").encode("utf-8")
            manifest["config_sha256"] = module.sha256_bytes(legacy_config)
            manifest_content = (
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            migrated_archive = root / "pre-host-thresholds.tar.gz"
            with tarfile.open(migrated_archive, "w:gz") as target:
                for name, content in (
                    ("manifest.json", manifest_content),
                    ("ppstime.env", legacy_config),
                ):
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    target.addfile(info, io.BytesIO(content))
            _, _, migrated = module.read_archive(migrated_archive)
            self.assertEqual(migrated, current_config)

    def test_restore_dry_run_apply_and_rollback_archive(self) -> None:
        module = load_backup_module()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "rootfs"
            self.install_alternate_root(root)
            active_path = root / "etc" / "ppstime" / "ppstime.env"
            initial_config = parse_env_file(active_path)
            archive, desired_config = self.export_archive(
                workspace,
                changes={
                    "NTP_ALLOW": "10.50.0.0/16",
                    "DEFAULT_HOSTNAME": "recovered-ppspi",
                },
            )

            dry_run = subprocess.run(
                self.restore_command(archive, root, "--dry-run"),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertIn("Dry run complete; no files were changed", dry_run.stdout)
            self.assertEqual(parse_env_file(active_path), initial_config)

            restore = subprocess.run(
                self.restore_command(archive, root, "--yes"),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(restore.returncode, 0, restore.stderr)
            self.assertEqual(parse_env_file(active_path), desired_config)
            chrony = (root / "etc" / "chrony" / "conf.d" / "ppstime.conf").read_text(
                encoding="utf-8"
            )
            self.assertIn("allow 10.50.0.0/16", chrony)
            boot = (root / "boot" / "firmware" / "config.txt").read_text(encoding="utf-8")
            self.assertEqual(boot.count("# BEGIN PPSPi managed configuration"), 1)

            rollback_archives = sorted(
                (root / "var" / "backups" / "ppstime").glob("*.tar.gz")
            )
            self.assertEqual(len(rollback_archives), 1)
            self.assertEqual(stat.S_IMODE(rollback_archives[0].stat().st_mode), 0o600)
            _, _, rollback_config = module.read_archive(rollback_archives[0])
            self.assertEqual(rollback_config, initial_config)

            rollback = subprocess.run(
                self.restore_command(rollback_archives[0], root, "--yes"),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(rollback.returncode, 0, rollback.stderr)
            self.assertEqual(parse_env_file(active_path), initial_config)
            self.assertEqual(
                len(list((root / "var" / "backups" / "ppstime").glob("*.tar.gz"))),
                2,
            )

    def test_restore_rejects_incompatible_model_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "rootfs"
            self.install_alternate_root(root)
            active_path = root / "etc" / "ppstime" / "ppstime.env"
            initial = active_path.read_bytes()
            archive, _ = self.export_archive(workspace)
            command = self.restore_command(archive, root, "--dry-run")
            model_index = command.index("--model") + 1
            command[model_index] = "Raspberry Pi 5 Model B Rev 1.0"
            process = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("incompatible", process.stderr)
            self.assertEqual(active_path.read_bytes(), initial)

    def test_failed_restore_reinstates_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "rootfs"
            self.install_alternate_root(root)
            active_path = root / "etc" / "ppstime" / "ppstime.env"
            chrony_path = root / "etc" / "chrony" / "conf.d" / "ppstime.conf"
            policy_path = (
                root / "etc" / "apt" / "apt.conf.d" / "52ppstime-unattended-upgrades"
            )
            timer_path = root / "etc" / "systemd" / "system" / "ppstime-maintenance.timer"
            before = {
                path: path.read_bytes()
                for path in (active_path, chrony_path, policy_path, timer_path)
            }
            boot = root / "boot" / "firmware"
            existing_backup = boot / "config.txt.ppstime-existing.bak"
            existing_backup.write_text("preserve me\n", encoding="utf-8")
            archive, _ = self.export_archive(
                workspace, changes={"DEFAULT_HOSTNAME": "should-not-remain"}
            )
            failing = workspace / "failing-configure"
            failing.write_text(
                "#!/bin/sh\n"
                f"printf 'corrupted\\n' > {str(active_path)!r}\n"
                f"printf 'corrupted\\n' > {str(chrony_path)!r}\n"
                f"printf 'corrupted\\n' > {str(policy_path)!r}\n"
                f"printf 'corrupted\\n' > {str(timer_path)!r}\n"
                f"printf 'new backup\\n' > {str(boot / 'config.txt.ppstime-new.bak')!r}\n"
                "exit 1\n",
                encoding="utf-8",
            )
            failing.chmod(0o700)
            process = subprocess.run(
                self.restore_command(
                    archive,
                    root,
                    "--yes",
                    configure_command=failing,
                ),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("managed files were rolled back", process.stderr)
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            self.assertEqual(existing_backup.read_text(encoding="utf-8"), "preserve me\n")
            self.assertFalse((boot / "config.txt.ppstime-new.bak").exists())

    def test_invalid_successful_restore_reinstates_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = workspace / "rootfs"
            self.install_alternate_root(root)
            active_path = root / "etc" / "ppstime" / "ppstime.env"
            before = active_path.read_bytes()
            archive, _ = self.export_archive(workspace)
            invalid = workspace / "invalid-configure"
            invalid.write_text(
                "#!/bin/sh\n"
                f"printf 'invalid\\n' > {str(active_path)!r}\n"
                "exit 0\n",
                encoding="utf-8",
            )
            invalid.chmod(0o700)
            process = subprocess.run(
                self.restore_command(
                    archive,
                    root,
                    "--yes",
                    configure_command=invalid,
                ),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("configuration is invalid", process.stderr)
            self.assertEqual(active_path.read_bytes(), before)

    def test_export_refuses_overwrite_and_missing_model(self) -> None:
        module = load_backup_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, _ = self.export_archive(root)
            config_path = root / "backup.tar.gz.env"
            build_info = root / "backup.tar.gz.build-info.json"
            with self.assertRaisesRegex(module.BackupError, "overwrite"):
                module.create_archive(
                    archive,
                    config_path=config_path,
                    build_info_path=build_info,
                    model=self.model,
                )
            with self.assertRaisesRegex(module.BackupError, "cannot read"):
                module.read_hardware_model(None, root / "missing-model")


if __name__ == "__main__":
    unittest.main()
