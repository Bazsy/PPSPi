#!/usr/bin/env python3
"""Validate a PPSPi profile and generate system configuration files."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT / "files" / "ppstime"))

from ppstime_core import (  # noqa: E402
    ConfigError,
    atomic_write,
    config_to_env,
    load_config,
    model_is_supported,
    remove_serial_console,
    render_boot_block,
    render_chrony,
    render_gpsd,
    update_managed_block,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=SCRIPT_ROOT)
    parser.add_argument("--root", type=Path, default=Path("/"), help="target root filesystem")
    parser.add_argument("--profile", help="hardware profile name")
    parser.add_argument("--config", type=Path, help="additional configuration file")
    parser.add_argument("--model", help="model string to validate instead of reading device tree")
    parser.add_argument("--allow-unsupported-model", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def rooted(root: Path, absolute_path: str) -> Path:
    return root / absolute_path.lstrip("/")


def read_model(root: Path) -> str | None:
    path = rooted(root, "/proc/device-tree/model")
    try:
        return path.read_text(encoding="utf-8").rstrip("\x00\n")
    except OSError:
        return None


def find_boot_file(root: Path, name: str) -> Path:
    candidates = [rooted(root, f"/boot/firmware/{name}"), rooted(root, f"/boot/{name}")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ConfigError(f"cannot find {name} below /boot/firmware or /boot")


def backup_if_changing(path: Path, new_content: str, *, dry_run: bool) -> None:
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if existing == new_content or dry_run:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.ppstime-{timestamp}.bak")
    shutil.copy2(path, backup_path)


def main() -> int:
    args = parse_args()
    try:
        source_root = args.source_root.resolve()
        root = args.root.resolve()
        config = load_config(
            source_root,
            profile=args.profile,
            custom_path=args.config.resolve() if args.config else None,
        )

        model = args.model or read_model(root)
        if model and not model_is_supported(model, config) and not args.allow_unsupported_model:
            raise ConfigError(
                f"unsupported hardware model {model!r}; expected pattern "
                f"{config['SUPPORTED_MODEL_PATTERN']!r}"
            )
        if args.validate_only:
            print(f"Configuration valid for profile {config['PPSTIME_PROFILE']}")
            return 0

        generated = {
            rooted(root, "/etc/ppstime/ppstime.env"): (config_to_env(config), 0o640),
            rooted(root, "/etc/chrony/conf.d/ppstime.conf"): (render_chrony(config), 0o644),
            rooted(root, "/etc/default/gpsd"): (render_gpsd(config), 0o644),
        }

        boot_config = find_boot_file(root, "config.txt")
        boot_existing = boot_config.read_text(encoding="utf-8")
        boot_content = update_managed_block(boot_existing, render_boot_block(config))
        generated[boot_config] = (boot_content, 0o644)

        cmdline = find_boot_file(root, "cmdline.txt")
        cmdline_content = remove_serial_console(cmdline.read_text(encoding="utf-8"))
        generated[cmdline] = (cmdline_content, 0o644)

        for path, (content, mode) in generated.items():
            if path in {boot_config, cmdline}:
                backup_if_changing(path, content, dry_run=args.dry_run)
            if args.dry_run:
                print(f"Would write {path}")
            else:
                changed = atomic_write(path, content, mode=mode)
                print(f"{'Updated' if changed else 'Unchanged'} {path}")
        return 0
    except ConfigError as exc:
        print(f"ppstime configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())