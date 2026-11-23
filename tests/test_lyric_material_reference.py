"""Lyric material binding and opacity in scene coordinates."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Line,
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    Scene,
    StateFunction,
    Style,
    Vec2,
    layout_document_lyrics,
)


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
    evaluator = scene.evaluator()
    ruby_target = animated.query("ruby")[0]
    for time in (2.5, 0.5, 1.5):
        assert evaluator.at(ruby_target.node_id, time).opacity == pytest.approx(
            0.6 if body_only else 0.15
        )
    assert animated.query("syllable")[0].node_id == line.query("syllable")[0].node_id
    assert not line.animations


@pytest.mark.parametrize(
    "radius,border", ((0.1, 2), (1, 2), (10, 2), (50, 2), (30, 60))
)
def test_glow_preserves_lyric_layout_and_singing(
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
    )(line)
    assert painted.layout.lyrics == line.layout.lyrics
    assert painted.query("character")[0].singing == line.query("character")[0].singing


def test_range_opacity_within_one_syllable_preserves_glyph_coverage():
    canvas, line = subject(r"{\k200}WW")
    assert len(line.query("syllable")) == 1
    offsets = {item.object.id: item.start for item in line.layout.body.characters}

    def factory(timing: LyricAnimationContext) -> StateFunction:
        opacity = 0.25 if offsets[timing.target.node_id] < 1 else 0.75
        return StateFunction(
            lambda base, p: replace(base, opacity=opacity), frozenset(("opacity",))
        )

    animated = line.bind(LyricRule("character", "enter", factory, duration=4))
    evaluator = Scene(canvas).add(animated).evaluator()
    assert [evaluator.at(t.node_id, 1.5).opacity for t in animated.query("character")] == [0.25, 0.75]
    assert len(animated.query("syllable")) == 1
