"""Output-only text anchoring coalesces pulses without changing source geometry."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    DriftOut,
    Lifetime,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    TextObject,
    Vec2,
    VisualState,
    linear_rate,
    smoother_rate,
)
from kara_templater._raster import rasterize
from kara_templater.ass import Style
from kara_templater.layout import text_extents


@pytest.mark.parametrize("text,italic,spacing", (("A", False, 0), ("gj", True, 0), ("AV", False, 1.5)))
@pytest.mark.parametrize("travel_rate", (None, linear_rate))
def test_centered_text_pulse_keeps_pixels_and_uses_one_event(text, italic, spacing, travel_rate):
    width, height, _, _ = text_extents(Style(
        fontname="DejaVu Sans", fontsize=48, italic=italic, spacing=spacing, outline=0,
    ), text)
    pivot = Vec2(width / 2, height / 2)
    node = TextObject(
        id="word", text=text, font_size=48, italic=italic, spacing=spacing,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(40, 24), border=1, blur=0.3),
        clip=RectangleClip(0, -3, width, height + 3, space="local", deform=RectangleKeyframes((
            (0, (0, -3, 0, height + 3)), (2, (0, -3, width, height + 3)),
        ))),
    ).animate(ScalePulse(peak=1.1, peak_at=0.42, pivot=pivot, rate=smoother_rate), duration=2)
    doc = Document.create(width=192, height=128)
    scene = Scene(doc).add(node)
    result = scene.ass.compile(native_tweens=True)
    report = result.objects[0]
    assert report.strategy == "native-clip-eased"
    assert report.events == 1
    assert all(r"\an5" in line.text for line in result.document.lines)
    assert node.alignment == 7 and scene.objects[0] is node
    assert isinstance(node.clip, RectangleClip)
    assert isinstance(node.clip.deform, RectangleKeyframes)
    for ms in (230, 590, 840, 1290, 1930, 2300):
        time = ms / 1000
        bounds = node.clip.deform.bounds_at(time)
        static = replace(node, state=node.at(time), animations=(), clip=replace(
            node.clip, deform=RectangleKeyframes(((0, bounds), (3, bounds))),
        ))
        expected = Scene(doc).add(static).ass.compile()
        actual_pixels = rasterize(result.document.dumps(), ms, (192, 128)).rgba
        expected_pixels = rasterize(expected.document.dumps(), ms, (192, 128)).rgba
        # Native ASS clips round to whole pixels; one boundary pixel plus
        # subpixel text placement may differ from independently rasterized clips.
        error = sum(abs(a - b) for a, b in zip(
            actual_pixels[3::4], expected_pixels[3::4], strict=True,
        ))
        perimeter = 2 * (width + height) * node.at(time).scale.x
        assert error <= perimeter * 255
        color_error = sum(
            abs(actual_pixels[i + c] * actual_pixels[i + 3]
                - expected_pixels[i + c] * expected_pixels[i + 3]) / 255
            for i in range(0, len(actual_pixels), 4) for c in range(3)
        )
        assert color_error <= 3 * perimeter * 255 + 0.02 * sum(expected_pixels[3::4])
    # A separate curved departure must not be swallowed into the fixed anchor.
    drifting = node.animate(DriftOut(offset=Vec2(12, -24), pivot=pivot, travel_rate=travel_rate), at=2.14, duration=0.56)
    output = Scene(doc).add(drifting).ass.compile(native_tweens=True)
    assert output.event_count > result.event_count
    assert any(r"\move(" in line.text for line in output.document.lines)
    if travel_rate is linear_rate:
        assert output.event_count <= 3
    time = 2.28
    static = replace(drifting, state=drifting.at(time), animations=(), clip=replace(
        node.clip, deform=RectangleKeyframes(((0, (0, -3, width, height + 3)),)),
    ))
    expected = Scene(doc).add(static).ass.compile()
    actual_pixels = rasterize(output.document.dumps(), 2280, (192, 128)).rgba
    expected_pixels = rasterize(expected.document.dumps(), 2280, (192, 128)).rgba
    assert sum(abs(a - b) for a, b in zip(
        actual_pixels[3::4], expected_pixels[3::4], strict=True,
    )) <= 2 * (width + height) * 255
