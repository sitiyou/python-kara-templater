from dataclasses import replace

import pytest
from source_assertions import require_origin

from kara_templater import (
    Body,
    DisplayWindow,
    Effect,
    EffectContext,
    Halo,
    KaraokeItem,
    KaraokeLine,
    LayoutCapabilityError,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    Segment,
    SourceRef,
    Style,
    TextUnit,
    compile_layers,
    layout_line,
    prepare_sampling,
)


def bind(effect, units):
    item = KaraokeItem("edge", KaraokeLine(units), "Default", DisplayWindow(0, 4000))
    style = Style(fontname="DejaVu Sans", fontsize=40)
    bound, style, ruby_style = effect._prepare(item, style, replace(style, fontsize=20))
    context = EffectContext(
        layout_line(
            item.source, style=style, ruby_style=ruby_style, resolution=(640, 480)
        ),
        style,
        ruby_style,
        (640, 480),
    )
    return bound, bound.build(item, context), item


class Decorated(Effect):
    def compose(self):
        yield Lyrics(
            Body(), Ruby(follow="syllable"), Halo(id="base"), Halo(id="accent")
        )


def test_empty_body_with_reading_reports_unavailable_mapping():
    with pytest.raises(OutputCapabilityError, match="zero-width body mapping") as error:
        bind(Decorated(), (TextUnit("", (Segment(1000, 2000, "a"),)),))
    assert require_origin(error.value).sources == (SourceRef("edge", 0, 0),)


def test_source_character_selection_cannot_split_a_shaped_ligature():
    class Split(Decorated):
        def configure(self):
            self.characters[1].on_singing(scale=(1, 1.2))

    with pytest.raises(LayoutCapabilityError, match="cluster") as error:
        bind(Split(), (TextUnit("office", (Segment(1000, 2000),)),))
    assert require_origin(error.value).sources == (SourceRef("edge", 0),)


@pytest.mark.parametrize("reverse", [False, True])
def test_selection_covering_whole_ligature_binds_to_actual_cluster(reverse):
    class Selected(Effect):
        def configure(self):
            selection = self.characters[1:4]
            if reverse:
                selection = selection[::-1]
            selection.on_singing(scale=(1, 1.2))

    _, plan, _ = bind(Selected(), (TextUnit("office", (Segment(1000, 2000),)),))
    assert {layer.text for layer in plan.layers if layer.animations} == {"ffi"}
    assert compile_layers(plan.layers).events


@pytest.mark.parametrize(
    "units",
    [(), (TextUnit(""),), (TextUnit("", (Segment(1000, 1500),)),)],
)
def test_empty_sources_keep_source_members_but_emit_no_decoration_or_callbacks(units):
    calls = []

    class Empty(Decorated):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(offset_x=lambda p: calls.append(p) or p)

    bound, plan, item = bind(Empty(), units)
    assert bound.source is item
    assert len(bound.syllables) == len(units)
    assert len(bound.segments) == sum(len(u.segments) for u in units)
    assert not bound.characters and not bound.rubies
    assert not plan.layers
    if plan.dynamic:
        assert not prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert not calls


def test_static_unit_has_characters_but_no_singing_clock():
    calls = []

    class Static(Decorated):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(offset_y=lambda p: calls.append(p) or p)

    bound, plan, item = bind(Static(), (TextUnit("AB"),))
    assert bound.characters.text == "AB"
    assert not bound.segments and not bound.rubies
    assert plan.layers and plan.dynamic is None
    assert not calls
    result = compile_layers(plan.layers)
    assert result.events
    for origin in result.origins:
        assert origin is not None
        assert origin.sources == (SourceRef(item.id, 0),)
        assert origin.sources[0].resolve(item) is item.source.units[0]


def test_ruby_layout_group_preserves_individual_reading_selection_and_origins():
    class Grouped(Decorated):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(offset_y=lambda p: -5 * p)

    units = (
        TextUnit("A", (Segment(1000, 1500, "ab"), Segment(1600, 2000, "cd"))),
        TextUnit("B", (Segment(2100, 3000, "ef"),), ruby_continuation=True),
    )
    bound, plan, item = bind(Grouped(), units)
    assert bound.rubies.readings == ("ab", "cd", "ef")
    assert bound.rubies.source_refs == (
        SourceRef(item.id, 0, 0),
        SourceRef(item.id, 0, 1),
        SourceRef(item.id, 1, 0),
    )
    assert bound.syllables[0].segments.text == "A"
    assert bound.rubies[-1].segments.intervals == ((2100, 3000),)
    assert item.source.units is units
    original = {
        layer.animation_id: require_origin(layer).sources for layer in plan.layers
    }
    assert plan.dynamic is not None
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert len(sampled) > len(plan.layers)
    for layer in sampled:
        assert require_origin(layer).sources == original[layer.animation_id]
        for ref in require_origin(layer).sources:
            assert (
                ref.resolve(item) is units[ref.unit_index].segments[ref.segment_index]
            )
    result = compile_layers(sampled)
    assert result.events and len(result.events) == len(result.origins)
    refs = set()
    for origin in result.origins:
        assert origin is not None
        refs.update(origin.sources)
    assert refs == set(bound.segments.source_refs)
    for text, refs in (
        ("ab", (SourceRef(item.id, 0, 0),)),
        ("ef", (SourceRef(item.id, 1, 0),)),
    ):
        layers = [layer for layer in sampled if layer.text == text]
        assert layers and all(require_origin(layer).sources == refs for layer in layers)


@pytest.mark.parametrize(
    "selection, expected",
    [
        (lambda fx: fx.characters[:1], {"A"}),
        (lambda fx: fx.rubies[1:], {"b"}),
        (lambda fx: fx.syllables[:1], {"A", "a"}),
        (lambda fx: fx.characters[:0], set()),
    ],
)
def test_halo_source_selection_limits_visuals_and_retains_sources(selection, expected):
    class Selected(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(), Halo(targets=selection(self), blur=3))

    _, plan, item = bind(
        Selected(),
        (
            TextUnit("A", (Segment(1000, 1500, "a"),)),
            TextUnit("B", (Segment(1500, 2000, "b"),)),
        ),
    )
    halos = [layer for layer in plan.layers if layer.component == "glow"]
    assert {layer.text for layer in halos} == expected
    for layer in halos:
        for ref in require_origin(layer).sources:
            assert ref.resolve(item) is not None
    assert {layer.text for layer in plan.layers if layer.component != "glow"} == {
        "A",
        "B",
        "a",
        "b",
    }


@pytest.mark.parametrize("whole", [False, True])
def test_halo_selection_validates_actual_ligature_boundary(whole):
    class Selected(Effect):
        def compose(self):
            selected = self.characters[1:4] if whole else self.characters[1]
            yield Lyrics(Body(), Halo(targets=selected))

    units = (TextUnit("office", (Segment(1000, 2000),)),)
    if whole:
        _, plan, _ = bind(Selected(), units)
        assert {layer.text for layer in plan.layers if layer.component == "glow"} == {
            "ffi"
        }
    else:
        with pytest.raises(LayoutCapabilityError, match="cluster") as error:
            bind(Selected(), units)
        assert require_origin(error.value).sources == (SourceRef("edge", 0, 0),)


def test_halo_rejects_temporal_segment_selection():
    class Selected(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(targets=self.segments))

    with pytest.raises(ValueError, match="temporal segments"):
        bind(Selected(), (TextUnit("A", (Segment(1000, 2000),)),))
