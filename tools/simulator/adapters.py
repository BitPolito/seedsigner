"""Hardware adapters used only by the desktop SeedSigner simulator.

This module is the single development-only boundary for display, camera and
GPIO. Nothing here is imported by the SeedSigner OS build.
"""

from pathlib import Path
from queue import Empty, Full
from threading import Lock
from types import ModuleType
from typing import Any
import time

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from seedsigner.models.settings import Settings, SettingsConstants


FramePayload = tuple[str, tuple[int, int], bytes]
SUPPORTED_DISPLAY_CONFIGS = (
    "st7789_240x240",
    "st7789_320x240",
    "ili9341_320x240",
)


def put_latest(target_queue: Any, payload: FramePayload) -> None:
    """Queue the newest frame without allowing rendering to block the app."""
    try:
        target_queue.put_nowait(payload)
        return
    except Full:
        pass

    try:
        target_queue.get_nowait()
    except Empty:
        pass
    target_queue.put_nowait(payload)


class QueueDisplay:
    """Minimal BaseDisplayDriver-compatible adapter backed by a frame queue."""

    def __init__(
        self,
        frame_queue: Any,
        width: int,
        height: int,
        *,
        display_type: str = "st7789",
    ):
        self._frame_queue = frame_queue
        self._width = int(width)
        self._height = int(height)
        self.display_type = display_type
        self.inverted = False
        self._last_frame_at = 0.0
        self._minimum_frame_interval = 1.0 / 30.0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def show_image(self, image: Image.Image, x_start: int = 0, y_start: int = 0):
        if image is None:
            return
        now = time.monotonic()
        remaining = self._minimum_frame_interval - (now - self._last_frame_at)
        if remaining > 0:
            time.sleep(remaining)
        self._last_frame_at = time.monotonic()
        frame = image.convert("RGB")
        if self.display_type == "ili9341":
            # Match the official ILI9341 driver: the renderer uses a portrait
            # 240x320 canvas and the hardware driver emits a physical 320x240
            # framebuffer after a clockwise 90-degree rotation.
            frame = frame.rotate(90, expand=True)

        expected_size = (self.width, self.height)
        if frame.size != expected_size:
            canvas = Image.new("RGB", expected_size, "black")
            canvas.paste(frame, (int(x_start), int(y_start)))
            frame = canvas
        put_latest(self._frame_queue, (frame.mode, frame.size, frame.tobytes()))

    def invert(self, enabled: bool = True):
        # LCD inversion is electrical and remains a hardware-only check.
        self.inverted = bool(enabled)
        return self

    def cleanup(self):
        return None


def image_from_payload(payload: FramePayload) -> Image.Image:
    mode, size, data = payload
    return Image.frombytes(mode, tuple(size), data)


class SimulatorCamera:
    """Fixture/test-pattern camera with the official rotation contract."""

    _instance = None
    _source_path: Path | None = None
    _lock = Lock()

    @classmethod
    def configure(
        cls,
        source_path: str | None = None,
    ):
        cls._source_path = Path(source_path).expanduser().resolve() if source_path else None
        cls._instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._video_stream = None
            cls._instance._picamera = None
            cls._instance._resolution = (512, 384)

        cls._instance._camera_rotation = int(
            Settings.get_instance().get_value(
                SettingsConstants.SETTING__CAMERA_ROTATION
            )
        )
        return cls._instance

    def _test_pattern(self, resolution: tuple[int, int]) -> Image.Image:
        width, height = resolution
        image = Image.new("RGB", resolution, "#F3F5FF")
        draw = ImageDraw.Draw(image)
        step = max(12, min(width, height) // 8)
        for offset in range(-height, width, step):
            draw.line(
                (offset, 0, offset + height, height),
                fill="#6666FF",
                width=max(1, step // 8),
            )
        draw.rectangle(
            (width // 5, height // 3, width * 4 // 5, height * 2 // 3),
            fill="#FFFFFF",
            outline="#001CE0",
            width=max(2, step // 6),
        )
        draw.text(
            (width // 2, height // 2),
            "SIMULATOR CAMERA",
            fill="#001CE0",
            anchor="mm",
        )
        return image

    def _read_source(self, resolution: tuple[int, int]) -> Image.Image:
        with self._lock:
            if self._source_path:
                with Image.open(self._source_path) as source:
                    frame = source.convert("RGB")
            else:
                frame = self._test_pattern(resolution)

        return ImageOps.fit(frame, resolution, method=Image.Resampling.LANCZOS)

    def start_video_stream_mode(
        self,
        resolution=(512, 384),
        framerate=12,
        format="bgr",
    ):
        self.stop_video_stream_mode()
        self._resolution = tuple(map(int, resolution))
        self._video_stream = self

    def read_video_stream(self, as_image=False):
        if self._video_stream is None:
            raise RuntimeError("Must call start_video_stream_mode first")

        frame = self._read_source(self._resolution)
        if as_image:
            return frame.convert("RGBA").rotate(
                90 + self._camera_rotation,
                expand=False,
            )
        return np.asarray(frame, dtype=np.uint8)

    def stop_video_stream_mode(self):
        self._video_stream = None

    def start_single_frame_mode(self, resolution=(720, 480)):
        self.stop_video_stream_mode()
        self._resolution = tuple(map(int, resolution))
        self._picamera = self

    def capture_frame(self):
        if self._picamera is None:
            raise RuntimeError("Must call start_single_frame_mode first")
        return self._read_source(self._resolution).rotate(
            90 + self._camera_rotation,
            expand=False,
        )

    def stop_single_frame_mode(self):
        self._picamera = None

    def close(self):
        self.stop_video_stream_mode()
        self.stop_single_frame_mode()


class SimulatorButtonPins:
    KEY_UP = 31
    KEY_DOWN = 35
    KEY_LEFT = 29
    KEY_RIGHT = 37
    KEY_PRESS = 33
    KEY1 = 40
    KEY2 = 38
    KEY3 = 36


class QueueGPIO:
    """RPi.GPIO-compatible active-low input adapter."""

    LOW = 0
    HIGH = 1
    BOARD = 10
    BCM = 11
    IN = 1
    OUT = 0
    PUD_UP = 22
    RPI_INFO = {"P1_REVISION": 3}

    def __init__(self, input_queue: Any):
        self._input_queue = input_queue
        self._states: dict[int, int] = {}
        self._low_observed: dict[int, bool] = {}
        self._pending_high: set[int] = set()

    def _drain_events(self) -> None:
        while True:
            try:
                pin, value = self._input_queue.get_nowait()
            except Empty:
                return
            pin = int(pin)
            value = int(value)
            if value == self.LOW:
                self._states[pin] = self.LOW
                self._low_observed[pin] = False
                self._pending_high.discard(pin)
            elif (
                self._states.get(pin) == self.LOW
                and not self._low_observed.get(pin, False)
            ):
                self._pending_high.add(pin)
            else:
                self._states[pin] = self.HIGH
                self._low_observed[pin] = True
                self._pending_high.discard(pin)

    def setmode(self, mode):
        return None

    def setwarnings(self, enabled):
        return None

    def setup(self, pin, mode, pull_up_down=None):
        pin = int(pin)
        self._states.setdefault(pin, self.HIGH)
        self._low_observed.setdefault(pin, True)

    def input(self, pin):
        self._drain_events()
        pin = int(pin)
        value = self._states.get(pin, self.HIGH)
        if value == self.LOW:
            self._low_observed[pin] = True
            if pin in self._pending_high:
                self._states[pin] = self.HIGH
                self._pending_high.remove(pin)
        return value

    def output(self, pin, value):
        self._states[int(pin)] = int(value)

    def cleanup(self):
        self._states.clear()
        self._low_observed.clear()
        self._pending_high.clear()


def build_gpio_module(input_queue: Any) -> ModuleType:
    backend = QueueGPIO(input_queue)
    module = ModuleType("RPi.GPIO")
    module._simulator_backend = backend

    for name in (
        "LOW", "HIGH", "BOARD", "BCM", "IN", "OUT", "PUD_UP", "RPI_INFO"
    ):
        setattr(module, name, getattr(backend, name))

    for name in ("setmode", "setwarnings", "setup", "input", "output", "cleanup"):
        setattr(module, name, getattr(backend, name))

    return module
