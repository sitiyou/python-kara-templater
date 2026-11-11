from dataclasses import replace

import pytest
from effect_values import properties_at
from test_effect_halo import build
from test_effect_properties import value

from kara_templater import (
    Body,
    DisplayWindow,
    Effect,
    Halo,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    SampleContext,
    Segment,
    SourceRef,
    Style,
    TextUnit,
    singing,
)


def prepare(effect):
    item = KaraokeItem(
        "selection",
        KaraokeLine(
            (
                TextUnit("AB", (Segment(1000, 1600, "a"), Segment(1800, 2400, "b"))),
                TextUnit("static"),
                TextUnit("", (Segment(2500, 2500),)),
                TextUnit("AB", (Segment(3000, 3400, "a"),)),
            )
        ),
        "Default",
        DisplayWindow(0, 4000),
    )
    style = Style(fontname="DejaVu Sans", fontsize=40)
    return effect._prepare(item, style, replace(style, name="ruby"))[0], item


def test_source_selection_metadata_preserves_order_identity_and_empty_sources():
    effect, item = prepare(Effect())
    assert [s.text for s in effect.syllables] == ["AB", "static", "", "AB"]
    assert effect.syllables.text == "ABstaticAB"
    assert len(effect.segments) == 4
    assert effect.segments.intervals == (
        (1000, 1600),
        (1800, 2400),
        (2500, 2500),
        (3000, 3400),
    )
    assert effect.segments.readings == ("a", "b", "", "a")
    assert effect.segments.source_refs == (
        SourceRef(item.id, 0, 0),
        SourceRef(item.id, 0, 1),
        SourceRef(item.id, 2, 0),
        SourceRef(item.id, 3, 0),
    )
    assert (
        effect.segments[1].source_refs[0].resolve(item)
        is item.source.units[0].segments[1]
    )
    assert effect.syllables[1].segments.text == ""
    assert not effect.syllables[1].segments
    assert len(effect.syllables[2].characters) == 0
    assert effect.syllables[2].characters.source_refs == ()
    assert effect.syllables[2].characters.intervals == ()
    assert effect.segments[-1].source_refs != effect.segments[0].source_refs


def test_selection_slices_and_nested_views_keep_source_addresses():
    effect, _ = prepare(Effect())
    assert effect.syllables[::2].source_refs == (
        SourceRef("selection", 0),
        SourceRef("selection", 2),
    )
    assert effect.syllables[0].segments[-1].intervals == ((1800, 2400),)
    assert effect.segments[::-1].readings == ("a", "", "b", "a")
    assert effect.syllables[3].characters[1].text == "B"
    assert effect.syllables[3].characters[1].source_refs == (SourceRef("selection", 3),)
    assert effect.segments[0:0].text == ""
    with pytest.raises(IndexError):
        effect.segments[99]
    with pytest.raises(ValueError, match="temporal segments"):
        _ = effect.segments.characters
    with pytest.raises(ValueError, match="pre-layout characters"):
        _ = effect.characters.segments


class Segmented(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby(follow="syllable"), Halo())


def test_selected_segment_drives_unit_body_and_only_its_ruby():
    class Second(Segmented):
        def configure(self):
            self.segments[1].on_singing(offset_x=lambda p: 20 * p)

    plan, _, _ = build(Second())
    assert value(plan, 1300).offset_x == 0
    assert value(plan, 2100).offset_x == 10
    assert value(plan, 2100, text="B").offset_x == 10
    assert value(plan, 2100, halo=True).offset_x == 10
    assert value(plan, 2500).offset_x == 0
    for layer in plan.layers:
        if layer.style.name == "ruby":
            state = plan.dynamic.function(
                SampleContext(2100, 0, layer.window, layer.animation_id, 0)
            )
            assert state.offset_x == (10 if layer.text == "b" else 0)


def test_segment_collection_runs_separate_clocks_and_pauses_between_readings():
    class Each(Segmented):
        def configure(self):
            self.syllables[0].segments.on_singing(offset_y=lambda p: -20 * p)

    plan, _, _ = build(Each())
    assert value(plan, 1300).offset_y == -10
    assert value(plan, 1700).offset_y == 0
    assert value(plan, 2100).offset_y == -10


def test_segment_relative_times_and_native_pivot_use_owning_unit():
    class Scale(Segmented):
        def configure(self):
            self.segments[1].animate(
                scale=(1, 1.2), during=(singing.start - 100, singing.end)
            )

    plan, _, context = build(Scale())
    body = [l for l in plan.layers if l.style.name == "Default"]
    assert body
    for layer in body:
        (animation,) = layer.animations
        assert (animation.start_ms, animation.end_ms) == (1700, 2400)
        assert animation.pivot == (
            context.layout.units[0].box.center,
            context.layout.units[0].box.middle,
        )


def test_segment_and_unit_rules_share_conflict_detection():
    class Conflict(Segmented):
        def configure(self):
            self.syllables.on_singing(offset_x=1)
            self.segments[1].on_singing(offset_x=2)

    with pytest.raises(OutputCapabilityError, match="offset_x conflict at 1800..2400"):
        build(Conflict())


def test_empty_selection_validates_but_registers_no_rules():
    effect, _ = prepare(Effect())
    effect.syllables[1].segments.on_singing(pulse=1.2)
    assert not effect._motion_rules
    with pytest.raises(ValueError, match="unsupported animated property"):
        effect.syllables[1].segments.on_singing(unknown=1)


def test_segment_selection_does_not_leak_rules_across_bound_instances():
    class Second(Effect):
        def configure(self):
            self.segments[1].on_singing(offset_x=2)

    shared = Second()
    first, _ = prepare(shared)
    second, _ = prepare(shared)
    first.segments[0].on_singing(offset_y=3)
    assert len(first._motion_rules) == 2
    assert len(second._motion_rules) == 1
    assert not hasattr(shared, "segments")


def test_segment_timing_error_identifies_the_selected_reading():
    class Reversed(Segmented):
        def configure(self):
            self.segments[1].animate(offset_x=2, during=(singing.end, singing.start))

    with pytest.raises(ValueError) as error:
        build(Reversed())
    assert error.value.origin.sources == (SourceRef("line", 0, 1),)


def test_ruby_selection_filters_absent_readings_and_retains_source_identity():
    effect, item = prepare(Effect())
    assert effect.rubies.text == "aba"
    assert effect.rubies.readings == ("a", "b", "a")
    assert effect.rubies[-1].source_refs == (SourceRef(item.id, 3, 0),)
    assert effect.rubies[-1].segments.text == "AB"
    assert effect.syllables[0].rubies[1].intervals == ((1800, 2400),)
    assert effect.segments[2].rubies.text == ""
    assert len(effect.segments[2].rubies) == 0


def test_direct_ruby_motion_works_without_body_following_and_only_own_halo_moves():
    class Independent(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(), Halo())

        def configure(self):
            self.rubies[1].on_singing(offset_x=lambda p: 20 * p)

    plan, _, _ = build(Independent())
    for layer in plan.layers:
        state = properties_at(plan, layer, 2100)
        assert state.offset_x == (10 if layer.text == "b" else 0)


def test_direct_ruby_scale_uses_ruby_center_and_segment_clock():
    class Independent(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(offset_y=7), Halo())

        def configure(self):
            self.rubies[1].on_singing(pulse=1.2)

    plan, _, _ = build(Independent())
    animated = [l for l in plan.layers if l.animations]
    assert animated and all(l.text == "b" for l in animated)
    for layer in animated:
        (animation,) = layer.animations
        assert (animation.start_ms, animation.end_ms) == (1800, 2400)
        assert animation.pivot == (layer.box.center, layer.box.middle)


def test_ruby_own_and_followed_motion_use_shared_conflict_rules():
    class Conflicting(Segmented):
        def configure(self):
            self.syllables.on_singing(offset_x=2)
            self.rubies[1].on_singing(offset_x=3)

    with pytest.raises(OutputCapabilityError, match="ruby:0:1.*offset_x conflict"):
        build(Conflicting())

    class Added(Segmented):
        def configure(self):
            self.syllables.on_singing(offset_x=2, compose="add")
            self.rubies[1].on_singing(offset_x=3, compose="add")

    plan, _, _ = build(Added())
    for layer in plan.layers:
        state = properties_at(plan, layer, 2100)
        assert state.offset_x == (5 if layer.text == "b" else 2)


def test_disabling_ruby_follow_does_not_disable_its_own_animation():
    from kara_templater import Follow

    class Independent(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(follow=Follow(position=False)), Halo())

        def configure(self):
            self.syllables.on_singing(offset_x=2)
            self.rubies[1].on_singing(offset_x=3)

    plan, _, _ = build(Independent())
    for layer in plan.layers:
        state = properties_at(plan, layer, 2100)
        assert state.offset_x == {"a": 0, "b": 3}.get(layer.text, 2)


def test_hidden_ruby_does_not_evaluate_its_own_animation():
    from kara_templater import prepare_sampling

    calls = []

    class Hidden(Segmented):
        def configure(self):
            self.ruby.hide()
            self.rubies.on_singing(offset_y=lambda p: calls.append(p) or 2)

    plan, _, _ = build(Hidden())
    assert all(layer.style.name != "ruby" for layer in plan.layers)
    if plan.dynamic:
        prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert calls == []
