from dataclasses import replace

import pytest
from effect_values import animated_property, properties_at, sampled_layers
from source_assertions import require_origin
from test_effect_halo import build

from kara_templater import (
    Body,
    DisplayWindow,
    Effect,
    Halo,
    Lyrics,
    OutputCapabilityError,
    Segment,
    Transition,
    display,
    layout_characters,
    singing,
    tracks_from_layout,
)


class Moving(Effect):
    def compose(self):
        yield Lyrics(Body(), Halo())


def value(plan, time, text="A", halo=False):
    layer = next(
        layer
        for layer in plan.layers
        if layer.text == text and (layer.component == "glow") == halo
    )
    return properties_at(plan, layer, time)


def test_independent_properties_compose_and_halo_follows_once():
    class Combined(Moving):
        def configure(self):
            self.syllables.on_singing(scale=Transition(1, 1.2))
            self.syllables.on_singing(
                offset_x=lambda p: 20 * p,
                offset_y=lambda p: -10 * p,
                opacity=lambda p: 1 - p / 2,
            )

    plan, _, _ = build(Combined())
    assert all(layer.animations for layer in plan.layers)
    body, halo = value(plan, 1700), value(plan, 1700, halo=True)
    assert body == halo
    assert (body.offset_x, body.offset_y, body.opacity) == (10, -5, 0.75)
    # Native scale and sampled translation coexist without a second scale.
    layers = sampled_layers(plan)
    assert all(len(layer.animations) == 1 for layer in layers)


def test_singing_progress_holds_through_gap_and_keep_uses_endpoint():
    class Active(Moving):
        def configure(self):
            self.syllables.on_singing(
                offset_x=lambda p: 100 * p, progress="singing", keep=True
            )

    plan, _, _ = build(Active(), segments=(Segment(1000, 1200), Segment(1800, 2400)))
    assert (
        value(plan, 1200).offset_x
        == value(plan, 1600).offset_x
        == value(plan, 1800).offset_x
        == 25
    )
    assert value(plan, 2100).offset_x == 62.5
    assert value(plan, 2800).offset_x == 100


def test_display_binding_works_on_static_text():
    class Display(Moving):
        def configure(self):
            self.syllables.animate(
                opacity=Transition(0, 1), during=(display.start, display.end)
            )

    plan, _, _ = build(Display(), segments=())
    assert value(plan, 500).opacity == 0
    assert value(plan, 1750).opacity == 0.5


def test_additive_offsets_and_multiplicative_opacity_are_explicit():
    class Composed(Moving):
        def configure(self):
            self.syllables.on_singing(offset_x=5, compose="add")
            self.syllables.on_singing(offset_x=7, compose="add")
            self.syllables.on_singing(opacity=0.8, compose="multiply")
            self.syllables.on_singing(opacity=0.5, compose="multiply")
            self.syllables.on_singing(scale=1.2, compose="multiply")
            self.syllables.on_singing(scale=1.1, compose="multiply")

    plan, _, _ = build(Composed())
    state = value(plan, 1500)
    assert state.offset_x == 12
    assert state.opacity == 0.4
    assert state.scale == pytest.approx(1.32)


def test_explicit_override_uses_declaration_order_only_in_overlap():
    class Override(Moving):
        def configure(self):
            self.syllables.on_singing(offset_y=-5, compose="override")
            self.syllables.animate(
                offset_y=-12,
                during=(singing.start + 200, singing.start + 400),
                compose="override",
            )

    plan, _, _ = build(Override())
    assert value(plan, 1100).offset_y == -5
    assert value(plan, 1300).offset_y == -12
    assert value(plan, 1500).offset_y == -5


def test_default_conflict_reports_property_and_time_before_callbacks():
    calls = []

    class Conflict(Moving):
        def configure(self):
            self.syllables.on_singing(offset_x=lambda p: calls.append(p) or 3)
            self.syllables.on_singing(offset_x=5)

    with pytest.raises(
        OutputCapabilityError, match="offset_x conflict at 1000..2400 ms"
    ):
        build(Conflict())
    assert calls == []


def echoes(layout):
    main = tracks_from_layout(layout)[0]
    return (
        main,
        replace(
            main,
            id="echo",
            passes=tuple(
                replace(p, start_ms=p.start_ms + 100, end_ms=p.end_ms + 100)
                for p in main.passes
            ),
        ),
    )


def test_arrival_named_track_and_threshold_ignore_decoration_padding():
    class Arrival(Moving):
        def configure(self):
            self.text.sweep(tracks=echoes, padding=80, lead=200, tail=200)
            self.characters.on_highlight(
                tracks="named",
                track_id="echo",
                threshold="center",
                duration_ms=200,
                offset_y=lambda p: -10,
            )

    plan, _, context = build(Arrival(), segments=(Segment(1000, 2000),))
    first = layout_characters(context.layout, style=context.style)[0]
    box = context.layout.units[0].box
    trigger = 1100 + (first.timing_region.center - box.left) / box.width * 1000
    assert value(plan, trigger - 1).offset_y == 0
    assert value(plan, trigger + 1).offset_y == -10
    assert value(plan, trigger + 200).offset_y == 0


def test_parallel_arrival_conflicts_are_checked_per_property():
    class Each(Moving):
        def configure(self):
            self.text.sweep(tracks=echoes)
            self.characters.on_highlight(tracks="each", duration_ms=300, offset_x=3)

    with pytest.raises(OutputCapabilityError, match="offset_x conflict"):
        build(Each(), segments=(Segment(1000, 2000),))

    class Add(Each):
        def configure(self):
            self.text.sweep(tracks=echoes)
            self.characters.on_highlight(
                tracks="each", duration_ms=300, offset_x=3, compose="add"
            )

    plan, _, _ = build(Add(), segments=(Segment(1000, 2000),))
    assert value(plan, 1050).offset_x == 3
    assert value(plan, 1150).offset_x == 6
    assert value(plan, 1350).offset_x == 3


def test_repeated_round_arrival_and_window_truncation_keep_original_progress():
    def repeated(layout):
        track = tracks_from_layout(layout)[0]
        return (
            replace(
                track,
                passes=(
                    *track.passes,
                    *(
                        replace(
                            p,
                            start_ms=p.start_ms + 1100,
                            end_ms=p.end_ms + 1100,
                            round_id=1,
                        )
                        for p in track.passes
                    ),
                ),
            ),
        )

    class Repeat(Moving):
        def configure(self):
            self.text.sweep(tracks=repeated)
            self.characters.on_highlight(duration_ms=400, offset_y=lambda p: -20 * p)

    plan, _, _ = build(
        Repeat(), segments=(Segment(1000, 2000),), window=DisplayWindow(1200, 3300)
    )
    assert value(plan, 1200).offset_y == -10
    assert value(plan, 2300).offset_y == -10


@pytest.mark.parametrize(
    "property,composition",
    [("opacity", "add"), ("offset_x", "multiply"), ("scale", "add")],
)
def test_invalid_composition_fails_during_configuration(property, composition):
    class Invalid(Moving):
        def configure(self):
            self.syllables.on_singing(
                **animated_property(property, 1), compose=composition
            )

    with pytest.raises(ValueError, match="does not support composition"):
        build(Invalid())


def test_halo_uses_same_keyframe_and_explicit_time_model():
    from kara_templater import Keyframe, Keyframes

    class Fading(Moving):
        def configure(self):
            self.query_one(Halo).animate(
                opacity=Keyframes(
                    Keyframe(0, 0.2),
                    Keyframe(0.25, 0.8),
                    Keyframe(0.75, 0.8),
                    Keyframe(1, 0.3),
                ),
                during=(singing.start - 200, singing.end + 200),
                keep=True,
            )

    plan, _, _ = build(Fading())
    assert value(plan, 500, halo=True).glow_opacity == 1
    assert value(plan, 1700, halo=True).glow_opacity == 0.8
    assert value(plan, 2800, halo=True).glow_opacity == 0.3


def test_halo_singing_progress_and_group_opacity_remain_independent():
    class Fading(Moving):
        def configure(self):
            self.query_one(Halo).on_singing(
                opacity=Transition(0.2, 0.8), progress="singing", keep=True
            )
            self.syllables.on_singing(opacity=0.5)

    plan, _, _ = build(Fading(), segments=(Segment(1000, 1200), Segment(1800, 2400)))
    state = value(plan, 1600, halo=True)
    assert state.opacity == 0.5
    assert state.glow_opacity == pytest.approx(0.35)
    sampled = sampled_layers(plan)
    halo = next(
        l
        for l in sampled
        if l.component == "glow"
        and (l.active_window or l.window).start_ms
        <= 1600
        < (l.active_window or l.window).end_ms
    )
    from kara_templater.ass_output import _animated_opacity

    assert _animated_opacity(halo, 1600, glow=True) == pytest.approx(0.175)


def test_halo_disjoint_intervals_reset_to_style_and_overlap_reports_source():
    class Sequential(Moving):
        def configure(self):
            h = self.query_one(Halo)
            h.animate(opacity=0.2, during=(singing.start, singing.start + 200))
            h.animate(opacity=0.6, during=(singing.start + 400, singing.end))

    plan, _, _ = build(Sequential())
    assert value(plan, 1100, halo=True).glow_opacity == 0.2
    assert value(plan, 1300, halo=True).glow_opacity == 1
    assert value(plan, 1600, halo=True).glow_opacity == 0.6

    class Overlap(Sequential):
        def configure(self):
            super().configure()
            self.query_one(Halo).on_singing(opacity=0.8)

    with pytest.raises(OutputCapabilityError, match="opacity conflict") as caught:
        build(Overlap())
    assert require_origin(caught.value).sources[0].unit_index == 0


def test_actual_progress_maps_absolute_keyframes_through_singing_gaps():
    from kara_templater import Keyframe, Keyframes

    class Mapped(Moving):
        def configure(self):
            self.syllables.on_singing(
                offset_y=Keyframes(
                    Keyframe(0, 0),
                    Keyframe(singing.start + 800, -10),
                    Keyframe(1, 0),
                ),
                progress="singing",
            )

    plan, _, _ = build(Mapped(), segments=(Segment(1000, 1200), Segment(1800, 2400)))
    assert (
        value(plan, 1200).offset_y
        == value(plan, 1600).offset_y
        == value(plan, 1800).offset_y
        == -10
    )
    assert value(plan, 2100).offset_y == pytest.approx(-5)


def test_parallel_sweep_example_matches_pre_migration_events():
    import hashlib
    import json
    from pathlib import Path

    from examples.parallel_tracks import build as parallel

    result = parallel()
    events = sorted(
        (e.start_time, e.end_time, e.layer, e.style, e.text)
        for e, _ in result.event_origins
    )
    expected = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "docs/parallel-effect-system-baseline.json"
        ).read_text()
    )
    assert result.event_count == expected["event_count"]
    assert hashlib.sha256(json.dumps(events).encode()).hexdigest() == expected["sha256"]
