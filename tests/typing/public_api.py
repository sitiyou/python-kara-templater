"""Checked by ty: these contracts must not decay to Any or Unknown."""

from collections.abc import Iterable, Iterator
from typing import assert_type

from kara_templater import (
    BLUE,
    RED,
    Body,
    Color,
    Component,
    Contextual,
    Document,
    Effect,
    EffectContext,
    EffectPlan,
    Halo,
    KaraokeItem,
    KaraokeLine,
    Keyframe,
    Keyframes,
    Line,
    Lyrics,
    PropertyContext,
    PropertyValue,
    RenderResult,
    Ruby,
    Segment,
    SelectionStyle,
    SourceRef,
    Style,
    StyleKeyword,
    StyleOverrides,
    StyleValues,
    TargetSelection,
    TextUnit,
    TimeRef,
    Transition,
    compile_layers,
    display,
    import_karaoke,
    layout_line,
    parse_karaoke,
    render_karaoke,
    singing,
    smooth,
    there_and_back,
    walk_karaoke,
)
from kara_templater.properties import BackRate


class CustomBody(Body):
    def custom(self) -> str:
        return "custom"


class TypedEffect(Effect):
    def compose(self) -> Iterable[Lyrics]:
        yield Lyrics(CustomBody(id="body", fill=RED), Ruby(), Halo(id="light"))

    def configure(self) -> None:
        assert_type(self.source, KaraokeItem)
        assert_type(self.body, Body)
        assert_type(self.ruby, Ruby)
        assert_type(self.query(Body), tuple[Body, ...])
        assert_type(self.query(Ruby), tuple[Ruby, ...])
        assert_type(self.query(Halo), tuple[Halo, ...])
        assert_type(self.query(Lyrics), tuple[Lyrics, ...])
        assert_type(self.query(CustomBody), tuple[CustomBody, ...])
        assert_type(self.query_one(CustomBody).custom(), str)
        assert_type(self.query(".accent"), tuple[Component, ...])
        assert_type(self.query_one("#body"), Component)
        assert_type(self.query_one("#body", Body), Body)
        assert_type(self.query_one("#body", CustomBody), CustomBody)
        assert_type(self.query_one("ruby", Ruby), Ruby)
        assert_type(self.query_one("#light", Halo), Halo)
        assert_type(self.body.add_class("accent"), Body)
        assert_type(self.body.walk(), Iterator[Component])
        assert_type(self.body.text_range(0, 1).style, StyleOverrides)
        assert_type(self.ruby.hide(), None)

        assert_type(self.syllables.source, KaraokeLine)
        assert_type(self.syllables.item_id, str)
        assert_type(self.syllables.units, tuple[int, ...])
        assert_type(self.syllables[0], TargetSelection)
        assert_type(self.characters[1:3], TargetSelection)
        assert_type(iter(self.rubies), Iterator[TargetSelection])
        assert_type(self.syllables.query(".accent"), TargetSelection)
        assert_type(self.rubies.query_one('[text="a"]').text, str)
        assert_type(self.segments.intervals, tuple[tuple[int, int], ...])
        assert_type(self.rubies.readings, tuple[str, ...])
        assert_type(self.characters.source_refs, tuple[SourceRef, ...])
        assert_type(self.characters.add_class("accent"), TargetSelection)
        assert_type(self.characters.style, SelectionStyle)
        assert_type(self.characters.style.sung, SelectionStyle)
        assert_type(self.body.style.sung, StyleValues)
        assert_type(self.body.style.fill, Color | StyleKeyword)
        assert_type(self.body.style.opacity, float | StyleKeyword)
        self.body.style.fill = "#ffffff"
        self.characters.style.sung.fill = BLUE
        assert_type(self.text.sweep(fill=RED), None)
        assert_type(self.text.fade(in_ms=100), None)
        assert_type(self.characters.on_highlight(pulse=1.1), TargetSelection)
        assert_type(
            self.syllables.on_singing(scale=lambda p: assert_type(p, float)),
            TargetSelection,
        )
        assert_type(
            self.rubies.animate(during=(singing.start, display.end), opacity=0.5),
            TargetSelection,
        )
        assert_type(
            self.query_one(Halo).on_singing(opacity=lambda p: assert_type(p, float)),
            Halo,
        )


def values_and_render(
    document: Document, item: KaraokeItem, context: EffectContext
) -> None:
    assert_type(Color.hex("#112233"), Color)
    assert_type(RED, Color)
    assert_type(document.styles, dict[str, Style])
    assert_type(document.lines, list[Line])
    assert_type(document.dumps(), str)
    assert_type(Document.parse(document.dumps()), Document)
    assert_type(document.meta.res_x, int)
    assert_type(parse_karaoke(Line()), KaraokeLine)
    assert_type(import_karaoke(document).items, tuple[KaraokeItem, ...])
    assert_type(walk_karaoke((item,)), Iterator[tuple[SourceRef, Segment]])
    assert_type(
        walk_karaoke((item,), level="unit"), Iterator[tuple[SourceRef, TextUnit]]
    )
    assert_type(
        walk_karaoke((item,), level="line"), Iterator[tuple[SourceRef, KaraokeLine]]
    )
    assert_type(singing.start + 100, TimeRef)
    assert_type(smooth(0.5), float)
    assert_type(there_and_back(0.5), float)
    assert_type(there_and_back(peak_at=0.2), BackRate)
    assert_type(Transition(1, 1.2, rate=lambda p: assert_type(p, float))(0.5), float)
    assert_type(
        Contextual(lambda ctx: assert_type(ctx, PropertyContext).progress), Contextual
    )
    expression: PropertyValue = Keyframes(Keyframe(0, 1), Keyframe(1, 1.2))
    assert_type(expression, Keyframes)
    assert_type(TypedEffect().build(item, context), EffectPlan)
    assert_type(render_karaoke(document, effect=TypedEffect), RenderResult)
    assert_type(
        render_karaoke(document, (item,), effect={"Default": TypedEffect()}),
        RenderResult,
    )
    assert_type(
        render_karaoke(document, effect=lambda item, context: EffectPlan()),
        RenderResult,
    )
    assert_type(compile_layers(EffectPlan().layers).events, tuple[Line, ...])
    assert_type(layout_line(item.source, style=Style()).box.width, float)
