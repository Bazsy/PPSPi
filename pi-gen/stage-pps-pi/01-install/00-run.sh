#!/usr/bin/env bash
set -Eeuo pipefail

install -d -m 0755 "${ROOTFS_DIR}/opt/ppspi-source"
tar -xzf files/ppspi-source.tar.gz -C "${ROOTFS_DIR}/opt/ppspi-source"

on_chroot << 'EOF'
/opt/ppspi-source/scripts/install.sh --skip-packages

# Raspberry Pi cloud-init 25.2-1~bpo13+1+rpt20 lists this final module but does
# not ship it. Remove the stale entry only while the import is unavailable so a
# successful first boot reports "done" rather than recoverable degradation.
if grep -qE '^[[:space:]]*-[[:space:]]*netplan_nm_patch[[:space:]]*$' /etc/cloud/cloud.cfg &&
	! python3 -c 'import cloudinit.config.cc_netplan_nm_patch' 2> /dev/null; then
	sed -i -E '/^[[:space:]]*-[[:space:]]*netplan_nm_patch[[:space:]]*$/d' \
		/etc/cloud/cloud.cfg
fi
EOF

install -D -m 0644 files/build-info.json "${ROOTFS_DIR}/etc/ppstime/build-info.json"
rm -rf "${ROOTFS_DIR}/opt/ppspi-source"
