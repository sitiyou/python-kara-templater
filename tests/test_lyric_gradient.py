"""Measured gradient appearance belongs to the sung glyph, not glow aliases."""

import pytest

from kara_templater import (
    BLUE,
    RED,
    Document,
    Glow,
    Lifetime,
    Line,
    LinearGradient,
    LyricGradient,
    LyricHighlights,
    LyricLine,
    LyricRule,
    ObjectGroup,
    ScalePulse,
    Scene,
    StatePatch,
    Style,
    Vec2,
    layout_document_lyrics,
    linear_rate,
)
from kara_templater._raster import rasterize


def subject():
    doc = Document.create(width=320, height=180, styles=(
        Style(fontname="DejaVu Sans", fontsize=40),
    ))
    doc.records.append(Line(text=r"{\k100}A|a", start_time=1000, end_time=2000))
    layout = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 3))
    return doc, LyricLine.from_layout(layout)


def nodes(node):
    yield node
    if isinstance(node, ObjectGroup):
        for child in node.children:
            yield from nodes(child)


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_base_paint_is_owned_by_unsung_layers_and_their_glow(strategy):
    _, original = subject()
    painted = LyricHighlights.from_singing(
        StatePatch(fill=RED), base_paint=StatePatch(opacity=0),
        base_glow=Glow(BLUE, opacity=0.2), glow=Glow(RED, opacity=0.4),
        strategy=strategy,
    )(original)
    objects = {node.id: node for node in nodes(painted)}
    for target in (*painted.query("character"), *painted.query("ruby")):
        assert objects[target.node_id].state.opacity == 0
        sung = [objects[name] for name in target.aliases if "/highlight:" in name and not name.endswith("/glow")]
        assert sung and all(node.state.opacity == 1 for node in sung)
        if strategy == "clip":
            assert objects[f"{target.node_id}/glow"].state.opacity == 0
    assert all(node.state.opacity == 1 for node in nodes(original))
    with pytest.raises(ValueError, match="geometry"):
        LyricHighlights.from_singing(StatePatch(), base_paint=StatePatch(scale=Vec2(2, 2)))


def test_measured_gradient_scales_to_body_and_ruby_without_tinting_glow():
    doc, original = subject()
    calls = []
    gradient = LyricGradient((RED, BLUE))

    def material(line, target):
        calls.append(target.id)
        return gradient(line, target)

    painted = LyricHighlights.from_singing(
        StatePatch(outline=RED), material=material,
        glow=Glow(BLUE, blur=2, border=4, opacity=0.3),
    )(original)
    objects = {node.id: node for node in nodes(painted)}
    assert len(calls) == 2
    for target in (*painted.query("character"), *painted.query("ruby")):
        assert objects[target.node_id].material is None
        tinted = [objects[name] for name in target.aliases if objects[name].material is not None]
        assert len(tinted) == 1
        field = tinted[0].material
        assert isinstance(field, LinearGradient)
        assert field.bounds == (0, 2 * target.center.y)
        assert field.space == "local"
        halos = [objects[name] for name in target.aliases if name.endswith("/glow")]
        assert halos and all(node.material is None for node in halos)
        assert all(node.state.opacity == pytest.approx(0.3) for node in halos)
    bound = painted.bind(LyricRule("character", "singing", ScalePulse(rate=linear_rate)))
    result = Scene(doc).add(bound).compile(native_tweens=True)
    assert result.event_count > 0
    assert any(report.strategy == "native-clip" for report in result.objects)
    # The factory runs at preparation, not per frame or once per color strip.
    assert len(calls) == 2
    assert all(node.material is None for node in nodes(original))


def test_gradient_follows_centered_scale_and_translation_in_scene():
    doc, line = subject()
    line = LyricHighlights.from_singing(
        StatePatch(), material=LyricGradient((RED, BLUE)),
    )(line).copy(id="copy", offset=Vec2(20, 30))
    bound = line.bind(LyricRule("character", "singing", ScalePulse(peak=1.2)))
    target = bound.query("character")[0]
    before = Scene(doc).add(line).evaluator().at(target.node_id, 1.5)
    after = Scene(doc).add(bound).evaluator().at(target.node_id, 1.5)
    a, b = before.transform.apply(target.center), after.transform.apply(target.center)
    assert (a.x, a.y) == pytest.approx((b.x, b.y))
    assert after.scale.x == pytest.approx(before.scale.x * 1.2)


def test_material_coverage_combination_fails_during_preparation():
    _, line = subject()
    with pytest.raises(ValueError, match="materials require clip"):
        LyricHighlights.from_singing(
            StatePatch(), material=LyricGradient((RED, BLUE)), strategy="coverage",
        )(line)


def test_rendered_sung_body_has_vertical_color_change_and_unsung_body_does_not():
    doc, line = subject()
    line = LyricHighlights.from_singing(
        StatePatch(), material=LyricGradient((RED, BLUE)),
    )(line).copy(id="render", offset=Vec2(80, 50))
    result = Scene(doc).add(line).compile(native_tweens=True)

    def colored_rows(time):
        rgba = rasterize(result.document.dumps(), time, (320, 180)).rgba
        rows = {}
        for y in range(180):
            values = []
            for x in range(320):
                i = (y * 320 + x) * 4
                r, g, b, a = rgba[i:i + 4]
                if a > 220 and abs(r - b) > 20 and g < 20:
                    values.append(r - b)
            if values:
                rows[y] = sum(values) / len(values)
        return rows

    assert not colored_rows(500)
    rows = colored_rows(2200)
    # Actual colored pixels, independent of generated node IDs or band count.
    assert len(rows) > 10
    assert max(rows.values()) > 50
    assert min(rows.values()) < -50
