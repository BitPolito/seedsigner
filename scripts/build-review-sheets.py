#!/usr/bin/env python3
"""Build compact visual-review sheets from screenshot-generator output."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from textwrap import shorten

from PIL import Image, ImageDraw, ImageFont


CATEGORIES = (
    "main_menu_views",
    "settings_views",
    "tools_views",
    "seed_views",
    "psbt_views",
    "misc_error_views",
)
TILE_WIDTH = 300
TILE_HEIGHT = 292
IMAGE_SIZE = (240, 240)
COLUMNS = 4
TITLE_HEIGHT = 46
BACKGROUND = (255, 255, 255)
TEXT = (0, 28, 224)


def font(size: int):
    candidates = (
        Path("src/seedsigner/resources/fonts/OpenSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def build_sheet(category: str, paths: list[Path], output: Path) -> None:
    rows = math.ceil(len(paths) / COLUMNS)
    canvas = Image.new(
        "RGB",
        (COLUMNS * TILE_WIDTH, TITLE_HEIGHT + rows * TILE_HEIGHT),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 12), f"{category} ({len(paths)} screens)", fill=TEXT, font=font(22))

    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        if image.size != IMAGE_SIZE:
            raise ValueError(f"{path} is {image.size}, expected {IMAGE_SIZE}")
        column = index % COLUMNS
        row = index // COLUMNS
        x = column * TILE_WIDTH + (TILE_WIDTH - IMAGE_SIZE[0]) // 2
        y = TITLE_HEIGHT + row * TILE_HEIGHT
        canvas.paste(image, (x, y))
        label = shorten(path.stem, width=39, placeholder="...")
        bbox = draw.textbbox((0, 0), label, font=font(13))
        label_x = column * TILE_WIDTH + (TILE_WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((label_x, y + IMAGE_SIZE[1] + 9), label, fill=(45, 55, 75), font=font(13))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="English screenshot root")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("design/review/0.8.7-bitpolito.1/en/full"),
    )
    args = parser.parse_args()

    input_root = args.input.expanduser().resolve()
    output_root = args.output.expanduser().resolve()
    if not input_root.is_dir():
        parser.error(f"Screenshot directory not found: {input_root}")

    manifest = {
        "source": "tests/screenshot_generator/generator.py",
        "canvas": {"width": IMAGE_SIZE[0], "height": IMAGE_SIZE[1], "mode": "RGB"},
        "categories": {},
    }
    for category in CATEGORIES:
        paths = sorted((input_root / category).glob("*.png"))
        if not paths:
            raise SystemExit(f"No PNG screenshots found for {category}")
        output = output_root / f"{CATEGORIES.index(category) + 1:02d}-{category}.png"
        build_sheet(category, paths, output)
        manifest["categories"][category] = {
            "count": len(paths),
            "sheet": output.name,
            "screens": [path.name for path in paths],
        }

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Review sheets written to {output_root} "
        f"({sum(item['count'] for item in manifest['categories'].values())} screens)"
    )


if __name__ == "__main__":
    main()
