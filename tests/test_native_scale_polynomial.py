"""Compact ASS scale polynomials retain source curves across event cuts."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
    smoother_rate,
)
from kara_templater._raster import rasterize
from kara_templater.output.ass_export import _scale_polynomials


def glyph(rate=smoother_rate, *, peak=1.06, duration=1, peak_at=0.42):
    return PathObject(
        id="glyph", lifetime=Lifetime(0, 1.7),
        path=VectorPath.rectangle(48, 32),
        state=VisualState(position=Vec2(20, 20), scale=Vec2(0.8, 1.1)),
        clip=RectangleClip(-100, -100, 200, 200, space="local",
                           deform=RectangleKeyframes(((0, (-100, -100, 200, 200)),))),
    ).animate(ScalePulse(peak=peak, rate=rate, peak_at=peak_at), at=0.2, duration=duration)


@pytest.mark.parametrize("rate", [smooth_rate, smoother_rate])
def test_polynomial_matches_independent_scale_frames_across_event_cuts(rate):
    doc = Document.create(width=100, height=80)
    node = glyph(rate)
    result = Scene(doc).add(node).ass.compile(native_tweens=True)
    assert all(item.strategy == "native-clip-eased" for item in result.objects)
    assert _scale_polynomials(node)
    assert result.event_count > 1  # Includes groups beginning inside a curve.
    for ms in (0, 199, *range(200, 1201, 10), 1450):
        reference = Scene(doc).add(replace(
            node, animations=(), clip=None, state=node.at(ms / 1000),
        )).ass.compile()
        actual = rasterize(result.document.dumps(), ms, (100, 80)).rgba[3::4]
        expected = rasterize(reference.document.dumps(), ms, (100, 80)).rgba[3::4]
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1, ms


def test_phase_rounding_has_a_scale_bound_and_unsafe_controls_fall_back():
    node = glyph(duration=0.25, peak_at=0.37)
    curve, = _scale_polynomials(node)
    for tick in range(2000, 4501):
        time = tick / 10000
        scale = node.state.scale
        for (start, initial), (end, final) in zip(curve.knots, curve.knots[1:], strict=False):
            a, b = round(start * 1000) / 1000, round(end * 1000) / 1000
            if time < a:
                continue
            if time >= b:
                scale = final
                continue
            p = (time - a) / (b - a)
            for coefficient in curve.controls:
                target = initial + (final - initial) * coefficient
                scale = scale.lerp(target, p)
        expected = node.at(time).scale
        assert abs(scale.x - expected.x) <= 0.001
        assert abs(scale.y - expected.y) <= 0.001
    assert not _scale_polynomials(glyph(smoother_rate, peak=1.25))
    assert not _scale_polynomials(glyph(smooth_rate, peak=1.6))
    assert not _scale_polynomials(glyph(duration=0.001, peak_at=0.42))
