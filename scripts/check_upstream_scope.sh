#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
# shellcheck disable=SC1091
. "${script_dir}/release.env"
cd "${repo_root}"

# Official SeedSigner 0.8.7 application commit. This is a read-only comparison
# point: the script never fetches from or writes to the upstream repository.
BASE_COMMIT="${SEEDSIGNER_APP_BASE_COMMIT}"
EXPECTED_CONTROLLER_DIFF_SHA256="127d24daf15d82e54224bf4a4a9688d32c220f38b4234932099483c927fa1b9b"

if ! git cat-file -e "${BASE_COMMIT}^{commit}" 2>/dev/null; then
    echo "Missing official SeedSigner 0.8.7 base commit: ${BASE_COMMIT}" >&2
    exit 1
fi

PROTECTED_PATHS="
src/seedsigner/models/settings_definition.py
src/seedsigner/gui/renderer.py
src/seedsigner/hardware/camera.py
src/seedsigner/hardware/pivideostream.py
src/seedsigner/hardware/buttons.py
src/seedsigner/hardware/displays
src/seedsigner/models/encode_qr.py
src/seedsigner/models/decode_qr.py
src/seedsigner/models/seed.py
src/seedsigner/models/seed_storage.py
src/seedsigner/models/psbt_parser.py
"
for protected_path in ${PROTECTED_PATHS}; do
    if ! git diff --quiet "${BASE_COMMIT}" -- "${protected_path}"; then
        echo "Protected official runtime file changed: ${protected_path}" >&2
        exit 1
    fi
done

controller_diff_sha256="$(
    git diff "${BASE_COMMIT}" -- src/seedsigner/controller.py |
        sha256sum |
        cut -d " " -f 1
)"
if [ "${controller_diff_sha256}" != "${EXPECTED_CONTROLLER_DIFF_SHA256}" ]; then
    echo "controller.py contains changes beyond version and 30-second timeout" >&2
    exit 1
fi

list_file="$(mktemp)"
trap 'rm -f "${list_file}"' EXIT HUP INT TERM

{
    git diff --name-only "${BASE_COMMIT}" --
    git ls-files --others --exclude-standard
} | sort -u > "${list_file}"

while IFS= read -r path; do
    [ -n "${path}" ] || continue
    case "${path}" in
        README.md|\
        CONTRIBUTING.md|\
        .gitignore|\
        .github/workflows/build.yml|\
        .github/workflows/tests.yml|\
        pyproject.toml|\
        scripts/build-pi0.sh|\
        scripts/build-review-sheets.py|\
        scripts/check_upstream_scope.sh|\
        scripts/release.env|\
        scripts/run-quality-gate.sh|\
        scripts/setup-dev.sh|\
        scripts/verify-image.sh|\
        src/seedsigner/controller.py|\
        src/seedsigner/views/screensaver.py|\
        src/seedsigner/gui/components.py|\
        src/seedsigner/gui/keyboard.py|\
        src/seedsigner/gui/screens/psbt_screens.py|\
        src/seedsigner/gui/screens/screen.py|\
        src/seedsigner/gui/screens/seed_screens.py|\
        src/seedsigner/gui/screens/settings_screens.py|\
        src/seedsigner/gui/screens/tools_screens.py|\
        src/seedsigner/gui/toast.py|\
        src/seedsigner/resources/img/bitpolito_splash.png|\
        src/seedsigner/resources/img/cow.png|\
        src/seedsigner/resources/img/partners/bitpolito_logo.png|\
        tests/*|\
        tools/simulator/*|\
        design/*|\
        docs/bitpolito-*)
            ;;
        *)
            echo "Out-of-scope change relative to SeedSigner 0.8.7: ${path}" >&2
            exit 1
            ;;
    esac
done < "${list_file}"

echo "BitPolito diff scope is valid relative to ${BASE_COMMIT}."
