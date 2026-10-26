#!/usr/bin/env python3
"""Replace only the Bitcoin glyph using the supplied BitPolito SVG.

Requires the development dependency FontTools. The production image continues
to use Pillow and the existing icon-font interface, without an SVG renderer.
"""

import argparse
from io import BytesIO
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = Path("src/seedsigner/resources/fonts/seedsigner-icons.otf")
SVG_PATH = Path("design/source-assets/bitsymbol.svg")
BITCOIN_CODEPOINT = 0xE91D


def build_font() -> bytes:
    manifest = json.loads((ROOT / "design/bitpolito-theme.json").read_text())
    base = subprocess.check_output(
        ["git", "show", f"{manifest['upstream']['application_commit']}:{FONT_PATH}"],
        cwd=ROOT,
    )
    font = TTFont(BytesIO(base), recalcTimestamp=False)
    glyphs = font.getGlyphSet()
    glyph_name = font.getBestCmap()[BITCOIN_CODEPOINT]
    bounds = BoundsPen(glyphs)
    glyphs[glyph_name].draw(bounds)
    left, bottom, right, top = bounds.bounds
    advance, _ = font["hmtx"][glyph_name]

    svg = ET.fromstring((ROOT / SVG_PATH).read_bytes())
    x, y, width, height = map(float, svg.attrib["viewBox"].split())
    scale = min((right - left) / width, (top - bottom) / height)
    offset_x = (left + right - width * scale) / 2
    offset_y = top - ((top - bottom) - height * scale) / 2

    pen = T2CharStringPen(advance, glyphs)
    transformed = TransformPen(
        pen, (scale, 0, 0, -scale, offset_x - x * scale, offset_y + y * scale)
    )
    paths = list(svg.iter("{http://www.w3.org/2000/svg}path"))
    if not paths:
        raise ValueError("Bitcoin SVG contains no paths")
    for path in paths:
        if "transform" in path.attrib:
            raise ValueError("Flatten SVG transforms before generating the icon font")
        parse_path(path.attrib["d"], transformed)

    cff = font["CFF "].cff
    top_dict = cff.topDictIndex[0]
    top_dict.CharStrings[glyph_name] = pen.getCharString(
        private=top_dict.Private, globalSubrs=cff.GlobalSubrs
    )
    font["hmtx"][glyph_name] = (advance, round(offset_x))
    output = BytesIO()
    font.save(output)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the generated font")
    args = parser.parse_args()
    generated = build_font()
    target = ROOT / FONT_PATH
    if args.check:
        if target.read_bytes() != generated:
            raise SystemExit("Icon font is stale; run scripts/build-brand-icons.py")
        print("Bitcoin icon font matches the source SVG")
    else:
        target.write_bytes(generated)
        print(f"Updated Bitcoin glyph only: {FONT_PATH}")


if __name__ == "__main__":
    main()
