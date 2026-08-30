#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# shellcheck disable=SC1091
. "${repo_root}/scripts/release.env"

check_only=0
case "${1:-}" in
    "") ;;
    --check) check_only=1 ;;
    -h|--help)
        printf '%s\n' "Usage: scripts/build-pi0.sh [--check]" \
            "Builds the committed and pushed BitPolito source through the pinned official SeedSigner OS."
        exit 0
        ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo "Too many arguments." >&2; exit 2; }

build_root="${BITPOLITO_BUILD_ROOT:-${repo_root}/.build/pi0}"
artifact_root="${BITPOLITO_RELEASE_DIR:-${repo_root}/artifacts/release/${BITPOLITO_VERSION}}"
os_dir="${build_root}/seedsigner-os"
app_commit="$(git -C "${repo_root}" rev-parse HEAD)"
ready=1

require_tool() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required tool: $1" >&2
        ready=0
    fi
}
require_tool git
require_tool docker
require_tool sha256sum

if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but the daemon is unavailable to this user." >&2
    ready=0
fi
if ! git -C "${repo_root}" diff --quiet ||
   ! git -C "${repo_root}" diff --cached --quiet ||
   [ -n "$(git -C "${repo_root}" ls-files --others --exclude-standard)" ]; then
    echo "The application working tree must be clean and committed." >&2
    ready=0
fi
submodule_state="$(git -C "${repo_root}" submodule status --recursive)"
if printf '%s\n' "${submodule_state}" | grep -Eq '^[+-U]'; then
    echo "Submodules must be initialized at their recorded commits." >&2
    ready=0
fi
if ! git -C "${repo_root}" show "${app_commit}:src/seedsigner/controller.py" 2>/dev/null |
    grep -Fq "VERSION = \"${BITPOLITO_VERSION}\""; then
    echo "Committed Controller.VERSION does not match scripts/release.env." >&2
    ready=0
fi
if ! git -C "${repo_root}" show "${app_commit}:design/bitpolito-theme.json" 2>/dev/null |
    grep -Fq "\"release\": \"${BITPOLITO_VERSION}\""; then
    echo "Committed theme manifest does not match scripts/release.env." >&2
    ready=0
fi
if ! remote_refs="$(git ls-remote "${BITPOLITO_APP_REPOSITORY}" 2>/dev/null)"; then
    echo "Cannot read the public BitPolito repository: ${BITPOLITO_APP_REPOSITORY}" >&2
    ready=0
elif ! printf '%s\n' "${remote_refs}" | awk -v commit="${app_commit}" '$1 == commit { found=1 } END { exit(found ? 0 : 1) }'; then
    echo "Current commit is not the tip of a published BitPolito ref: ${app_commit}" >&2
    ready=0
fi

if [ "${ready}" -ne 1 ]; then
    echo "Pi Zero image preflight failed." >&2
    exit 1
fi
"${repo_root}/scripts/check_upstream_scope.sh"

echo "Pi Zero build preflight passed."
echo "Application: ${app_commit}"
echo "SeedSigner OS: ${SEEDSIGNER_OS_COMMIT}"
echo "Output: ${artifact_root}/${BITPOLITO_IMAGE_NAME}"
if [ "${check_only}" -eq 1 ]; then
    exit 0
fi

"${repo_root}/scripts/run-quality-gate.sh" --release

mkdir -p "${build_root}" "${artifact_root}" "${build_root}/buildroot_dl" "${build_root}/ccache"
for final_path in \
    "${artifact_root}/${BITPOLITO_IMAGE_NAME}" \
    "${artifact_root}/${BITPOLITO_MANIFEST_NAME}" \
    "${artifact_root}/${BITPOLITO_SHA256_NAME}"; do
    [ ! -e "${final_path}" ] || {
        echo "Refusing to overwrite existing release artifact: ${final_path}" >&2
        exit 1
    }
done

if [ ! -d "${os_dir}/.git" ]; then
    [ ! -e "${os_dir}" ] || {
        echo "Build path exists but is not a SeedSigner OS checkout: ${os_dir}" >&2
        exit 1
    }
    git clone https://github.com/SeedSigner/seedsigner-os.git "${os_dir}"
else
    git -C "${os_dir}" fetch --tags origin
fi
git -C "${os_dir}" checkout --detach "${SEEDSIGNER_OS_COMMIT}"
git -C "${os_dir}" submodule sync --recursive
git -C "${os_dir}" submodule update --init --recursive
[ "$(git -C "${os_dir}" rev-parse HEAD)" = "${SEEDSIGNER_OS_COMMIT}" ] || {
    echo "SeedSigner OS checkout does not match the pinned commit." >&2
    exit 1
}

buildroot_commit="$(git -C "${os_dir}/opt/buildroot" rev-parse HEAD)"
stage_dir="$(mktemp -d "${build_root}/images.XXXXXX")"
cleanup() {
    case "${stage_dir}" in
        "${build_root}"/images.*) rm -rf -- "${stage_dir}" ;;
    esac
}
trap cleanup EXIT HUP INT TERM

docker_tag="bitpolito-seedsigner-os:$(printf '%s' "${SEEDSIGNER_OS_COMMIT}" | cut -c1-12)"
DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/amd64}"
export DOCKER_DEFAULT_PLATFORM
docker build --platform linux/amd64 -t "${docker_tag}" "${os_dir}"
docker run \
    --rm \
    -v "${os_dir}/opt:/opt" \
    -v "${stage_dir}:/images" \
    -v "${build_root}/buildroot_dl:/buildroot_dl" \
    -v "${build_root}/ccache:/root/.buildroot-ccache" \
    "${docker_tag}" \
    --pi0 \
    --app-repo="${BITPOLITO_APP_REPOSITORY}" \
    --app-commit-id="${app_commit}" \
    --no-clean

source_image="${stage_dir}/seedsigner_os.${app_commit}.pi0.img"
[ -f "${source_image}" ] || {
    echo "Official OS build did not produce the expected Pi Zero image." >&2
    exit 1
}
cp "${source_image}" "${artifact_root}/${BITPOLITO_IMAGE_NAME}"
(
    cd "${artifact_root}"
    sha256sum "${BITPOLITO_IMAGE_NAME}" > "${BITPOLITO_SHA256_NAME}"
)
image_sha256="$(sha256sum "${artifact_root}/${BITPOLITO_IMAGE_NAME}" | awk '{print $1}')"
{
    echo "image=${BITPOLITO_IMAGE_NAME}"
    echo "application_commit=${app_commit}"
    echo "os_commit=${SEEDSIGNER_OS_COMMIT}"
    echo "buildroot_commit=${buildroot_commit}"
    echo "sha256=${image_sha256}"
} > "${artifact_root}/${BITPOLITO_MANIFEST_NAME}"

"${repo_root}/scripts/verify-image.sh" \
    "${artifact_root}/${BITPOLITO_IMAGE_NAME}" \
    "${artifact_root}/${BITPOLITO_MANIFEST_NAME}"
echo "Pi Zero candidate created in ${artifact_root}"
