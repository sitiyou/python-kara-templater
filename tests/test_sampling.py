from dataclasses import replace

import pytest

from kara_templater import (
    Box,
    ClipSpan,
    DisplayWindow,
    DynamicEffect,
    DynamicProperties,
    Fade,
    Glow,
    OutputCapabilityError,
    Paint,
    Region,
    SampleContext,
    SamplingSettings,
    Style,
    TextLayer,
    compile_layers,
    prepare_sampling,
)

BASE = TextLayer("a", "A", Style(), Box(100, 100, 40, 40), DisplayWindow(10, 130))


@pytest.mark.parametrize("component,passes", [("both", 2), ("fill", 1), ("glow", 1)])
def test_component_budget_and_independent_glow_opacity(component, passes):
    layer = replace(
        BASE, component=component, paint=Paint(opacity=0.6, glow=Glow(opacity=0.9))
    )
    effect = DynamicEffect(lambda ctx: DynamicProperties(glow_opacity=0.25))
    plan = prepare_sampling((layer,), effect, max_events=4 * passes)
    assert plan.estimate.estimated_events == 4 * passes
    sampled = plan.evaluate()
    assert len(sampled) == 1
    assert sampled[0].paint.opacity == 0.6
    assert sampled[0].paint.glow is not None
    assert sampled[0].paint.glow.opacity == 0.25
    events = compile_layers(sampled).events
    assert len(events) == passes
    assert [event.layer for event in events] == {
        "both": [0, 1],
        "fill": [1],
        "glow": [0],
    }[component]
    for event in events:
        assert (r"\alpha&HD9&" if event.layer == 0 else r"\alpha&H66&") in event.text
    with pytest.raises(OutputCapabilityError, match="preflight"):
        prepare_sampling((layer,), effect, max_events=4 * passes - 1)


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_glow_opacity(value):
    with pytest.raises(ValueError):
        DynamicProperties(glow_opacity=value)


def test_invalid_paint_component():
    with pytest.raises(ValueError, match="requires a glow"):
        replace(BASE, component="glow")
    with pytest.raises(ValueError, match="component"):
        replace(BASE, component="unknown")


def test_sampling_errors_retain_origin_time_and_callback_cause():
    from kara_templater import EventOrigin, SourceRef

    origin = EventOrigin((SourceRef("line", 1, 2),), "custom", ("echo",))
    layer = replace(BASE, origin=origin)
    failure = RuntimeError("broken property")
    calls = []

    def fail(context):
        calls.append(context.time_ms)
        raise failure

    effect = DynamicEffect(fail)
    with pytest.raises(OutputCapabilityError, match="preflight") as caught:
        prepare_sampling((layer,), effect, max_events=0)
    assert not calls
    assert caught.value.origin is origin and caught.value.time_ms == 10
    with pytest.raises(OutputCapabilityError, match="broken property") as caught:
        prepare_sampling((layer,), effect).evaluate()
    assert calls == [10]
    assert caught.value.origin is origin and caught.value.time_ms == 10
    assert caught.value.__cause__ is failure


def test_preflight_cache_and_absolute_grid():
    seen = []

    def sample(ctx):
        seen.append(ctx)
        return DynamicProperties(offset_x=7, offset_y=3)

    layers = (
        replace(BASE, animation_id="shared"),
        replace(
            BASE,
            source_id="b",
            animation_id="shared",
            clips=(ClipSpan(30, 130, Region(100, 110), Region(100, 140)),),
        ),
    )
    plan = prepare_sampling(layers, DynamicEffect(sample))
    assert not seen
    assert plan.estimate.target_samples == 4
    sampled = plan.evaluate()
    assert [c.time_ms for c in seen] == [10, 40, 80, 120]
    assert all(layer.window == BASE.window for layer in sampled)
    assert sampled[0].box.left == 107
    assert len(sampled) == 2
    assert sampled[1].clips is not None
    assert sampled[1].clips[0].start == Region(107, 117)
    assert sampled[0].active_window == DisplayWindow(10, 130)


def test_budgets_reject_without_callbacks():
    def forbidden(ctx):
        pytest.fail("callback ran before preflight")

    for effect, budget in (
        (DynamicEffect(forbidden), 2),
        (DynamicEffect(forbidden, SamplingSettings(max_samples=2)), 100),
    ):
        with pytest.raises(OutputCapabilityError, match="preflight"):
            prepare_sampling((BASE,), effect, max_events=budget)


def test_noise_is_reproducible_and_channel_specific():
    ctx = SampleContext(10, 0, BASE.window, "a", 123)
    assert ctx.noise() == replace(ctx).noise()
    assert ctx.noise() != replace(ctx, seed=124).noise()
    assert ctx.noise() != ctx.noise("other")
    assert ctx.noise(animated=False) == replace(ctx, time_ms=50).noise(animated=False)


def test_blur_bound_and_global_fade():
    layer = replace(BASE, paint=Paint(glow=Glow()), fade=Fade(100, 0))
    dynamic = DynamicEffect(
        lambda ctx: DynamicProperties(glow_blur=20, offset_y=ctx.time_ms / 100),
        max_glow_blur=20,
    )
    sampled = prepare_sampling((layer,), dynamic).evaluate()
    for sample in sampled:
        assert sample.paint.glow is not None
        assert sample.paint.glow.blur == 20
    events = compile_layers(sampled).events
    later = [e for e in events if e.start_time == 80]
    # The original 10..110 ms fade is 70% complete at this event's t=0.
    assert later and all(
        r"\alpha&HFF&\t(-70,30,1,\alpha&H00&)" in e.text for e in later
    )
    with pytest.raises(OutputCapabilityError, match="max_glow_blur"):
        prepare_sampling((layer,), replace(dynamic, max_glow_blur=10)).evaluate()


def test_callback_errors_identify_target_and_time():
    with pytest.raises(OutputCapabilityError, match="a at 10 ms"):
        # Invalid callback results are diagnosed during evaluation.
        prepare_sampling(
            (BASE,),
            DynamicEffect(lambda ctx: None),  # ty: ignore[invalid-argument-type]
        ).evaluate()


def test_sampled_clip_retains_original_interpolation_endpoints():
    import re

    layer = replace(
        BASE,
        window=DisplayWindow(0, 1000),
        clips=(ClipSpan(0, 1000, Region(100.2, 100.2), Region(100.2, 307.8)),),
    )
    sampled = prepare_sampling(
        (layer,),
        DynamicEffect(lambda ctx: DynamicProperties(offset_y=ctx.time_ms / 100)),
    ).evaluate()
    for event in compile_layers(sampled).events:
        match = re.search(
            r"\\t\((-?\d+),(\d+),1,\\clip\(100,0,308,1080\)\)", event.text
        )
        assert match
        assert int(match[1]) + event.start_time == 0
        assert int(match[2]) + event.start_time == 1000


def test_sampling_preserves_native_pulse_fade_and_clip_approximation():
    import re

    from kara_templater import ScaleAnimation

    layer = replace(
        BASE,
        window=DisplayWindow(0, 1000),
        fade=Fade(300, 300),
        clips=(ClipSpan(0, 1000, Region(100, 100), Region(100, 300)),),
        animations=(ScaleAnimation("a", "track", 0, 100, 900, 1.4, (120, 120)),),
    )
    native = compile_layers((layer,)).events
    # Force exposure cuts even though an identity callback now coalesces them.
    sampled = compile_layers(
        tuple(
            replace(layer, active_window=DisplayWindow(t, min(t + 40, 1000)))
            for t in range(0, 1000, 40)
        )
    ).events

    def absolute_tags(event):
        text = re.sub(
            r"\\t\((-?\d+),(-?\d+),",
            lambda m: (
                rf"\t({int(m[1]) + event.start_time},{int(m[2]) + event.start_time},"
            ),
            event.text,
        )
        return re.sub(
            r"(\\move\([^,]+,[^,]+,[^,]+,[^,]+,)(-?\d+),(-?\d+)\)",
            lambda m: (
                f"{m[1]}{int(m[2]) + event.start_time},{int(m[3]) + event.start_time})"
            ),
            text,
        )

    for event in sampled:
        reference = next(
            e
            for e in native
            if e.start_time <= event.start_time and e.end_time >= event.end_time
        )
        assert absolute_tags(event) == absolute_tags(reference)


def test_constant_sampling_coalesces_but_evaluates_every_timestamp():
    calls = []

    def properties(ctx):
        calls.append(ctx.time_ms)
        return DynamicProperties(opacity=0.5)

    plan = prepare_sampling((BASE,), DynamicEffect(properties))
    sampled = plan.evaluate()
    assert calls == [10, 40, 80, 120]
    assert len(sampled) == 1
    assert sampled[0].active_window == BASE.window
    assert sampled[0].paint.opacity == 0.5
    assert len(compile_layers(sampled).events) == 1


def test_sampling_does_not_merge_across_gaps_or_small_property_changes():
    layer = replace(
        BASE,
        clips=(
            ClipSpan(10, 40, Region(100, 110), Region(100, 110)),
            ClipSpan(80, 130, Region(100, 110), Region(100, 110)),
        ),
    )
    result = prepare_sampling(
        (layer,), DynamicEffect(lambda ctx: DynamicProperties())
    ).evaluate()
    assert [s.active_window for s in result] == [
        DisplayWindow(10, 40),
        DisplayWindow(80, 130),
    ]
    changing = prepare_sampling(
        (BASE,),
        DynamicEffect(lambda ctx: DynamicProperties(opacity=1 - ctx.time_ms * 1e-10)),
    ).evaluate()
    assert len(changing) == 4


def test_source_read_order_does_not_follow_exposure_start_time():
    # Same ASS layer: z starts earlier, but a must remain below z when either
    # source is split or merged. ReadOrder is the order of event records.
    layers = (
        replace(BASE, source_id="z"),
        replace(BASE, source_id="a", active_window=DisplayWindow(40, 80)),
    )
    events = compile_layers(layers).events
    assert [e.effect.rsplit(":", 1)[-1] for e in events] == ["a", "z"]
    merged = prepare_sampling(
        layers, DynamicEffect(lambda ctx: DynamicProperties())
    ).evaluate()
    events = compile_layers(merged).events
    assert [e.effect.split("/sample:")[0].rsplit(":", 1)[-1] for e in events] == [
        "a",
        "z",
    ]
