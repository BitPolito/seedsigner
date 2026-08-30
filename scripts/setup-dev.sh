#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
venv_path="${BITPOLITO_VENV:-${repo_root}/.venv-simulator}"
bootstrap_python="${BITPOLITO_BOOTSTRAP_PYTHON:-python3.12}"

usage() {
    printf '%s\n' "Usage: scripts/setup-dev.sh" \
        "Initializes official submodules and the local Python environment."
}

for argument in "$@"; do
    case "${argument}" in
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: ${argument}" >&2; usage >&2; exit 2 ;;
    esac
done

if ! command -v "${bootstrap_python}" >/dev/null 2>&1; then
    echo "Missing ${bootstrap_python}. Install Python 3.12 or set BITPOLITO_BOOTSTRAP_PYTHON." >&2
    exit 1
fi
"${bootstrap_python}" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else "Python 3.10 through 3.12 is required")'

git -C "${repo_root}" submodule sync --recursive
git -C "${repo_root}" submodule update --init --recursive src/seedsigner/resources/seedsigner-translations
git -C "${repo_root}" -c submodule.seedsigner-screenshots.update=checkout submodule update --init --recursive seedsigner-screenshots

if [ ! -x "${venv_path}/bin/python" ]; then
    "${bootstrap_python}" -m venv "${venv_path}"
fi
python_bin="${venv_path}/bin/python"
"${python_bin}" -m pip install --upgrade pip
"${python_bin}" -m pip install \
    -r "${repo_root}/requirements.txt" \
    -r "${repo_root}/tests/requirements.txt" \
    -r "${repo_root}/l10n/requirements-l10n.txt" \
    -r "${repo_root}/tools/simulator/requirements-simulator.txt"
"${python_bin}" -m pip install -e "${repo_root}"
(cd "${repo_root}" && "${python_bin}" setup.py compile_catalog)

if ! "${python_bin}" -c 'from ctypes.util import find_library; raise SystemExit(0 if find_library("zbar") else 1)'; then
    echo "Warning: zbar was not found. Install the system zbar library before scan tests." >&2
fi

echo "Development environment ready: ${venv_path}"
echo "Quick gate: ${repo_root}/scripts/run-quality-gate.sh --quick"
echo "Simulator:  ${python_bin} ${repo_root}/tools/simulator/run_simulator.py"
