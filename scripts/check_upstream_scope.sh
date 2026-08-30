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

list_file="$(mktemp)"
controller_changes_file="$(mktemp)"
expected_controller_changes_file="$(mktemp)"
cleanup() {
    rm -f "${list_file}" "${controller_changes_file}" "${expected_controller_changes_file}"
}
trap 'cleanup' EXIT HUP INT TERM

# Compare the actual changed lines instead of hashing the complete diff output.
# Git versions and local diff settings can format hunk headers differently on
# the developer machine and on GitHub Actions, while the allowed source change
# itself remains identical.
git diff --unified=0 "${BASE_COMMIT}" -- src/seedsigner/controller.py |
    awk '/^@@/ { in_hunk = 1; next } in_hunk && /^[+-][^-+]/ { print }' |
    sed 's/[[:space:]]*$//' |
    sort > "${controller_changes_file}"
{
    printf '%s\n' "+_SCREENSAVER_ACTIVATION_MS = 30 * 1000"
    printf '%s\n' '-    VERSION = "0.8.7"'
    printf '%s\n' "+    VERSION = \"${BITPOLITO_VERSION}\""
    printf '%s\n' '-        controller.screensaver_activation_ms = 2 * 60 * 1000  # two minutes'
    printf '%s\n' '+        controller.screensaver_activation_ms = _SCREENSAVER_ACTIVATION_MS'
} | sort > "${expected_controller_changes_file}"
if ! diff -u "${expected_controller_changes_file}" "${controller_changes_file}"; then
    echo "controller.py contains changes beyond version and 30-second timeout" >&2
    exit 1
fi

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
