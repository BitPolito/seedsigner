#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# shellcheck disable=SC1091
. "${repo_root}/scripts/release.env"
mode="quick"

usage() {
    printf '%s\n' "Usage: scripts/run-quality-gate.sh [--quick|--release]" \
        "--quick: core tests and 240x240 startup, Settings and scan smokes." \
        "--release: all displays, real screensaver timeout and all locales."
}

for argument in "$@"; do
    case "${argument}" in
        --quick) mode="quick" ;;
        --release) mode="release" ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: ${argument}" >&2; usage >&2; exit 2 ;;
    esac
done

python_bin="${BITPOLITO_PYTHON:-${repo_root}/.venv-simulator/bin/python}"
artifact_dir="${BITPOLITO_ARTIFACTS_DIR:-${repo_root}/artifacts/quality}"
if [ ! -x "${python_bin}" ] && ! command -v "${python_bin}" >/dev/null 2>&1; then
    echo "Python environment not found: ${python_bin}" >&2
    echo "Run scripts/setup-dev.sh first or set BITPOLITO_PYTHON." >&2
    exit 1
fi
if [ -d "${repo_root}/.simulator-runtime/lib" ]; then
    LD_LIBRARY_PATH="${repo_root}/.simulator-runtime/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
    export LD_LIBRARY_PATH
fi

mkdir -p "${artifact_dir}"
cd "${repo_root}"
echo "BitPolito quality gate (${mode}) with $("${python_bin}" --version 2>&1)"
"${python_bin}" setup.py compile_catalog
"${python_bin}" -m compileall -q -x 'seedsigner-translations' src tools/simulator tests
./scripts/check_upstream_scope.sh
git diff --check
"${python_bin}" -m pytest --ignore=tests/bitpolito_visual_checks.py --ignore=tests/test_simulator.py -q
"${python_bin}" -m pytest tests/bitpolito_visual_checks.py -q
"${python_bin}" -m pytest tests/test_simulator.py -q

run_startup_smoke() {
    display_config="$1"
    "${python_bin}" tools/simulator/run_simulator.py \
        --headless-smoke \
        --display-config "${display_config}" \
        --screenshot "${artifact_dir}/simulator-startup-${display_config}.png"
}
run_settings_smoke() {
    display_config="$1"
    "${python_bin}" tools/simulator/run_simulator.py \
        --headless-smoke \
        --smoke-flow settings \
        --display-config "${display_config}" \
        --screenshot "${artifact_dir}/simulator-settings-${display_config}.png"
}
run_scan_smoke() {
    display_config="$1"
    "${python_bin}" tools/simulator/run_simulator.py \
        --headless-smoke \
        --smoke-flow scan \
        --smoke-timeout 20 \
        --camera-image tests/fixtures/bitpolito-settings-qr.png \
        --display-config "${display_config}" \
        --screenshot "${artifact_dir}/simulator-scan-${display_config}.png"
}

run_startup_smoke st7789_240x240
run_settings_smoke st7789_240x240
run_scan_smoke st7789_240x240

if [ "${mode}" = "release" ]; then
    for display_config in st7789_320x240 ili9341_320x240; do
        run_startup_smoke "${display_config}"
        run_settings_smoke "${display_config}"
        run_scan_smoke "${display_config}"
    done
    for display_config in st7789_240x240 st7789_320x240 ili9341_320x240; do
        "${python_bin}" tools/simulator/run_simulator.py \
            --headless-smoke \
            --smoke-flow screensaver \
            --display-config "${display_config}"
    done
    screenshot_dir="$(mktemp -d "${artifact_dir}/screenshots.XXXXXX")"
    "${python_bin}" -m pytest tests/screenshot_generator/generator.py \
        --screenshot-output "${screenshot_dir}" \
        -q
    echo "Generated screenshots: ${screenshot_dir}"
fi

if [ -n "$(git -C seedsigner-screenshots status --porcelain)" ]; then
    echo "Screenshot submodule was modified by the quality gate." >&2
    exit 1
fi
echo "BitPolito ${mode} quality gate passed for ${BITPOLITO_VERSION}."
