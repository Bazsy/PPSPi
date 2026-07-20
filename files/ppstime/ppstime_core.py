#!/usr/bin/env python3
"""Shared configuration, rendering, and parsing helpers for PPSPi.

This module intentionally uses only the Python standard library so the same
code can run in CI, on a clean Raspberry Pi OS installation, and in pi-gen.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import shlex
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a PPSPi configuration value is invalid."""


CONFIG_KEYS = frozenset(
    {
        "PPSTIME_PROFILE",
        "GPS_DEVICE",
        "GPS_BAUD",
        "GPSD_ENABLED",
        "GPSD_OPTIONS",
        "PPS_DEVICE",
        "PPS_GPIO",
        "PPS_ASSERT_EDGE",
        "RTC_ENABLED",
        "RTC_OVERLAY",
        "RTC_DEVICE",
        "NTP_ALLOW",
        "NTP_FALLBACK_POOL",
        "CHRONY_GPS_OFFSET",
        "CHRONY_ENABLED",
        "SSH_ENABLED",
        "DEFAULT_HOSTNAME",
        "SUPPORTED_MODEL_PATTERN",
    }
)

BOOLEAN_KEYS = frozenset({"GPSD_ENABLED", "RTC_ENABLED", "CHRONY_ENABLED", "SSH_ENABLED"})
DEVICE_KEYS = frozenset({"GPS_DEVICE", "PPS_DEVICE", "RTC_DEVICE"})
GPSD_BAUD_RATES = frozenset({4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800})
SAFE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# NTP client networks accepted by configuration validation. This intentionally
# means administratively private LAN address space, not every range that Python
# classifies as non-global (for example, loopback, link-local, CGNAT, or test
# networks).
PRIVATE_LAN_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)


@dataclass(frozen=True)
class CommandResult:
    """Normalized result from a command used by runtime diagnostics."""

    returncode: int
    stdout: str
    stderr: str


def parse_env_file(path: Path, *, allowed_keys: frozenset[str] = CONFIG_KEYS) -> dict[str, str]:
    """Parse a strict KEY=VALUE file without executing it as shell code."""

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"{path}:{line_number}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in allowed_keys:
            raise ConfigError(f"{path}:{line_number}: unsupported key {key!r}")
        if key in values:
            raise ConfigError(f"{path}:{line_number}: duplicate key {key!r}")
        value = _parse_env_value(raw_value.strip(), path, line_number)
        if "\x00" in value or "\n" in value or "\r" in value:
            raise ConfigError(f"{path}:{line_number}: control characters are not allowed")
        values[key] = value
    return values


def _parse_env_value(raw_value: str, path: Path, line_number: int) -> str:
    if not raw_value:
        return ""
    try:
        tokens = shlex.split(raw_value, comments=True, posix=True)
    except ValueError as exc:
        raise ConfigError(f"{path}:{line_number}: invalid quoting: {exc}") from exc
    if len(tokens) > 1:
        raise ConfigError(
            f"{path}:{line_number}: values containing spaces must be quoted as one value"
        )
    return tokens[0] if tokens else ""


def load_config(
    source_root: Path,
    *,
    profile: str | None = None,
    custom_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load defaults, one profile, an optional custom file, then env overrides."""

    env = os.environ if environ is None else environ
    defaults_path = source_root / "config" / "default.env"
    config = parse_env_file(defaults_path)
    custom_values = parse_env_file(custom_path) if custom_path is not None else {}
    selected_profile = (
        profile
        or env.get("PPSTIME_PROFILE")
        or custom_values.get("PPSTIME_PROFILE")
        or config.get("PPSTIME_PROFILE")
    )
    if not selected_profile or not PROFILE_RE.fullmatch(selected_profile):
        raise ConfigError(f"invalid profile name: {selected_profile!r}")

    profile_path = source_root / "config" / "profiles" / f"{selected_profile}.env"
    config.update(parse_env_file(profile_path))
    config.update(custom_values)

    for key in CONFIG_KEYS:
        if key in env:
            config[key] = env[key]

    config["PPSTIME_PROFILE"] = selected_profile
    validate_config(config)
    return config


def validate_config(config: Mapping[str, str]) -> None:
    """Validate all supported configuration values and fail closed."""

    missing = sorted(CONFIG_KEYS - config.keys())
    if missing:
        raise ConfigError(f"missing required configuration keys: {', '.join(missing)}")
    unknown = sorted(config.keys() - CONFIG_KEYS)
    if unknown:
        raise ConfigError(f"unsupported configuration keys: {', '.join(unknown)}")
    for key, value in config.items():
        if any(character in value for character in ("\x00", "\n", "\r")):
            raise ConfigError(f"{key} contains a forbidden control character")

    if not PROFILE_RE.fullmatch(config["PPSTIME_PROFILE"]):
        raise ConfigError("PPSTIME_PROFILE must use lowercase letters, digits, and hyphens")
    for key in BOOLEAN_KEYS:
        if config[key] not in {"true", "false"}:
            raise ConfigError(f"{key} must be true or false")
    for key in DEVICE_KEYS:
        value = config[key]
        path = Path(value)
        if (
            not value.startswith("/dev/")
            or not re.fullmatch(r"/dev/[A-Za-z0-9._/+:-]+", value)
            or ".." in path.parts
            or "//" in value
        ):
            raise ConfigError(f"{key} must be a safe absolute path below /dev")

    try:
        baud = int(config["GPS_BAUD"])
    except ValueError as exc:
        raise ConfigError("GPS_BAUD must be an integer") from exc
    if baud not in GPSD_BAUD_RATES:
        supported = ", ".join(str(rate) for rate in sorted(GPSD_BAUD_RATES))
        raise ConfigError(f"GPS_BAUD must be one of: {supported}")

    try:
        gpio = int(config["PPS_GPIO"])
    except ValueError as exc:
        raise ConfigError("PPS_GPIO must be an integer") from exc
    if not 0 <= gpio <= 53:
        raise ConfigError("PPS_GPIO must be between 0 and 53")
    if config["PPS_ASSERT_EDGE"] not in {"rising", "falling"}:
        raise ConfigError("PPS_ASSERT_EDGE must be rising or falling")
    if not SAFE_NAME_RE.fullmatch(config["RTC_OVERLAY"]):
        raise ConfigError("RTC_OVERLAY contains unsafe characters")
    if config["GPSD_OPTIONS"] != "-n":
        raise ConfigError("GPSD_OPTIONS must be -n for reliable unattended time service")

    cidrs = split_cidrs(config["NTP_ALLOW"])
    if not cidrs:
        raise ConfigError("NTP_ALLOW must contain at least one CIDR")
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=True)
        except ValueError as exc:
            raise ConfigError(f"NTP_ALLOW contains invalid CIDR {cidr!r}: {exc}") from exc
        if not any(
            network.version == private_network.version and network.subnet_of(private_network)
            for private_network in PRIVATE_LAN_NETWORKS
        ):
            raise ConfigError(f"NTP_ALLOW must not expose NTP publicly: {cidr!r}")

    pool = config["NTP_FALLBACK_POOL"]
    if not HOSTNAME_RE.fullmatch(pool):
        raise ConfigError("NTP_FALLBACK_POOL must be a valid hostname")
    try:
        offset = float(config["CHRONY_GPS_OFFSET"])
    except ValueError as exc:
        raise ConfigError("CHRONY_GPS_OFFSET must be numeric") from exc
    if not math.isfinite(offset) or not -1.0 <= offset <= 1.0:
        raise ConfigError("CHRONY_GPS_OFFSET must be between -1.0 and 1.0 seconds")
    if not HOSTNAME_RE.fullmatch(config["DEFAULT_HOSTNAME"]):
        raise ConfigError("DEFAULT_HOSTNAME must be a valid hostname")
    try:
        re.compile(config["SUPPORTED_MODEL_PATTERN"])
    except re.error as exc:
        raise ConfigError(f"SUPPORTED_MODEL_PATTERN is invalid: {exc}") from exc


def split_cidrs(value: str) -> list[str]:
    """Split a comma-separated CIDR list while rejecting empty members."""

    if not value.strip():
        return []
    parts = [part.strip() for part in value.split(",")]
    if any(not part for part in parts):
        raise ConfigError("NTP_ALLOW contains an empty CIDR")
    return parts


def config_to_env(config: Mapping[str, str]) -> str:
    """Serialize validated configuration in deterministic, shell-safe form."""

    validate_config(config)
    lines = ["# Managed by PPSPi. Use ppstime-config to change values."]
    lines.extend(f"{key}={shlex.quote(config[key])}" for key in sorted(config))
    return "\n".join(lines) + "\n"


def render_chrony(config: Mapping[str, str]) -> str:
    """Render the PPSPi Chrony fragment."""

    validate_config(config)
    serial_name = Path(config["GPS_DEVICE"]).name
    socket_path = f"/run/chrony.{serial_name}.sock"
    lines = [
        "# Managed by PPSPi. Local changes will be replaced by ppstime-config apply.",
        "#",
        "# GPS serial messages identify the UTC second but have variable latency.",
        "# They are monitored and used to lock PPS, but are not selected directly.",
        f"refclock SOCK {socket_path} refid GPS poll 2 filter 4 precision 1e-1 "
        f"offset {config['CHRONY_GPS_OFFSET']} delay 0.2 noselect",
        "#",
        "# PPS precisely marks the second boundary but carries no date/time label.",
        "# Locking it to GPS safely combines the two signals. Rising assert events",
        "# are the Linux PPS default; the clear option is used for a falling edge.",
    ]
    pps_parameter = config["PPS_DEVICE"]
    if config["PPS_ASSERT_EDGE"] == "falling":
        pps_parameter += ":clear"
    lines.append(
        f"refclock PPS {pps_parameter} refid PPS lock GPS poll 0 dpoll 0 prefer precision 1e-7"
    )
    lines.extend(
        [
            "",
            "# Network time accelerates startup and remains available when GNSS is lost.",
            f"pool {config['NTP_FALLBACK_POOL']} iburst maxsources 4",
            "",
            "# Serve only validated RFC 1918 IPv4 and RFC 4193 IPv6 ULA networks.",
        ]
    )
    lines.extend(f"allow {cidr}" for cidr in split_cidrs(config["NTP_ALLOW"]))
    lines.extend(
        [
            "",
            "# Step only during the first three valid updates after startup.",
            "makestep 1.0 3",
            "driftfile /var/lib/chrony/drift",
            "dumpdir /var/lib/chrony",
            "leapsectz right/UTC",
            "log tracking statistics refclocks",
            "logdir /var/log/chrony",
            "clientloglimit 524288",
            "ratelimit interval 1 burst 16",
        ]
    )
    return "\n".join(lines) + "\n"


def render_gpsd(config: Mapping[str, str]) -> str:
    """Render Debian's /etc/default/gpsd configuration."""

    validate_config(config)
    enabled = "true" if config["GPSD_ENABLED"] == "true" else "false"
    devices = f"{config['GPS_DEVICE']} {config['PPS_DEVICE']}"
    return (
        "# Managed by PPSPi.\n"
        f'START_DAEMON="{enabled}"\n'
        f'GPSD_OPTIONS="{config["GPSD_OPTIONS"]} -s {config["GPS_BAUD"]}"\n'
        f'DEVICES="{devices}"\n'
        'USBAUTO="false"\n'
        'GPSD_SOCKET="/run/gpsd.sock"\n'
    )


def render_boot_block(config: Mapping[str, str]) -> str:
    """Render the project-owned config.txt block."""

    validate_config(config)
    pps_overlay = f"dtoverlay=pps-gpio,gpiopin={config['PPS_GPIO']}"
    if config["PPS_ASSERT_EDGE"] == "falling":
        pps_overlay += ",assert_falling_edge"
    lines = [
        "# BEGIN PPSPi managed configuration",
        "enable_uart=1",
        "dtparam=i2c_arm=on",
        pps_overlay,
    ]
    if config["RTC_ENABLED"] == "true":
        lines.append(f"dtoverlay=i2c-rtc,{config['RTC_OVERLAY']}")
    lines.append("# END PPSPi managed configuration")
    return "\n".join(lines)


def update_managed_block(existing: str, block: str) -> str:
    """Insert or replace one PPSPi block without touching unrelated settings."""

    start = "# BEGIN PPSPi managed configuration"
    end = "# END PPSPi managed configuration"
    start_count = existing.count(start)
    end_count = existing.count(end)
    if start_count != end_count or start_count > 1:
        raise ConfigError("boot configuration contains malformed or duplicate PPSPi markers")
    if start_count == 1:
        prefix, remainder = existing.split(start, 1)
        _, suffix = remainder.split(end, 1)
        updated = prefix.rstrip() + "\n\n" + block + suffix
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    return updated.rstrip() + "\n"


def remove_serial_console(cmdline: str) -> str:
    """Remove only serial console arguments while preserving the one-line format."""

    tokens = cmdline.strip().split()
    filtered = [
        token
        for token in tokens
        if not re.fullmatch(r"console=(?:serial0|ttyAMA\d+|ttyS\d+),[^ ]+", token)
    ]
    return " ".join(filtered) + "\n"


def model_is_supported(model: str, config: Mapping[str, str]) -> bool:
    """Return whether a normalized Raspberry Pi model matches the profile."""

    return re.fullmatch(config["SUPPORTED_MODEL_PATTERN"], model.strip().rstrip("\x00")) is not None


def atomic_write(path: Path, content: str, *, mode: int = 0o644) -> bool:
    """Atomically write text when changed; return True if the file changed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.read_text(encoding="utf-8") == content:
            os.chmod(path, mode)
            return False
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc

    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def run_command(command: Sequence[str], *, timeout: float = 10.0) -> CommandResult:
    """Run a diagnostic command with bounded execution and normalized output."""

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, PermissionError) as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(124, stdout, stderr or f"timed out after {timeout} seconds")
    return CommandResult(process.returncode, process.stdout, process.stderr)


def read_rtc_sysfs(
    device: str | Path, *, sysfs_root: Path = Path("/sys/class/rtc")
) -> CommandResult:
    """Read a validated RTC timestamp from world-readable Linux sysfs files."""

    rtc_name = Path(device).name
    if not re.fullmatch(r"rtc[0-9]+", rtc_name):
        return CommandResult(1, "", f"invalid RTC device name: {rtc_name}")
    rtc_dir = sysfs_root / rtc_name
    try:
        driver = (rtc_dir / "name").read_text(encoding="utf-8").strip()
        if not driver or not re.fullmatch(r"[A-Za-z0-9._:+ -]+", driver):
            raise ValueError("invalid RTC driver name")
        for _ in range(3):
            date_before = (rtc_dir / "date").read_text(encoding="ascii").strip()
            rtc_time = (rtc_dir / "time").read_text(encoding="ascii").strip()
            date_after = (rtc_dir / "date").read_text(encoding="ascii").strip()
            if date_before != date_after:
                continue
            timestamp = datetime.strptime(
                f"{date_before} {rtc_time}", "%Y-%m-%d %H:%M:%S"
            )
            return CommandResult(
                0,
                f"{timestamp:%Y-%m-%d %H:%M:%S} UTC (sysfs; {driver})\n",
                "",
            )
        return CommandResult(1, "", "RTC date changed repeatedly while reading sysfs")
    except (OSError, UnicodeError, ValueError) as exc:
        return CommandResult(1, "", f"cannot read RTC sysfs state: {exc}")


def parse_key_value_output(text: str) -> dict[str, str]:
    """Parse `Label : value` output used by chronyc tracking."""

    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_chrony_sources(text: str) -> list[dict[str, str]]:
    """Parse the stable columns in `chronyc sources -n` output."""

    sources: list[dict[str, str]] = []
    in_rows = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("==="):
            in_rows = True
            continue
        if not in_rows or not line.strip():
            continue
        columns = line.split()
        if len(columns) < 7 or len(columns[0]) != 2:
            continue
        sources.append(
            {
                "mode": columns[0][0],
                "state": columns[0][1],
                "name": columns[1],
                "stratum": columns[2],
                "poll": columns[3],
                "reach": columns[4],
                "last_rx": columns[5],
                "last_sample": " ".join(columns[6:]),
            }
        )
    return sources


def parse_chrony_clients(text: str) -> int:
    """Count client rows from `chronyc clients` output."""

    in_rows = False
    count = 0
    for line in text.splitlines():
        if line.startswith("==="):
            in_rows = True
            continue
        if in_rows and line.strip() and len(line.split()) >= 6:
            count += 1
    return count


def parse_gpsd_json(text: str, *, device: str | None = None) -> dict[str, Any]:
    """Return the newest TPV and SKY observations from a gpspipe JSON stream."""

    tpv: dict[str, Any] = {}
    sky: dict[str, Any] = {}
    reported_baud: int | None = None
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate_devices: list[dict[str, Any]] = []
        if record.get("class") == "TPV":
            tpv = record
        elif record.get("class") == "SKY":
            sky = record
        elif record.get("class") == "DEVICE":
            candidate_devices = [record]
        elif record.get("class") == "DEVICES":
            candidate_devices = record.get("devices", [])
        for candidate in candidate_devices:
            if device is None or candidate.get("path") == device:
                baud = candidate.get("bps")
                if isinstance(baud, int):
                    reported_baud = baud
    mode = int(tpv.get("mode", 0) or 0)
    satellites_used = sum(1 for satellite in sky.get("satellites", []) if satellite.get("used"))
    return {
        "mode": mode,
        "fix": {0: "UNKNOWN", 1: "NO FIX", 2: "2D", 3: "3D"}.get(mode, "UNKNOWN"),
        "satellites_used": satellites_used,
        "reported_baud": reported_baud,
    }


def parse_ppstest(text: str) -> bool:
    """Detect at least two distinct PPS assert sequence numbers."""

    sequences = set(
        re.findall(r"assert [^\n]*?(?:sequence:\s*|#)(\d+)", text, flags=re.IGNORECASE)
    )
    return len(sequences) >= 2


def sanitize_config(config: Mapping[str, str]) -> dict[str, str]:
    """Redact values whose names could carry credentials in future profiles."""

    sensitive_fragments = ("PASSWORD", "SECRET", "TOKEN", "PRIVATE", "WIFI", "SSID", "KEY")
    return {
        key: (
            "<redacted>"
            if any(fragment in key.upper() for fragment in sensitive_fragments)
            else value
        )
        for key, value in sorted(config.items())
    }