import logging
import os
import random
import time

from dataclasses import dataclass
from seedsigner.gui.components import Fonts, GUIConstants, load_image
from seedsigner.gui.screens.screen import BaseScreen
from seedsigner.models.settings import Settings
from seedsigner.models.settings_definition import SettingsConstants
from seedsigner.views.view import View

logger = logging.getLogger(__name__)



# TODO: This early code is now outdated vis-a-vis Screen vs View distinctions
class LogoScreen(BaseScreen):
    def __init__(self):
        super().__init__()
        self.logo = load_image("bitpolito_splash.png")

        self.partners = [
            "bitpolito",
        ]

        self.partner_logos: dict = {}
        for partner in self.partners:
            logo_url = os.path.join("partners", f"{partner}_logo.png")
            self.partner_logos[partner] = load_image(logo_url)


    def _run(self):
        pass


    def get_random_partner(self) -> str:
        return self.partners[random.randrange(len(self.partners))]



@dataclass
class OpeningSplashView(View):
    force_partner_logos: bool|None = None

    def run(self):
        self.run_screen(
            OpeningSplashScreen,
            force_partner_logos=self.force_partner_logos
        )



class OpeningSplashScreen(LogoScreen):
    def __init__(self, force_partner_logos=None):
        self.force_partner_logos = force_partner_logos
        super().__init__()


    def _render(self):
        from PIL import Image
        from seedsigner.controller import Controller

        controller = Controller.get_instance()

        # Clear stale pixels left by a previously rendered screen or locale.
        self.clear_screen()

        show_partner_logos = (
            Settings.get_instance().get_value(SettingsConstants.SETTING__PARTNER_LOGOS)
            == SettingsConstants.OPTION__ENABLED
        )
        if self.force_partner_logos is not None:
            show_partner_logos = self.force_partner_logos

        logo_offset_x = int((self.canvas_width - self.logo.width) / 2)
        logo_offset_y = -min(56, self.canvas_height // 4) if show_partner_logos else 0

        # Keep load_image RGB-compatible; transparency is only needed locally for the
        # splash fade.
        logo_rgba = self.logo.convert("RGBA")
        background = Image.new(
            "RGBA",
            size=self.logo.size,
            color=GUIConstants.BACKGROUND_COLOR,
        )
        if not self.renderer.is_screenshot_generator:
            for alpha in range(5, 256, 25):
                fade_frame = logo_rgba.copy()
                fade_frame.putalpha(alpha)
                self.renderer.canvas.paste(
                    Image.alpha_composite(background, fade_frame).convert("RGB"),
                    (logo_offset_x, logo_offset_y),
                )
                self.renderer.show_image()
        else:
            self.renderer.canvas.paste(self.logo, (logo_offset_x, logo_offset_y))

        # The version is deliberately visible on every splash variant.
        version_font = Fonts.get_font(
            GUIConstants.get_body_font_name(),
            GUIConstants.get_top_nav_title_font_size(),
        )
        base_version = controller.VERSION.partition("-")[0]
        version = f"v{base_version}"
        version_x = int(self.canvas_width / 2)
        version_y = (
            int(self.canvas_height / 2)
            + 35
            + logo_offset_y
            + GUIConstants.COMPONENT_PADDING
        )
        self.renderer.draw.text(
            xy=(version_x, version_y),
            text=version,
            font=version_font,
            fill=GUIConstants.PRIMARY_COLOR,
            anchor="mt",
        )

        if not self.renderer.is_screenshot_generator:
            self.renderer.show_image()

        if show_partner_logos:
            if not self.renderer.is_screenshot_generator:
                time.sleep(1)

            partner_logo = self.partner_logos[self.get_random_partner()]
            brand_font = Fonts.get_font(
                GUIConstants.get_body_font_name(),
                GUIConstants.LABEL_FONT_SIZE,
            )
            sponsor_text = "designed by"
            left, top, right, bottom = brand_font.getbbox(sponsor_text, anchor="lt")
            text_height = bottom - top

            x = int(self.canvas_width / 2)
            y = (
                self.canvas_height
                - GUIConstants.COMPONENT_PADDING
                - partner_logo.height
                - int(GUIConstants.COMPONENT_PADDING / 2)
                - text_height
            )
            self.renderer.draw.text(
                xy=(x, y),
                text=sponsor_text,
                font=brand_font,
                fill=GUIConstants.PRIMARY_COLOR,
                anchor="mt",
            )
            self.renderer.canvas.paste(
                partner_logo,
                (
                    int((self.canvas_width - partner_logo.width) / 2),
                    y + text_height + int(GUIConstants.COMPONENT_PADDING / 2),
                ),
            )
            self.renderer.show_image()

        if not self.renderer.is_screenshot_generator:
            time.sleep(2)



class ScreensaverScreen(BaseScreen):
    def __init__(self, buttons):
        from pathlib import Path
        from PIL import Image

        super().__init__()
        self.buttons = buttons

        # Keep load_image returning RGB. The cow is the only runtime asset that needs
        # transparency, so it is opened and converted locally.
        cow_path = (
            Path(__file__).parent.parent
            / "resources"
            / "img"
            / "cow.png"
        )
        cow_asset = Image.open(cow_path).convert("RGBA")
        alpha_bbox = cow_asset.getchannel("A").getbbox()
        if alpha_bbox is None:
            raise ValueError("cow.png has no visible pixels")

        self.sprite = cow_asset.crop(alpha_bbox)
        self.sprite.thumbnail(
            (
                max(1, int(self.renderer.canvas_width * 0.60)),
                max(1, int(self.renderer.canvas_height * 0.60)),
            ),
            Image.Resampling.LANCZOS,
        )

        self.min_coords = (0, 0)
        self.max_coords = (
            max(0, self.renderer.canvas_width - self.sprite.width),
            max(0, self.renderer.canvas_height - self.sprite.height),
        )
        self.cur_x = self.max_coords[0] / 2
        self.cur_y = self.max_coords[1] / 2
        self.increment_x = self.rand_increment()
        self.increment_y = self.rand_increment()

        self._is_running = False
        self.last_screen = None


    @property
    def is_running(self):
        return self._is_running


    def rand_increment(self):
        increment = random.uniform(1.0, 4.0)
        if random.uniform(-1.0, 1.0) < 0.0:
            return -increment
        return increment


    def render_frame(self, x=None, y=None):
        from PIL import Image

        if x is None:
            x = self.cur_x
        if y is None:
            y = self.cur_y

        frame = Image.new(
            "RGBA",
            (self.renderer.canvas_width, self.renderer.canvas_height),
            GUIConstants.BACKGROUND_COLOR,
        )
        frame.alpha_composite(self.sprite, (int(round(x)), int(round(y))))
        return frame.convert("RGB")


    def advance_frame(self):
        self.cur_x += self.increment_x
        self.cur_y += self.increment_y

        if self.cur_x < self.min_coords[0]:
            self.cur_x = self.min_coords[0]
            self.increment_x = abs(self.rand_increment())
        elif self.cur_x > self.max_coords[0]:
            self.cur_x = self.max_coords[0]
            self.increment_x = -abs(self.rand_increment())

        if self.cur_y < self.min_coords[1]:
            self.cur_y = self.min_coords[1]
            self.increment_y = abs(self.rand_increment())
        elif self.cur_y > self.max_coords[1]:
            self.cur_y = self.max_coords[1]
            self.increment_y = -abs(self.rand_increment())


    def start(self):
        if self.is_running:
            return

        self._is_running = True
        self.last_screen = self.renderer.canvas.copy()

        # Hold the Renderer lock until input stops the screensaver, matching upstream.
        with self.renderer.lock:
            try:
                while self._is_running:
                    if self.buttons.has_any_input() or self.buttons.override_ind:
                        break

                    self.renderer.disp.show_image(self.render_frame(), 0, 0)
                    self.advance_frame()

            except KeyboardInterrupt as e:
                logger.info("Shutting down Screensaver")
                raise e

            finally:
                self._is_running = False
                self.renderer.show_image(self.last_screen)


    def stop(self):
        self._is_running = False
