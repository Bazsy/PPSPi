#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SOURCE_ROOT
readonly PI_GEN_REPOSITORY="https://github.com/RPi-Distro/pi-gen.git"
PI_GEN_COMMIT="$(tr -d '[:space:]' < "${SOURCE_ROOT}/pi-gen/PI_GEN_COMMIT")"
readonly PI_GEN_COMMIT

version="$(tr -d '[:space:]' < "${SOURCE_ROOT}/VERSION")"
output_dir="${SOURCE_ROOT}/artifacts"
checkout_dir="${SOURCE_ROOT}/.pi-gen/checkout"
prepare_only="false"
image_url=""
readonly SEMVER_RE='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'

usage() {
    cat << 'EOF'
Usage: ./scripts/build-image.sh [options]

Options:
  --version VERSION       Artifact version (default: VERSION file).
  --output-dir PATH       Packaged output directory (default: artifacts).
  --checkout-dir PATH     Reusable pi-gen checkout location.
    --image-url URL         Add an Imager manifest for this release image URL.
  --prepare-only          Prepare and validate pi-gen without running Docker.
  -h, --help              Show this help.
EOF
}

die() {
    printf 'PPSPi image build error: %s\n' "$*" >&2
    exit 1
}

while (($# > 0)); do
    case "$1" in
        --version)
            (($# >= 2)) || die "--version requires a value"
            version="${2#v}"
            shift 2
            ;;
        --output-dir)
            (($# >= 2)) || die "--output-dir requires a value"
            output_dir="$2"
            shift 2
            ;;
        --checkout-dir)
            (($# >= 2)) || die "--checkout-dir requires a value"
            checkout_dir="$2"
            shift 2
            ;;
        --image-url)
            (($# >= 2)) || die "--image-url requires a value"
            image_url="$2"
            shift 2
            ;;
        --prepare-only)
            prepare_only="true"
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

[[ "${version}" =~ ${SEMVER_RE} ]] || die "version must be valid semantic versioning"
command -v git > /dev/null 2>&1 || die "git is required"
command -v tar > /dev/null 2>&1 || die "tar is required"
command -v python3 > /dev/null 2>&1 || die "python3 is required"
if [[ -n "$(git -C "${SOURCE_ROOT}" status --porcelain --untracked-files=normal)" && "${ALLOW_DIRTY:-0}" != "1" ]]; then
    die "source tree is not clean; commit changes or set ALLOW_DIRTY=1 for a non-release build"
fi

mkdir -p "$(dirname "${checkout_dir}")"
if [[ ! -d "${checkout_dir}/.git" ]]; then
    git clone --filter=blob:none "${PI_GEN_REPOSITORY}" "${checkout_dir}"
fi
git -C "${checkout_dir}" fetch --depth=1 origin "${PI_GEN_COMMIT}"
git -C "${checkout_dir}" checkout --detach --force "${PI_GEN_COMMIT}"
git -C "${checkout_dir}" clean -ffdqx
[[ "$(git -C "${checkout_dir}" rev-parse HEAD)" == "${PI_GEN_COMMIT}" ]] ||
    die "pi-gen checkout does not match the pinned commit"

cp -a "${SOURCE_ROOT}/pi-gen/stage-pps-pi" "${checkout_dir}/stage-pps-pi"
# Stage 2 is still built as the base for PPSPi, but its EXPORT_IMAGE would
# create an intermediate *-lite image in addition to the final PPSPi image.
touch "${checkout_dir}/stage2/SKIP_IMAGES"
payload_dir="${checkout_dir}/stage-pps-pi/01-install/files"
mkdir -p "${payload_dir}"
tar \
    --exclude-vcs \
    --exclude='./.pi-gen' \
    --exclude='./artifacts' \
    --exclude='./build' \
    --exclude='./dist' \
    -czf "${payload_dir}/ppspi-source.tar.gz" \
    -C "${SOURCE_ROOT}" .

git_commit="$(git -C "${SOURCE_ROOT}" rev-parse HEAD)"
build_date_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
python3 "${SCRIPT_DIR}/build-info.py" \
    --output "${payload_dir}/build-info.json" \
    --project-version "${version}" \
    --git-commit "${git_commit}" \
    --build-date-utc "${build_date_utc}" \
    --pi-gen-commit "${PI_GEN_COMMIT}"

image_name="ppspi-${version}-raspios-trixie-arm64"
cat > "${checkout_dir}/config-ppspi" << EOF
IMG_NAME='${image_name}'
PI_GEN_RELEASE='PPSPi ${version}'
RELEASE='trixie'
ARCH='arm64'
TARGET_HOSTNAME='ppspi'
LOCALE_DEFAULT='en_GB.UTF-8'
KEYBOARD_KEYMAP='gb'
TIMEZONE_DEFAULT='UTC'
FIRST_USER_NAME='pi'
DISABLE_FIRST_BOOT_USER_RENAME=0
ENABLE_SSH=0
ENABLE_CLOUD_INIT=1
STAGE_LIST='stage0 stage1 stage2 stage-pps-pi'
DEPLOY_COMPRESSION='xz'
COMPRESSION_LEVEL=6
EOF

if [[ "${prepare_only}" == "true" ]]; then
    printf 'Prepared pinned pi-gen checkout at %s\n' "${checkout_dir}"
    exit 0
fi
command -v docker > /dev/null 2>&1 || die "Docker is required for image builds"
docker info > /dev/null 2>&1 || die "Docker daemon is unavailable or access is denied"

(
    cd "${checkout_dir}"
    PRESERVE_CONTAINER=0 CONTINUE=0 ./build-docker.sh -c config-ppspi
)

if ! image_path="$(
    python3 "${SCRIPT_DIR}/select-image.py" \
        --deploy-dir "${checkout_dir}/deploy" \
        --image-name "${image_name}"
)"; then
    die "could not select the final pi-gen image"
fi
package_args=(
    --image "${image_path}"
    --build-info "${payload_dir}/build-info.json"
    --version "${version}"
    --output-dir "${output_dir}"
)
if [[ -n "${image_url}" ]]; then
    package_args+=(--image-url "${image_url}")
fi
"${SCRIPT_DIR}/package-release.sh" "${package_args[@]}"
