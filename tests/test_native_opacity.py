from dataclasses import replace

import pytest

from kara_templater import (
    Box,
    ClipSpan,
    DisplayWindow,
    Fade,
    Glow,
    OpacityAnimation,
    OutputCapabilityError,
    Paint,
    Region,
    Style,
    TextLayer,
    compile_layers,
)

BASE = TextLayer("opacity", "A", Style(), Box(100, 100, 40, 40), DisplayWindow(0, 3000))


def events(*motions, **kwargs):
    return compile_layers((replace(BASE, opacity_animations=motions, **kwargs),)).events


def test_native_opacity_preserves_start_jump_and_end_reset():
    result = events(OpacityAnimation(((1000, 0.2), (2000, 0.8))))
    assert [(e.start_time, e.end_time) for e in result] == [
        (0, 1000),
        (1000, 2000),
        (2000, 3000),
    ]
    assert r"\alpha&H00&" in result[0].text and r"\t(" not in result[0].text
    assert r"\alpha&HCC&" in result[1].text
    assert r"\t(0,1000,1,\alpha&H33&)" in result[1].text
    assert r"\alpha&H00&" in result[2].text and r"\t(" not in result[2].text


def test_native_opacity_keep_and_piecewise_hold():
    result = events(
        OpacityAnimation(((500, 0.2), (1000, 0.8), (1500, 0.8), (2000, 0.4)), keep=True)
    )
    hold = next(e for e in result if e.start_time == 1000)
    assert r"\alpha&H33&" in hold.text and r"\t(" not in hold.text
    assert r"\alpha&H99&" in result[-1].text


def test_glow_override_does_not_modify_body_or_lose_zero_base_opacity():
    result = events(
        OpacityAnimation(((1000, 0.2), (2000, 0.8)), component="glow", keep=True),
        paint=Paint(opacity=0.5, glow=Glow(opacity=0)),
    )
    body = [e for e in result if e.layer == 1]
    glow = [e for e in result if e.layer == 0]
    assert all(r"\alpha&H80&" in e.text and r"\t(" not in e.text for e in body)
    assert r"\alpha&HFF&" in glow[0].text
    assert r"\alpha&H99&" in glow[-1].text


def test_native_alpha_uses_original_knots_across_clip_cuts_and_sample_exposures():
    motion = OpacityAnimation(((1000, 0.2), (2000, 0.8)), keep=True)
    result = events(
        motion,
        clips=(
            ClipSpan(1000, 1500, Region(100, 120), Region(100, 130)),
            ClipSpan(1500, 2000, Region(100, 130), Region(100, 140)),
        ),
        active_window=DisplayWindow(1600, 1700),
    )
    assert len(result) == 1
    assert (result[0].start_time, result[0].end_time) == (1600, 1700)
    assert r"\alpha&HCC&" in result[0].text
    assert r"\t(-600,400,1,\alpha&H33&)" in result[0].text


def test_nonoverlapping_fade_and_opacity_ramps_are_exact_native_transforms():
    result = events(
        OpacityAnimation(((1000, 0.2), (2000, 0.8)), keep=True),
        fade=Fade(in_ms=500, out_ms=500),
    )
    assert r"\alpha&HFF&" in result[0].text
    assert r"\t(0,500,1,\alpha&H00&)" in result[0].text
    assert r"\alpha&H33&" in result[-1].text
    assert r"\t(0,500,1,\alpha&HFF&)" in result[-1].text


@pytest.mark.parametrize("other", ["fade", "glow"])
def test_nonlinear_products_are_rejected_for_author_sampling_fallback(other):
    motions = [OpacityAnimation(((0, 0.2), (1000, 0.8)))]
    options = (
        {"fade": Fade(in_ms=1000)} if other == "fade" else {"paint": Paint(glow=Glow())}
    )
    if other == "glow":
        motions.append(OpacityAnimation(((0, 0.3), (1000, 0.7)), component="glow"))
    with pytest.raises(
        OutputCapabilityError, match="nonlinear opacity product requires sampling"
    ):
        events(*motions, **options)


def test_instantaneous_keep_transition_and_quantization_diagnostics():
    result = events(OpacityAnimation(((1000, 0.2), (1000, 0.8)), keep=True))
    assert len(result) == 2
    assert r"\alpha&H33&" in result[1].text
    with pytest.raises(OutputCapabilityError, match="opacity keyframes collapse"):
        events(OpacityAnimation(((1000, 0), (1004, 1))))


def test_overlapping_native_opacity_rules_and_invalid_values_are_rejected():
    with pytest.raises(ValueError, match="overlapping group opacity"):
        events(
            OpacityAnimation(((0, 0), (1000, 1)), keep=True),
            OpacityAnimation(((1500, 0), (2000, 1))),
        )
    with pytest.raises(ValueError, match="0..1"):
        OpacityAnimation(((0, -0.1), (1000, 1)))
    with pytest.raises(ValueError, match="must increase"):
        OpacityAnimation(((1000, 0), (0, 1)))


def test_native_opacity_preserves_origins_and_enforces_output_budget():
    from kara_templater import EventOrigin, OutputSettings, SourceRef

    origin = EventOrigin((SourceRef("line", 0, 0),), "native opacity")
    layer = replace(
        BASE,
        origin=origin,
        opacity_animations=(OpacityAnimation(((1000, 0.2), (2000, 0.8))),),
    )
    result = compile_layers((layer,))
    assert result.origins == (origin,) * 3
    with pytest.raises(OutputCapabilityError) as error:
        compile_layers((layer,), settings=OutputSettings(max_events=1))
    assert error.value.origin == origin


def test_native_opacity_survives_sampled_position_changes():
    from kara_templater import DynamicEffect, DynamicProperties, prepare_sampling

    layer = replace(
        BASE, opacity_animations=(OpacityAnimation(((1000, 0.2), (2000, 0.8))),)
    )
    sampled = prepare_sampling(
        (layer,),
        DynamicEffect(
            lambda context: DynamicProperties(offset_x=context.progress * 10)
        ),
    ).evaluate()
    assert sampled and all(
        l.opacity_animations == layer.opacity_animations for l in sampled
    )
    event = next(e for e in compile_layers(sampled).events if e.start_time == 1600)
    assert r"\alpha&HCC&" in event.text
    assert r"\t(-600,400,1,\alpha&H33&)" in event.text
