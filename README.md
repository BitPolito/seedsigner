# BitPolito SeedSigner

BitPolito SeedSigner is a visual customization of
[SeedSigner](https://github.com/SeedSigner/seedsigner) 0.8.7. It preserves the
official wallet, QR, PSBT, camera, GPIO and display behavior while adding the
BitPolito blue-and-white theme, branding assets and a 30-second screensaver.

## Download

Download the latest Raspberry Pi Zero image from the
[latest BitPolito release](https://github.com/BitPolito/seedsigner/releases/latest).
Before flashing, verify the image with the SHA-256 file published alongside it.

## Simulator

The simulator runs the real SeedSigner application with in-memory desktop
adapters. It does not build or emulate the SeedSigner OS.

~~~bash
./scripts/setup-dev.sh
.venv-simulator/bin/python tools/simulator/run_simulator.py
~~~

Run a headless smoke test:

~~~bash
.venv-simulator/bin/python tools/simulator/run_simulator.py --headless-smoke
~~~

The default display is ST7789 240x240. ST7789 320x240 and ILI9341 320x240 are
also supported. See the [simulator guide](tools/simulator/README.md) for camera
fixtures and additional options.

## Contributing

Development happens in the BitPolito repository only. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Upstream

- [SeedSigner application](https://github.com/SeedSigner/seedsigner)
- [SeedSigner OS](https://github.com/SeedSigner/seedsigner-os)
- [SeedSigner documentation](https://seedsigner.com/)

SeedSigner is released under the MIT License. BitPolito retains the upstream
attribution and license; see [LICENSE.md](LICENSE.md).
