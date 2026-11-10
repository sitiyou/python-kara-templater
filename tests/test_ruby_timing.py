from dataclasses import replace

import pytest

from kara_templater import (
    CharacterTarget,
    Color,
    DisplayWindow,
    EffectContext,
    HighlightEnter,
    HighlightTrack,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Paint,
    PaintPair,
    ProgressCurve,
    Pulse,
    Region,
    RubyPolicy,
    Segment,
    SingingPass,
    Style,
    TextUnit,
    compile_layers,
    layout_line,
    plan_pulses,
)


@pytest.mark.parametrize(
    "threshold,expected", [("enter", 140), ("center", 300), ("complete", 1020)]
)
@pytest.mark.parametrize("instant", [False, True])
def test_ruby_coordinate_mapping_keeps_threshold_arrivals(threshold, expected, instant):
    source = KaraokeLine((TextUnit("A", (Segment(100, 1100, "reading"),)),))
    style = Style(fontname="DejaVu Sans", fontsize=40)
    layout = layout_line(source, style=style, ruby_style=replace(style, fontsize=20))
    body = layout.units[0].box
    ruby = layout.units[0].segments[0].ruby
    curve = ProgressCurve(((0, 0), (0.2, 0.5), (0.6, 0.5), (1, 1)))
    starts = []
    for name, box in (("body", body), ("ruby", ruby)):
        track = HighlightTrack(
            "mapped",
            0,
            (
                SingingPass(
                    100, 100 if instant else 1100, Region(box.left, box.right), curve
                ),
            ),
        )
        target = CharacterTarget(
            name,
            0,
            Region(box.left + box.width * 0.1, box.left + box.width * 0.9),
            box.middle,
        )
        result = plan_pulses(
            (Pulse.each_char(trigger=HighlightEnter(threshold), duration_ms=50),),
            layout=layout,
            characters=(target,),
            tracks=(track,),
            window=DisplayWindow(0, 1200),
        )
        starts.append(result.animations[0].start_ms)
    assert starts == pytest.approx([100 if instant else expected] * 2)


@pytest.mark.parametrize("repeat", ["hold", "reset"])
@pytest.mark.parametrize("ending", ["hold", "hide"])
def test_ruby_affine_mapping_preserves_pauses_rounds_and_exit(repeat, ending):
    source = KaraokeLine(
        (TextUnit("Wide", (Segment(100, 300, "wi"), Segment(500, 700, "de"))),)
    )
    style = Style(fontname="DejaVu Sans", fontsize=40)
    ruby_style = replace(style, name="ruby", fontsize=20)
    layout = layout_line(
        source, style=style, ruby_style=ruby_style, resolution=(640, 480)
    )
    first, second = layout.units[0].segments
    curve = ProgressCurve(((0, 0), (0.25, 0.5), (0.75, 0.5), (1, 1)))
    track = HighlightTrack(
        "reading",
        0,
        (
            SingingPass(100, 300, Region(first.left, first.right), curve),
            SingingPass(500, 700, Region(second.left, second.right)),
            SingingPass(800, 1000, Region(first.left, second.right), round_id=1),
        ),
        repeat=repeat,
        end_behavior=ending,
    )
    before, after = Paint(), Paint(Color(255, 0, 0))
    plan = KaraokeEffect(
        paints=PaintPair(before, after),
        tracks=(track,),
        pulses=(Pulse.whole_syllable(duration_ms=100),),
        ruby=RubyPolicy(follow="syllable"),
    ).build(
        KaraokeItem("line", source, "Default", DisplayWindow(0, 1200)),
        EffectContext(layout, style, ruby_style, (640, 480)),
    )
    for index, segment in enumerate((first, second)):
        layers = [
            layer
            for layer in plan.layers
            if layer.animation_id == f"line/ruby:0:{index}"
        ]
        assert layers
        # Both readings follow the body's same group pivot and singing rounds.
        animations = {a for layer in layers for a in layer.animations}
        assert {a.start_ms for a in animations} == {100, 800}
        assert {a.pivot for a in animations} == {
            (layout.units[0].box.center, layout.units[0].box.middle)
        }
        for time in (
            99,
            100,
            150,
            200,
            250,
            299,
            300,
            400,
            500,
            600,
            700,
            800,
            850,
            950,
            1000,
            1100,
        ):
            for progress in (0.1, 0.5, 0.9):
                body_x = segment.left + (segment.right - segment.left) * progress
                ruby_x = segment.ruby.left + segment.ruby.width * progress
                expected = (
                    after
                    if any(r.left <= body_x < r.right for r in track.regions_at(time))
                    else before
                )
                actual = [
                    layer.paint
                    for layer in layers
                    if (
                        layer.active_window is None
                        or layer.active_window.start_ms
                        <= time
                        < layer.active_window.end_ms
                    )
                    and (
                        layer.clips is None
                        or any(
                            span.start_ms <= time < span.end_ms
                            and span.at(time).left <= ruby_x < span.at(time).right
                            for span in layer.clips
                        )
                    )
                ]
                assert actual == [expected], (index, time, progress)
    assert compile_layers(plan.layers).events
