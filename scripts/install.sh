#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SOURCE_ROOT
readonly PACKAGES=(chrony gpsd gpsd-clients pps-tools i2c-tools jq minisign python3 raspi-utils unattended-upgrades util-linux-extra)

target_root="/"
profile=""
custom_config=""
dry_run="false"
skip_packages="false"
allow_unsupported_model="false"
install_origin="source"
update_public_key=""
build_info=""

usage() {
    cat << 'EOF'
Usage: sudo ./scripts/install.sh [options]

Options:
  --profile NAME              Select a hardware profile.
  --config PATH               Apply an additional environment-style config.
  --root PATH                 Configure an alternate root filesystem.
  --dry-run                   Validate and describe changes without writing.
  --skip-packages             Do not run apt (used by pi-gen and tests).
  --allow-unsupported-model   Bypass the Raspberry Pi model guard.
    --install-origin TYPE       Record source or image origin (default: source).
    --update-public-key PATH    Install an explicitly supplied minisign public key.
    --build-info PATH           Record image build identity in install-origin metadata.
  -h, --help                  Show this help.
EOF
}

log() {
    printf 'PPSPi: %s\n' "$*"
}

die() {
    printf 'PPSPi error: %s\n' "$*" >&2
    exit 1
}

rooted() {
    local absolute_path="$1"
    printf '%s/%s' "${target_root%/}" "${absolute_path#/}"
}

run() {
    if [[ "${dry_run}" == "true" ]]; then
        printf 'Would run:'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

copy_file() {
    local source_file="$1"
    local destination="$2"
    local mode="$3"
    run install -D -m "${mode}" "${source_file}" "$(rooted "${destination}")"
}

while (($# > 0)); do
    case "$1" in
        --profile)
            (($# >= 2)) || die "--profile requires a value"
            profile="$2"
            shift 2
            ;;
        --config)
            (($# >= 2)) || die "--config requires a value"
            custom_config="$2"
            shift 2
            ;;
        --root)
            (($# >= 2)) || die "--root requires a value"
            target_root="$2"
            shift 2
            ;;
        --dry-run)
            dry_run="true"
            shift
            ;;
        --skip-packages)
            skip_packages="true"
            shift
            ;;
        --allow-unsupported-model)
            allow_unsupported_model="true"
            shift
            ;;
        --install-origin)
            (($# >= 2)) || die "--install-origin requires a value"
            install_origin="$2"
            shift 2
            ;;
        --update-public-key)
            (($# >= 2)) || die "--update-public-key requires a value"
            update_public_key="$2"
            shift 2
            ;;
        --build-info)
            (($# >= 2)) || die "--build-info requires a value"
            build_info="$2"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

[[ -d "${target_root}" ]] || die "target root does not exist: ${target_root}"
[[ "${install_origin}" == "source" || "${install_origin}" == "image" ]] ||
    die "install origin must be source or image"
target_root="$(cd "${target_root}" && pwd)"

if [[ "${target_root}" == "/" && "${EUID}" -ne 0 ]]; then
    die "installation into / must run as root"
fi
if [[ -n "${custom_config}" && ! -f "${custom_config}" ]]; then
    die "custom configuration does not exist: ${custom_config}"
fi
if [[ -n "${update_public_key}" && ! -f "${update_public_key}" ]]; then
    die "application update public key does not exist: ${update_public_key}"
fi
if [[ -n "${build_info}" && ! -f "${build_info}" ]]; then
    die "build metadata does not exist: ${build_info}"
fi

configure_args=(
    python3
    "${SCRIPT_DIR}/configure-profile.py"
    --source-root "${SOURCE_ROOT}"
    --root "${target_root}"
)
[[ -n "${profile}" ]] && configure_args+=(--profile "${profile}")
[[ -n "${custom_config}" ]] && configure_args+=(--config "${custom_config}")
[[ "${dry_run}" == "true" ]] && configure_args+=(--dry-run)
[[ "${allow_unsupported_model}" == "true" ]] && configure_args+=(--allow-unsupported-model)

log "validating configuration"
validate_args=("${configure_args[@]}" --validate-only)
"${validate_args[@]}"

if [[ "${skip_packages}" == "false" && "${target_root}" == "/" ]]; then
    log "installing required packages"
    run apt-get update
    run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        "${PACKAGES[@]}"
elif [[ "${skip_packages}" == "false" ]]; then
    die "package installation for alternate roots must be handled by the image builder"
fi

netplan_renderer="/usr/lib/netplan/00-network-manager-all.yaml"
if [[ "${target_root}" == "/" && "${dry_run}" == "false" && -e "${netplan_renderer}" ]]; then
    [[ -f "${netplan_renderer}" && ! -L "${netplan_renderer}" ]] ||
        die "Netplan renderer configuration is not a regular file"
    netplan_owner="$(dpkg-query -S "${netplan_renderer}" 2> /dev/null || true)"
    [[ "${netplan_owner}" == "rpi-cloud-init-mods: ${netplan_renderer}" ]] ||
        die "Netplan renderer configuration has an unexpected package owner"
    netplan_override="$(dpkg-statoverride --list "${netplan_renderer}" || true)"
    expected_netplan_override="root root 600 ${netplan_renderer}"
    if [[ -z "${netplan_override}" ]]; then
        log "persisting secure Netplan renderer permissions"
        dpkg-statoverride --add --update root root 0600 "${netplan_renderer}"
    elif [[ "${netplan_override}" == "${expected_netplan_override}" ]]; then
        chown root:root "${netplan_renderer}"
        chmod 0600 "${netplan_renderer}"
    else
        die "Netplan renderer configuration has a conflicting statoverride"
    fi
fi

log "installing PPSPi runtime"
copy_file "${SOURCE_ROOT}/files/ppstime/ppstime_core.py" "/usr/lib/ppstime/ppstime_core.py" 0644
copy_file "${SOURCE_ROOT}/files/ppstime/ppstime_update.py" "/usr/lib/ppstime/ppstime_update.py" 0644
copy_file "${SCRIPT_DIR}/configure-profile.py" "/usr/lib/ppstime/configure-profile.py" 0755
for command_name in ppstime-status ppstime-test ppstime-config ppstime-diagnostics \
    ppstime-backup ppstime-host-health ppstime-wait-devices ppstime-rtc \
    ppstime-health ppstime-healthcheck ppstime-maintenance ppstime-update \
    ppstime-dashboard; do
    copy_file "${SOURCE_ROOT}/files/ppstime/${command_name}" "/usr/lib/ppstime/${command_name}" 0755
done
run install -d -m 0755 "$(rooted /usr/local/sbin)"
for public_command in ppstime-status ppstime-test ppstime-config ppstime-diagnostics \
    ppstime-backup ppstime-host-health ppstime-maintenance ppstime-update; do
    run ln -sfn "/usr/lib/ppstime/${public_command}" "$(rooted "/usr/local/sbin/${public_command}")"
done
run ln -sfnT "/usr/lib/ppstime/ppstime-health" "$(rooted /usr/local/sbin/ppstime-health)"
run install -d -m 0755 "$(rooted /etc/ppstime/health-transition.d)"
run install -d -m 0755 "$(rooted /var/lib/ppstime)"
run install -d -m 0755 "$(rooted /var/lib/ppstime-dashboard)"
version="$(tr -d '[:space:]' < "${SOURCE_ROOT}/VERSION")"
git_commit=""
if [[ -n "${build_info}" ]]; then
    git_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["git_commit"])' "${build_info}")"
elif git -C "${SOURCE_ROOT}" rev-parse --verify HEAD > /dev/null 2>&1; then
    git_commit="$(git -C "${SOURCE_ROOT}" rev-parse HEAD)"
fi
origin_file="$(rooted /var/lib/ppstime/install-origin.json)"
if [[ "${dry_run}" == "false" && ! -e "${origin_file}" ]]; then
    python3 - "${origin_file}" "${install_origin}" "${version}" "${git_commit}" << 'PY'
import json
import sys

path, origin, version, commit = sys.argv[1:]
with open(path, "w", encoding="ascii") as stream:
    json.dump(
        {
            "adopted": False,
            "git_commit": commit or None,
            "origin": origin,
            "schema_version": 1,
            "version": version,
        },
        stream,
        separators=(",", ":"),
        sort_keys=True,
    )
    stream.write("\n")
PY
    chmod 0644 "${origin_file}"
fi

run install -d -m 0755 "$(rooted /usr/share/ppstime/config/profiles)"
if [[ -n "${update_public_key}" ]]; then
    copy_file "${update_public_key}" "/usr/share/ppstime/application-update.pub" 0644
else
    copy_file "${SOURCE_ROOT}/files/application-update.pub" \
        "/usr/share/ppstime/application-update.pub" 0644
fi
copy_file "${SOURCE_ROOT}/config/default.env" "/usr/share/ppstime/config/default.env" 0644
for profile_file in "${SOURCE_ROOT}"/config/profiles/*.env; do
    copy_file "${profile_file}" "/usr/share/ppstime/config/profiles/$(basename "${profile_file}")" 0644
done
run install -d -m 0755 "$(rooted /usr/share/ppstime/dashboard)"
for dashboard_asset in "${SOURCE_ROOT}"/files/dashboard/*; do
    copy_file "${dashboard_asset}" "/usr/share/ppstime/dashboard/$(basename "${dashboard_asset}")" 0644
done

copy_file "${SOURCE_ROOT}/files/udev/80-ppstime.rules" "/etc/udev/rules.d/80-ppstime.rules" 0644
copy_file "${SOURCE_ROOT}/files/modules-load.d/ppstime.conf" \
    "/etc/modules-load.d/ppstime.conf" 0644
for unit_file in "${SOURCE_ROOT}"/files/systemd/*.service "${SOURCE_ROOT}"/files/systemd/*.timer; do
    copy_file "${unit_file}" "/etc/systemd/system/$(basename "${unit_file}")" 0644
done
copy_file "${SOURCE_ROOT}/files/systemd/gpsd.service.d/ppstime.conf" \
    "/etc/systemd/system/gpsd.service.d/ppstime.conf" 0644
copy_file "${SOURCE_ROOT}/files/systemd/chrony.service.d/ppstime.conf" \
    "/etc/systemd/system/chrony.service.d/ppstime.conf" 0644

if [[ "${dry_run}" == "false" ]]; then
    PYTHONPATH="${SOURCE_ROOT}/files/ppstime" python3 - \
        "${SOURCE_ROOT}" "${target_root}" "${version}" "${git_commit}" << 'PY'
import hashlib
import sys
from pathlib import Path

from ppstime_update import (
    atomic_json,
    canonical_json,
    signing_key_id,
    source_payload_files,
)

source_root = Path(sys.argv[1])
target_root = Path(sys.argv[2])
version = sys.argv[3]
git_commit = sys.argv[4] or "0" * 40
managed_paths = [destination for _, destination, _ in source_payload_files(source_root)]
file_identity = []
for relative in managed_paths:
    installed = target_root / relative
    file_identity.append(
        {"path": relative, "sha256": hashlib.sha256(installed.read_bytes()).hexdigest()}
    )
baseline = {
    "files": file_identity,
    "git_commit": git_commit,
    "version": version,
}
baseline_sha256 = hashlib.sha256(canonical_json(baseline)).hexdigest()
atomic_json(
    target_root / "var/lib/ppstime/application-installation.json",
    {
        "schema_version": 1,
        "repository": "Bazsy/PPSPi",
        "version": version,
        "git_commit": git_commit,
        "manifest_sha256": baseline_sha256,
        "archive_sha256": baseline_sha256,
        "signing_key_id": signing_key_id(
            target_root / "usr/share/ppstime/application-update.pub"
        ),
        "managed_paths": managed_paths,
    },
)
PY
fi

log "generating boot, GPSD, and Chrony configuration"
"${configure_args[@]}"

if [[ "${target_root}" == "/" && "${dry_run}" == "false" ]]; then
    log "enabling services"
    systemctl daemon-reload
    if grep -qx 'CHRONY_ENABLED=true' /etc/ppstime/ppstime.env; then
        systemctl enable chrony.service
    else
        systemctl disable --now chrony.service || true
    fi
    if grep -qx 'GPSD_ENABLED=true' /etc/ppstime/ppstime.env; then
        systemctl enable gpsd.service
    else
        systemctl disable --now gpsd.service gpsd.socket || true
    fi
    systemctl enable ppstime-healthcheck.timer
    systemctl disable apt-daily.timer apt-daily-upgrade.timer
    systemctl stop apt-daily.timer apt-daily-upgrade.timer || true
    systemctl enable ppstime-maintenance-post-boot.timer
    systemctl enable ppstime-update-recovery.service
    if grep -Eqx '(OS_UPDATES_ENABLED|APP_UPDATES_ENABLED)=true' /etc/ppstime/ppstime.env; then
        systemctl enable ppstime-maintenance.timer
    else
        systemctl disable --now ppstime-maintenance.timer || true
    fi
    if grep -qx 'RTC_ENABLED=true' /etc/ppstime/ppstime.env; then
        systemctl enable ppstime-rtc-restore.service ppstime-rtc-save.timer
    else
        systemctl disable --now ppstime-rtc-restore.service ppstime-rtc-save.timer || true
    fi
    if grep -qx 'DASHBOARD_ENABLED=true' /etc/ppstime/ppstime.env; then
        /usr/lib/ppstime/ppstime-dashboard preflight
        systemctl enable ppstime-dashboard.service ppstime-dashboard-sample.timer
        systemctl start ppstime-dashboard.service ppstime-dashboard-sample.timer
    else
        systemctl disable ppstime-dashboard.service ppstime-dashboard-sample.timer || true
        systemctl stop ppstime-dashboard.service ppstime-dashboard-sample.timer || true
    fi
    if grep -qx 'RTC_ENABLED=true' /etc/ppstime/ppstime.env &&
        systemctl list-unit-files fake-hwclock.service > /dev/null 2>&1; then
        systemctl disable --now fake-hwclock.service || true
    fi
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=pps || true
    systemctl try-restart chrony.service gpsd.service || true
else
    log "service activation deferred to first boot/image finalization"
fi

log "installation complete; reboot is required for boot overlay changes"
