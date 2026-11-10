import re
from dataclasses import replace

import pytest

from kara_templater.animation import ScaleAnimation
from kara_templater.ass import Style
from kara_templater.ass_output import (
    ClipSpan,
    Fade,
    OutputCapabilityError,
    OutputSettings,
    TextLayer,
    alpha,
    color,
    compile_layers,
    escape_text,
    quantize,
    sweep_spans,
)
from kara_templater.composition import Color, Glow, Paint
from kara_templater.model import Box
from kara_templater.timeline import (
    DisplayWindow,
    EdgeSweep,
    ProgressCurve,
    Region,
    SingingPass,
)

WINDOW = DisplayWindow(500, 2500)
LAYER = TextLayer("unit:0/text:0:1", "A", Style(), Box(100, 100, 100, 40), WINDOW)


def test_clip_subdivision_keeps_original_scale_and_decoration_clock():
    layer = replace(
        LAYER,
        paint=Paint(glow=Glow(blur=8, border=3)),
        clips=(ClipSpan(1000, 2000, Region(100, 100), Region(100, 300)),),
        animations=(ScaleAnimation("a", "main", 0, 1000, 2000, 1.4, (150, 120)),),
    )
    events = compile_layers((layer,)).events
    rising = [e for e in events if 1000 <= e.start_time < 1500]
    assert len(rising) > 2  # moving clip forces adaptive subdivisions
    for event in rising:
        match = re.search(r"\\t\((-?\d+),(-?\d+),1,\\fscx140\\fscy140", event.text)
        assert match
        assert event.start_time + int(match[1]) == 1000
        assert event.start_time + int(match[2]) == 1500
        assert r"\fscx100\fscy100" in event.text
        if event.layer == 0:
            assert r"\bord3\blur8" in event.text
            assert r"\bord4.2\blur11.2" in event.text


def test_origins_follow_sorted_events_and_all_visual_passes():
    from kara_templater import EventOrigin, SourceRef

    first = EventOrigin((SourceRef("first", 0, 0),), "sweep", ("main",))
    second = EventOrigin((SourceRef("second", 0),), "static")
    result = compile_layers(
        (
            replace(
                LAYER,
                source_id="z",
                origin=first,
                order=10,
                paint=Paint(glow=Glow(blur=4)),
                fade=Fade(100, 100),
            ),
            replace(LAYER, source_id="a", origin=second),
        )
    )
    assert len(result.events) == len(result.origins) > 3
    assert result.origins[0] is second
    for event, origin in zip(result.events, result.origins, strict=True):
        assert origin is (first if event.effect.endswith("z") else second)
    assert compile_layers((LAYER,)).origins == (None,)


def test_codec_and_shared_time_quantization():
    assert color(Color(1, 2, 3)) == "&H030201&"
    assert alpha(0) == "&HFF&"
    assert alpha(1) == "&H00&"
    assert alpha(0.5) == "&H80&"
    assert [quantize(t) for t in (0, 4, 5, 14, 15)] == [0, 0, 10, 10, 20]
    assert escape_text("a{b}\\N\nc") == "a\\{b\\}\\\u2060N\\Nc"


def test_static_layer_has_one_event_and_uses_requested_paint():
    result = compile_layers((replace(LAYER, paint=Paint(Color(255, 0, 0))),))
    assert len(result.events) == 1
    event = result.events[0]
    assert (event.start_time, event.end_time) == (500, 2500)
    assert r"\1c&H0000FF&" in event.text
    assert r"\pos(150,120)" in event.text
    assert event.effect.endswith(LAYER.source_id)


def test_sweep_body_endpoints_do_not_depend_on_padding_or_glow_extent():
    singing = SingingPass(1000, 2000, Region(100, 200))
    small = sweep_spans(
        singing, paint=Region(90, 210), window=WINDOW, edges=EdgeSweep(5, 100, 200)
    )
    large = sweep_spans(
        singing, paint=Region(-100, 400), window=WINDOW, edges=EdgeSweep(50, 100, 200)
    )
    for spans in (small, large):
        body = next(s for s in spans if s.start_ms == 1000)
        assert body.start.right == 100
        assert body.at(1500).right == 150
        assert body.end.right == 200
    result = compile_layers(
        (replace(LAYER, clips=large),), settings=OutputSettings((640, 480))
    )
    assert len(result.events) == 4
    assert all(
        ",480)" in event.text and ",1080)" not in event.text for event in result.events
    )


def test_piecewise_sweep_keeps_pause_and_does_not_sample_frames():
    curve = ProgressCurve(((0, 0), (0.2, 0.4), (0.6, 0.4), (1, 1)))
    spans = sweep_spans(
        SingingPass(1000, 2000, Region(100, 200), curve),
        paint=Region(100, 200),
        window=WINDOW,
    )
    result = compile_layers((replace(LAYER, clips=spans),))
    pause = next(e for e in result.events if e.start_time == 1200)
    assert pause.end_time == 1600
    assert r"\clip(100,0,140,1080)" in pause.text
    assert r"\t(" not in pause.text
    assert len(result.events) == 4


def test_zero_duration_singing_releases_mask_without_zero_length_event():
    spans = sweep_spans(
        SingingPass(1000, 1000, Region(100, 200)), paint=Region(90, 210), window=WINDOW
    )
    result = compile_layers((replace(LAYER, clips=spans),))
    assert len(result.events) == 1
    assert result.events[0].start_time == 1000
    assert r"\clip(90,0,210,1080)" in result.events[0].text


def test_fade_uses_global_time_across_clip_segments():
    spans = (
        ClipSpan(500, 700, Region(0, 200), Region(0, 200)),
        ClipSpan(700, 2500, Region(0, 200), Region(0, 200)),
    )
    result = compile_layers((replace(LAYER, clips=spans, fade=Fade(400, 200)),))
    second = next(e for e in result.events if e.start_time == 700)
    # Keep the original 500..900 ms endpoints; at this event's t=0 the
    # transform is halfway through, without rounding/restarting at alpha 128.
    assert r"\alpha&HFF&\t(-200,200,1,\alpha&H00&)" in second.text
    assert any(e.start_time == 2300 and r"\alpha&HFF&" in e.text for e in result.events)


def test_group_scale_moves_center_and_all_visual_layers_together():
    animation = ScaleAnimation(LAYER.source_id, "main", 0, 1000, 2000, 2, (100, 120))
    layer = replace(
        LAYER,
        paint=Paint(glow=Glow(blur=5, border=3)),
        animations=(animation,),
        order=7,
    )
    result = compile_layers((layer,))
    growing = [e for e in result.events if e.start_time == 1000]
    assert len(growing) == 2
    assert {e.layer for e in growing} == {14, 15}
    assert all(r"\move(150,120,200,120,0,500)" in e.text for e in growing)
    assert all(r"\fscx200\fscy200" in e.text for e in growing)


def test_sweep_and_scale_subdivide_by_spatial_error_and_report_cost_limit():
    animation = ScaleAnimation(LAYER.source_id, "main", 0, 1000, 2000, 2, (100, 120))
    spans = sweep_spans(
        SingingPass(1000, 2000, Region(100, 200)), paint=Region(100, 200), window=WINDOW
    )
    layer = replace(LAYER, animations=(animation,), clips=spans)
    result = compile_layers((layer,))
    assert 4 < len(result.events) < 50
    assert all(e.end_time > e.start_time for e in result.events)
    for event in result.events:
        if not 1000 <= event.start_time < 2000:
            continue
        masks = re.findall(r"\\clip\((-?\d+),0,(-?\d+),1080\)", event.text)
        first, last = masks[0], masks[-1]
        for fraction in (0, 0.25, 0.5, 0.75, 1):
            time = event.start_time + (event.end_time - event.start_time) * fraction
            scale = 1 + (1 - abs(2 * (time - 1000) / 1000 - 1))
            expected = 100 + ((time - 1000) / 10) * scale
            actual = int(first[1]) + (int(last[1]) - int(first[1])) * fraction
            assert abs(actual - expected) <= 0.75 + 1e-8
    with pytest.raises(OutputCapabilityError, match="event limit 2"):
        compile_layers((layer,), settings=OutputSettings(max_events=2))


def test_short_windows_and_clip_quantization_diagnostics():
    result = compile_layers((replace(LAYER, window=DisplayWindow(1, 4)),))
    assert not result.events and "vanished" in result.diagnostics[0]


def test_pre_sweep_before_zero_keeps_its_original_progress():
    window = DisplayWindow(0, 1000)
    spans = sweep_spans(
        SingingPass(50, 500, Region(100, 200)),
        paint=Region(0, 300),
        window=window,
        edges=EdgeSweep(lead_ms=100),
    )
    result = compile_layers((replace(LAYER, window=window, clips=spans),))
    assert result.events[0].start_time == 0
    # At event-local t=0 this original -50..50 transform is halfway through.
    assert r"\clip(0,0,0,1080)\t(-50,50,1,\clip(0,0,100,1080))" in result.events[0].text


def test_subcentisecond_pulse_is_diagnosed():
    from kara_templater import EventOrigin, SourceRef

    origin = EventOrigin((SourceRef("lyric", 2, 1),), "pulse", ("main",))
    animation = ScaleAnimation(LAYER.source_id, "main", 0, 1000, 1004, 2, (100, 120))
    with pytest.raises(
        OutputCapabilityError, match="pulse rise/fall collapses"
    ) as caught:
        compile_layers((replace(LAYER, animations=(animation,), origin=origin),))
    assert caught.value.origin is origin
    assert caught.value.time_ms == 1000
    assert "segment_index=1" in caught.value.__notes__[0]


def test_clips_and_animation_conflicts_rejected():
    with pytest.raises(ValueError, match="clip spans"):
        replace(
            LAYER,
            clips=(
                ClipSpan(100, 200, Region(0, 1), Region(0, 1)),
                ClipSpan(150, 300, Region(0, 1), Region(0, 1)),
            ),
        )
