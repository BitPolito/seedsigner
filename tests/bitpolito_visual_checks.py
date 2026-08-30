import json
import hashlib
import sys
from contextlib import ExitStack
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qrcode
from PIL import Image, ImageChops, ImageColor, ImageDraw
from tools.simulator.adapters import SUPPORTED_DISPLAY_CONFIGS

# Prevent Raspberry Pi-only imports in this standalone visual test process.
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()

from seedsigner import controller as controller_module
from seedsigner.controller import Controller
from seedsigner.gui.components import GUIConstants, load_image
from seedsigner.gui.keyboard import Keyboard
from seedsigner.gui.renderer import Renderer
from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption
from seedsigner.hardware.buttons import HardwareButtons
from seedsigner.models.encode_qr import SeedQrEncoder
from seedsigner.models.settings import Settings
from seedsigner.models.settings_definition import SettingsConstants
from seedsigner.views.screensaver import OpeningSplashScreen, ScreensaverScreen


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_IMAGES = REPO_ROOT / "src" / "seedsigner" / "resources" / "img"
SOURCE_IMAGES = REPO_ROOT / "design" / "source-assets"
THEME_MANIFEST = json.loads(
    (REPO_ROOT / "design" / "bitpolito-theme.json").read_text()
)


class FakeDisplay:
    def __init__(self):
        self.frames = []

    def show_image(self, image, x, y):
        self.frames.append((image.copy(), x, y))


class FakeRenderer:
    def __init__(self, width=240, height=240):
        self.canvas_width = width
        self.canvas_height = height
        self.canvas = Image.new("RGB", (width, height), GUIConstants.BACKGROUND_COLOR)
        self.draw = ImageDraw.Draw(self.canvas)
        self.disp = FakeDisplay()
        self.lock = Lock()
        self.show_count = 0

    @property
    def is_screenshot_generator(self):
        return True

    def show_image(self, image=None, **kwargs):
        if image is not None:
            self.canvas.paste(image)
        self.show_count += 1


class FakeSettings:
    def __init__(self, partner_logos=SettingsConstants.OPTION__ENABLED):
        self.partner_logos = partner_logos

    def get_value(self, attr_name, default_if_none=False):
        if attr_name == SettingsConstants.SETTING__LOCALE:
            return SettingsConstants.LOCALE__ENGLISH
        if attr_name == SettingsConstants.SETTING__PARTNER_LOGOS:
            return self.partner_logos
        return None


class FakeButtons:
    def __init__(self, has_input=False, override_ind=False):
        self._has_input = has_input
        self.override_ind = override_ind

    def has_any_input(self):
        return self._has_input


def patched_gui(renderer, partner_logos=SettingsConstants.OPTION__ENABLED):
    stack = ExitStack()
    stack.enter_context(patch.object(Renderer, "get_instance", return_value=renderer))
    stack.enter_context(patch.object(HardwareButtons, "get_instance", return_value=FakeButtons()))
    stack.enter_context(
        patch.object(
            Settings,
            "get_instance",
            return_value=FakeSettings(partner_logos=partner_logos),
        )
    )
    return stack


def contrast_ratio(foreground, background):
    def luminance(color):
        channels = []
        for channel in ImageColor.getrgb(color):
            normalized = channel / 255
            channels.append(
                normalized / 12.92
                if normalized <= 0.04045
                else ((normalized + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    lighter = max(luminance(foreground), luminance(background))
    darker = min(luminance(foreground), luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def test_theme_tokens_and_normal_text_contrast():
    assert GUIConstants.BACKGROUND_COLOR == "#FFFFFF"
    assert GUIConstants.PRIMARY_COLOR == "#001CE0"
    assert GUIConstants.ACCENT_COLOR == "#6666FF"
    assert GUIConstants.SECONDARY_SURFACE_COLOR == "#F3F5FF"
    assert GUIConstants.INACTIVE_COLOR == "#667085"
    assert GUIConstants.WARNING_COLOR == "#8A5A00"
    assert GUIConstants.ERROR_COLOR == "#B42318"
    assert GUIConstants.SUCCESS_COLOR == "#087A45"
    assert GUIConstants.INFO_COLOR == "#005FCC"
    assert GUIConstants.SECONDARY_TEXT_COLOR == GUIConstants.INFO_COLOR
    assert GUIConstants.LABEL_FONT_COLOR == GUIConstants.SECONDARY_TEXT_COLOR

    manifest_tokens = {
        "background": GUIConstants.BACKGROUND_COLOR,
        "primary": GUIConstants.PRIMARY_COLOR,
        "accent": GUIConstants.ACCENT_COLOR,
        "text_on_primary": GUIConstants.TEXT_ON_PRIMARY_COLOR,
        "secondary_surface": GUIConstants.SECONDARY_SURFACE_COLOR,
        "inactive": GUIConstants.INACTIVE_COLOR,
        "warning": GUIConstants.WARNING_COLOR,
        "error": GUIConstants.ERROR_COLOR,
        "success": GUIConstants.SUCCESS_COLOR,
        "info": GUIConstants.INFO_COLOR,
    }
    assert THEME_MANIFEST["colors"] == manifest_tokens

    text_pairs = [
        (GUIConstants.PRIMARY_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.PRIMARY_COLOR, GUIConstants.SECONDARY_SURFACE_COLOR),
        (GUIConstants.INACTIVE_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.INACTIVE_COLOR, GUIConstants.SECONDARY_SURFACE_COLOR),
        (GUIConstants.TEXT_ON_PRIMARY_COLOR, GUIConstants.PRIMARY_COLOR),
        (GUIConstants.WARNING_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.ERROR_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.SUCCESS_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.INFO_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.SECONDARY_TEXT_COLOR, GUIConstants.BACKGROUND_COLOR),
        (GUIConstants.SECONDARY_TEXT_COLOR, GUIConstants.SECONDARY_SURFACE_COLOR),
    ]
    for foreground, background in text_pairs:
        assert contrast_ratio(foreground, background) >= 4.5


def test_runtime_assets_and_rgb_contract():
    expected = {
        REPO_ROOT / asset["path"]: (tuple(asset["size"]), asset["mode"])
        for asset in THEME_MANIFEST["assets"].values()
    }
    for path, (size, mode) in expected.items():
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == size
            assert image.mode == mode

    for asset in THEME_MANIFEST["assets"].values():
        runtime_path = REPO_ROOT / asset["path"]
        source_path = REPO_ROOT / asset["source_path"]
        assert hashlib.sha256(runtime_path.read_bytes()).hexdigest() == asset["sha256"]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == asset["source_sha256"]

    assert load_image("bitpolito_splash.png").mode == "RGB"
    assert load_image("cow.png").mode == "RGB"
    assert not list(RUNTIME_IMAGES.rglob("*.svg"))

    dependency_manifests = "\n".join(
        (REPO_ROOT / path).read_text()
        for path in ("requirements.txt", "pyproject.toml")
    ).lower()
    for svg_runtime_dependency in ("cairosvg", "librsvg", "svgwrite"):
        assert svg_runtime_dependency not in dependency_manifests

    with Image.open(SOURCE_IMAGES / "bitpolito-logo.png") as source_logo:
        assert source_logo.width > 200
        assert source_logo.height > 59
    with Image.open(SOURCE_IMAGES / "cow.png") as source_cow:
        assert source_cow.width > 240
        assert source_cow.height > 240

    for unused_name in [
        "BitPolito_logo1.png",
        "seed_logo.png",
        "arrow-down (2).png",
        "arrow-up (2).png",
        "back (2).png",
    ]:
        assert not any(RUNTIME_IMAGES.parent.rglob(unused_name))


def test_keyboard_states_use_theme_tokens():
    canvas = Image.new("RGB", (120, 40), GUIConstants.BACKGROUND_COLOR)
    with patch.object(Settings, "get_instance", return_value=FakeSettings()):
        keyboard = Keyboard(
            draw=ImageDraw.Draw(canvas),
            charset="abc",
            selected_char="a",
            rows=1,
            cols=3,
            rect=(0, 0, 120, 40),
            additional_keys=[],
        )

    selected_key = keyboard.keys[0][0]
    regular_key = keyboard.keys[0][1]
    assert canvas.getpixel((selected_key.screen_x + 8, selected_key.screen_y + 5)) == ImageColor.getrgb(GUIConstants.BUTTON_SELECTED_COLOR)
    assert canvas.getpixel((regular_key.screen_x + 8, regular_key.screen_y + 5)) == ImageColor.getrgb(GUIConstants.BUTTON_BACKGROUND_COLOR)

    keyboard.update_active_keys(["a"])
    keyboard.render_keys()
    disabled_key = keyboard.keys[0][1]
    assert canvas.getpixel((disabled_key.screen_x + 8, disabled_key.screen_y + 5)) == ImageColor.getrgb(GUIConstants.SECONDARY_SURFACE_COLOR)


def render_splash(width, show_partner_logos, height=240):
    renderer = FakeRenderer(width=width, height=height)
    partner_value = (
        SettingsConstants.OPTION__ENABLED
        if show_partner_logos
        else SettingsConstants.OPTION__DISABLED
    )
    with patched_gui(renderer, partner_logos=partner_value):
        with patch.object(
            Controller,
            "get_instance",
            return_value=SimpleNamespace(VERSION=Controller.VERSION),
        ):
            screen = OpeningSplashScreen(force_partner_logos=show_partner_logos)
            screen._render()
    return renderer.canvas


def test_splash_renders_brand_version_and_partner_toggle_on_supported_widths():
    for width, height in ((240, 240), (320, 240), (240, 320)):
        without_partner = render_splash(width, show_partner_logos=False, height=height)
        with_partner = render_splash(width, show_partner_logos=True, height=height)

        assert without_partner.size == (width, height)
        assert with_partner.size == (width, height)
        assert without_partner.getbbox() == (0, 0, width, height)
        assert with_partner.getbbox() == (0, 0, width, height)
        assert without_partner.tobytes() != with_partner.tobytes()

        primary = ImageColor.getrgb(GUIConstants.PRIMARY_COLOR)
        assert sum(pixel == primary for pixel in without_partner.getdata()) > 0
        assert sum(pixel == primary for pixel in with_partner.getdata()) > 0


def test_screensaver_frame_bounds_and_immediate_wake():
    for width, height in ((240, 240), (320, 240), (240, 320)):
        renderer = FakeRenderer(width=width, height=height)
        buttons = FakeButtons(has_input=True)
        with patched_gui(renderer):
            screen = ScreensaverScreen(buttons)
            frame = screen.render_frame(x=screen.max_coords[0], y=screen.max_coords[1])

            assert frame.size == (width, height)
            assert frame.mode == "RGB"
            assert screen.sprite.mode == "RGBA"
            assert 0 < screen.sprite.width <= width
            assert 0 < screen.sprite.height <= height
            assert screen.max_coords[0] >= 0
            assert screen.max_coords[1] >= 0

            background = Image.new("RGB", frame.size, GUIConstants.BACKGROUND_COLOR)
            visible_bbox = ImageChops.difference(frame, background).getbbox()
            assert visible_bbox is not None
            assert 0 <= visible_bbox[0] < visible_bbox[2] <= width
            assert 0 <= visible_bbox[1] < visible_bbox[3] <= height

            screen.start()
            assert screen.is_running is False
            assert renderer.disp.frames == []


def test_button_list_construction_has_no_overflow_on_supported_canvases():
    for width, height in ((240, 240), (320, 240), (240, 320)):
        renderer = FakeRenderer(width=width, height=height)
        with patched_gui(renderer):
            screen = ButtonListScreen(
                title="BitPolito",
                button_data=[ButtonOption("One"), ButtonOption("Two")],
            )
            screen._render()

        assert renderer.canvas.size == (width, height)
        for button in screen.buttons:
            assert button.screen_x >= 0
            assert button.screen_x + button.width <= renderer.canvas_width
            assert button.screen_y >= screen.top_nav.height
            assert button.screen_y + button.height <= renderer.canvas_height


def test_timeout_version_and_qr_remain_fixed():
    assert controller_module._SCREENSAVER_ACTIVATION_MS == 30_000
    assert THEME_MANIFEST["behavior"]["screensaver_timeout_seconds"] == 30
    assert Controller.VERSION == "0.8.7-bitpolito.1"

    mnemonic = (
        "forum undo fragile fade shy sign arrest garment culture tube off merit"
    ).split()
    encoder = SeedQrEncoder(mnemonic=mnemonic)
    part = encoder.next_part()
    native_qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=5,
        border=3,
    )
    native_qr.add_data(part)
    native_qr.make(fit=True)
    native_size = native_qr.make_image(
        fill_color="black",
        back_color="white",
    ).size[0]
    qr_image = encoder.qr.qrimage(
        part,
        native_size,
        native_size,
        border=3,
        background_color="#FFFFFF",
    ).convert("RGB")
    assert set(qr_image.getdata()) == {(0, 0, 0), (255, 255, 255)}


def test_keyboard_and_list_arrows_have_no_legacy_hard_coded_colors():
    keyboard_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "keyboard.py"
    ).read_text()
    list_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "screens" / "screen.py"
    ).read_text()

    for literal in [
        "\"#333\"",
        "\"#666\"",
        "\"#999\"",
        "\"#ccc\"",
        "\"#e8e8e8\"",
        "color=\"black\"",
        "fill=\"black\"",
    ]:
        assert literal not in keyboard_source
        assert literal not in list_source


def test_metadata_labels_use_secondary_blue_tokens():
    component_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "components.py"
    ).read_text()
    tools_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "screens" / "tools_screens.py"
    ).read_text()
    seed_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "screens" / "seed_screens.py"
    ).read_text()

    assert "LABEL_FONT_COLOR = SECONDARY_TEXT_COLOR" in component_source
    assert 'font_color="orange"' not in seed_source
    assert 'fill="#ddd"' not in seed_source
    assert "GUIConstants.SECONDARY_TEXT_COLOR" in tools_source or "GUIConstants.LABEL_FONT_COLOR" in tools_source


def test_psbt_rendering_uses_light_theme_tokens():
    psbt_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "screens" / "psbt_screens.py"
    ).read_text()

    for legacy_literal in [
        'association_line_color = "#666"',
        'chart_font_color = "#ddd"',
        'reset_color = "#666"',
        'secondary_digit_color = "#888"',
        'tertiary_digit_color = "#666"',
        'info_text_color="darkorange"',
    ]:
        assert legacy_literal not in psbt_source

    assert "association_line_color = GUIConstants.ACCENT_COLOR" in psbt_source
    assert "reset_color = GUIConstants.ACCENT_COLOR" in psbt_source
    assert "secondary_digit_color = GUIConstants.ACCENT_COLOR" in psbt_source
    assert "tertiary_digit_color = GUIConstants.ACCENT_COLOR" in psbt_source


def test_ci_workflows_keep_build_manual_and_cover_official_hardware_matrix():
    build_workflow = (REPO_ROOT / ".github/workflows/build.yml").read_text()
    test_workflow = (REPO_ROOT / ".github/workflows/tests.yml").read_text()
    build_trigger = build_workflow.split("jobs:", maxsplit=1)[0]

    assert "workflow_dispatch:" in build_trigger
    assert "push:" not in build_trigger
    assert "pull_request:" not in build_trigger
    release_gate = (REPO_ROOT / "scripts/run-quality-gate.sh").read_text()
    release_metadata = (REPO_ROOT / "scripts/release.env").read_text()

    assert "needs: quality" in build_workflow
    assert "environment: bitpolito-image-build" in build_workflow
    assert "expected_app_commit:" in build_workflow
    assert "BUILD PI0 CANDIDATE" in build_workflow
    assert "d13859392660fe512a753bc14ecd0edc86c35510" in build_workflow
    assert "--pi0" in build_workflow
    assert '--app-repo="${BITPOLITO_APP_REPOSITORY}"' in build_workflow
    assert '--app-commit-id="${app_commit}"' in build_workflow
    assert "--skip-repo" not in build_workflow
    for forbidden_target in ("--pi02w", "--pi2", "--pi4"):
        assert forbidden_target not in build_workflow

    assert "python-version: [\"3.10\", \"3.12\"]" in test_workflow
    for display_config in SUPPORTED_DISPLAY_CONFIGS:
        assert f"--display-config {display_config}" in test_workflow
        assert display_config in release_gate
    assert "--smoke-flow screensaver" in release_gate
    assert "--screenshot-output ./artifacts/screenshots" in test_workflow
    assert "--screenshot-output" in release_gate
    assert "python -m compileall -q -x 'seedsigner-translations' src tools/simulator tests" in test_workflow
    assert "git diff --check" in test_workflow
    assert "./scripts/check_upstream_scope.sh" in test_workflow

    assert 'BITPOLITO_VERSION="0.8.7-bitpolito.1"' in release_metadata
    assert (
        'SEEDSIGNER_OS_COMMIT="d13859392660fe512a753bc14ecd0edc86c35510"'
        in release_metadata
    )
    assert THEME_MANIFEST["release"] in release_metadata
    assert THEME_MANIFEST["upstream"]["os_commit"] in release_metadata


def test_qr_brightness_tip_uses_white_text_on_dark_overlay():
    screen_source = (
        REPO_ROOT / "src" / "seedsigner" / "gui" / "screens" / "screen.py"
    ).read_text()
    brightness_tip = screen_source.split(
        "def render_brightness_tip", maxsplit=1
    )[1].split("def run", maxsplit=1)[0]

    assert brightness_tip.count(
        "font_color=GUIConstants.TEXT_ON_PRIMARY_COLOR"
    ) == 2
    assert brightness_tip.count(
        "icon_color=GUIConstants.TEXT_ON_PRIMARY_COLOR"
    ) == 2

    screensaver_source = (
        REPO_ROOT / "src" / "seedsigner" / "views" / "screensaver.py"
    ).read_text()
    assert 'controller.VERSION.partition("-")[0]' in screensaver_source
    sponsor_block = screensaver_source.split(
        'sponsor_text = "designed by"', maxsplit=1
    )[1]
    assert "fill=GUIConstants.PRIMARY_COLOR" in sponsor_block
