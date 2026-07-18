#!/usr/bin/env bash
set -Eeuo pipefail

if [ ! -d "${ROOTFS_DIR}" ]; then
    copy_previous
fi
