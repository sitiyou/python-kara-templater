"""Source singing owns body width independently of decorative raster margins."""

from dataclasses import replace

import pytest
from PIL import Image, ImageChops

from kara_templater import (
    BLUE,
    RED,
    Document,
    Glow,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    ObjectGroup,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneBudget,
    StatePatch,
    Style,
    layout_document_lyrics,
)
from kara_templater._raster import rasterize


def make_line(text=r"{\k8}A{\k15}B"):
    doc = Document.create(
        width=160,
        height=96,
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=2, shadow=0),),
    )
    doc.records.append(Line(start_time=1000, end_time=1230, text=text))
    line = LyricLine.from_layout(
        layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0.9, 1.4))
    )
    return doc, line


def leaves(node):
    if isinstance(node, ObjectGroup):
        return tuple(leaf for child in node.children for leaf in leaves(child))
    return (node,)


@pytest.mark.parametrize("blur", (0, 10, 32))
def test_short_syllable_front_reaches_body_edges_on_source_clock(blur):
    _, line = make_line()
    effect = LyricHighlights.from_singing(
        StatePatch(fill=RED, outline=BLUE, border=8),
        glow=Glow(RED, blur=blur, border=14),
        base_glow=Glow(BLUE, blur=blur, border=13),
    )(line)
    nodes = {node.id: node for node in leaves(effect)}
    for target, glyph in zip(
        effect.query("character"), line.layout.body.characters, strict=True
    ):
        unit = next(
            u for u in line.layout.lyrics.units if u.start <= glyph.start < u.end
        )
        body = line.layout.body.range_bounds(unit.start, unit.end)
        assert glyph.layout_scale is not None
        for identity in (target.node_id, *target.aliases):
            node = nodes[identity]
            assert isinstance(node.clip, RectangleClip)
            assert isinstance(node.clip.deform, RectangleKeyframes)
            # Base is a suffix; highlight is its exact complementary prefix.
            edge = 2 if "/highlight:" in identity else 0
            for progress in (0, 0.1, 0.25, 0.5, 0.9, 1):
                span = unit.segments[0].singing
                time = span.start + (span.end - span.start) * progress
                actual = node.clip.deform.bounds_at(time - node.time_origin)[edge]
                expected = (
                    body.left + body.width * progress - glyph.bounds.left
                ) / glyph.layout_scale.x
                assert actual == pytest.approx(expected)


def test_automatic_shoulders_reserve_layout_time_without_changing_singing():
    _, line = make_line()
    line = line.with_display(Lifetime(1, 1.23))
    result = LyricHighlights.from_singing(StatePatch(fill=RED))(line)
    assert result.lifetime.start == pytest.approx(0.98)
    assert result.lifetime.end == pytest.approx(1.25)
    assert result.layout.lyrics == line.layout.lyrics
    assert result.query("character")[0].singing == line.query("character")[0].singing


def test_single_pass_lowers_at_one_fps_and_matches_static_boundary_pixels():
    doc, line = make_line()
    line = LyricHighlights.from_singing(
        StatePatch(fill=RED),
        glow=Glow(RED, blur=3, border=3),
        base_glow=Glow(BLUE, blur=3, border=3),
    )(line)
    canvas = Document.create(width=160, height=96, styles=tuple(doc.styles.values()))
    scene = Scene(canvas).add(line)
    native = scene.compile(budget=SceneBudget(fps=1), native_tweens=True)
    assert any(obj.strategy == "native-clip" for obj in native.objects)
    # Both include the separate 20 ms shoulders, the 80 ms syllable and handoff.
    for time in (980, 1000, 1080, 1230, 1250):

        def freeze(node, time=time):
            if isinstance(node, ObjectGroup):
                return replace(node, children=tuple(freeze(c) for c in node.children))
            assert isinstance(node.clip, RectangleClip)
            assert isinstance(node.clip.deform, RectangleKeyframes)
            bounds = node.clip.deform.bounds_at(time / 1000 - node.time_origin)
            state = scene.evaluator().at(node.id, time / 1000)
            left, top, right, bottom = bounds
            screen = (
                state.position.x + left * state.scale.x,
                state.position.y + top * state.scale.y,
                state.position.x + right * state.scale.x,
                state.position.y + bottom * state.scale.y,
            )
            return replace(node, clip=RectangleClip(*screen))

        expected_scene = Scene(canvas).add(freeze(line))
        sampled = expected_scene.compile()
        actual = rasterize(native.document.dumps(), time, (160, 96)).rgba
        expected = rasterize(sampled.document.dumps(), time, (160, 96)).rgba
        for background in ("black", "white"):
            images = [
                Image.alpha_composite(
                    Image.new("RGBA", (160, 96), background),
                    Image.frombytes("RGBA", (160, 96), pixels),
                ).convert("RGB")
                for pixels in (actual, expected)
            ]
            assert max(ImageChops.difference(*images).tobytes()) <= 2, time


def test_coverage_uses_body_ownership_without_clip_shoulders():
    _, line = make_line()
    line = replace(line, lifetime=Lifetime(1, 1.23))
    result = LyricHighlights.from_singing(
        StatePatch(fill=RED),
        strategy="coverage",
        glow=Glow(RED, blur=3),
    )(line)
    assert result.lifetime == line.lifetime
    assert result.coverage is not None


def test_ruby_and_delayed_copy_use_body_progress_with_their_own_geometry():
    _, line = make_line(r"{\k8}A|reading{\k15}B|b")
    copied = line.copy(id="delayed", delay=2)
    result = LyricHighlights.from_singing(
        StatePatch(fill=RED),
        glow=Glow(RED, blur=20),
    )(copied)
    nodes = {n.id: n for n in leaves(result)}
    for target in result.query("ruby"):
        piece = nodes[next(a for a in target.aliases if "/highlight:" in a)]
        keys = piece.clip.deform
        assert isinstance(keys, RectangleKeyframes)
        assert keys.keyframes[1][0] + piece.time_origin == pytest.approx(
            target.singing[0].start + target.delay
        )
        assert keys.keyframes[2][0] + piece.time_origin == pytest.approx(
            target.singing[0].end + target.delay
        )


def test_zero_duration_and_repeated_singing_remain_valid():
    for text in (r"{\k0}A{\k23}B", r"{\k8}A{\k15}#"):
        doc, line = make_line(text)
        result = LyricHighlights.from_singing(
            StatePatch(fill=RED),
            glow=Glow(RED, blur=2),
        )(line)
        canvas = Document.create(
            width=160, height=96, styles=tuple(doc.styles.values())
        )
        compiled = Scene(canvas).add(result).compile(native_tweens=True)
        assert compiled.event_count
