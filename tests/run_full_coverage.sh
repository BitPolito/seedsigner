#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python_bin="${BITPOLITO_PYTHON:-${repo_root}/.venv-simulator/bin/python}"
coverage_dir="${BITPOLITO_ARTIFACTS_DIR:-${repo_root}/artifacts}/coverage"

if [ ! -x "${python_bin}" ] && ! command -v "${python_bin}" >/dev/null 2>&1; then
    echo "Python environment not found: ${python_bin}" >&2
    exit 1
fi

mkdir -p "${coverage_dir}"
cd "${repo_root}"
"${python_bin}" -m coverage erase
"${python_bin}" -m coverage run --parallel -m pytest
"${python_bin}" -m coverage run --parallel -m pytest tests/bitpolito_visual_checks.py
"${python_bin}" -m coverage run --parallel -m pytest tests/screenshot_generator/generator.py --locale es
"${python_bin}" -m coverage combine
"${python_bin}" -m coverage report
"${python_bin}" -m coverage html --directory "${coverage_dir}/html"
echo "Coverage report: ${coverage_dir}/html/index.html"
