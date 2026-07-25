#!/usr/bin/env python3
"""Verified, transactional PPSPi application update primitives."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ppstime_core import semantic_version_is_valid

SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 256 * 1024
MAX_SIGNATURE_BYTES = 16 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 256
MAX_REDIRECTS = 5
MAX_TAR_BYTES = MAX_PAYLOAD_BYTES + MAX_MEMBERS * 1024 + 1024
CHUNK_SIZE = 1024 * 1024
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_EXACT = frozenset(
    {
        "usr/lib/ppstime/configure-profile.py",
        "usr/lib/ppstime/ppstime_core.py",
        "usr/lib/ppstime/ppstime_update.py",
        "usr/share/ppstime/config/default.env",
        "usr/share/ppstime/application-update.pub",
        "etc/systemd/system/gpsd.service.d/ppstime.conf",
        "etc/systemd/system/chrony.service.d/ppstime.conf",
        "etc/udev/rules.d/80-ppstime.rules",
        "etc/modules-load.d/ppstime.conf",
    }
)
MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "project",
        "repository",
        "version",
        "git_commit",
        "compatibility_series",
        "platform",
        "archive",
        "payload",
    }
)
PLATFORM_KEYS = frozenset({"architecture", "os_release"})
ARCHIVE_KEYS = frozenset({"filename", "size", "sha256"})
ENTRY_KEYS = frozenset({"path", "size", "sha256", "mode"})
ORIGIN_KEYS = frozenset(
    {"schema_version", "origin", "version", "git_commit", "adopted"}
)
STATUS_KEYS = frozenset(
    {"schema_version", "installed_version", "install_origin", "last_action", "transaction"}
)
TRANSACTION_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "state",
        "from_version",
        "from_commit",
        "from_adopted",
        "to_version",
        "to_commit",
        "created_utc",
        "files",
    }
)
TRANSACTION_KEYS_V2 = TRANSACTION_KEYS | frozenset({"previous_identity", "unit_states"})
TRANSACTION_FILE_KEYS = frozenset({"path", "existed", "mode"})
TRANSACTION_FILE_KEYS_V2 = frozenset(
    {"path", "existed", "mode", "size", "sha256"}
)
GENERATED_TRANSACTION_PATHS = frozenset(
    {
        "etc/ppstime/ppstime.env",
        "etc/chrony/conf.d/ppstime.conf",
        "etc/default/gpsd",
        "etc/apt/apt.conf.d/52ppstime-unattended-upgrades",
        "etc/systemd/system/ppstime-maintenance.timer",
        "boot/firmware/config.txt",
        "boot/firmware/cmdline.txt",
        "boot/config.txt",
        "boot/cmdline.txt",
    }
)
MAX_TRANSACTION_FILES = MAX_MEMBERS * 2 + len(GENERATED_TRANSACTION_PATHS)
INSTALLATION_KEYS = frozenset(
    {
        "schema_version",
        "repository",
        "version",
        "git_commit",
        "manifest_sha256",
        "archive_sha256",
        "signing_key_id",
        "managed_paths",
    }
)
UNIT_STATE_KEYS = frozenset({"existed", "enabled", "active"})
EXTERNAL_MANAGED_UNITS = frozenset({"chrony.service", "gpsd.service"})


class UpdateError(ValueError):
    """Raised when an application update cannot proceed safely."""


def canonical_json(value: Any) -> bytes:
    content = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return f"{content}\n".encode("ascii")


def now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path: Path) -> None:
    """Persist directory-entry changes made below *path*."""

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_unlink(path: Path, *, missing_ok: bool = False) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        if not missing_ok:
            raise
        return
    fsync_directory(path.parent)


def durable_replace(source: Path, destination: Path) -> None:
    os.replace(source, destination)
    fsync_directory(destination.parent)


def durable_copy(source: Path, destination: Path, mode: int) -> None:
    """Copy one regular file and durably publish it at *destination*."""

    source_stat = source.stat()
    if not stat.S_ISREG(source_stat.st_mode):
        raise UpdateError(f"snapshot source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, output, CHUNK_SIZE)
            os.fchmod(output.fileno(), mode)
            output.flush()
            os.fsync(output.fileno())
        durable_replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def durable_tree(root: Path) -> None:
    """Fsync a completed file tree bottom-up before publishing metadata for it."""

    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        fsync_directory(directory)
    fsync_directory(root)
    fsync_directory(root.parent)


def parse_version(value: str) -> tuple[int, int, int, tuple[str, ...]]:
    match = SEMVER_RE.fullmatch(value)
    if match is None or not semantic_version_is_valid(value):
        raise UpdateError(f"invalid semantic version: {value!r}")
    prerelease = tuple((match.group(4) or "").split(".")) if match.group(4) else ()
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease


def compatibility_series(version: str) -> str:
    major, minor, _, _ = parse_version(version)
    return f"{major}.{minor}" if major == 0 else str(major)


def version_is_downgrade(current: str, target: str) -> bool:
    current_parts = parse_version(current)
    target_parts = parse_version(target)
    current_core, target_core = current_parts[:3], target_parts[:3]
    if target_core != current_core:
        return target_core < current_core
    current_pre, target_pre = current_parts[3], target_parts[3]
    if not current_pre:
        return bool(target_pre)
    if not target_pre:
        return False
    for current_identifier, target_identifier in zip(
        current_pre, target_pre, strict=False
    ):
        if current_identifier == target_identifier:
            continue
        current_numeric = current_identifier.isdigit()
        target_numeric = target_identifier.isdigit()
        if current_numeric and target_numeric:
            return int(target_identifier) < int(current_identifier)
        if current_numeric != target_numeric:
            return target_numeric
        return target_identifier < current_identifier
    return len(target_pre) < len(current_pre)


def safe_payload_path(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise UpdateError("payload path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or "\\" in value:
        raise UpdateError(f"unsafe payload path: {value!r}")
    if value in {"etc/ppstime/ppstime.env", "etc/passwd", "etc/shadow"}:
        raise UpdateError(f"payload path is forbidden: {value}")
    allowed = (
        value in ALLOWED_EXACT
        or re.fullmatch(r"usr/lib/ppstime/ppstime-[a-z0-9-]+", value) is not None
        or re.fullmatch(r"usr/share/ppstime/config/profiles/[a-z0-9][a-z0-9-]*\.env", value)
        is not None
        or re.fullmatch(r"etc/systemd/system/ppstime-[a-z0-9-]+\.(?:service|timer)", value)
        is not None
    )
    if allowed:
        return value
    raise UpdateError(f"payload path is outside the PPSPi application boundary: {value}")


def safe_transaction_path(value: Any) -> str:
    if isinstance(value, str) and value in GENERATED_TRANSACTION_PATHS:
        return value
    return safe_payload_path(value)


def load_manifest_bytes(
    data: bytes,
    *,
    expected_version: str | None = None,
    expected_repository: str | None = None,
) -> dict[str, Any]:
    if not data or len(data) > MAX_MANIFEST_BYTES:
        raise UpdateError("manifest size is invalid")
    try:
        value = json.loads(data.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"manifest is invalid JSON: {exc}") from exc
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS:
        raise UpdateError("manifest schema is invalid")
    if canonical_json(value) != data:
        raise UpdateError("manifest is not canonical JSON")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise UpdateError("manifest schema version is unsupported")
    if value["project"] != "PPSPi":
        raise UpdateError("manifest project is invalid")
    repository = value["repository"]
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise UpdateError("manifest repository is invalid")
    if expected_repository is not None and repository != expected_repository:
        raise UpdateError("manifest repository does not match the configured repository")
    version = value["version"]
    if not isinstance(version, str):
        raise UpdateError("manifest version is invalid")
    parse_version(version)
    if expected_version is not None and version != expected_version:
        raise UpdateError("manifest version does not match the explicit requested version")
    if value["compatibility_series"] != compatibility_series(version):
        raise UpdateError("manifest compatibility series is invalid")
    if not isinstance(value["git_commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", value["git_commit"]
    ):
        raise UpdateError("manifest Git commit is invalid")
    platform = value["platform"]
    if not isinstance(platform, dict) or set(platform) != PLATFORM_KEYS:
        raise UpdateError("manifest platform schema is invalid")
    if platform != {"architecture": "arm64", "os_release": "trixie"}:
        raise UpdateError("manifest platform is unsupported")
    archive = value["archive"]
    expected_archive_name = f"ppspi-{version}-application.tar.gz"
    if not isinstance(archive, dict) or set(archive) != ARCHIVE_KEYS:
        raise UpdateError("manifest archive schema is invalid")
    if archive["filename"] != expected_archive_name:
        raise UpdateError("manifest archive filename is invalid")
    if type(archive["size"]) is not int or not 0 < archive["size"] <= MAX_ARCHIVE_BYTES:
        raise UpdateError("manifest archive size is invalid")
    if not isinstance(archive["sha256"], str) or not SHA256_RE.fullmatch(archive["sha256"]):
        raise UpdateError("manifest archive SHA-256 is invalid")
    payload = value["payload"]
    if not isinstance(payload, list) or not payload or len(payload) > MAX_MEMBERS:
        raise UpdateError("manifest payload count is invalid")
    seen: set[str] = set()
    total = 0
    for entry in payload:
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise UpdateError("manifest payload entry schema is invalid")
        entry_path = safe_payload_path(entry["path"])
        if entry_path in seen:
            raise UpdateError(f"duplicate manifest payload path: {entry_path}")
        seen.add(entry_path)
        if type(entry["size"]) is not int or not 0 <= entry["size"] <= MAX_PAYLOAD_BYTES:
            raise UpdateError(f"payload size is invalid for {entry_path}")
        total += entry["size"]
        if total > MAX_PAYLOAD_BYTES:
            raise UpdateError("manifest payload is too large")
        if not isinstance(entry["sha256"], str) or not SHA256_RE.fullmatch(entry["sha256"]):
            raise UpdateError(f"payload SHA-256 is invalid for {entry_path}")
        if type(entry["mode"]) is not int or entry["mode"] not in {0o644, 0o755}:
            raise UpdateError(f"payload mode is invalid for {entry_path}")
    if [entry["path"] for entry in payload] != sorted(seen):
        raise UpdateError("manifest payload paths are not sorted")
    return value


def verify_signature(
    manifest: Path,
    signature: Path,
    public_key: Path,
    *,
    minisign: str = "minisign",
) -> None:
    try:
        key_text = public_key.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise UpdateError(f"cannot read application update public key: {exc}") from exc
    if not key_text or key_text.startswith("UNCONFIGURED"):
        raise UpdateError("application update public key is not configured")
    if signature.stat().st_size > MAX_SIGNATURE_BYTES:
        raise UpdateError("manifest signature is too large")
    try:
        result = subprocess.run(
            [minisign, "-HVm", str(manifest), "-x", str(signature), "-p", str(public_key)],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"cannot verify manifest signature: {exc}") from exc
    if result.returncode != 0:
        raise UpdateError("manifest minisign verification failed")


def signing_key_id(public_key: Path) -> str:
    """Return the embedded minisign key ID as stable lowercase hexadecimal."""

    try:
        lines = [
            line.strip()
            for line in public_key.read_text(encoding="ascii").splitlines()
            if line.strip() and not line.startswith("untrusted comment:")
        ]
        decoded = base64.b64decode(lines[-1], validate=True)
    except (OSError, UnicodeError, IndexError, ValueError) as exc:
        raise UpdateError(f"cannot read application update public key ID: {exc}") from exc
    if len(decoded) != 42:
        raise UpdateError("application update public key has an invalid encoding")
    return decoded[2:10].hex()


def source_payload_files(source_root: Path) -> list[tuple[Path, str, int]]:
    """Return the complete deterministic PPSPi-owned application payload."""

    files: list[tuple[Path, str, int]] = []
    for source in sorted((source_root / "files" / "ppstime").iterdir()):
        if source.is_file():
            mode = (
                0o644
                if source.name in {"ppstime_core.py", "ppstime_update.py"}
                else 0o755
            )
            files.append((source, f"usr/lib/ppstime/{source.name}", mode))
    files.extend(
        [
            (
                source_root / "scripts" / "configure-profile.py",
                "usr/lib/ppstime/configure-profile.py",
                0o755,
            ),
            (
                source_root / "config" / "default.env",
                "usr/share/ppstime/config/default.env",
                0o644,
            ),
            (
                source_root / "files" / "application-update.pub",
                "usr/share/ppstime/application-update.pub",
                0o644,
            ),
        ]
    )
    for source in sorted((source_root / "config" / "profiles").glob("*.env")):
        files.append(
            (source, f"usr/share/ppstime/config/profiles/{source.name}", 0o644)
        )
    for source in sorted((source_root / "files" / "systemd").rglob("*")):
        if source.is_file():
            relative = source.relative_to(source_root / "files" / "systemd").as_posix()
            files.append((source, f"etc/systemd/system/{relative}", 0o644))
    for source in sorted((source_root / "files" / "udev").glob("*.rules")):
        files.append((source, f"etc/udev/rules.d/{source.name}", 0o644))
    for source in sorted((source_root / "files" / "modules-load.d").glob("*.conf")):
        files.append((source, f"etc/modules-load.d/{source.name}", 0o644))
    return sorted(files, key=lambda item: item[1])


def validate_archive(archive: Path, manifest: dict[str, Any], staging: Path) -> None:
    archive_info = manifest["archive"]
    if (
        archive.stat().st_size != archive_info["size"]
        or sha256_file(archive) != archive_info["sha256"]
    ):
        raise UpdateError("application archive identity does not match the signed manifest")
    try:
        expanded = 0
        with gzip.open(archive, "rb") as compressed:
            while chunk := compressed.read(CHUNK_SIZE):
                expanded += len(chunk)
                if expanded > MAX_TAR_BYTES:
                    raise UpdateError("expanded application archive is too large")
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise UpdateError(f"application archive gzip stream is invalid: {exc}") from exc
    expected = {entry["path"]: entry for entry in manifest["payload"]}
    staging.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    total = 0
    try:
        with tarfile.open(archive, mode="r|gz") as handle:
            member_count = 0
            for member in handle:
                member_count += 1
                if member_count > len(expected) or member_count > MAX_MEMBERS:
                    raise UpdateError("archive member count does not match the manifest")
                name = safe_payload_path(member.name)
                if name in seen or name not in expected:
                    raise UpdateError(f"unexpected or duplicate archive member: {name}")
                if not member.isfile() or member.pax_headers:
                    raise UpdateError(f"archive member must be a plain regular file: {name}")
                entry = expected[name]
                if member.size != entry["size"] or member.mode != entry["mode"]:
                    raise UpdateError(f"archive metadata does not match manifest: {name}")
                total += member.size
                if total > MAX_PAYLOAD_BYTES:
                    raise UpdateError("archive payload is too large")
                source = handle.extractfile(member)
                if source is None:
                    raise UpdateError(f"cannot read archive member: {name}")
                destination = staging / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                remaining = member.size
                with destination.open("xb") as output:
                    while remaining:
                        chunk = source.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            raise UpdateError(f"archive member is truncated: {name}")
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                    if source.read(1):
                        raise UpdateError(f"archive member exceeds declared size: {name}")
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != entry["sha256"]:
                    raise UpdateError(f"archive member SHA-256 mismatch: {name}")
                if name.endswith(".py") or destination.read_bytes().startswith(
                    b"#!/usr/bin/env python3"
                ):
                    try:
                        compile(destination.read_bytes(), name, "exec")
                    except (SyntaxError, ValueError) as exc:
                        raise UpdateError(
                            f"archive Python source is invalid: {name}: {exc}"
                        ) from exc
                os.chmod(destination, entry["mode"])
                seen.add(name)
            if member_count != len(expected):
                raise UpdateError("archive member count does not match the manifest")
    except (tarfile.TarError, OSError) as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"cannot parse application archive: {exc}") from exc
    if seen != set(expected):
        raise UpdateError("archive members do not match the manifest")


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(canonical_json(value).decode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        durable_replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_origin(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"cannot read install origin metadata: {exc}") from exc
    if not isinstance(value, dict) or set(value) != ORIGIN_KEYS:
        raise UpdateError("install origin metadata schema is invalid")
    if value["schema_version"] != 1 or value["origin"] not in {"image", "source"}:
        raise UpdateError("install origin metadata is invalid")
    if type(value["adopted"]) is not bool or not isinstance(value["version"], str):
        raise UpdateError("install origin metadata values are invalid")
    parse_version(value["version"])
    if value["git_commit"] is not None and (
        not isinstance(value["git_commit"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", value["git_commit"])
    ):
        raise UpdateError("install origin Git commit is invalid")
    return value


def validate_installation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != INSTALLATION_KEYS:
        raise UpdateError("installed application identity schema is invalid")
    if value["schema_version"] != 1:
        raise UpdateError("installed application identity version is invalid")
    repository = value["repository"]
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise UpdateError("installed application repository is invalid")
    if not isinstance(value["version"], str):
        raise UpdateError("installed application version is invalid")
    parse_version(value["version"])
    if not isinstance(value["git_commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", value["git_commit"]
    ):
        raise UpdateError("installed application Git commit is invalid")
    for key in ("manifest_sha256", "archive_sha256"):
        if not isinstance(value[key], str) or not SHA256_RE.fullmatch(value[key]):
            raise UpdateError(f"installed application {key} is invalid")
    if not isinstance(value["signing_key_id"], str) or not re.fullmatch(
        r"[0-9a-f]{16}", value["signing_key_id"]
    ):
        raise UpdateError("installed application signing key ID is invalid")
    paths = value["managed_paths"]
    if not isinstance(paths, list) or not paths or len(paths) > MAX_MEMBERS:
        raise UpdateError("installed application managed inventory is invalid")
    validated = [safe_payload_path(path) for path in paths]
    if validated != sorted(set(validated)):
        raise UpdateError("installed application managed inventory is not sorted and unique")
    return value


def read_installation(path: Path, *, missing_ok: bool = False) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except FileNotFoundError:
        if missing_ok:
            return None
        raise UpdateError("installed application identity is missing") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"cannot read installed application identity: {exc}") from exc
    return validate_installation(value)


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow a small number of redirects without permitting HTTPS downgrade."""

    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Any:
        redirects = int(req.get_header("X-ppspi-redirects", "0")) + 1
        if redirects > MAX_REDIRECTS:
            raise UpdateError("download redirect limit exceeded")
        if urllib.parse.urlsplit(newurl).scheme.lower() != "https":
            raise UpdateError("download redirect must use HTTPS")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.add_unredirected_header("X-PPSPi-Redirects", str(redirects))
        return redirected


def fetch(url: str, destination: Path, maximum: int) -> None:
    if urllib.parse.urlsplit(url).scheme.lower() != "https":
        raise UpdateError("download URL must use HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": "PPSPi-application-update/1"})
    opener = urllib.request.build_opener(HTTPSRedirectHandler())
    try:
        with (
            opener.open(request, timeout=30) as response,
            destination.open("xb") as output,
        ):
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > maximum):
                raise UpdateError("download size exceeds the allowed bound")
            total = 0
            while chunk := response.read(CHUNK_SIZE):
                total += len(chunk)
                if total > maximum:
                    raise UpdateError("download size exceeds the allowed bound")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"cannot download {url}: {exc}") from exc


def bounded_local_copy(source: Path, destination: Path, maximum: int) -> None:
    try:
        source_stat = source.stat()
    except OSError as exc:
        raise UpdateError(f"cannot inspect local artifact {source}: {exc}") from exc
    if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_size > maximum:
        raise UpdateError(f"local artifact size is invalid: {source}")
    total = 0
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output:
            while chunk := input_stream.read(CHUNK_SIZE):
                total += len(chunk)
                if total > maximum:
                    raise UpdateError(f"local artifact exceeds the allowed bound: {source}")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        raise UpdateError(f"cannot copy local artifact {source}: {exc}") from exc


def restore_transaction(root: Path, transaction_dir: Path, transaction: dict[str, Any]) -> None:
    snapshot = transaction_dir / "snapshot"
    for entry in transaction["files"]:
        if not entry["existed"]:
            continue
        relative = safe_transaction_path(entry["path"])
        source = snapshot / relative
        try:
            source_stat = source.lstat()
        except OSError as exc:
            raise UpdateError(f"rollback snapshot is missing: {relative}") from exc
        if not stat.S_ISREG(source_stat.st_mode):
            raise UpdateError(f"rollback snapshot is not a regular file: {relative}")
        if transaction["schema_version"] >= 2 and (
            source_stat.st_size != entry["size"]
            or sha256_file(source) != entry["sha256"]
        ):
            raise UpdateError(f"rollback snapshot identity mismatch: {relative}")
    for entry in reversed(transaction["files"]):
        relative = safe_transaction_path(entry["path"])
        destination = root / relative
        if entry["existed"]:
            source = snapshot / relative
            durable_copy(source, destination, entry["mode"])
        else:
            durable_unlink(destination, missing_ok=True)


def load_transaction(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"cannot read update transaction: {exc}") from exc
    if not isinstance(value, dict):
        raise UpdateError("update transaction schema is invalid")
    valid_states = {
        "PREPARED",
        "APPLYING",
        "COMMITTED",
        "ROLLING_BACK",
        "ROLLED_BACK",
        "RECOVERED",
    }
    schema_version = value.get("schema_version")
    expected_keys = TRANSACTION_KEYS_V2 if schema_version == 2 else TRANSACTION_KEYS
    if set(value) != expected_keys:
        raise UpdateError("update transaction schema is invalid")
    if schema_version not in {1, 2} or value["state"] not in valid_states:
        raise UpdateError("update transaction state is invalid")
    parse_version(value["from_version"])
    parse_version(value["to_version"])
    for key in ("from_commit", "to_commit"):
        if value[key] is not None and (
            not isinstance(value[key], str)
            or not re.fullmatch(r"[0-9a-f]{40}", value[key])
        ):
            raise UpdateError(f"update transaction {key} is invalid")
    if type(value["from_adopted"]) is not bool:
        raise UpdateError("update transaction from_adopted is invalid")
    if schema_version == 2:
        if value["previous_identity"] is not None:
            validate_installation(value["previous_identity"])
        unit_states = value["unit_states"]
        if not isinstance(unit_states, dict) or len(unit_states) > MAX_TRANSACTION_FILES:
            raise UpdateError("update transaction unit state is invalid")
        for unit, state in unit_states.items():
            if not isinstance(unit, str) or not (
                re.fullmatch(r"ppstime-[a-z0-9-]+\.(?:service|timer)", unit)
                or unit in EXTERNAL_MANAGED_UNITS
            ):
                raise UpdateError("update transaction unit state is invalid")
            if not isinstance(state, dict) or set(state) != UNIT_STATE_KEYS:
                raise UpdateError("update transaction unit state is invalid")
            if type(state["existed"]) is not bool or type(state["active"]) is not bool:
                raise UpdateError("update transaction unit state is invalid")
            if state["enabled"] not in {
                "enabled",
                "disabled",
                "static",
                "indirect",
                "masked",
                "not-found",
            }:
                raise UpdateError("update transaction unit state is invalid")
    if not isinstance(value["files"], list) or len(value["files"]) > MAX_TRANSACTION_FILES:
        raise UpdateError("update transaction file list is invalid")
    seen: set[str] = set()
    for entry in value["files"]:
        expected_keys = (
            TRANSACTION_FILE_KEYS_V2
            if value["schema_version"] == 2
            else TRANSACTION_FILE_KEYS
        )
        if not isinstance(entry, dict) or set(entry) != expected_keys:
            raise UpdateError("update transaction file entry is invalid")
        relative = safe_transaction_path(entry["path"])
        if relative in seen:
            raise UpdateError("update transaction contains duplicate paths")
        seen.add(relative)
        if type(entry["existed"]) is not bool or type(entry["mode"]) is not int:
            raise UpdateError("update transaction file metadata is invalid")
        if value["schema_version"] == 2:
            if type(entry["size"]) is not int or entry["size"] < 0:
                raise UpdateError("update transaction snapshot size is invalid")
            if not isinstance(entry["sha256"], str) or not SHA256_RE.fullmatch(entry["sha256"]):
                raise UpdateError("update transaction snapshot SHA-256 is invalid")
            if not entry["existed"] and (
                entry["size"] != 0
                or entry["sha256"] != hashlib.sha256(b"").hexdigest()
            ):
                raise UpdateError("update transaction absent-file metadata is invalid")
    return value
