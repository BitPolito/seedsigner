# Tests

The test suite covers the upstream SeedSigner application, BitPolito visual
tokens and assets, simulator adapters, and screenshot generation.

From the repository root:

~~~bash
./scripts/setup-dev.sh
scripts/run-quality-gate.sh --quick
~~~

Use the release gate before publishing:

~~~bash
scripts/run-quality-gate.sh --release
~~~

Run a focused test with:

~~~bash
LD_LIBRARY_PATH=.simulator-runtime/lib .venv-simulator/bin/python -m pytest tests/test_settings.py -q
~~~

Generate screenshots only into the ignored artifacts directory:

~~~bash
.venv-simulator/bin/python -m pytest tests/screenshot_generator/generator.py \
  --locale en --screenshot-output artifacts/screenshots/en
~~~

Generate the coverage report with:

~~~bash
./tests/run_full_coverage.sh
~~~

The HTML report is written to artifacts/coverage/html/.
