#!/usr/bin/env bash
set -Eeuo pipefail

install -d -m 0755 "${ROOTFS_DIR}/opt/ppspi-source"
tar -xzf files/ppspi-source.tar.gz -C "${ROOTFS_DIR}/opt/ppspi-source"

on_chroot << 'EOF'
/opt/ppspi-source/scripts/install.sh --skip-packages
EOF

install -D -m 0644 files/build-info.json "${ROOTFS_DIR}/etc/ppstime/build-info.json"
rm -rf "${ROOTFS_DIR}/opt/ppspi-source"
