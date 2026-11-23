from pathlib import Path

import pytest
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from kara_templater import Document, Line, Style, layout_document_lyrics, load_font


def test_palt_keeps_gpos_placement_separate_from_portable_glyph_advance(tmp_path):
    # Give both CJK glyphs distinct XPlacement and XAdvance values. In particular
    # the initial negative placement must survive libass's top-left alignment.
    with TTFont(Path(__file__).parent / "fonts/KaraTestCJK.ttf") as font:
        name = "KaraTest Proportional"
        for record in font["name"].names:
            if record.nameID in (1, 3, 4, 6, 16):
                record.string = (name.replace(" ", "") if record.nameID == 6 else name).encode(record.getEncoding())
        addOpenTypeFeaturesFromString(font, """
            languagesystem DFLT dflt;
            feature palt {
                pos uni6642 <-100 0 -200 0>;
                pos uni3005 <-200 0 -300 0>;
            } palt;
        """)
        path = tmp_path / "palt.ttf"
        font.save(path)
    face = load_font(path)
    style = Style(fontname=face.family, fontsize=100, shadow=0)
    doc = Document.create(styles=(style,))
    doc.records.append(Line(text=r"{\k50}時{\k50}々", start_time=1000, end_time=3000))
    index = len(doc.records) - 1
    ordinary = layout_document_lyrics(doc, index).body
    adjusted = layout_document_lyrics(doc, index, palt=True).body
    assert adjusted.bounds.width < ordinary.bounds.width
    assert adjusted.singing == ordinary.singing
    for old, new in zip(ordinary.characters, adjusted.characters, strict=True):
        assert new.object.state.position.x < new.bounds.left
        assert new.ink_bounds and old.ink_bounds
        assert new.ink_bounds.left - new.object.state.position.x == pytest.approx(
            old.ink_bounds.left - old.object.state.position.x, abs=.25
        )
    assert adjusted.characters[1].bounds.left == pytest.approx(adjusted.characters[0].bounds.right, abs=.25)
    assert layout_document_lyrics(doc, index).body.bounds == ordinary.bounds

    from kara_templater import KaraokeEffects, Track, prepare_tracks

    recipe = KaraokeEffects(entry="none", exit="none", singing="none")
    scene = prepare_tracks(doc, tracks=(Track(id="main", palt=True, min_outline_gap=None, effects=(recipe,)),))
    assert scene.lines[0].layout.body.bounds.width == pytest.approx(adjusted.bounds.width)
    output = scene.ass.compile().document
    rows = [line.text for line in output.lines if not line.comment]
    assert any(line.endswith("時") for line in rows)
    assert any(line.endswith("々") for line in rows)
    assert all(r"\pos(" in line or r"\move(" in line for line in rows)
