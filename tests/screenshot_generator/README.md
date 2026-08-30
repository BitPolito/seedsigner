# Screenshot Generator

From the project root, run:
```bash
# Generate screenshots for a specific locale
pytest tests/screenshot_generator/generator.py --locale es --screenshot-output artifacts/screenshots/es

# Generate screenshots for all supported locales
pytest tests/screenshot_generator/generator.py --screenshot-output artifacts/screenshots/all
```

You can also run a `coverage` report to see exactly what the screenshots are and are not hitting:
```bash
coverage erase
coverage run -m pytest tests/screenshot_generator/generator.py --locale es --screenshot-output artifacts/screenshots/es && coverage combine && coverage report

# Generate the interactive html report
coverage html
```

Always select an ignored output directory when generating screenshots locally;
never write generated files into the tracked screenshot submodule:

```bash
pytest tests/screenshot_generator/generator.py \
  --screenshot-output artifacts/screenshots
```
