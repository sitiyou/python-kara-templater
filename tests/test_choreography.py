"""Timeline semantics, source clocks, and backend integration."""

from dataclasses import replace

import pytest

from examples.alternating_colors import document
from examples.syllable_pulse import SyllablePulse
from kara_templater import (
    Animation,
    AnimationContext,
    Body,
    Composition,
    Display,
    DisplayWindow,
    KaraokeItem,
    KaraokeLine,
    LineMatch,
    MoveTo,
    On,
    OpacityTo,
    ScaleTo,
    Segment,
    TextUnit,
    Track,
    Transform,
    TransformTo,
    render_karaoke,
)
from kara_templater.behaviors import MotionRule, bind_property


def source():
    return KaraokeItem(
        "line",
        KaraokeLine(
            (
                TextUnit("A", (Segment(1000, 1400),)),
                TextUnit("B", (Segment(1600, 2400),)),
            )
        ),
        "Default",
        DisplayWindow(800, 2400),
    )


def bound(animation, item=None):
    item = source() if item is None else item
    rules = animation.bind(AnimationContext(item))
    result = {}
    for rule in rules:
        assert isinstance(rule, MotionRule)
        segments = tuple(s for i in rule.units for s in item.source.units[i].segments)
        value = bind_property(rule, segments, item.window, (0, 0))
        assert value is not None
        result[rule.units, rule.property] = value
    return result


def test_next_syllable_pulse_preserves_target_and_source_clock():
    values = bound(SyllablePulse(peak=1.2))
    first = values[(0,), "scale"]
    second = values[(1,), "scale"]
    # The next syllable supplies timing; it does not become the first target.
    assert first.interval == (1000, 2400)
    assert second.interval == (1600, 2600)
    expected = {
        1000: 1,
        1200: 1.1,
        1400: 1.2,
        1500: 1.2,
        1600: 1.2,
        2000: 1.1,
        2400: 1,
        3000: 1,
    }
    # Seeking backwards and repeat sampling must not accumulate state.
    for t in (2400, 1200, 3000, 1000, 2000, 1400, 1600, 1500, 1200):
        assert first.at(t) == pytest.approx(expected[t])
    assert second.at(2500) == pytest.approx(1.1)
    track = Track(source=LineMatch(), animations=(SyllablePulse(),))
    resolved = track.bind((source(),))["line"]
    assert resolved.window.end_ms == 2600
    assert resolved.rules[0].during == (1000, 2400)


def test_later_start_takes_over_from_interpolated_value():
    def compose(timeline, context):
        timeline.play(ScaleTo(2), at=0, duration=1)
        timeline.play(ScaleTo(1), at=0.5, duration=1)

    value = bound(Composition(compose))[(0,), "scale"]
    assert value.at(1250) == pytest.approx(1.25)
    assert value.at(1500) == pytest.approx(1.5)
    assert value.at(2000) == pytest.approx(1.25)
    assert value.at(2500) == 1
    assert value.points is not None  # Built-in linear timelines stay native.


def test_takeover_only_replaces_overlapping_properties():
    def compose(timeline, context):
        timeline.play(TransformTo(Transform(scale=2, offset_y=10)), duration=1)
        timeline.play(ScaleTo(1), t=0.5, duration=0.5)

    values = bound(Composition(compose))
    assert values[(0,), "scale"].at(1750) == pytest.approx(1.25)
    assert values[(0,), "offset_y"].at(1750) == pytest.approx(7.5)


def test_parallel_cursor_and_explicit_time_are_independent():
    def compose(timeline, context):
        timeline.play(ScaleTo(2, duration=0.2), MoveTo(y=10, duration=0.5))
        timeline.play(ScaleTo(1), duration=0.1)  # starts at .5
        timeline.play(OpacityTo(0), t=0.3, duration=0.1)

    values = bound(Composition(compose))
    scale = values[(0,), "scale"]
    assert scale.interval == (1000, 1600)
    assert scale.at(1400) == 2
    assert scale.at(1550) == pytest.approx(1.5)
    assert values[(0,), "opacity"].at(1350) == pytest.approx(0.5)


def test_timeline_sorts_chronologically_before_capturing_initial_state():
    def compose(timeline, context):
        timeline.play(ScaleTo(1), at=0.5, duration=0.5)
        timeline.play(ScaleTo(2), at=0, duration=0.5)

    value = bound(Composition(compose))[(0,), "scale"]
    assert value.at(1500) == 2
    assert value.at(1750) == pytest.approx(1.5)


def test_nested_composition_time_stretching_and_initial_snapshot():
    calls = []

    def child(timeline, context):
        calls.append(context.target.units)
        timeline.play(ScaleTo(2), duration=0.2)
        timeline.play(ScaleTo(1), duration=0.2)

    def parent(timeline, context):
        timeline.play(ScaleTo(1.5), duration=0.2)
        timeline.play(Composition(child), duration=0.8)

    value = bound(Composition(parent))[(0,), "scale"]
    assert value.interval == (1000, 2000)
    assert value.at(1400) == pytest.approx(1.75)
    assert value.at(1600) == pytest.approx(2)
    assert value.at(1800) == pytest.approx(1.5)
    assert calls == [(0,), (1,)]  # one recording per binding, never per sample


def test_function_animation_receives_local_time_and_snapshot():
    seen = []

    def sample(t, context):
        seen.append((t, context.duration, context.initial.scale))
        assert context.initial.scale is not None
        return Transform(scale=context.initial.scale + t / context.duration)

    def compose(timeline, context):
        timeline.play(ScaleTo(1.5), duration=0.2)
        timeline.play(Animation(sample, duration=0.5, hold=True))

    value = bound(Composition(compose))[(0,), "scale"]
    assert value.at(1450) == 2
    assert seen[-1] == (0.25, 0.5, 1.5)
    assert value.at(1700) == 2.5


def test_on_can_bind_composition_to_display_event():
    animation = On(Display.Start, ScaleTo(2, duration=0.2))
    values = bound(animation)
    assert values[(0, 1), "scale"].interval == (800, 1000)
    assert values[(0, 1), "scale"].at(900) == 1.5


@pytest.mark.parametrize("at", [float("nan"), float("inf"), -0.1])
def test_invalid_start_rejected(at):
    with pytest.raises(ValueError):
        bound(Composition(lambda tl, ctx: tl.play(ScaleTo(2), at=at)))


@pytest.mark.parametrize("duration", [0, -1, 0.0001, float("nan")])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError):
        bound(Composition(lambda tl, ctx: tl.play(ScaleTo(2), duration=duration)))


def test_simultaneous_property_writes_are_reported():
    with pytest.raises(ValueError, match="simultaneous.*scale"):
        bound(Composition(lambda tl, ctx: tl.play(ScaleTo(2), ScaleTo(3))))


def test_recursive_composition_rejected():
    composition = Composition(lambda tl, ctx: tl.play(composition))
    with pytest.raises(ValueError, match="recursive"):
        bound(composition)


def test_callback_cannot_change_its_write_set():
    value = bound(
        Animation(lambda t, ctx: Transform(scale=1) if t == 0 else Transform(opacity=1))
    )[(0,), "scale"]
    with pytest.raises(ValueError, match="same properties"):
        value.at(1200)


def test_untimed_next_syllable_is_not_silently_skipped():
    item = replace(
        source(),
        source=KaraokeLine(
            (
                TextUnit("A", (Segment(1000, 1400),)),
                TextUnit(" ", ()),
                TextUnit("B", (Segment(1800, 2200),)),
            )
        ),
    )
    value = bound(SyllablePulse(), item)[(0,), "scale"]
    assert value.interval == (1000, 1600)  # explicit fallback, not B's interval


@pytest.mark.parametrize("parsed", [False, True])
def test_pulse_renders_constructed_and_parsed_ass(parsed):
    from kara_templater import Document

    doc = document(fontname="DejaVu Sans", text="AB")
    for line in doc.lines:
        line.text = r"{\k40}A{\k80}B"
    if parsed:
        doc = Document.parse(doc.dumps())
    track = Track(source=LineMatch(), body=Body(), animations=(SyllablePulse(),))
    result = render_karaoke(doc, tracks=(track,))
    assert result.event_count > 0


def test_zero_duration_syllable_uses_explicit_release_policy():
    item = replace(
        source(), source=KaraokeLine((TextUnit("A", (Segment(1000, 1000),)),))
    )
    value = bound(SyllablePulse(), item)[(0,), "scale"]
    assert value.interval == (1000, 1200)
    assert value.at(1100) == 1


def test_schedule_boundaries_split_native_sampling_buckets():
    from kara_templater import Line

    def compose(timeline, context):
        timeline.play(
            Animation(lambda t, ctx: Transform(offset_y=10 + t)),
            at=0.11,
            duration=0.13,
        )

    doc = document(fontname="DejaVu Sans", text="AB")
    track = Track(source=LineMatch(), animations=(Composition(compose),))
    result = render_karaoke(doc, items=(source(),), tracks=(track,))
    lines = [
        line
        for line in result.document.lines
        if isinstance(line, Line) and line.effect.startswith("karaoke:v1:")
    ]
    assert any(line.start_time == 1110 for line in lines)
    assert any(line.start_time == 1240 for line in lines)


def test_raster_backend_respects_schedule_boundaries():
    from kara_templater import OutputSettings, RasterSettings

    doc = document(fontname="DejaVu Sans", text="A")
    doc.styles["Default"].fontsize = 12
    item = replace(
        source(),
        source=KaraokeLine((TextUnit("A", (Segment(0, 50),)),)),
        window=DisplayWindow(0, 100),
    )
    track = Track(
        source=LineMatch(),
        animations=(
            Composition(
                lambda tl, ctx: tl.play(
                    Animation(lambda t, ctx: Transform(offset_y=3 + t)),
                    at=0.03,
                    duration=0.02,
                ),
            ),
        ),
    )
    result = render_karaoke(
        doc,
        items=(item,),
        tracks=(track,),
        settings=OutputSettings(resolution=(640, 480), raster=RasterSettings()),
    )
    assert result.event_count > 0
    assert any(line.start_time == 30 for line in result.document.lines)


def test_idle_composition_does_not_claim_properties_before_first_play():
    animation = Composition(
        lambda tl, ctx: tl.play(ScaleTo(1.1), at=0.5, duration=0.2),
        hold=False,
    )
    value = bound(animation)[(0,), "scale"]
    assert value.interval == (1500, 1700)
    track = Track(
        source=LineMatch(),
        animations=(
            Animation(lambda t, ctx: Transform(scale=1 + t), duration=0.2),
            animation,
        ),
    )
    result = render_karaoke(
        document(fontname="DejaVu Sans", text="AB"), items=(source(),), tracks=(track,)
    )
    assert result.event_count > 0


def test_takeover_can_capture_a_nonlinear_sampled_animation():
    def compose(timeline, context):
        timeline.play(
            Animation(lambda t, ctx: Transform(scale=1 + t * t), duration=1, hold=True)
        )
        timeline.play(ScaleTo(1), at=0.5, duration=0.5)

    value = bound(Composition(compose))[(0,), "scale"]
    assert value.at(1500) == pytest.approx(1.25)
    assert value.at(1750) == pytest.approx(1.125)
    assert value.at(2000) == 1


def test_top_level_competing_writers_still_raise():
    from kara_templater import OutputCapabilityError

    track = Track(source=LineMatch(), animations=(ScaleTo(1.1), ScaleTo(1.2)))
    with pytest.raises(OutputCapabilityError, match="scale conflict"):
        render_karaoke(
            document(fontname="DejaVu Sans", text="AB"),
            items=(source(),),
            tracks=(track,),
        )
