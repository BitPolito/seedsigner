#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# shellcheck disable=SC1091
. "${repo_root}/scripts/release.env"

if [ "$#" -ne 2 ]; then
    echo "Usage: scripts/verify-image.sh IMAGE MANIFEST" >&2
    exit 2
fi
image_path="$1"
manifest_path="$2"
[ -f "${image_path}" ] || { echo "Image not found: ${image_path}" >&2; exit 1; }
[ -f "${manifest_path}" ] || { echo "Manifest not found: ${manifest_path}" >&2; exit 1; }

manifest_value() {
    key="$1"
    awk -F= -v requested_key="${key}" '
        $1 == requested_key {
            count += 1
            value = substr($0, index($0, "=") + 1)
        }
        END {
            if (count != 1) exit 1
            print value
        }
    ' "${manifest_path}"
}

image_name="$(manifest_value image)" || { echo "Invalid image entry in manifest." >&2; exit 1; }
application_commit="$(manifest_value application_commit)" || { echo "Invalid application_commit entry." >&2; exit 1; }
os_commit="$(manifest_value os_commit)" || { echo "Invalid os_commit entry." >&2; exit 1; }
buildroot_commit="$(manifest_value buildroot_commit)" || { echo "Invalid buildroot_commit entry." >&2; exit 1; }
expected_sha256="$(manifest_value sha256)" || { echo "Invalid sha256 entry." >&2; exit 1; }

[ "${image_name}" = "$(basename -- "${image_path}")" ] || { echo "Manifest image name does not match the selected file." >&2; exit 1; }
[ "${image_name}" = "${BITPOLITO_IMAGE_NAME}" ] || { echo "Unexpected BitPolito image name: ${image_name}" >&2; exit 1; }
[ "${os_commit}" = "${SEEDSIGNER_OS_COMMIT}" ] || { echo "Manifest uses an unapproved SeedSigner OS commit." >&2; exit 1; }

for commit_value in "${application_commit}" "${os_commit}" "${buildroot_commit}"; do
    printf '%s\n' "${commit_value}" | grep -Eq '^[0-9a-f]{40}$' || {
        echo "Manifest contains an invalid commit id: ${commit_value}" >&2
        exit 1
    }
done
printf '%s\n' "${expected_sha256}" | grep -Eq '^[0-9a-f]{64}$' || {
    echo "Manifest contains an invalid SHA-256." >&2
    exit 1
}

actual_sha256="$(sha256sum "${image_path}" | awk '{print $1}')"
[ "${actual_sha256}" = "${expected_sha256}" ] || {
    echo "SHA-256 mismatch for ${image_path}" >&2
    exit 1
}

echo "Verified ${image_name}"
echo "SHA-256: ${actual_sha256}"
echo "Application commit: ${application_commit}"
echo "SeedSigner OS commit: ${os_commit}"
echo "Buildroot commit: ${buildroot_commit}"
