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


@pytest.mark.parametrize("unsung", [False, True])
def test_material_coverage_combination_fails_during_preparation(unsung):
    _, line = subject()
    gradient = LyricGradient((RED, BLUE))
    with pytest.raises(ValueError, match="materials require clip"):
        LyricHighlights.from_singing(
            StatePatch(), strategy="coverage", material=None if unsung else gradient,
            base_material=gradient if unsung else None,
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


def test_horizontal_ramp_uses_the_same_body_coordinates_for_glyphs_and_readings():
    doc = Document.create(width=320, height=180, styles=(
        Style(fontname="DejaVu Sans", fontsize=40),
    ))
    doc.records.append(Line(text=r"{\k100}M|i{\k100}M|i", start_time=1000, end_time=3000))
    layout = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 4))
    line = LyricLine.from_layout(layout)
    gradient = LyricGradient((RED, BLUE), axis="x")
    for role, characters in (
        ("character", layout.body.characters),
        ("ruby", tuple(c for ruby in layout.ruby for c in ruby.layout.characters)),
    ):
        for target, glyph in zip(line.query(role), characters, strict=True):
            ramp = gradient(line, target)
            assert ramp.fill is not None and glyph.layout_scale is not None
            # Compare both ends in line coordinates. A glyph-wide restart,
            # or a separate reading-wide ramp, would move these endpoints.
            assert tuple(glyph.bounds.left + stop.position * glyph.layout_scale.x
                         for stop in ramp.fill.stops) == pytest.approx(
                             (min(c.ink_bounds.left for c in layout.body.characters if c.ink_bounds),
                              max(c.ink_bounds.right for c in layout.body.characters if c.ink_bounds))
                         )


@pytest.mark.parametrize("placement", ("inline", "independent"))
def test_volume_gradient_shares_the_body_span_only_for_a_leading_inline_cue(placement):
    from kara_templater import (
        CueMarker,
        CuePreset,
        KaraokeEffects,
        Track,
        VolumeCue,
        prepare_tracks,
    )

    doc = Document.create(width=320, height=180, styles=(Style(fontname="DejaVu Sans", fontsize=40),))
    marker = CueMarker("intro", "lead", placement=placement)
    doc.records.append(Line(text=marker.markup() + r"{\k100}M|i{\k100}M",
                            start_time=1000, end_time=3000))
    gradient = LyricGradient((RED, BLUE), axis="x")
    track = Track(id="voice", cues={"lead": CuePreset(factory=VolumeCue(count=3, height=24, border=0))},
                  effects=(KaraokeEffects(entry="none", exit="none", singing="none", material=gradient),))
    scene = prepare_tracks(doc, tracks=(track,))
    line, = scene.lines
    cue = next(c for c in (*line.children, *line.independent) if "/cue:" in c.id)
    columns = [n for n in nodes(cue) if isinstance(n.material, LinearGradient)]
    assert len(columns) == 3
    for bar in columns:
        left, right = bar.material.bounds
        assert left + bar.state.position.x == pytest.approx(0)
        assert right + bar.state.position.x == pytest.approx(
            line.layout.body.bounds.right - cue.state.position.x if placement == "inline" else 18
        )
    target = line.query("character")[0]
    left, right = gradient(line, target).bounds
    assert (left < 0) == (placement == "inline")
    assert right - left > 18
    assert scene.compile(native_tweens=True).event_count > 0


def test_alternating_styles_share_their_own_ramps_with_readings_and_lead():
    from kara_templater import (
        CueMarker,
        CuePreset,
        KaraokeEffects,
        Track,
        VolumeCue,
        prepare_tracks,
    )

    doc = Document.create(width=400, height=200, styles=tuple(
        Style(name=name, fontname="DejaVu Sans", fontsize=40)
        for name in ("Default", "Lead", "Reply")
    ))
    cue = CueMarker("intro", "bars")
    doc.records.append(Line(
        text=cue.markup() + r"{\rLead\k50}M|i{\rReply\k50}M|i{\rLead\k50}M|i{\rReply\k50}M|i",
        start_time=1000, end_time=3000,
    ))
    ramps = {"Lead": LyricGradient((RED, BLUE), axis="x"),
             "Reply": LyricGradient((BLUE, RED), axis="x")}
    scene = prepare_tracks(doc, tracks=(Track(
        id="duet", cues={"bars": CuePreset(factory=VolumeCue(count=2, height=24, border=0))},
        effects=(KaraokeEffects(entry="none", exit="none", singing="scanline",
                               ruby_scanline="both", scanline_mode="follow_after", material=ramps,
                               base_material={"Lead": ramps["Reply"]}),),
    ),))
    line, = scene.lines
    body = line.layout.body.characters
    assert [t.source_style for t in line.query("ruby")] == ["Lead", "Reply"] * 2
    for role, glyphs in (("character", body), ("ruby", tuple(
        g for r in line.layout.ruby for g in r.layout.characters
    ))):
        for target, glyph in zip(line.query(role), glyphs, strict=True):
            style = target.source_style
            assert style is not None and glyph.layout_scale is not None
            left, right = ramps[style](line, target).bounds
            ink = [c.ink_bounds for c in body if c.source_style == style and c.ink_bounds]
            expected_left = 0 if style == "Lead" else min(b.left for b in ink)
            assert (glyph.object.state.position.x + left * glyph.layout_scale.x,
                    glyph.object.state.position.x + right * glyph.layout_scale.x) == pytest.approx(
                        (expected_left, max(b.right for b in ink)))
    prefix = next(n for n in line.children if "/cue:" in n.id)
    bars = [n for n in nodes(prefix) if isinstance(n.material, LinearGradient)]
    assert len(bars) == 4
    assert [bar.material.fill.stops[0].color for bar in bars] == [BLUE, RED, BLUE, RED]
    for bar in bars:
        assert bar.material.bounds[1] + bar.state.position.x == pytest.approx(body[2].bounds.right)
    first = line.query("character")[0]
    front = next(n for n in nodes(line) if n.id.startswith(first.node_id + "/")
                 and ":front:" in n.id and isinstance(n.material, LinearGradient))
    glyph = body[0]
    assert glyph.layout_scale is not None
    assert tuple(glyph.object.state.position.x + x * glyph.layout_scale.x
                 for x in front.material.bounds) == pytest.approx(
                     (glyph.bounds.left, glyph.bounds.right))
    scene.compile(native_tweens=True)
