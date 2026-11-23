"""The installed metrics engine must operate independently of subtitle renderers."""

import sys
from pathlib import Path

from kara_templater import _metrics, _text_native


def test_native_font_geometry_is_standalone():
    width, height, _, baseline, glyphs = _metrics.text_shape(
        "sans-serif", 32, 0, 0, 100, 100, 0, 1, "Hello"
    )
    assert width > 0 and height >= baseline > 0
    assert len(glyphs) == 5 and all(glyph[0] for glyph in glyphs)
    assert not hasattr(_text_native, "rasterize")
    if sys.platform == "linux":
        assert not any("/libass.so" in line for line in Path("/proc/self/maps").read_text().splitlines())


def test_shaped_font_scale_uses_windows_cell_height():
    # This subset has a 1000-unit em, a 1209-unit Windows cell and a
    # 1210-unit hhea cell. Placement and contours must share the ASS scale.
    from kara_templater.fonts import load_font

    face = load_font(Path(__file__).parent / "fonts/KaraTestCJK.ttf")
    _, _, _, _, glyphs = _metrics.text_shape(face.family, 100, 0, 0, 100, 100, 0, 1, "時")
    assert glyphs[0][3][3] == 1000 / 1209
