"""Retained authoring capabilities across the consolidated Track frontend."""

from dataclasses import replace

import pytest
from test_track_preparation import binding

from kara_templater import (
    BLUE,
    RED,
    Body,
    DisplayWindow,
    Document,
    HighlightAnimation,
    HighlightStyle,
    HighlightTrack,
    KaraokeItem,
    KaraokeLine,
    LineMatch,
    ObjectGroup,
    Overlay,
    Paint,
    PaintStyle,
    Pulse,
    Region,
    SceneBudget,
    SceneCompileError,
    Segment,
    SingingPass,
    Style,
    Sweep,
    TextStyle,
    TextUnit,
    Track,
    Transition,
    layout_characters,
    prepare_tracks,
    there_and_back,
)
from kara_templater._raster import rasterize
from kara_templater.behaviors import sample_properties


def test_highlight_callback_uses_each_drawable_characters_arrival_clock():
    trigger = Pulse(duration_ms=200)
    bound, item, context = binding(
        HighlightAnimation(
            trigger=trigger, offset_y=Transition(0, -12, rate=there_and_back)
        )
    )
    prepared = bound.prepare(item, context)
    characters = layout_characters(context.layout, style=context.style)
    unit = context.layout.units[0]
    segment = item.source.units[0].segments[0]
    start_times = []
    for char in characters:
        motions = prepared.properties[char.id]
        expected = segment.start_ms + (
            (char.target.region.left - unit.box.left) / unit.box.width
        ) * (segment.end_ms - segment.start_ms)
        assert motions[0].interval == pytest.approx((expected, expected + 200))
        assert sample_properties(motions, expected + 100)["offset_y"] == pytest.approx(
            -12
        )
        assert sample_properties(motions, expected + 250).get("offset_y", 0) == 0
        start_times.append(motions[0].interval[0])
    assert start_times[1] > start_times[0]
    assert item.source.units[0].segments == (Segment(500, 1500, "ab"),)


@pytest.mark.parametrize("mode", ("priority", "layer"))
@pytest.mark.parametrize("time", (0, 500, 1000, 1500))
def test_named_parallel_highlights_keep_paint_policy_in_both_output_modes(mode, time):
    document = Document.create(
        width=320,
        height=180,
        styles=(Style(fontname="DejaVu Sans", fontsize=32, align=5, shadow=0),),
    )
    item = KaraokeItem(
        "line",
        KaraokeLine((TextUnit("AB", (Segment(0, 1000),)),)),
        "Default",
        DisplayWindow(0, 2000),
    )
    opacity = 0.5 if mode == "layer" else 1.0

    def highlights(layout):
        box = layout.units[0].box
        region = Region(box.left, box.right)
        return (
            HighlightTrack("red", 0, (SingingPass(0, 1000, region),)),
            HighlightTrack("blue", 0, (SingingPass(0, 1000, region),)),
        )

    configured = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(stroke_width=0)),
        overlay=Overlay(
            style=PaintStyle(fill=RED),
            highlights=highlights,
            styles=(
                HighlightStyle("red", Paint(RED, opacity=opacity)),
                HighlightStyle("blue", Paint(BLUE, opacity=opacity), priority=10),
            ),
            overlap=mode,
        ),
    )
    native = prepare_tracks(
        document, (item,), tracks=(configured,), mode="native"
    ).compile()
    editable = prepare_tracks(document, (item,), tracks=(configured,)).compile()
    frames = [
        rasterize(native.document.dumps(), time + 10, (320, 180)).rgba,
        rasterize(editable.document.dumps(), time, (320, 180)).rgba,
    ]
    assert frames[0] == frames[1]
    pixels = list(zip(*(iter(frames[0]),) * 4, strict=True))
    opaque = max(pixels, key=lambda pixel: pixel[3])
    if time < 1000:
        assert opaque[3] > 0
    elif mode == "priority":
        assert opaque == (0, 0, 255, 255)
    else:
        # Layer composition retains the base: half-alpha blue over red.
        assert opaque == pytest.approx((128, 0, 127, 255), abs=2)
    assert all(origin is not None for _, origin in native.event_origins)
    assert item.source.units[0].segments == (Segment(0, 1000),)


def test_editable_is_default_and_shared_scene_budgets_cover_native_output():
    document = Document.create()
    item = KaraokeItem(
        "line",
        KaraokeLine((TextUnit("A", (Segment(0, 1000),)),)),
        "Default",
        DisplayWindow(0, 1000),
    )
    configured = Track(source=LineMatch(), overlay=Overlay())
    editable = prepare_tracks(document, (item,), tracks=(configured,))
    assert isinstance(editable.scene.objects[0], ObjectGroup)
    native = prepare_tracks(document, (item,), tracks=(configured,), mode="native")
    with pytest.raises(SceneCompileError, match="budget"):
        native.compile(budget=SceneBudget(max_bytes=1))
    result = native.compile()
    assert all(
        any(event is record for record in result.document.records)
        for event, _ in result.event_origins
    )
    assert native.compile().document.dumps() == result.document.dumps()


def test_sweep_has_one_curve_parameter_and_output_modes_are_explicit():
    with pytest.raises(TypeError, match="curve"):
        Sweep(curve=lambda progress: progress)  # ty: ignore[unknown-argument]
    document = Document.create()
    with pytest.raises(ValueError, match="mode"):
        prepare_tracks(document, tracks=(), mode="unknown")  # ty: ignore[invalid-argument-type]
    assert replace(Sweep(), completion="clip").completion == "clip"
