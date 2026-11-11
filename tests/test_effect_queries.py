import pytest
from test_effect import events
from test_effect_selection import prepare

from examples.alternating_colors import document
from kara_templater import (
    BLUE,
    GREEN,
    RED,
    Body,
    Document,
    Effect,
    Lyrics,
    SourceRef,
    render_karaoke,
)


def test_source_attribute_queries_keep_repeated_text_and_source_order():
    effect, _ = prepare(Effect())
    selected = effect.syllables.query('syllable[text="AB"]')
    assert selected.source_refs == (
        SourceRef("selection", 0),
        SourceRef("selection", 3),
    )
    assert selected[-1].query_one("[unit=3]").text == "AB"
    assert effect.segments.query_one('[start_ms=1800][reading="b"]').intervals == (
        (1800, 2400),
    )
    assert effect.rubies.query_one("#ruby-0-1").text == "b"
    assert effect.characters.query_one("#char-3-1-2").text == "B"


def test_source_descendant_queries_use_unit_segment_character_relationships():
    effect, _ = prepare(Effect())
    effect.syllables[0].add_class("lead")
    effect.rubies[1].add_class("accent")
    assert effect.characters.query("syllable.lead character").text == "AB"
    assert effect.segments.query("syllable.lead segment").readings == ("a", "b")
    assert (
        effect.rubies.query_one("syllable.lead segment[segment=1] ruby.accent").text
        == "b"
    )
    assert effect.rubies.query(".absent").source_refs == ()
    assert (
        effect.syllables.query_one("syllable[text=static]")
        .segments.query("segment")
        .source_refs
        == ()
    )


def test_queries_are_read_only_and_empty_single_queries_report_cardinality():
    effect, _ = prepare(Effect())
    assert not effect.body._ranges and not effect._ruby_targets
    assert not effect.syllables.query('[missing="None"]')
    assert not effect.query('[missing="None"]')
    assert len(effect.characters.query("character")) == 10
    assert len(effect.rubies.query("ruby")) == 3
    assert not effect.body._ranges and not effect._ruby_targets
    with pytest.raises(ValueError, match="found 2"):
        effect.syllables.query_one('[text="AB"]')
    with pytest.raises(ValueError, match="found 0"):
        effect.rubies.query_one('[text="missing"]')
    with pytest.raises(ValueError, match="unsupported selector"):
        effect.syllables.query("syllable > character")


def test_filtered_queries_keep_selection_order_and_support_animation():
    effect, _ = prepare(Effect())
    reverse = effect.segments[::-1].query('segment[reading="a"]')
    assert reverse.source_refs == (
        SourceRef("selection", 3, 0),
        SourceRef("selection", 0, 0),
    )
    reverse.on_singing(offset_x=2)
    assert [r.segments for r in effect._motion_rules] == [((3, 0),), ((0, 0),)]
    assert not effect.segments[0:0].query("segment")


def test_query_classes_follow_range_aliases_and_have_no_cross_instance_leak():
    effect, _ = prepare(Effect())
    effect.characters.query('[unit=0][text="A"]').add_class("accent")
    assert effect.characters.query(".accent").text == "A"
    assert effect.syllables.query(".accent").text == ""
    fresh, _ = prepare(Effect())
    assert not fresh.characters.query(".accent")


def test_empty_unit_does_not_inherit_range_class_at_shared_boundary():
    effect, _ = prepare(Effect())
    effect.syllables[1].add_class("static")
    assert effect.syllables.query(".static").source_refs == (SourceRef("selection", 1),)


def test_query_selected_styles_match_range_styles_for_both_document_inputs():
    class Queried(Effect):
        def compose(self):
            yield Lyrics(Body())

        def configure(self):
            for text, color in (("A", RED), ("B", GREEN), ("C", BLUE)):
                self.characters.query(f'character[text="{text}"]').style.sung.fill = (
                    color
                )
            self.text.sweep()

    class Ranged(Queried):
        def configure(self):
            for i in range(6):
                self.body.text_range(i, i + 1).style.sung.fill = (RED, GREEN, BLUE)[
                    i % 3
                ]
            self.text.sweep()

    source = document(fontname="DejaVu Sans", text="ABCABC")
    expected = events(render_karaoke(source, effect=Ranged))
    assert events(render_karaoke(source, effect=Queried)) == expected
    assert (
        events(render_karaoke(Document.parse(source.dumps()), effect=Queried))
        == expected
    )
