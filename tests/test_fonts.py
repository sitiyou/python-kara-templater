from pathlib import Path

import pytest

from kara_templater import KaraokeLine, Style, TextUnit, layout_characters, layout_line
from kara_templater.fonts import load_font


def test_registered_font_identity_and_repeated_loading():
    path = Path(__file__).parent / "fonts/DejaVuSans.ttf"
    first = load_font(path)
    assert first.family == "DejaVu Sans"
    assert load_font(path) is first


def test_invalid_font_reports_error_instead_of_silent_fallback(tmp_path):
    path = tmp_path / "invalid.ttf"
    path.write_bytes(b"not a font")
    with pytest.raises(ValueError, match="font data"):
        load_font(path)


def test_registered_resources_leave_font_selection_to_each_style():
    fonts = Path(__file__).parent / "fonts"
    primary = load_font(fonts / "KaraTestPrimary.ttf")
    dejavu = load_font(fonts / "DejaVuSans.ttf")
    source = KaraokeLine((TextUnit("A"),))
    styles = (
        Style(name="Body", fontname=primary.family, fontsize=40),
        Style(name="Ruby", fontname=dejavu.family, fontsize=20),
    )
    for style in (*styles, styles[0]):
        layout = layout_line(source, style=style)
        chars = layout_characters(layout, style=style)
        assert {face.family for char in chars for face in char.font_faces} == {
            style.fontname
        }
