"""Runtime patch boundary for the development-only simulator."""

from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch
import os
import sys
import traceback

from tools.simulator.adapters import (
    QueueDisplay,
    SimulatorCamera,
    build_gpio_module,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


class SimulatorMicroSD:
    is_inserted = True

    def start_detection(self):
        return None


def _install_module(name: str, module: ModuleType, originals: dict[str, Any]):
    originals[name] = sys.modules.get(name)
    sys.modules[name] = module


def _restore_modules(originals: dict[str, Any]):
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


@contextmanager
def simulator_runtime(
    frame_queue: Any,
    input_queue: Any,
    *,
    camera_image: str | None = None,
):
    """Patch hardware boundaries while leaving all application modules untouched."""
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    originals: dict[str, Any] = {}
    gpio_module = build_gpio_module(input_queue)

    rpi_module = ModuleType("RPi")
    rpi_module.GPIO = gpio_module
    _install_module("RPi", rpi_module, originals)
    _install_module("RPi.GPIO", gpio_module, originals)

    picamera_module = ModuleType("picamera")
    picamera_module.PiCameraError = RuntimeError
    picamera_module.PiCamera = object
    picamera_array_module = ModuleType("picamera.array")
    picamera_array_module.PiRGBArray = object
    picamera_module.array = picamera_array_module
    _install_module("picamera", picamera_module, originals)
    _install_module("picamera.array", picamera_array_module, originals)

    spidev_module = ModuleType("spidev")
    spidev_module.SpiDev = object
    _install_module("spidev", spidev_module, originals)

    SimulatorCamera.configure(
        source_path=camera_image,
    )

    from seedsigner.hardware import camera as camera_module
    from seedsigner.hardware.displays.display_driver import DisplayDriverFactory
    from seedsigner.hardware.microsd import MicroSD

    microsd = SimulatorMicroSD()

    def create_display(display_type, width=None, height=None):
        return QueueDisplay(
            frame_queue,
            int(width),
            int(height),
            display_type=display_type,
        )

    patchers = [
        patch.object(
            DisplayDriverFactory,
            "instantiate_display_driver",
            side_effect=create_display,
        ),
        patch.object(MicroSD, "get_instance", return_value=microsd),
        patch.object(camera_module, "Camera", SimulatorCamera),
    ]

    try:
        for patcher in patchers:
            patcher.start()
        yield
    finally:
        SimulatorCamera.get_instance().close()
        for patcher in reversed(patchers):
            patcher.stop()
        _restore_modules(originals)


def run_application(
    frame_queue: Any,
    input_queue: Any,
    error_queue: Any,
    config: dict[str, Any],
):
    """Child-process entry point that runs the real SeedSigner main loop."""
    try:
        if str(SRC_ROOT) not in sys.path:
            sys.path.insert(0, str(SRC_ROOT))

        runtime_dir = Path(config["runtime_dir"])
        runtime_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(runtime_dir)

        with simulator_runtime(
            frame_queue,
            input_queue,
            camera_image=config.get("camera_image"),
        ):
            from seedsigner.models.settings import Settings
            from seedsigner.models.settings_definition import SettingsConstants

            Settings.SETTINGS_FILENAME = str(runtime_dir / "settings.json")
            Settings.HOSTNAME = "bitpolito-simulator"
            settings = Settings.get_instance()
            settings._data[SettingsConstants.SETTING__DISPLAY_CONFIGURATION] = (
                config["display_config"]
            )
            settings._data[SettingsConstants.SETTING__LOCALE] = config["locale"]
            settings.load_locale()

            from main import main

            main([])
    except BaseException:
        error_queue.put(traceback.format_exc())
        raise
