"""User extensions retain concrete return types without compiler internals."""

from typing import assert_type

from kara_templater import (
    Document,
    DocumentLyrics,
    FadeIn,
    Jump,
    Layout,
    LayoutContext,
    LineLayoutRequest,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricTarget,
    ObjectGroup,
    Placement,
    StateAnimation,
    TextObject,
)


class CustomLayout(Layout):
    def allocate(
        self, lines: tuple[LineLayoutRequest, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        return super().allocate(lines, context)


def animate(
    line: LyricLine, text: TextObject, group: ObjectGroup, animation: StateAnimation
) -> LyricLine:
    assert_type(text.animate(animation, duration=0.2), TextObject)
    assert_type(group.animate(animation, duration=0.2), ObjectGroup)
    assert_type(line.animate(FadeIn(), duration=0.2), LyricLine)
    assert_type(line.query("syllable"), tuple[LyricTarget, ...])
    assert_type(line.bind(LyricRule("syllable", "timing", Jump())), LyricLine)
    return line.animate(animation, duration=0.2)


def orchestrate(document: "Document") -> "LyricScene":
    from kara_templater import LyricLinePlan, Track, build_lyric_scene

    scene = build_lyric_scene(
        document,
        tracks=(
            Track(
                id="main",
                source=lambda source: source.style == "Main",
                layout=CustomLayout(rows=3),
                effects=(LyricRule("line", "enter", FadeIn(), duration=0.2),),
            ),
        ),
    )
    assert_type(scene, LyricScene)
    assert_type(scene.lines, tuple[LyricLine, ...])
    assert_type(scene.plans, tuple[LyricLinePlan, ...])
    return scene


def bind_arrival(line: LyricLine) -> LyricLine:
    from kara_templater import Highlight, HighlightArrival, TimeSpan

    def highlights(line: LyricLine) -> tuple[Highlight, ...]:
        return ()

    anchor = HighlightArrival(highlights=highlights)
    assert_type(anchor(line, line.query("character")[0]), tuple[TimeSpan, ...])
    return line.bind(LyricRule("character", anchor, Jump(), hold=False))


def structured(document: Document, lyrics: "DocumentLyrics") -> LyricScene:
    from kara_templater import (
        Lifetime,
        LyricLayout,
        LyricSource,
        Track,
        build_lyric_scene,
        layout_lyrics,
    )

    source = LyricSource.from_lyrics("verse", lyrics, display=Lifetime(0, 5))
    assert_type(source.record_index, int | None)
    assert_type(source.lyrics, DocumentLyrics)
    assert_type(
        layout_lyrics(document, lyrics, id="verse", display=source.display), LyricLayout
    )
    return build_lyric_scene(document, tracks=(Track(id="main"),), inputs=(source,))


def bind_selected(line: LyricLine, target: LyricTarget) -> LyricLine:
    assert_type(line.bind(LyricRule(target, "timing", Jump())), LyricLine)
    return line.bind(LyricRule(line.query("ruby"), "timing", Jump()))


def glow_targets(line: LyricLine) -> LyricLine:
    from kara_templater import Glow, LyricHighlights

    def glow(line: LyricLine, target: LyricTarget) -> Glow:
        return Glow(border=1 if target.role == "ruby" else 2)

    assert_type(LyricHighlights(highlights=(), glow=glow)(line), LyricLine)
    return line
