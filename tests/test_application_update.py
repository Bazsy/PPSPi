from __future__ import annotations

import fcntl
import hashlib
import importlib.machinery
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = PROJECT_ROOT / "files" / "ppstime"
UPDATE_COMMAND = CORE_ROOT / "ppstime-update"
sys.path.insert(0, str(CORE_ROOT))

from ppstime_update import (
    MAX_ARCHIVE_BYTES,
    MAX_MEMBERS,
    MAX_TRANSACTION_FILES,
    UpdateError,
    atomic_json,
    bounded_local_copy,
    canonical_json,
    compatibility_series,
    fetch,
    load_manifest_bytes,
    load_transaction,
    parse_version,
    signing_key_id,
    source_payload_files,
    validate_archive,
    verify_signature,
    version_is_downgrade,
)

LEGACY_0_2_3_ALLOWED_EXACT = frozenset(
    {
        "usr/lib/ppstime/configure-profile.py",
        "usr/lib/ppstime/ppstime_core.py",
        "usr/lib/ppstime/ppstime_update.py",
        "usr/share/ppstime/config/default.env",
        "usr/share/ppstime/application-update.pub",
        "usr/share/ppstime/dashboard/index.html",
        "usr/share/ppstime/dashboard/dashboard.css",
        "usr/share/ppstime/dashboard/dashboard.js",
        "usr/share/ppstime/dashboard/ppspi.svg",
        "etc/systemd/system/gpsd.service.d/ppstime.conf",
        "etc/systemd/system/chrony.service.d/ppstime.conf",
        "etc/udev/rules.d/80-ppstime.rules",
        "etc/modules-load.d/ppstime.conf",
    }
)


def accepted_by_legacy_0_2_3_updater(value: str) -> bool:
    """Mirror the immutable v0.2.3 payload boundary used on deployed images."""

    return bool(
        value in LEGACY_0_2_3_ALLOWED_EXACT
        or re.fullmatch(r"usr/lib/ppstime/ppstime-[a-z0-9-]+", value)
        or re.fullmatch(
            r"usr/share/ppstime/config/profiles/[a-z0-9][a-z0-9-]*\.env",
            value,
        )
        or re.fullmatch(
            r"etc/systemd/system/ppstime-[a-z0-9-]+\.(?:service|timer)",
            value,
        )
    )


def load_command() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ppstime_update_command", str(UPDATE_COMMAND))
    module = ModuleType(loader.name)
    loader.exec_module(module)
    return module


def manifest_for(
    version: str, archive: Path, entries: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": "PPSPi",
        "repository": "Bazsy/PPSPi",
        "version": version,
        "git_commit": "1" * 40,
        "compatibility_series": compatibility_series(version),
        "platform": {"architecture": "arm64", "os_release": "trixie"},
        "archive": {
            "filename": f"ppspi-{version}-application.tar.gz",
            "size": archive.stat().st_size,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        },
        "payload": entries,
    }


def write_archive(path: Path, members: list[tuple[str, bytes, int, str]]) -> None:
    with tarfile.open(path, "w:gz", format=tarfile.USTAR_FORMAT) as handle:
        for name, data, mode, kind in members:
            info = tarfile.TarInfo(name)
            info.mode = mode
            if kind == "file":
                info.size = len(data)
                handle.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/shadow"
                handle.addfile(info)


class ApplicationUpdateTests(unittest.TestCase):
    def test_current_payload_is_accepted_by_immutable_v023_updater(self) -> None:
        paths = [
            destination
            for _, destination, _ in source_payload_files(PROJECT_ROOT)
        ]
        rejected = sorted(
            path for path in paths if not accepted_by_legacy_0_2_3_updater(path)
        )
        self.assertEqual(rejected, [])
        self.assertIn(
            "etc/systemd/system/ppstime-dashboard-lock.service",
            paths,
        )
        self.assertLess(
            "ppstime-dashboard-lock.service",
            "ppstime-dashboard.service",
        )
        self.assertNotIn("usr/lib/tmpfiles.d/ppstime.conf", paths)

    def test_compatibility_series_and_downgrade_rules(self) -> None:
        self.assertEqual(compatibility_series("0.2.3"), "0.2")
        self.assertEqual(compatibility_series("1.7.4"), "1")
        self.assertTrue(version_is_downgrade("0.2.2", "0.2.1"))
        self.assertTrue(version_is_downgrade("1.0.0", "1.0.0-rc.1"))
        self.assertFalse(version_is_downgrade("0.2.0-rc.1", "0.2.0"))
        self.assertEqual(parse_version("1.2.3-rc.1+build.7")[:3], (1, 2, 3))
        for invalid in ("1.2.3-01", "1.2.3-alpha.01"):
            with self.subTest(invalid=invalid), self.assertRaises(UpdateError):
                parse_version(invalid)

    def test_manifest_requires_canonical_closed_schema_and_safe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "ppspi-0.2.1-application.tar.gz"
            archive.write_bytes(b"archive")
            entry = {
                "path": "usr/lib/ppstime/ppstime-status",
                "size": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
                "mode": 0o755,
            }
            manifest = manifest_for("0.2.1", archive, [entry])
            parsed = load_manifest_bytes(canonical_json(manifest), expected_version="0.2.1")
            self.assertEqual(parsed["version"], "0.2.1")
            with self.assertRaisesRegex(UpdateError, "repository"):
                load_manifest_bytes(
                    canonical_json(manifest),
                    expected_repository="Other/Repository",
                )
            with self.assertRaisesRegex(UpdateError, "Git commit"):
                load_manifest_bytes(canonical_json({**manifest, "git_commit": "bad"}))
            with self.assertRaisesRegex(UpdateError, "canonical"):
                load_manifest_bytes(json.dumps(manifest, indent=2).encode("ascii"))
            with self.assertRaisesRegex(UpdateError, "schema"):
                load_manifest_bytes(canonical_json({**manifest, "extra": True}))
            forbidden = dict(entry, path="etc/ppstime/ppstime.env")
            with self.assertRaisesRegex(UpdateError, "forbidden"):
                load_manifest_bytes(canonical_json(manifest_for("0.2.1", archive, [forbidden])))
            traversal = dict(entry, path="usr/lib/ppstime/../../etc/shadow")
            with self.assertRaisesRegex(UpdateError, "unsafe"):
                load_manifest_bytes(canonical_json(manifest_for("0.2.1", archive, [traversal])))

    def test_archive_is_extracted_member_by_member_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "ppspi-0.2.1-application.tar.gz"
            data = b"#!/bin/sh\nexit 0\n"
            name = "usr/lib/ppstime/ppstime-status"
            write_archive(archive, [(name, data, 0o755, "file")])
            entry = {
                "path": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "mode": 0o755,
            }
            manifest = manifest_for("0.2.1", archive, [entry])
            staging = root / "staging"
            validate_archive(archive, manifest, staging)
            self.assertEqual((staging / name).read_bytes(), data)
            self.assertEqual(stat.S_IMODE((staging / name).stat().st_mode), 0o755)

    def test_archive_rejects_links_and_unmanifested_members(self) -> None:
        for kind, expected in (("symlink", "plain regular"), ("file", "count")):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "ppspi-0.2.1-application.tar.gz"
                name = "usr/lib/ppstime/ppstime-status"
                members = [(name, b"x", 0o755, kind)]
                if kind == "file":
                    members.append(("usr/lib/ppstime/unlisted", b"y", 0o755, "file"))
                write_archive(archive, members)
                entry = {
                    "path": name,
                    "size": 1,
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                    "mode": 0o755,
                }
                with self.assertRaisesRegex(UpdateError, expected):
                    validate_archive(
                        archive,
                        manifest_for("0.2.1", archive, [entry]),
                        root / "staging",
                    )

    def test_archive_rejects_hardlinks_fifos_pax_duplicates_and_truncation(self) -> None:
        name = "usr/lib/ppstime/ppstime-status"
        data = b"x"
        entry = {
            "path": name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mode": 0o755,
        }
        for kind in ("hardlink", "fifo", "pax", "duplicate", "truncated"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "ppspi-0.2.1-application.tar.gz"
                archive_format = (
                    tarfile.PAX_FORMAT if kind == "pax" else tarfile.USTAR_FORMAT
                )
                with tarfile.open(archive, "w:gz", format=archive_format) as handle:
                    info = tarfile.TarInfo(name)
                    info.mode = 0o755
                    if kind == "hardlink":
                        info.type = tarfile.LNKTYPE
                        info.linkname = name
                        handle.addfile(info)
                    elif kind == "fifo":
                        info.type = tarfile.FIFOTYPE
                        handle.addfile(info)
                    else:
                        info.size = len(data)
                        if kind == "pax":
                            info.pax_headers = {"comment": "not allowed"}
                        handle.addfile(info, io.BytesIO(data))
                        if kind == "duplicate":
                            duplicate = tarfile.TarInfo(name)
                            duplicate.mode = 0o755
                            duplicate.size = len(data)
                            handle.addfile(duplicate, io.BytesIO(data))
                if kind == "truncated":
                    archive.write_bytes(archive.read_bytes()[:-16])
                with self.assertRaises(UpdateError):
                    validate_archive(
                        archive,
                        manifest_for("0.2.1", archive, [entry]),
                        root / "staging",
                    )

    def test_unconfigured_public_key_fails_closed_without_invoking_minisign(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest"
            signature = root / "signature"
            key = root / "key"
            manifest.write_text("{}", encoding="ascii")
            signature.write_text("signature", encoding="ascii")
            key.write_text("UNCONFIGURED: placeholder\n", encoding="ascii")
            with patch("ppstime_update.subprocess.run") as run, self.assertRaisesRegex(
                UpdateError, "not configured"
            ):
                verify_signature(manifest, signature, key)
            run.assert_not_called()

    @unittest.skipUnless(shutil.which("minisign"), "minisign is not installed")
    def test_real_minisign_prehashed_signature_verifies(self) -> None:
        minisign = shutil.which("minisign")
        self.assertIsNotNone(minisign)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = root / "test-only.sec"
            public = root / "test-only.pub"
            manifest = root / "manifest.json"
            signature = root / "manifest.json.minisig"
            manifest.write_bytes(b'{"fixture":true}\n')
            generate = subprocess.run(
                [str(minisign), "-G", "-W", "-s", str(secret), "-p", str(public)],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(generate.returncode, 0, generate.stderr)
            sign = subprocess.run(
                [
                    str(minisign),
                    "-HSm",
                    str(manifest),
                    "-s",
                    str(secret),
                    "-x",
                    str(signature),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(sign.returncode, 0, sign.stderr)
            verify_signature(manifest, signature, public, minisign=str(minisign))

    def args(self, root: Path, version: str = "0.2.1") -> Namespace:
        return Namespace(
            version=version,
            root=root,
            origin=Path("/var/lib/ppstime/install-origin.json"),
            state_file=Path("/var/lib/ppstime/application-update-state.json"),
            transactions_dir=Path("/var/lib/ppstime/application-updates"),
            allow_non_root=True,
            adopt_source_install=False,
            allow_breaking=False,
            yes=True,
            archive=None,
            manifest=None,
            signature=None,
            repository="Bazsy/PPSPi",
            public_key=PROJECT_ROOT / "files" / "application-update.pub",
            minisign="minisign",
            installation_file=Path(
                "/var/lib/ppstime/application-installation.json"
            ),
        )

    def transaction(
        self,
        state: str,
        relative: str,
        snapshot_data: bytes,
    ) -> dict[str, object]:
        return {
            "schema_version": 2,
            "id": "20260725T000000Z-deadbeef-0.2.1",
            "state": state,
            "from_version": "0.2.0",
            "from_commit": None,
            "from_adopted": False,
            "to_version": "0.2.1",
            "to_commit": "1" * 40,
            "created_utc": "2026-07-25T00:00:00Z",
            "files": [
                {
                    "path": relative,
                    "existed": True,
                    "mode": 0o755,
                    "size": len(snapshot_data),
                    "sha256": hashlib.sha256(snapshot_data).hexdigest(),
                }
            ],
            "previous_identity": None,
            "unit_states": {},
        }

    def test_apply_snapshots_files_and_local_rollback_restores_them(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin_path = root / "var/lib/ppstime/install-origin.json"
            origin_path.parent.mkdir(parents=True)
            origin_path.write_text(
                '{"adopted":false,"git_commit":null,"origin":"image","schema_version":1,'
                '"version":"0.2.0"}\n',
                encoding="ascii",
            )
            relative = "usr/lib/ppstime/ppstime-status"
            destination = root / relative
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"old")
            os.chmod(destination, 0o755)
            staging = root / "prepared"
            (staging / relative).parent.mkdir(parents=True)
            (staging / relative).write_bytes(b"new")
            manifest = {
                "version": "0.2.1",
                "git_commit": "1" * 40,
                "compatibility_series": "0.2",
                "payload": [
                    {
                        "path": relative,
                        "size": 3,
                        "sha256": hashlib.sha256(b"new").hexdigest(),
                        "mode": 0o755,
                    }
                ],
            }
            args = self.args(root)
            with (
                patch.object(
                    module,
                    "prepare",
                    return_value=(manifest, root / "archive", staging),
                ),
                patch.object(module, "service_validation"),
                patch.object(module, "candidate_configuration_validation"),
                patch.object(module, "regenerate_configuration"),
                patch.object(module, "activate"),
            ):
                self.assertEqual(module.apply_update(args), 0)
            self.assertEqual(destination.read_bytes(), b"new")
            state = json.loads(
                (root / "var/lib/ppstime/application-update-state.json").read_text(
                    encoding="ascii"
                )
            )
            self.assertEqual(state["installed_version"], "0.2.1")
            self.assertEqual(state["installed_commit"], "1" * 40)
            with patch.object(module, "activate"):
                self.assertEqual(module.rollback(args), 0)
            self.assertEqual(destination.read_bytes(), b"old")
            origin = json.loads(origin_path.read_text(encoding="ascii"))
            self.assertEqual(origin["version"], "0.2.0")

    def test_failed_apply_restores_snapshot(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin_path = root / "var/lib/ppstime/install-origin.json"
            origin_path.parent.mkdir(parents=True)
            origin_path.write_text(
                '{"adopted":false,"git_commit":null,"origin":"image","schema_version":1,'
                '"version":"0.2.0"}\n',
                encoding="ascii",
            )
            relative = "usr/lib/ppstime/ppstime-status"
            destination = root / relative
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"old")
            staging = root / "prepared"
            (staging / relative).parent.mkdir(parents=True)
            (staging / relative).write_bytes(b"new")
            manifest = {
                "version": "0.2.1",
                "git_commit": "1" * 40,
                "compatibility_series": "0.2",
                "payload": [
                    {
                        "path": relative,
                        "size": 3,
                        "sha256": hashlib.sha256(b"new").hexdigest(),
                        "mode": 0o755,
                    }
                ],
            }
            with (
                patch.object(
                    module,
                    "prepare",
                    return_value=(manifest, root / "archive", staging),
                ),
                patch.object(module, "service_validation"),
                patch.object(module, "candidate_configuration_validation"),
                patch.object(module, "regenerate_configuration"),
                patch.object(
                    module,
                    "activate",
                    side_effect=(UpdateError("health failed"), None),
                ),
                self.assertRaisesRegex(UpdateError, "health"),
            ):
                module.apply_update(self.args(root))
            self.assertEqual(destination.read_bytes(), b"old")
            transaction_path = next(
                (root / "var/lib/ppstime/application-updates").glob(
                    "*/transaction.json"
                )
            )
            transaction = json.loads(transaction_path.read_text(encoding="ascii"))
            self.assertEqual(transaction["state"], "ROLLED_BACK")

    def test_post_activation_persistence_failure_rolls_back_before_reactivation(
        self,
    ) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin_path = root / "var/lib/ppstime/install-origin.json"
            origin_path.parent.mkdir(parents=True)
            origin_path.write_text(
                '{"adopted":false,"git_commit":null,"origin":"image",'
                '"schema_version":1,"version":"0.2.0"}\n',
                encoding="ascii",
            )
            relative = "usr/lib/ppstime/ppstime-dashboard"
            destination = root / relative
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"old dashboard")
            os.chmod(destination, 0o755)
            staging = root / "prepared"
            staged = staging / relative
            staged.parent.mkdir(parents=True)
            staged.write_bytes(b"new dashboard")
            archive = root / "ppspi-0.2.1-application.tar.gz"
            archive.write_bytes(b"archive")
            manifest = manifest_for(
                "0.2.1",
                archive,
                [
                    {
                        "path": relative,
                        "size": len(b"new dashboard"),
                        "sha256": hashlib.sha256(b"new dashboard").hexdigest(),
                        "mode": 0o755,
                    }
                ],
            )
            args = self.args(root)
            installation = root / args.installation_file.as_posix().lstrip("/")
            real_atomic_json = module.atomic_json
            events: list[str] = []

            def persist(path: Path, value: dict[str, object]) -> None:
                if path == installation and not path.exists():
                    events.append("persistence_failed")
                    raise OSError("injected installation identity failure")
                real_atomic_json(path, value)

            def restore(
                restore_root: Path,
                states: dict[str, dict[str, object]],
            ) -> None:
                del states
                self.assertEqual(restore_root, root)
                self.assertEqual(destination.read_bytes(), b"old dashboard")
                events.append("unit_states_restored")

            def activate(_root: Path, *, validate_health: bool = True) -> None:
                events.append("activate_forward" if validate_health else "activate_rollback")

            with (
                patch.object(module, "prepare", return_value=(manifest, archive, staging)),
                patch.object(module, "service_validation"),
                patch.object(module, "candidate_configuration_validation"),
                patch.object(module, "regenerate_configuration"),
                patch.object(module, "atomic_json", side_effect=persist),
                patch.object(module, "restore_unit_states", side_effect=restore),
                patch.object(module, "activate", side_effect=activate),
                self.assertRaisesRegex(OSError, "injected installation"),
            ):
                module.apply_update(args)
            self.assertEqual(destination.read_bytes(), b"old dashboard")
            self.assertFalse(installation.exists())
            self.assertEqual(
                events,
                [
                    "activate_forward",
                    "persistence_failed",
                    "unit_states_restored",
                    "activate_rollback",
                ],
            )
            transaction_path = next(
                (root / "var/lib/ppstime/application-updates").glob(
                    "*/transaction.json"
                )
            )
            transaction = json.loads(transaction_path.read_text(encoding="ascii"))
            self.assertEqual(transaction["state"], "ROLLED_BACK")

    def test_activation_reports_failed_health_checks(self) -> None:
        module = load_command()
        results = (
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess(
                [],
                1,
                json.dumps(
                    {
                        "checks": [
                            {
                                "name": "chrony_synchronized",
                                "status": "FAIL",
                                "essential": True,
                            },
                            {
                                "name": "gps_fix",
                                "status": "WARN",
                                "essential": False,
                            },
                        ]
                    }
                ),
                "",
            ),
        )
        with (
            patch.object(module, "run_command", side_effect=results),
            self.assertRaisesRegex(UpdateError, "chrony_synchronized"),
        ):
            module.activate(Path("/"))

    def test_activation_restarts_dashboard_with_regenerated_configuration(self) -> None:
        module = load_command()
        results = (
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        )
        with patch.object(module, "run_command", side_effect=results) as run:
            module.activate(Path("/"), validate_health=False)
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                "systemctl",
                "try-restart",
                "chrony.service",
                "gpsd.service",
                "ppstime-dashboard.service",
            ],
        )

    def test_dashboard_reconciliation_enables_and_starts_server(self) -> None:
        module = load_command()
        config = {
            "OS_UPDATES_ENABLED": "false",
            "APP_UPDATES_ENABLED": "false",
            "RTC_ENABLED": "true",
            "DASHBOARD_ENABLED": "true",
        }
        with (
            patch.object(module, "parse_env_file", return_value=config),
            patch.object(
                module,
                "run_command",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ) as run,
        ):
            module.reconcile_units(
                Path("/"),
                {
                    "ppstime-dashboard-lock.service",
                    "ppstime-dashboard.service",
                },
                set(),
                {},
            )
        commands = [call.args[0] for call in run.call_args_list]
        lock_index = commands.index(
            [
                "systemctl",
                "disable",
                "--now",
                "ppstime-dashboard-lock.service",
            ]
        )
        dashboard_index = commands.index(
            ["systemctl", "enable", "--now", "ppstime-dashboard.service"]
        )
        self.assertLess(lock_index, dashboard_index)

    def test_status_does_not_acquire_root_owned_maintenance_lock(self) -> None:
        module = load_command()
        args = Namespace(
            action="status",
            root=Path("/"),
            lock_file=Path("/run/lock/ppstime-maintenance.lock"),
            skip_lock=False,
        )
        with (
            patch.object(module, "parse_args", return_value=args),
            patch.object(module, "acquire_lock") as acquire,
            patch.object(module, "status", return_value=0),
        ):
            self.assertEqual(module.main(), 0)
        acquire.assert_not_called()

    def test_prepare_lock_action_does_not_reacquire_held_lock(self) -> None:
        module = load_command()
        args = Namespace(
            action="prepare-lock",
            root=Path("/"),
            lock_file=Path("/run/lock/ppstime-maintenance.lock"),
            skip_lock=False,
            allow_non_root=True,
        )
        with (
            patch.object(module, "parse_args", return_value=args),
            patch.object(module, "acquire_lock") as acquire,
            patch.object(module, "prepare_lock_file") as prepare,
        ):
            self.assertEqual(module.main(), 0)
        acquire.assert_not_called()
        prepare.assert_called_once_with(Path("/run/lock/ppstime-maintenance.lock"))

    def test_prepare_lock_preserves_inode_exclusive_lock_and_mode(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "run/lock/ppstime-maintenance.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("", encoding="ascii")
            os.chmod(lock_path, 0o644)
            inode = lock_path.stat().st_ino
            with lock_path.open("rb") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                module.prepare_lock_file(lock_path)
                self.assertEqual(lock_path.stat().st_ino, inode)
                self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o600)
                with lock_path.open("rb") as contender, self.assertRaises(
                    BlockingIOError
                ):
                    fcntl.flock(
                        contender.fileno(),
                        fcntl.LOCK_SH | fcntl.LOCK_NB,
                    )

    def test_prepare_lock_creates_file_and_rejects_symlink(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / "run/lock/ppstime-maintenance.lock"
            module.prepare_lock_file(lock_path)
            self.assertTrue(lock_path.is_file())
            self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o600)
            lock_path.unlink()
            lock_path.symlink_to(root / "attacker-controlled")
            with self.assertRaisesRegex(UpdateError, "cannot prepare"):
                module.prepare_lock_file(lock_path)

    def test_recovery_restores_prepared_and_applying_transactions(self) -> None:
        module = load_command()
        for state in ("PREPARED", "APPLYING"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = self.args(root)
                origin = root / "var/lib/ppstime/install-origin.json"
                origin.parent.mkdir(parents=True)
                origin.write_text(
                    '{"adopted":false,"git_commit":null,"origin":"image",'
                    '"schema_version":1,"version":"0.2.0"}\n',
                    encoding="ascii",
                )
                relative = "usr/lib/ppstime/ppstime-status"
                destination = root / relative
                destination.parent.mkdir(parents=True)
                destination.write_bytes(b"new")
                transaction_dir = (
                    root
                    / "var/lib/ppstime/application-updates"
                    / f"20260725-{state.lower()}"
                )
                snapshot = transaction_dir / "snapshot" / relative
                snapshot.parent.mkdir(parents=True)
                snapshot.write_bytes(b"old")
                atomic_json(
                    transaction_dir / "transaction.json",
                    self.transaction(state, relative, b"old"),
                )
                with patch.object(module, "activate"):
                    self.assertEqual(module.rollback(args, recovery=True), 0)
                self.assertEqual(destination.read_bytes(), b"old")
                recovered = load_transaction(transaction_dir / "transaction.json")
                self.assertEqual(recovered["state"], "RECOVERED")

    def test_recovery_fails_closed_for_missing_or_corrupt_snapshot(self) -> None:
        module = load_command()
        for snapshot_data in (None, b"corrupt"):
            with self.subTest(snapshot=snapshot_data), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = self.args(root)
                relative = "usr/lib/ppstime/ppstime-status"
                destination = root / relative
                destination.parent.mkdir(parents=True)
                destination.write_bytes(b"live")
                transaction_dir = root / "var/lib/ppstime/application-updates/interrupted"
                snapshot = transaction_dir / "snapshot" / relative
                snapshot.parent.mkdir(parents=True)
                if snapshot_data is not None:
                    snapshot.write_bytes(snapshot_data)
                atomic_json(
                    transaction_dir / "transaction.json",
                    self.transaction("APPLYING", relative, b"old"),
                )
                with self.assertRaisesRegex(UpdateError, "snapshot"):
                    module.rollback(args, recovery=True)
                self.assertEqual(destination.read_bytes(), b"live")

    def test_transaction_limit_is_separate_from_archive_member_limit(self) -> None:
        from ppstime_update import GENERATED_TRANSACTION_PATHS

        self.assertEqual(
            MAX_TRANSACTION_FILES,
            MAX_MEMBERS * 2 + len(GENERATED_TRANSACTION_PATHS),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transaction.json"
            value = {
                "schema_version": 1,
                "id": "transaction",
                "state": "PREPARED",
                "from_version": "0.2.0",
                "from_commit": None,
                "from_adopted": False,
                "to_version": "0.2.1",
                "to_commit": "1" * 40,
                "created_utc": "2026-07-25T00:00:00Z",
                "files": [
                    {
                        "path": f"usr/lib/ppstime/ppstime-tool-{index}",
                        "existed": False,
                        "mode": 0o755,
                    }
                    for index in range(MAX_MEMBERS + 1)
                ],
            }
            path.write_text(json.dumps(value), encoding="ascii")
            self.assertEqual(len(load_transaction(path)["files"]), MAX_MEMBERS + 1)

    def test_persisted_transaction_accepts_exact_external_timing_units(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transaction.json"
            value = self.transaction(
                "ROLLING_BACK",
                "usr/lib/ppstime/ppstime-status",
                b"old",
            )
            value["unit_states"] = {
                unit: {"existed": True, "enabled": "enabled", "active": True}
                for unit in ("chrony.service", "gpsd.service")
            }
            atomic_json(path, value)
            loaded = load_transaction(path)
            self.assertEqual(set(loaded["unit_states"]), {"chrony.service", "gpsd.service"})
            value["unit_states"]["ssh.service"] = {
                "existed": True,
                "enabled": "enabled",
                "active": True,
            }
            atomic_json(path, value)
            with self.assertRaisesRegex(UpdateError, "unit state"):
                load_transaction(path)

    def test_stale_managed_file_removal_and_rollback_preserve_unknowns(
        self,
    ) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.args(root)
            origin_path = root / "var/lib/ppstime/install-origin.json"
            origin_path.parent.mkdir(parents=True)
            origin_path.write_text(
                '{"adopted":false,"git_commit":"0000000000000000000000000000000000000000",'
                '"origin":"image","schema_version":1,"version":"0.2.0"}\n',
                encoding="ascii",
            )
            stale_relative = "usr/lib/ppstime/ppstime-old"
            new_relative = "usr/lib/ppstime/ppstime-new"
            unknown_relative = "usr/lib/ppstime/local-admin-file"
            for relative, data in (
                (stale_relative, b"old managed"),
                (unknown_relative, b"unknown"),
            ):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            key_id = signing_key_id(args.public_key)
            previous_identity = {
                "schema_version": 1,
                "repository": "Bazsy/PPSPi",
                "version": "0.2.0",
                "git_commit": "0" * 40,
                "manifest_sha256": "a" * 64,
                "archive_sha256": "b" * 64,
                "signing_key_id": key_id,
                "managed_paths": [stale_relative],
            }
            installation = root / args.installation_file.as_posix().lstrip("/")
            atomic_json(installation, previous_identity)
            archive = root / "ppspi-0.2.1-application.tar.gz"
            archive.write_bytes(b"archive")
            data = b"new managed"
            manifest = manifest_for(
                "0.2.1",
                archive,
                [
                    {
                        "path": new_relative,
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "mode": 0o755,
                    }
                ],
            )
            staging = root / "prepared"
            staged = staging / new_relative
            staged.parent.mkdir(parents=True)
            staged.write_bytes(data)
            with (
                patch.object(module, "prepare", return_value=(manifest, archive, staging)),
                patch.object(module, "service_validation"),
                patch.object(module, "candidate_configuration_validation"),
                patch.object(module, "regenerate_configuration"),
                patch.object(module, "activate"),
            ):
                self.assertEqual(module.apply_update(args), 0)
            self.assertFalse((root / stale_relative).exists())
            self.assertEqual((root / unknown_relative).read_bytes(), b"unknown")
            installed = json.loads(installation.read_text(encoding="ascii"))
            self.assertEqual(installed["managed_paths"], [new_relative])
            with patch.object(module, "activate"):
                self.assertEqual(module.rollback(args), 0)
            self.assertEqual((root / stale_relative).read_bytes(), b"old managed")
            self.assertFalse((root / new_relative).exists())
            self.assertEqual((root / unknown_relative).read_bytes(), b"unknown")
            self.assertEqual(
                json.loads(installation.read_text(encoding="ascii")), previous_identity
            )

    def test_candidate_systemd_validation_uses_staged_overlay(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            staging = Path(temporary) / "staging"
            staged_unit = staging / "etc/systemd/system/ppstime-new.service"
            staged_unit.parent.mkdir(parents=True)
            staged_unit.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
            payload = [{"path": "etc/systemd/system/ppstime-new.service"}]
            with patch.object(
                module, "run_command", return_value=subprocess.CompletedProcess([], 0, "", "")
            ) as run:
                module.service_validation(root, payload, staging)
            self.assertEqual(run.call_args.args[0][-1], "ppstime-new.service")
            unit_path = run.call_args.kwargs["extra_env"]["SYSTEMD_UNIT_PATH"]
            self.assertEqual(
                unit_path.split(":", 1)[0],
                str(staging / "etc/systemd/system"),
            )

    def test_atomic_json_fsyncs_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            with patch("ppstime_update.os.fsync", wraps=os.fsync) as fsync:
                atomic_json(path, {"ok": True})
            self.assertGreaterEqual(fsync.call_count, 2)

    def test_bounded_local_copy_rejects_oversize_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            with source.open("wb") as stream:
                stream.seek(MAX_ARCHIVE_BYTES)
                stream.write(b"x")
            destination = root / "destination"
            with self.assertRaisesRegex(UpdateError, "size"):
                bounded_local_copy(source, destination, MAX_ARCHIVE_BYTES)
            self.assertFalse(destination.exists())

    def test_invalid_repository_version_and_non_https_url_fail_before_network(self) -> None:
        module = load_command()
        with self.assertRaises(UpdateError):
            module.artifact_urls("invalid repository", "0.2.1")
        with self.assertRaises(UpdateError):
            module.artifact_urls("Bazsy/PPSPi", "0.2.1-01")
        with tempfile.TemporaryDirectory() as temporary, patch(
            "ppstime_update.urllib.request.build_opener"
        ) as build_opener, self.assertRaisesRegex(UpdateError, "HTTPS"):
            fetch("http://example.invalid/artifact", Path(temporary) / "artifact", 1)
        build_opener.assert_not_called()

    def test_same_version_without_full_installed_identity_fails_closed(self) -> None:
        module = load_command()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin = root / "var/lib/ppstime/install-origin.json"
            origin.parent.mkdir(parents=True)
            origin.write_text(
                '{"adopted":false,"git_commit":null,"origin":"image",'
                '"schema_version":1,"version":"0.2.1"}\n',
                encoding="ascii",
            )
            manifest = {
                "version": "0.2.1",
                "git_commit": "1" * 40,
                "compatibility_series": "0.2",
                "payload": [],
            }
            with patch.object(
                module,
                "prepare",
                return_value=(manifest, root / "archive", root / "staging"),
            ), self.assertRaisesRegex(UpdateError, "identity is unavailable"):
                module.apply_update(self.args(root, version="0.2.1"))

    def test_source_install_requires_explicit_adoption_and_cross_series_is_rejected(self) -> None:
        module = load_command()
        origin = {
            "schema_version": 1,
            "origin": "source",
            "version": "0.2.0",
            "git_commit": None,
            "adopted": False,
        }
        manifest = {"version": "0.2.1", "compatibility_series": "0.2", "payload": []}
        args = self.args(Path("/tmp"))
        with self.assertRaisesRegex(UpdateError, "adopt"):
            module.preflight(args, manifest, origin)
        args.adopt_source_install = True
        module.preflight(args, manifest, origin)
        with self.assertRaisesRegex(UpdateError, "compatibility"):
            module.preflight(
                args,
                {**manifest, "version": "0.3.0", "compatibility_series": "0.3"},
                origin,
            )

    def test_application_package_is_deterministic_and_contains_only_allowlisted_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_minisign = root / "minisign"
            fake_minisign.write_text(
                "#!/bin/sh\n"
                "while [ $# -gt 0 ]; do\n"
                "  [ \"$1\" = -x ] && { shift; printf signature > \"$1\"; exit 0; }\n"
                "  shift\n"
                "done\n"
                "exit 1\n",
                encoding="utf-8",
            )
            os.chmod(fake_minisign, 0o755)
            secret = root / "secret.key"
            secret.write_text("fixture", encoding="ascii")
            archives = []
            for output_name in ("one", "two"):
                output = root / output_name
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "scripts/package-application-update.py"),
                        "--version", "0.2.1",
                        "--git-commit", "1" * 40,
                        "--output-dir", str(output),
                        "--secret-key", str(secret),
                        "--minisign", str(fake_minisign),
                    ],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                archives.append(output / "ppspi-0.2.1-application.tar.gz")
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())
            manifest_path = archives[0].with_name(
                f"{archives[0].name}.manifest.json"
            )
            manifest = load_manifest_bytes(manifest_path.read_bytes())
            paths = {entry["path"] for entry in manifest["payload"]}
            self.assertIn("usr/lib/ppstime/ppstime-update", paths)
            self.assertNotIn("etc/ppstime/ppstime.env", paths)
            forbidden_prefixes = ("home/", "etc/ssh/", "etc/NetworkManager/", "boot/")
            self.assertFalse(
                any(path.startswith(forbidden_prefixes) for path in paths)
            )


if __name__ == "__main__":
    unittest.main()
