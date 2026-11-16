"""Common lyric opacity against independently encoded native ASS glyphs."""

from dataclasses import replace
from math import floor

import pytest
from PIL import Image, ImageChops

from kara_templater import (
    Document,
    Lifetime,
    Line,
    LyricLine,
    LyricRole,
    LyricRule,
    LyricTarget,
    Scene,
    StateFunction,
    Style,
    Vec2,
    layout_document_lyrics,
)
from kara_templater._raster import rasterize
from kara_templater.scene_text import PositionedText

SIZE = (640, 480)


def subject(text: str) -> tuple[Document, LyricLine]:
    document = Document.create(
        width=640,
        height=480,
        styles=(Style(fontname="DejaVu Sans", fontsize=40, outline=0, shadow=0),),
    )
    document.records.append(Line(text=text, start_time=1000, end_time=3000))
    layout = layout_document_lyrics(
        document, len(document.records) - 1, display=Lifetime(0, 4)
    )
    # The Scene renders only its objects; remove the source event from this canvas.
    canvas = Document.create(
        width=640, height=480, styles=tuple(document.styles.values())
    )
    return canvas, LyricLine.from_layout(layout)


def reference_glyph(item: PositionedText, opacity: float, offset: Vec2) -> Image.Image:
    obj = item.object
    point = obj.state.position + offset
    document = Document.create(width=640, height=480)
    document.records.append(
        Line(
            start_time=0,
            end_time=4000,
            text=(
                rf"{{\an7\pos({point.x},{point.y})\fn{obj.font}\fs{obj.font_size}"
                r"\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}" + obj.text
            ),
        )
    )
    image = Image.frombytes("RGBA", SIZE, rasterize(document.dumps(), 500, SIZE).rgba)
    image.putalpha(image.getchannel("A").point(lambda a: floor(a * opacity + 0.5)))
    return image


def compare(actual: bytes, expected: Image.Image) -> None:
    image = Image.frombytes("RGBA", SIZE, actual)
    assert image.getchannel("A").getbbox()
    assert (
        max(
            ImageChops.difference(
                image.getchannel("A"), expected.getchannel("A")
            ).tobytes()
        )
        <= 1
    )
    for color in ("black", "white"):
        backdrop = Image.new("RGBA", SIZE, color)
        left = Image.alpha_composite(backdrop, image).convert("RGB")
        right = Image.alpha_composite(backdrop, expected).convert("RGB")
        assert max(ImageChops.difference(left, right).tobytes()) <= 1


@pytest.mark.parametrize("role", ("syllable", "character"))
def test_selected_opacity_matches_independent_native_letters(role: LyricRole):
    canvas, line = subject(r"{\k100}A{\k100}B")

    def opacity_factory(line: LyricLine, target: LyricTarget) -> StateFunction:
        value = 0.25 if target.singing[0].start == 1 else 0.75
        return StateFunction(
            lambda base, p: replace(base, opacity=value), frozenset(("opacity",))
        )

    animated = line.bind(LyricRule(role, "enter", opacity_factory, duration=4))
    output = Scene(canvas).add(animated).compile().document.dumps()
    expected = Image.new("RGBA", SIZE)
    for item, opacity in zip(line.layout.body.characters, (0.25, 0.75), strict=True):
        expected = Image.alpha_composite(
            expected, reference_glyph(item, opacity, Vec2())
        )
    compare(rasterize(output, 500, SIZE).rgba, expected)


@pytest.mark.parametrize("body_only", (False, True))
def test_ruby_opacity_selection_keeps_whole_line_transform(body_only: bool):
    canvas, line = subject(r"{\k200}A|a")
    offset = Vec2(20, -10)
    parent = StateFunction(
        lambda base, p: replace(base, position=base.position + offset, opacity=0.6),
        frozenset(("position", "opacity")),
    )
    child = StateFunction(
        lambda base, p: replace(base, opacity=0.25), frozenset(("opacity",))
    )
    animated = line.bind(
        LyricRule("line", "enter", parent, duration=4),
        LyricRule("character" if body_only else "syllable", "enter", child, duration=4),
    )
    scene = Scene(canvas).add(animated)
    expected = Image.new("RGBA", SIZE)
    for item in line.layout.body.characters:
        expected = Image.alpha_composite(expected, reference_glyph(item, 0.15, offset))
    for ruby in line.layout.ruby:
        for item in ruby.layout.characters:
            expected = Image.alpha_composite(
                expected, reference_glyph(item, 0.6 if body_only else 0.15, offset)
            )
    output = scene.compile().document.dumps()
    compare(rasterize(output, 500, SIZE).rgba, expected)
    evaluator = scene.evaluator()
    ruby_target = animated.query("ruby")[0]
    for time in (2.5, 0.5, 1.5):
        assert evaluator.at(ruby_target.node_id, time).opacity == pytest.approx(
            0.6 if body_only else 0.15
        )
    assert animated.query("syllable")[0].node_id == line.query("syllable")[0].node_id
    assert not line.animations


def test_dynamic_glow_scale_and_composed_alpha_match_native_glyphs():
    from kara_templater import RED, Coverage, Glow, GlowFunction, SceneBudget

    size = (160, 120)
    source = Document.create(
        width=160,
        height=120,
        styles=(
            Style(
                fontname="DejaVu Sans", fontsize=20, outline=0, shadow=0, margin_v=40
            ),
        ),
    )
    source.records.append(Line(text=r"{\k10}A|a", start_time=0, end_time=100))
    layout = layout_document_lyrics(source, len(source.records) - 1)
    line = LyricLine.from_layout(layout)
    glow = GlowFunction(
        lambda state, t: Glow(RED, blur=(0.5 + 2 * t / 0.1) * state.scale.x),
        max_blur=3,
        max_border=0,
    )
    line = replace(
        line,
        coverage=Coverage(
            glows={
                target.node_id: glow
                for target in (*line.query("character"), *line.query("ruby"))
            }
        ),
    )
    line = line.bind(
        LyricRule(
            "line",
            "enter",
            StateFunction(
                lambda base, p: replace(
                    base,
                    scale=Vec2(1 + 0.2 * p, 1 + 0.2 * p),
                    position=Vec2(10 * p, 0),
                    opacity=0.65,
                ),
                frozenset(("scale", "position", "opacity")),
            ),
            duration=0.1,
        ),
        LyricRule(
            "character",
            "enter",
            StateFunction(
                lambda base, p: replace(base, opacity=0.8),
                frozenset(("opacity",)),
            ),
            duration=0.1,
        ),
        LyricRule(
            "ruby",
            "enter",
            StateFunction(
                lambda base, p: replace(base, opacity=0.6),
                frozenset(("opacity",)),
            ),
            duration=0.1,
        ),
    )
    canvas = Document.create(width=160, height=120)
    budget = SceneBudget(fps=50, max_events=100_000, max_active=10_000)
    result = Scene(canvas).add(line).compile(budget=budget)
    assert result.objects[0].sample_times == pytest.approx(
        (0.01, 0.03, 0.05, 0.07, 0.09)
    )
    script = result.document.dumps()
    glyphs = [(item, 0.8) for item in layout.body.characters]
    glyphs.extend(
        (item, 0.6) for ruby in layout.ruby for item in ruby.layout.characters
    )
    for time in (90, 10, 50, 30, 70):
        p = time / 100
        scale = 1 + 0.2 * p
        radius = (0.5 + 2 * p) * scale
        expected = Image.new("RGBA", size)
        for item, opacity in glyphs:
            obj = item.object
            point = obj.state.position * scale + Vec2(10 * p, 0)
            reference = Document.create(width=160, height=120)
            for layer, color, blur in ((0, "0000FF", radius), (1, "FFFFFF", 0)):
                reference.records.append(
                    Line(
                        start_time=0,
                        end_time=100,
                        layer=layer,
                        text=(
                            rf"{{\an7\pos({point.x},{point.y})\fn{obj.font}\fs{obj.font_size}"
                            rf"\fscx{100 * scale}\fscy{100 * scale}\bord0\shad0\blur{blur}"
                            rf"\1c&H{color}&\alpha&H00&}}" + obj.text
                        ),
                    )
                )
            component = Image.frombytes(
                "RGBA", size, rasterize(reference.dumps(), time, size).rgba
            )
            component.putalpha(
                component.getchannel("A").point(
                    [floor(a * opacity + 0.5) for a in range(256)]
                )
            )
            expected = Image.alpha_composite(expected, component)
        expected.putalpha(
            expected.getchannel("A").point(lambda a: floor(a * 0.65 + 0.5))
        )
        actual = Image.frombytes("RGBA", size, rasterize(script, time, size).rgba)
        assert actual.getchannel("A").getbbox()
        for background in ("black", "white"):
            backdrop = Image.new("RGBA", size, background)
            left = Image.alpha_composite(backdrop, actual).convert("RGB")
            right = Image.alpha_composite(backdrop, expected).convert("RGB")
            assert max(ImageChops.difference(left, right).tobytes()) <= 2


@pytest.mark.parametrize(
    "radius,border", ((0.1, 2), (1, 2), (10, 2), (50, 2), (30, 60))
)
def test_native_glow_bounds_preserve_independent_whole_glyph(
    radius: float, border: float
):
    from kara_templater import (
        BLUE,
        RED,
        Glow,
        Highlight,
        HighlightPass,
        LyricHighlights,
        Region,
        StatePatch,
        TimeSpan,
    )

    canvas, line = subject(r"{\k200}A")
    offset = Vec2(150, 120)
    line = replace(line, state=replace(line.state, position=offset))
    painted = LyricHighlights(
        highlights=(
            Highlight(
                "singing",
                0,
                (
                    HighlightPass(
                        TimeSpan(1, 3),
                        Region(
                            line.layout.body.bounds.left, line.layout.body.bounds.right
                        ),
                    ),
                ),
                StatePatch(fill=BLUE),
                glow=Glow(BLUE, border=border, blur=radius),
            ),
        ),
        glow=Glow(RED, border=border, blur=radius),
    ).apply(line)
    script = Scene(canvas).add(painted).compile().document.dumps()
    assert painted.layout.lyrics == line.layout.lyrics
    assert painted.query("character")[0].singing == line.query("character")[0].singing
    obj = line.layout.body.characters[0].object
    point = obj.state.position + offset
    # The same original pass is complete at 3s even with a 60px stroke and
    # large blur. Both endpoints include the complete off-box drawing.
    for time, glow_color, fill_color in (
        (3500, "FF0000", "FF0000"),
        (500, "0000FF", "FFFFFF"),
    ):
        reference = Document.create(width=640, height=480)
        for layer, color, width, blur in (
            (0, glow_color, border, radius),
            (1, fill_color, 0, 0),
        ):
            reference.records.append(
                Line(
                    start_time=0,
                    end_time=4000,
                    layer=layer,
                    text=(
                        rf"{{\an7\pos({point.x},{point.y})\fn{obj.font}\fs{obj.font_size}"
                        rf"\bord{width}\shad0\blur{blur}\1c&H{color}&\3c&H{color}&\alpha&H00&}}A"
                    ),
                )
            )
        actual = rasterize(script, time, SIZE)
        expected = rasterize(reference.dumps(), time, SIZE)
        assert any(actual.rgba[3::4])
        assert actual.rgba == expected.rgba


def test_range_opacity_within_one_syllable_preserves_glyph_coverage():
    canvas, line = subject(r"{\k200}WW")
    assert len(line.query("syllable")) == 1
    offsets = {item.object.id: item.start for item in line.layout.body.characters}

    def factory(line: LyricLine, target: LyricTarget) -> StateFunction:
        opacity = 0.25 if offsets[target.node_id] < 1 else 0.75
        return StateFunction(
            lambda base, p: replace(base, opacity=opacity), frozenset(("opacity",))
        )

    animated = line.bind(LyricRule("character", "enter", factory, duration=4))
    expected = Image.new("RGBA", SIZE)
    for item, opacity in zip(line.layout.body.characters, (0.25, 0.75), strict=True):
        expected = Image.alpha_composite(
            expected, reference_glyph(item, opacity, Vec2())
        )
    output = Scene(canvas).add(animated).compile().document.dumps()
    compare(rasterize(output, 500, SIZE).rgba, expected)
    assert len(animated.query("syllable")) == 1
