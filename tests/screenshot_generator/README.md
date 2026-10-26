# Screenshot Generator

After `scripts/setup-dev.sh`, run from the project root:

```bash
# Generate the English review input
.venv-simulator/bin/python -m pytest tests/screenshot_generator/generator.py \
  --locale en --screenshot-output artifacts/screenshots/en

# Rebuild the checked-in sheets for the current theme revision
.venv-simulator/bin/python scripts/build-review-sheets.py \
  --input artifacts/screenshots/en
```

Use the release gate to generate all locales, or run the generator without
`--locale` into a fresh ignored directory:

```bash
.venv-simulator/bin/python -m pytest tests/screenshot_generator/generator.py \
  --screenshot-output artifacts/screenshots/all
```

Never write generated files into the official screenshot submodule. Raw PNGs
remain local or CI artifacts; only the current compact English sheets and
manifest belong in `design/review/`. For coverage use
`./tests/run_full_coverage.sh`; see [the test guide](../README.md).
