"""Literal author text stays literal in native text and glyph geometry."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Scene,
    TextObject,
    Vec2,
    VisualState,
    outline_text,
    text_to_path,
)
from kara_templater._raster import rasterize


@pytest.mark.parametrize(
    "literal,encoded",
    (
        ("a{b}", r"a\{b\}"),
        (r"\N\n\h", "\\\u2060N\\\u2060n\\\u2060h"),
        (r"{\p1}m 0 0 l 50 50", "\\{\\\u2060p1\\}m 0 0 l 50 50"),
        ("A\nB", r"A\NB"),
    ),
)
def test_literal_text_compiles_without_ass_injection(literal, encoded):
    doc = Document.create(width=640, height=120)
    node = TextObject(
        id="literal",
        text=literal,
        lifetime=Lifetime(0, 1),
        font_size=24,
        state=VisualState(position=Vec2(10, 10)),
    )
    result = Scene(doc).add(node).ass.compile()
    # Build the independent ASS reference from a safe placeholder event and the
    # explicit encoding above, without passing the literal through the compiler.
    reference = Scene(doc).add(replace(node, text="PLACEHOLDER")).ass.compile().document
    reference.lines[-1].text = reference.lines[-1].text.replace("PLACEHOLDER", encoded)
    assert result.document.lines[-1].text.endswith("}" + encoded)
    record_index = next(
        index
        for index, record in enumerate(result.document.records)
        if record is result.document.lines[-1]
    )
    assert result.document.text_at(record_index).text == literal
    actual = rasterize(result.document.dumps(), 500, (640, 120))
    expected = rasterize(reference.dumps(), 500, (640, 120))
    assert actual.rgba == expected.rgba
    assert any(actual.rgba[3::4])
    assert Document.parse(result.document.dumps()).dumps() == result.document.dumps()


@pytest.mark.parametrize("literal", (r"\N", r"\h", r"{\p1}", "a{b}"))
def test_literal_outline_measurement_does_not_interpret_ass_escapes(literal):
    node = TextObject(
        id="literal",
        text=literal,
        font="DejaVu Sans Mono",
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(10, 10)),
    )
    outline = outline_text(node)
    cell = outline_text(replace(node, text="M"))
    assert outline.path is not None
    assert outline.layout_bounds.width == pytest.approx(
        len(literal) * cell.layout_bounds.width
    )
    assert outline.layout_bounds.height == cell.layout_bounds.height
    doc = Document.create(width=640, height=120)
    native = rasterize(Scene(doc).add(node).ass.compile().document.dumps(), 0, (640, 120))
    vector = rasterize(
        Scene(doc).add(text_to_path(node)).ass.compile().document.dumps(), 0, (640, 120)
    )
    alpha = native.rgba[3::4]
    # Match the existing glyph-outline tolerance for text versus vector hinting.
    assert sum(
        abs(a - b) for a, b in zip(alpha, vector.rgba[3::4], strict=True)
    ) / sum(alpha) < 0.05


@pytest.mark.parametrize("literal", ("A\rB", "A\x00B"))
def test_literal_text_rejects_record_breaks_and_nul(literal):
    with pytest.raises(ValueError, match="CR or NUL"):
        TextObject(id="invalid", text=literal, lifetime=Lifetime(0, 1))
