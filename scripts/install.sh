#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SOURCE_ROOT
readonly PACKAGES=(chrony gpsd gpsd-clients pps-tools i2c-tools jq python3 util-linux-extra)

target_root="/"
profile=""
custom_config=""
dry_run="false"
skip_packages="false"
allow_unsupported_model="false"

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
target_root="$(cd "${target_root}" && pwd)"

if [[ "${target_root}" == "/" && "${EUID}" -ne 0 ]]; then
    die "installation into / must run as root"
fi
if [[ -n "${custom_config}" && ! -f "${custom_config}" ]]; then
    die "custom configuration does not exist: ${custom_config}"
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

log "installing PPSPi runtime"
copy_file "${SOURCE_ROOT}/files/ppstime/ppstime_core.py" "/usr/lib/ppstime/ppstime_core.py" 0644
copy_file "${SCRIPT_DIR}/configure-profile.py" "/usr/lib/ppstime/configure-profile.py" 0755
for command_name in ppstime-status ppstime-test ppstime-config ppstime-diagnostics \
    ppstime-wait-devices ppstime-rtc ppstime-healthcheck; do
    copy_file "${SOURCE_ROOT}/files/ppstime/${command_name}" "/usr/lib/ppstime/${command_name}" 0755
done
run install -d -m 0755 "$(rooted /usr/local/sbin)"
for public_command in ppstime-status ppstime-test ppstime-config ppstime-diagnostics; do
    run ln -sfn "/usr/lib/ppstime/${public_command}" "$(rooted "/usr/local/sbin/${public_command}")"
done

run install -d -m 0755 "$(rooted /usr/share/ppstime/config/profiles)"
copy_file "${SOURCE_ROOT}/config/default.env" "/usr/share/ppstime/config/default.env" 0644
for profile_file in "${SOURCE_ROOT}"/config/profiles/*.env; do
    copy_file "${profile_file}" "/usr/share/ppstime/config/profiles/$(basename "${profile_file}")" 0644
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
    if grep -qx 'RTC_ENABLED=true' /etc/ppstime/ppstime.env; then
        systemctl enable ppstime-rtc-restore.service ppstime-rtc-save.timer
    else
        systemctl disable --now ppstime-rtc-restore.service ppstime-rtc-save.timer || true
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
