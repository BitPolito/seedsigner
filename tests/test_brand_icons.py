"""Verify the SVG-derived Bitcoin glyph without changing other upstream icons."""

import hashlib
from io import BytesIO
import json
from pathlib import Path
import runpy
import subprocess

from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]


def test_bitcoin_font_matches_svg_and_manifest():
    manifest = json.loads((ROOT / "design/bitpolito-theme.json").read_text())
    icon = manifest["icons"]["bitcoin"]
    script = runpy.run_path(str(ROOT / icon["generator"]))
    generated = script["build_font"]()
    assert generated == (ROOT / icon["font_path"]).read_bytes()
    assert hashlib.sha256(generated).hexdigest() == icon["font_sha256"]
    assert hashlib.sha256((ROOT / icon["source_path"]).read_bytes()).hexdigest() == icon["source_sha256"]


def test_bitcoin_is_the_only_changed_glyph_and_keeps_advance():
    manifest = json.loads((ROOT / "design/bitpolito-theme.json").read_text())
    icon = manifest["icons"]["bitcoin"]
    source = subprocess.check_output(
        ["git", "show", f"{manifest['upstream']['application_commit']}:{icon['font_path']}"],
        cwd=ROOT,
    )
    original = TTFont(BytesIO(source))
    branded = TTFont(ROOT / icon["font_path"])
    assert original.getBestCmap() == branded.getBestCmap()
    assert original.getGlyphOrder() == branded.getGlyphOrder()
    assert original["head"].unitsPerEm == branded["head"].unitsPerEm
    bitcoin = original.getBestCmap()[0xE91D]
    original_glyphs, branded_glyphs = original.getGlyphSet(), branded.getGlyphSet()
    for name in original.getGlyphOrder():
        before, after = RecordingPen(), RecordingPen()
        original_glyphs[name].draw(before)
        branded_glyphs[name].draw(after)
        if name == bitcoin:
            assert before.value != after.value
            assert original["hmtx"][name][0] == branded["hmtx"][name][0]
        else:
            assert before.value == after.value, name
            assert original["hmtx"][name] == branded["hmtx"][name], name
