from pathlib import Path
import importlib
import json
import sys
from queue import Queue
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from tools.simulator.adapters import (
    QueueGPIO,
    QueueDisplay,
    SUPPORTED_DISPLAY_CONFIGS,
    SimulatorButtonPins,
    SimulatorCamera,
    image_from_payload,
)
from tools.simulator.runtime import simulator_runtime
from tools.simulator.web_ui import SimulatorWebServer


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_queue_display_emits_latest_rgb_frame():
    frames = Queue(maxsize=1)
    display = QueueDisplay(frames, 240, 240)

    display.show_image(Image.new("RGBA", (240, 240), "#001CE0"))
    payload = frames.get_nowait()
    frame = image_from_payload(payload)

    assert frame.mode == "RGB"
    assert frame.size == (240, 240)
    assert frame.getpixel((0, 0)) == (0, 28, 224)


def test_queue_gpio_matches_hardware_button_active_low_contract():
    events = Queue()
    gpio = QueueGPIO(events)
    pin = 31

    gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_UP)
    assert gpio.input(pin) == gpio.HIGH

    events.put((pin, gpio.LOW))
    assert gpio.input(pin) == gpio.LOW

    events.put((pin, gpio.HIGH))
    assert gpio.input(pin) == gpio.HIGH


def test_queue_gpio_preserves_a_fast_press_and_release():
    events = Queue()
    gpio = QueueGPIO(events)
    pressed_pin = SimulatorButtonPins.KEY_DOWN
    other_pin = SimulatorButtonPins.KEY_UP

    gpio.setup(pressed_pin, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(other_pin, gpio.IN, pull_up_down=gpio.PUD_UP)
    events.put((pressed_pin, gpio.LOW))
    events.put((pressed_pin, gpio.HIGH))

    # The GPIO loop may poll a different key first. The fast click must still
    # expose LOW once when it reaches the intended pin.
    assert gpio.input(other_pin) == gpio.HIGH
    assert gpio.input(pressed_pin) == gpio.LOW
    assert gpio.input(pressed_pin) == gpio.HIGH


def test_native_zbar_decodes_a_generated_qr():
    import qrcode
    from pyzbar.pyzbar import ZBarSymbol, decode

    payload = b"bitpolito-zbar-smoke"
    image = qrcode.make(payload.decode()).convert("RGB")
    decoded = decode(image, symbols=[ZBarSymbol.QRCODE])

    assert [result.data for result in decoded] == [payload]


def test_simulator_camera_supports_pil_and_numpy_frames(tmp_path):
    source = tmp_path / "camera.png"
    Image.new("RGB", (300, 200), "#001CE0").save(source)

    SimulatorCamera.configure(source_path=str(source))
    with patch(
        "seedsigner.models.settings.Settings.get_instance"
    ) as get_settings:
        get_settings.return_value.get_value.return_value = 0
        camera = SimulatorCamera.get_instance()

    camera.start_video_stream_mode(resolution=(240, 240), format="rgb")
    image_frame = camera.read_video_stream(as_image=True)
    array_frame = camera.read_video_stream(as_image=False)

    assert image_frame.mode == "RGBA"
    assert image_frame.size == (240, 240)
    assert isinstance(array_frame, np.ndarray)
    assert array_frame.shape == (240, 240, 3)
    camera.close()


def test_runtime_patches_display_factory_without_touching_driver_api():
    frames = Queue(maxsize=2)
    inputs = Queue()
    module_name = "seedsigner.hardware.buttons"
    previously_imported = sys.modules.pop(module_name, None)

    try:
        with simulator_runtime(frames, inputs):
            from seedsigner.hardware.displays.display_driver import DisplayDriverFactory

            display = DisplayDriverFactory.instantiate_display_driver(
                "st7789",
                width=240,
                height=240,
            )
            buttons_module = importlib.import_module(module_name)
            constants = buttons_module.HardwareButtonsConstants

            assert constants.KEY_UP == SimulatorButtonPins.KEY_UP
            assert constants.KEY_PRESS == SimulatorButtonPins.KEY_PRESS
            assert constants.KEY3 == SimulatorButtonPins.KEY3
    finally:
        sys.modules.pop(module_name, None)
        if previously_imported is not None:
            sys.modules[module_name] = previously_imported

    assert isinstance(display, QueueDisplay)
    assert display.width == 240
    assert display.height == 240


def test_browser_ui_serves_real_frames_and_forwards_gpio_events():
    frames = Queue(maxsize=1)
    inputs = Queue()
    errors = Queue()
    display = QueueDisplay(frames, 240, 240)
    display.show_image(Image.new("RGB", (240, 240), "#001CE0"))

    simulator = SimulatorWebServer(
        frames,
        inputs,
        errors,
        SimpleNamespace(is_alive=lambda: True),
        host="127.0.0.1",
        port=0,
    )
    server = simulator.create_server()
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(base_url, timeout=2) as response:
            assert "BitPolito SeedSigner Simulator" in response.read().decode()
        with urlopen(f"{base_url}/frame.png", timeout=2) as response:
            frame = Image.open(response)
            assert frame.mode == "RGB"
            assert frame.size == (240, 240)
            assert frame.getpixel((0, 0)) == (0, 28, 224)
        with urlopen(f"{base_url}/status", timeout=2) as response:
            status = json.load(response)
            assert status == {"alive": True, "frames": 1, "error": None}

        request = Request(
            f"{base_url}/input",
            data=json.dumps(
                {"pin": SimulatorButtonPins.KEY_PRESS, "value": 0}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            assert response.status == 204
        assert inputs.get_nowait() == (SimulatorButtonPins.KEY_PRESS, 0)

        invalid = Request(
            f"{base_url}/input",
            data=b'{"pin": 999, "value": 0}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(invalid, timeout=2)
            raise AssertionError("Invalid GPIO event was accepted")
        except HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_simulator_is_excluded_from_production_runtime_and_dependencies():
    production_tree = REPO_ROOT / "src" / "seedsigner"
    assert not list(production_tree.rglob("*simulator*"))

    production_requirements = "\n".join(
        (REPO_ROOT / name).read_text()
        for name in ("requirements.txt", "requirements-raspi.txt")
    )
    assert "opencv-python" not in production_requirements

    build_workflow = (REPO_ROOT / ".github/workflows/build.yml").read_text()
    assert '--app-repo="${BITPOLITO_APP_REPOSITORY}"' in build_workflow
    assert '--app-commit-id="${app_commit}"' in build_workflow
    assert "--skip-repo" not in build_workflow


def test_supported_display_configs_match_official_0_8_7_values():
    from seedsigner.models.settings_definition import SettingsConstants

    official = tuple(value for value, _label in SettingsConstants.ALL_DISPLAY_CONFIGURATIONS)
    assert SUPPORTED_DISPLAY_CONFIGS == official


def test_ili9341_adapter_matches_official_physical_rotation_and_inversion():
    frames = Queue(maxsize=1)
    display = QueueDisplay(
        frames,
        320,
        240,
        display_type="ili9341",
    )
    logical = Image.new("RGB", (240, 320), "black")
    logical.putpixel((0, 0), (255, 0, 0))
    logical.putpixel((239, 319), (0, 255, 0))

    display.invert()
    display.show_image(logical)
    physical = image_from_payload(frames.get_nowait())

    assert display.inverted is True
    assert physical.size == (320, 240)
    assert physical.tobytes() == logical.rotate(90, expand=True).tobytes()
    display.invert(False)
    assert display.inverted is False


def test_runtime_factory_preserves_each_official_display_contract():
    frames = Queue(maxsize=3)
    inputs = Queue()

    with simulator_runtime(frames, inputs):
        from seedsigner.hardware.displays.display_driver import DisplayDriverFactory

        for display_config in SUPPORTED_DISPLAY_CONFIGS:
            display_type, dimensions = display_config.split("_", maxsplit=1)
            width, height = (int(value) for value in dimensions.split("x"))
            display = DisplayDriverFactory.instantiate_display_driver(
                display_type,
                width=width,
                height=height,
            )
            assert isinstance(display, QueueDisplay)
            assert display.display_type == display_type
            assert (display.width, display.height) == (width, height)


def test_simulator_camera_matches_official_rotation_formula_for_preview_and_photo(tmp_path):
    source_path = tmp_path / "asymmetric-camera.png"
    source = Image.new("RGB", (16, 16), "black")
    source.putpixel((1, 2), (255, 0, 0))
    source.putpixel((13, 4), (0, 255, 0))
    source.putpixel((7, 14), (0, 0, 255))
    source.save(source_path)

    for rotation in (0, 90, 180, 270):
        SimulatorCamera.configure(source_path=str(source_path))
        with patch("seedsigner.models.settings.Settings.get_instance") as get_settings:
            get_settings.return_value.get_value.return_value = rotation
            camera = SimulatorCamera.get_instance()

        expected_rgb = source.rotate(90 + rotation, expand=False)
        expected_rgba = source.convert("RGBA").rotate(90 + rotation, expand=False)

        camera.start_video_stream_mode(resolution=source.size, format="rgb")
        preview = camera.read_video_stream(as_image=True)
        decoder_frame = camera.read_video_stream(as_image=False)
        assert preview.tobytes() == expected_rgba.tobytes()
        assert np.array_equal(decoder_frame, np.asarray(source, dtype=np.uint8))

        camera.start_single_frame_mode(resolution=source.size)
        photo = camera.capture_frame()
        assert photo.tobytes() == expected_rgb.tobytes()
        camera.close()


def test_settingsqr_applies_display_immediately_and_persists_hardware_values(tmp_path):
    from seedsigner.models.settings import Settings
    from seedsigner.models.settings_definition import SettingsConstants

    frames = Queue(maxsize=1)
    inputs = Queue()
    previous_filename = Settings.SETTINGS_FILENAME
    previous_settings = Settings._instance
    renderer_class = None
    previous_renderer = None
    controller_class = None
    previous_controller = None

    try:
        Settings.SETTINGS_FILENAME = str(tmp_path / "settings.json")
        Settings._instance = None
        with simulator_runtime(frames, inputs):
            from seedsigner.controller import Controller
            from seedsigner.gui import Renderer
            from seedsigner.views.settings_views import SettingsIngestSettingsQRView

            renderer_class = Renderer
            previous_renderer = Renderer._instance
            Renderer._instance = None
            controller_class = Controller
            previous_controller = Controller._instance
            Controller._instance = None
            settings = Settings.get_instance()
            with patch("seedsigner.controller.BackgroundImportThread.start"):
                Controller.get_instance()
            renderer = Renderer.get_instance()
            assert (renderer.canvas_width, renderer.canvas_height) == (240, 240)

            settings_view = SettingsIngestSettingsQRView(
                "settings::v1 name=Hardware_Test persistent=E "
                "disp_conf=ili9341_320x240 rgb_inv=E camera=270"
            )
            assert settings_view.settings is settings
            assert settings_view.renderer is renderer

            assert settings.get_value(
                SettingsConstants.SETTING__DISPLAY_CONFIGURATION
            ) == "ili9341_320x240"
            assert settings.get_value(
                SettingsConstants.SETTING__DISPLAY_COLOR_INVERTED
            ) == SettingsConstants.OPTION__ENABLED
            assert settings.get_value(
                SettingsConstants.SETTING__CAMERA_ROTATION
            ) == 270
            assert (renderer.canvas_width, renderer.canvas_height) == (240, 320)
            assert (renderer.disp.width, renderer.disp.height) == (320, 240)
            assert renderer.disp.inverted is True

            persisted = json.loads(Path(Settings.SETTINGS_FILENAME).read_text())
            assert persisted[SettingsConstants.SETTING__DISPLAY_CONFIGURATION] == "ili9341_320x240"
            assert persisted[SettingsConstants.SETTING__DISPLAY_COLOR_INVERTED] == SettingsConstants.OPTION__ENABLED
            assert persisted[SettingsConstants.SETTING__CAMERA_ROTATION] == 270
    finally:
        Settings.SETTINGS_FILENAME = previous_filename
        Settings._instance = previous_settings
        if renderer_class is not None:
            renderer_class._instance = previous_renderer
        if controller_class is not None:
            controller_class._instance = previous_controller
