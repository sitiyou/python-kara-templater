"""Public lyric configuration and layout extensions use the common animation API."""

from typing import assert_type

from kara_templater import (
    RED,
    Document,
    FadeIn,
    Layout,
    LayoutContext,
    LayoutLine,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricSource,
    LyricSweep,
    LyricTarget,
    Placement,
    ScalePulse,
    StateAnimation,
    Track,
    Vec2,
    prepare_tracks,
)


class CustomLayout(Layout):
    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        return tuple(
            Placement(line.id, Vec2(20, 40 + 60 * index), line.display)
            for index, line in enumerate(lines)
        )


def selected(source: LyricSource) -> bool:
    assert_type(source.style, str)
    assert_type(source.record_index, int | None)
    return source.style == "Default"


def animate(line: LyricLine, target: LyricTarget) -> StateAnimation:
    assert_type(line.query("syllable"), tuple[LyricTarget, ...])
    return ScalePulse()


class Lead(Track):
    def __init__(self, id: str, *, layout: Layout | None = None) -> None:
        super().__init__(
            id=id,
            source=selected,
            layout=Layout() if layout is None else layout,
            animations=(
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("syllable", "singing", animate),
            ),
            factory=LyricSweep(fill=RED).apply,
        )


def prepare(document: Document) -> LyricScene:
    scene = prepare_tracks(document, tracks=(Lead("main", layout=CustomLayout()),))
    assert_type(scene, LyricScene)
    assert_type(scene.lines, tuple[LyricLine, ...])
    return scene


def display_edit(line: LyricLine) -> LyricLine:
    from kara_templater import Lifetime

    adjusted = line.with_display(Lifetime(line.lifetime.start, line.lifetime.end + 1))
    assert_type(adjusted, LyricLine)
    return adjusted
