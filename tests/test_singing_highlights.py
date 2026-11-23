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
        blend_glow=False,
    )(line)
    canvas = Document.create(width=160, height=96, styles=tuple(doc.styles.values()))
    scene = Scene(canvas).add(line)
    native = scene.ass.compile(budget=SceneBudget(fps=1), native_tweens=True)
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
        sampled = expected_scene.ass.compile()
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


@pytest.mark.parametrize("reverse", [False, True])
def test_two_color_soft_glow_meets_at_the_singing_front(reverse):
    doc, line = make_line()
    painted = LyricHighlights.from_singing(
        StatePatch(fill=RED), reverse=reverse,
        glow=Glow.from_studio(RED, radius=4), base_glow=Glow.from_studio(BLUE, radius=4),
    )(line)
    nodes = {n.id: n for n in leaves(painted)}
    char = painted.query("character")[0]
    halos = [nodes[k] for k in char.aliases if "/glow" in k]
    strips = []
    for halo in halos:
        assert isinstance(halo.clip, RectangleClip) and isinstance(halo.clip.deform, RectangleKeyframes)
        left, _, right, _ = halo.clip.deform.bounds_at(1.04 - halo.time_origin)
        strips.append((left, right, halo.state.fill))
    strips.sort(key=lambda strip: strip[0])
    assert all(a[1] == b[0] for a, b in zip(strips, strips[1:], strict=False))
    red = [ink.red for _, _, ink in strips]
    assert red == sorted(red, reverse=not reverse)
    assert min(red) == 0 and max(red) == 255
    assert max(abs(a - b) for a, b in zip(red, red[1:], strict=False)) < 64


@pytest.mark.parametrize("before_alpha", [0, 0.25])
def test_soft_glow_blends_premultiplied_color(before_alpha):
    _, line = make_line()
    effect = LyricHighlights.from_singing(
        StatePatch(fill=RED), glow=Glow(RED, blur=4),
        base_glow=Glow(BLUE, blur=4, opacity=before_alpha),
    )(line)
    char = effect.query("character")[0]
    strips = [node.state for node in leaves(effect) if node.id in char.aliases and "/band:" in node.id]
    assert strips and all(before_alpha < state.opacity < 1 for state in strips)
    for state in strips:
        # Opacity gives the sung fraction independently of strip placement.
        sung = (state.opacity - before_alpha) / (1 - before_alpha)
        assert state.fill.red * state.opacity == pytest.approx(255 * sung, abs=0.5)
        assert state.fill.blue * state.opacity == pytest.approx(255 * before_alpha * (1 - sung), abs=0.5)


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


def test_delayed_copy_offsets_each_ruby_glyphs_own_wipe():
    _, line = make_line(r"{\k8}A|reading{\k15}B|b")
    copied = line.copy(id="delayed", delay=2)
    result = LyricHighlights.from_singing(
        StatePatch(fill=RED),
        glow=Glow(RED, blur=20),
    )(copied)
    nodes = {n.id: n for n in leaves(result)}
    # "reading" shares its 80 ms across seven glyphs; "b" gets the next 150 ms.
    cuts = (1000, 1011, 1022, 1034, 1045, 1057, 1068, 1080, 1230)
    for target, start, end in zip(result.query("ruby"), cuts[:-1], cuts[1:], strict=True):
        piece = nodes[next(a for a in target.aliases if "/highlight:" in a)]
        keys = piece.clip.deform
        assert isinstance(keys, RectangleKeyframes)
        assert keys.keyframes[1][0] + piece.time_origin == pytest.approx(
            start / 1000 + 2
        )
        assert keys.keyframes[2][0] + piece.time_origin == pytest.approx(
            end / 1000 + 2
        )


def test_ass_supports_instant_wipe_and_rejects_repeated_singing():
    for text in (r"{\k0}A{\k23}B", r"{\k8}A{\k15}#"):
        doc, line = make_line(text)
        result = LyricHighlights.from_singing(
            StatePatch(fill=RED),
            glow=Glow(RED, blur=2),
            blend_glow=False,
        )(line)
        canvas = Document.create(
            width=160, height=96, styles=tuple(doc.styles.values())
        )
        scene = Scene(canvas).add(result)
        if "#" in text:
            with pytest.raises(ValueError, match="frame sampling"):
                scene.ass.compile()
        else:
            assert scene.ass.compile().event_count
