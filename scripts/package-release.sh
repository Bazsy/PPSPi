#!/usr/bin/env bash
set -Eeuo pipefail

input_image=""
build_info=""
version=""
output_dir="artifacts"
readonly SEMVER_RE='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'

usage() {
    cat << 'EOF'
Usage: ./scripts/package-release.sh --image PATH --build-info PATH --version VERSION [options]

Options:
  --output-dir PATH  Destination directory (default: artifacts).
  -h, --help         Show this help.
EOF
}

die() {
    printf 'PPSPi package error: %s\n' "$*" >&2
    exit 1
}

while (($# > 0)); do
    case "$1" in
        --image)
            (($# >= 2)) || die "--image requires a value"
            input_image="$2"
            shift 2
            ;;
        --build-info)
            (($# >= 2)) || die "--build-info requires a value"
            build_info="$2"
            shift 2
            ;;
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
        -h | --help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

[[ -f "${input_image}" ]] || die "image not found: ${input_image}"
[[ "${input_image}" == *.img.xz ]] || die "image must use the .img.xz format"
[[ -f "${build_info}" ]] || die "build metadata not found: ${build_info}"
[[ "${version}" =~ ${SEMVER_RE} ]] || die "version must be valid semantic versioning"
command -v xz > /dev/null 2>&1 || die "xz is required"
xz --test "${input_image}" || die "image failed XZ integrity validation"
python3 -c '
import json, sys
metadata = json.load(open(sys.argv[1], encoding="utf-8"))
required = {"project_version", "git_commit", "build_date_utc", "pi_gen_commit", "raspberry_pi_os_release", "architecture", "default_profile"}
missing = sorted(required - metadata.keys())
if missing:
    raise SystemExit("missing build metadata: " + ", ".join(missing))
if metadata["project_version"] != sys.argv[2]:
    raise SystemExit("build metadata version does not match requested version")
' "${build_info}" "${version}" || die "build metadata validation failed"

mkdir -p "${output_dir}"
artifact_name="ppspi-${version}-raspios-bookworm-arm64.img.xz"
artifact_path="${output_dir%/}/${artifact_name}"
cp --reflink=auto "${input_image}" "${artifact_path}"
cp "${build_info}" "${output_dir%/}/build-info.json"
(
    cd "${output_dir}"
    sha256sum "${artifact_name}" > "${artifact_name}.sha256"
)

printf '%s\n' "${artifact_path}" "${artifact_path}.sha256" "${output_dir%/}/build-info.json"
