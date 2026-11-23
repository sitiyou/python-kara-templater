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
