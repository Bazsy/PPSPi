#!/usr/bin/env bash
set -Eeuo pipefail

image_file="${1:-}"
[[ -n "${image_file}" ]] || {
    printf 'Usage: %s IMAGE.img.xz\n' "${0##*/}" >&2
    exit 2
}
[[ -f "${image_file}" && "${image_file}" == *.img.xz ]] || {
    printf 'PPSPi image validation error: expected an existing .img.xz file\n' >&2
    exit 2
}

for command_name in apt-config find grep jq losetup mount mountpoint systemd-analyze umount xz; do
    command -v "${command_name}" > /dev/null 2>&1 || {
        printf 'PPSPi image validation error: missing command %s\n' "${command_name}" >&2
        exit 2
    }
done

work_dir="$(mktemp -d)"
raw_image="${work_dir}/ppspi.img"
root_mount="${work_dir}/root"
loop_device=""
mkdir -p "${root_mount}"

cleanup() {
    set +e
    if mountpoint -q "${root_mount}/boot/firmware"; then
        sudo umount "${root_mount}/boot/firmware"
    fi
    if mountpoint -q "${root_mount}"; then
        sudo umount "${root_mount}"
    fi
    if [[ -n "${loop_device}" ]]; then
        sudo losetup --detach "${loop_device}"
    fi
    rm -rf "${work_dir}"
}
trap cleanup EXIT

printf 'Decompressing %s for read-only validation...\n' "${image_file}"
xz --decompress --stdout "${image_file}" > "${raw_image}"
loop_device="$(sudo losetup --find --show --read-only --partscan "${raw_image}")"

for _ in {1..20}; do
    [[ -b "${loop_device}p1" && -b "${loop_device}p2" ]] && break
    sudo udevadm settle
done
[[ -b "${loop_device}p1" && -b "${loop_device}p2" ]] || {
    printf 'PPSPi image validation error: expected two image partitions\n' >&2
    exit 1
}

sudo mount -o ro "${loop_device}p2" "${root_mount}"
sudo mkdir -p "${root_mount}/boot/firmware"
sudo mount -o ro "${loop_device}p1" "${root_mount}/boot/firmware"

sudo grep -qx 'VERSION_CODENAME=trixie' "${root_mount}/etc/os-release"
[[ -x "${root_mount}/usr/bin/cloud-init" ]]
[[ -x "${root_mount}/usr/sbin/hwclock" ]]
[[ -x "${root_mount}/usr/bin/vcgencmd" ]]
sudo find "${root_mount}/usr/lib/python3" -type f -name 'cc_raspberry_pi.py' -print -quit |
    grep -q .
sudo grep -qx 'i2c-dev' "${root_mount}/etc/modules-load.d/ppstime.conf"
if sudo grep -qE '^[[:space:]]*-[[:space:]]*netplan_nm_patch[[:space:]]*$' \
    "${root_mount}/etc/cloud/cloud.cfg"; then
    printf 'PPSPi image validation error: cloud-init references missing netplan_nm_patch\n' >&2
    exit 1
fi

for seed_file in meta-data network-config user-data; do
    [[ -s "${root_mount}/boot/firmware/${seed_file}" ]] || {
        printf 'PPSPi image validation error: missing cloud-init seed %s\n' "${seed_file}" >&2
        exit 1
    }
done

sudo jq -e \
    '.raspberry_pi_os_release == "trixie" and .architecture == "arm64"' \
    "${root_mount}/etc/ppstime/build-info.json" > /dev/null
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-status" ]]
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-backup" ]]
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-host-health" ]]
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-maintenance" ]]
[[ -x "${root_mount}/usr/bin/unattended-upgrade" ]]
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-health" ]]
[[ -x "${root_mount}/usr/lib/ppstime/ppstime-healthcheck" ]]
[[ -L "${root_mount}/usr/local/sbin/ppstime-health" ]]
[[ -L "${root_mount}/usr/local/sbin/ppstime-backup" ]]
[[ "$(sudo readlink "${root_mount}/usr/local/sbin/ppstime-backup")" == "/usr/lib/ppstime/ppstime-backup" ]]
[[ -L "${root_mount}/usr/local/sbin/ppstime-host-health" ]]
[[ "$(sudo readlink "${root_mount}/usr/local/sbin/ppstime-host-health")" == "/usr/lib/ppstime/ppstime-host-health" ]]
[[ "$(sudo readlink "${root_mount}/usr/local/sbin/ppstime-health")" == "/usr/lib/ppstime/ppstime-health" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-healthcheck.service" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-healthcheck.timer" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-maintenance.service" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-maintenance.timer" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-maintenance-post-boot.service" ]]
[[ -f "${root_mount}/etc/systemd/system/ppstime-maintenance-post-boot.timer" ]]
[[ -f "${root_mount}/etc/apt/apt.conf.d/52ppstime-unattended-upgrades" ]]
APT_CONFIG="${root_mount}/etc/apt/apt.conf.d/52ppstime-unattended-upgrades" \
    apt-config dump > /dev/null
apt_validation_config="${work_dir}/apt-validation.conf"
cat > "${apt_validation_config}" << EOF
Dir::Etc "${root_mount}/etc/apt";
Dir::Etc::parts "apt.conf.d";
EOF
effective_apt="$(APT_CONFIG="${apt_validation_config}" apt-config dump)"
printf '%s\n' "${effective_apt}" | grep -Fq "\${distro_codename}-security"
if printf '%s\n' "${effective_apt}" | grep -Eq \
    'Unattended-Upgrade::Allowed-Origins:: .*'; then
    printf 'PPSPi image validation error: security scope inherited allowed origins\n' >&2
    exit 1
fi
if printf '%s\n' "${effective_apt}" | grep -Eq \
    '(Origins-Pattern|Allowed-Origins)::[^ ]+ .*codename=\$\{distro_codename\}([",]|$)'; then
    printf 'PPSPi image validation error: security scope inherited base Debian origins\n' >&2
    exit 1
fi
sudo grep -Fq '${distro_codename}-security' \
    "${root_mount}/etc/apt/apt.conf.d/52ppstime-unattended-upgrades"
sudo grep -Fxq 'Unattended-Upgrade::Automatic-Reboot "false";' \
    "${root_mount}/etc/apt/apt.conf.d/52ppstime-unattended-upgrades"
sudo grep -Fxq 'StateDirectory=ppstime' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.service"
sudo grep -Fxq 'TimeoutStartSec=3h' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.service"
if sudo grep -Eq '^(ProtectKernelModules|RestrictSUIDSGID)=true$' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.service"; then
    printf 'PPSPi image validation error: package-incompatible maintenance sandbox\n' >&2
    exit 1
fi
sudo grep -Fxq 'ProtectSystem=strict' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance-post-boot.service"
sudo grep -Fxq 'TimeoutStartSec=4min' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance-post-boot.service"
sudo grep -Fxq 'OnCalendar=Sun *-*-* 04:00:00 UTC' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.timer"
sudo grep -Fxq 'Persistent=true' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.timer"
sudo grep -Fxq 'RandomizedDelaySec=30min' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance.timer"
sudo grep -Fxq 'OnBootSec=10min' \
    "${root_mount}/etc/systemd/system/ppstime-maintenance-post-boot.timer"
systemd-analyze calendar 'Sun *-*-* 04:00:00 UTC' > /dev/null
[[ "$(sudo stat -c '%U:%G:%a' "${root_mount}/var/lib/ppstime")" == "root:root:755" ]]
sudo grep -Fxq 'ExecStart=/usr/lib/ppstime/ppstime-healthcheck' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.service"
sudo grep -Fxq 'RuntimeDirectory=ppstime' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.service"
sudo grep -Fxq 'RuntimeDirectoryPreserve=yes' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.service"
sudo grep -Fxq 'ProtectSystem=strict' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.service"
sudo grep -Fxq 'CapabilityBoundingSet=' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.service"
sudo grep -Fxq 'OnUnitActiveSec=2min' \
    "${root_mount}/etc/systemd/system/ppstime-healthcheck.timer"
[[ "$(sudo stat -c '%U:%G:%a' "${root_mount}/etc/ppstime/health-transition.d")" == "root:root:755" ]]
health_timer_state="$(
    sudo systemctl --root="${root_mount}" is-enabled ppstime-healthcheck.timer \
        2> /dev/null || true
)"
[[ "${health_timer_state}" == "enabled" ]] || {
    printf 'PPSPi image validation error: health timer state is %s, expected enabled\n' \
        "${health_timer_state:-unknown}" >&2
    exit 1
}
maintenance_timer_state="$(
    sudo systemctl --root="${root_mount}" is-enabled ppstime-maintenance.timer \
        2> /dev/null || true
)"
[[ "${maintenance_timer_state}" == "enabled" ]] || {
    printf 'PPSPi image validation error: maintenance timer state is %s, expected enabled\n' \
        "${maintenance_timer_state:-unknown}" >&2
    exit 1
}
post_boot_timer_state="$(
    sudo systemctl --root="${root_mount}" is-enabled ppstime-maintenance-post-boot.timer \
        2> /dev/null || true
)"
[[ "${post_boot_timer_state}" == "enabled" ]] || {
    printf 'PPSPi image validation error: post-boot timer state is %s, expected enabled\n' \
        "${post_boot_timer_state:-unknown}" >&2
    exit 1
}
for apt_timer in apt-daily.timer apt-daily-upgrade.timer; do
    apt_timer_state="$(
        sudo systemctl --root="${root_mount}" is-enabled "${apt_timer}" \
            2> /dev/null || true
    )"
    [[ "${apt_timer_state}" == "disabled" ]] || {
        printf 'PPSPi image validation error: %s state is %s, expected disabled\n' \
            "${apt_timer}" "${apt_timer_state:-unknown}" >&2
        exit 1
    }
done
[[ "$(sudo stat -c '%a' "${root_mount}/etc/ppstime/ppstime.env")" == "644" ]]
sudo grep -Fxq 'HOST_DISK_WARNING_PERCENT=15.0' \
    "${root_mount}/etc/ppstime/ppstime.env"
sudo grep -qx \
    'dtoverlay=i2c-rtc,rv3028,backup-switchover-mode=3' \
    "${root_mount}/boot/firmware/config.txt"
[[ -f "${root_mount}/etc/chrony/conf.d/ppstime.conf" ]]
sudo grep -Fq \
    'refclock SOCK /run/chrony.clk.serial0.sock refid GPS' \
    "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -Fxq \
    'refclock PPS /dev/pps0 refid PPS lock GPS poll 0 dpoll 0 precision 1e-7' \
    "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -Fxq 'maxclockerror 200' "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -Fxq 'maxdistance 0.1' "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -Fxq 'allow 127.0.0.1/32' "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -Fxq 'allow ::1/128' "${root_mount}/etc/chrony/conf.d/ppstime.conf"
sudo grep -q 'GPSD_OPTIONS="-n -s 115200"' "${root_mount}/etc/default/gpsd"

ssh_state="$(sudo systemctl --root="${root_mount}" is-enabled ssh.service 2> /dev/null || true)"
[[ "${ssh_state}" == "disabled" ]] || {
    printf 'PPSPi image validation error: SSH state is %s, expected disabled\n' \
        "${ssh_state:-unknown}" >&2
    exit 1
}

first_user_hash="$(sudo awk -F: '$1 == "pi" { print $2 }' "${root_mount}/etc/shadow")"
[[ "${first_user_hash}" == '!'* || "${first_user_hash}" == '*'* ]] || {
    printf 'PPSPi image validation error: temporary pi account is not locked\n' >&2
    exit 1
}

if sudo find "${root_mount}/home" -type f -name authorized_keys -size +0c -print -quit |
    grep -q .; then
    printf 'PPSPi image validation error: image contains an authorized_keys file\n' >&2
    exit 1
fi

printf '%s\n' 'PPSPi built-image validation passed:'
printf '%s\n' '  Raspberry Pi OS Trixie arm64'
printf '%s\n' '  cloud-init-rpi image support present'
printf '%s\n' '  RTC utility and I2C userspace module configuration present'
printf '%s\n' '  PPSPi runtime and generated configuration present'
printf '%s\n' '  temporary account locked and SSH disabled'
