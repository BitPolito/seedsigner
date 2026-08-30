# BitPolito SeedSigner simulator

The simulator runs the real SeedSigner application with in-memory desktop
adapters for display, buttons, camera and microSD. It is development-only and
is never copied into the SeedSigner OS image.

## Prerequisites

- Python 3.10-3.12;
- repository submodules;
- a working virtual environment;
- native zbar for QR decoding;
- a desktop display for interactive mode, or headless mode in CI.

On Debian/Ubuntu install zbar with `sudo apt install libzbar0`; on Fedora use
`sudo dnf install zbar`.

## Setup

From the repository root:

~~~bash
./scripts/setup-dev.sh
~~~

The script installs application, test and simulator dependencies and compiles
translations.

## Run

Interactive mode:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py
~~~

If a native window is unavailable, use the browser UI explicitly:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py --ui web
~~~

Headless smoke test:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py --headless-smoke
~~~

Choose an official display configuration:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py --display-config st7789_320x240
.venv-simulator/bin/python tools/simulator/run_simulator.py --display-config ili9341_320x240
~~~

Use a deterministic camera fixture:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py \
  --headless-smoke --smoke-flow scan --smoke-timeout 20 \
  --camera-image tests/fixtures/bitpolito-settings-qr.png
~~~

The default configuration is ST7789 240x240. The simulator validates the
rendered RGB framebuffer and keeps settings in a temporary directory.

## Safety

A desktop is not air-gapped and does not reproduce Raspberry Pi hardware
security. Never enter real seeds, private keys or funds. Use test data only.
