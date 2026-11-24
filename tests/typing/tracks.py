"""Public lyric configuration and layout extensions use the common animation API."""

from typing import assert_type

from kara_templater import (
    RED,
    Document,
    FadeIn,
    Layout,
    LayoutContext,
    LineLayoutRequest,
    LyricAnimationContext,
    LyricHighlights,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricSource,
    LyricTarget,
    Placement,
    ScalePulse,
    StateAnimation,
    StatePatch,
    Track,
    Transform,
    Vec2,
    build_lyric_scene,
)


class CustomLayout(Layout):
    def allocate(
        self, lines: tuple[LineLayoutRequest, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        return tuple(
            Placement(line.id, Vec2(20, 40 + 60 * index), line.requested_display)
            for index, line in enumerate(lines)
        )


def selected(source: LyricSource) -> bool:
    assert_type(source.style, str)
    assert_type(source.record_index, int | None)
    return source.style == "Default"


def animate(timing: LyricAnimationContext) -> StateAnimation:
    assert_type(timing.line.query("syllable"), tuple[LyricTarget, ...])
    assert_type(timing.duration, float)
    assert_type(timing.target, LyricTarget)
    return ScalePulse()


class Lead(Track):
    def __init__(self, id: str, *, layout: Layout | None = None) -> None:
        super().__init__(
            id=id,
            source=selected,
            layout=Layout() if layout is None else layout,
            effects=(
                LyricHighlights.from_timing(StatePatch(fill=RED)),
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("syllable", "timing", animate),
                LyricRule(
                    "character", "after_timing",
                    Transform(offset=lambda p: Vec2(0, -20 * p), opacity=lambda p: 1 - p),
                    duration=0.3, offset=0.1,
                ),
            ),
        )


def prepare(document: Document) -> LyricScene:
    scene = build_lyric_scene(document, tracks=(Lead("main", layout=CustomLayout()),))
    assert_type(scene, LyricScene)
    assert_type(scene.lines, tuple[LyricLine, ...])
    return scene


def display_edit(line: LyricLine) -> LyricLine:
    from kara_templater import Lifetime

    adjusted = line.with_display(Lifetime(line.lifetime.start, line.lifetime.end + 1))
    assert_type(adjusted, LyricLine)
    return adjusted
