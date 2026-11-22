"""Compiler-owned cubic approximation keeps clocks and bounded native motion."""

from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    ColorRamp,
    ColorStop,
    Document,
    DriftOut,
    Lifetime,
    LinearGradient,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    SceneBudget,
    Vec2,
    VectorPath,
    VisualState,
    linear_rate,
    smooth_rate,
    smoother_rate,
)
from kara_templater._raster import rasterize
from kara_templater.scene_output import _eased_rectangle_leaf, _leaves


def subject(duration=2, rate=smooth_rate):
    return PathObject(
        id="glyph", lifetime=Lifetime(0, duration + 1),
        path=VectorPath.rectangle(48, 32),
        state=VisualState(position=Vec2(32, 40), opacity=0.8),
        material=LinearGradient(
            axis="y", space="local",
            fill=ColorRamp((ColorStop(0, Color.hex("#30FFFF")),
                            ColorStop(32, Color.hex("#FF60C0")))),
        ),
        clip=RectangleClip(0, 0, 48, 32, space="local", deform=RectangleKeyframes((
            (0, (0, 0, 0, 32)), (duration, (0, 0, 48, 32)),
        ))),
    ).animate(
        ScalePulse(peak=1.06, peak_at=0.42, pivot=Vec2(24, 16), rate=rate), duration=duration,
    ).animate(
        DriftOut(offset=Vec2(24, -24), pivot=Vec2(24, 16)),
        at=duration + 0.14, duration=0.56,
    )


def motion_probes(clips):
    # Exercise both ends and the interior of every emitted interpolation segment.
    return sorted({clip.start + clip.duration * fraction
                   for clip in clips for fraction in (0, 0.25, 0.5, 0.75, 1)})


@pytest.mark.parametrize("duration", (0.25, 2))
@pytest.mark.parametrize("rate", (smooth_rate, smoother_rate))
def test_curve_bounds_between_grid_points_preserve_source_and_endpoints(duration, rate):
    node = subject(duration, rate)
    scene = Scene(Document.create(width=128, height=96)).add(node)
    original = _leaves(scene, scene.evaluator())[0][0]
    lowered = _eased_rectangle_leaf(original)
    assert lowered is not original
    assert _eased_rectangle_leaf(original, max_sections=1) is original
    assert scene.objects[0] is node
    for time in motion_probes(lowered.node.animations):
        a, b = node.at(time), lowered.node.at(time)
        assert abs(a.position.x - b.position.x) <= 0.1 + 1e-9
        assert abs(a.position.y - b.position.y) <= 0.1 + 1e-9
        assert abs(a.scale.x - b.scale.x) <= 0.001 + 1e-9
        assert abs(a.opacity - b.opacity) <= 1 / 255 + 1e-9
    for time in (0, duration, duration + 0.14, duration + 0.7):
        a, b = node.at(time), lowered.node.at(time)
        assert b.position.x == pytest.approx(a.position.x)
        assert b.scale.x == pytest.approx(a.scale.x)
        assert b.opacity == pytest.approx(a.opacity)


@pytest.mark.parametrize("rate", (smooth_rate, smoother_rate))
def test_native_gradient_matches_independent_static_frames_and_reduces_output(rate):
    node = subject(rate=rate)
    doc = Document.create(width=128, height=96)
    scene = Scene(doc).add(node)
    result = scene.compile(native_tweens=True)
    sampled = scene.compile()
    assert result.objects[0].strategy == "native-clip-eased-bands"
    assert result.event_count < sampled.event_count * 0.6
    assert scene.compile(native_tweens=True, budget=SceneBudget(fps=10)).event_count == result.event_count
    assert isinstance(node.clip, RectangleClip)
    assert isinstance(node.clip.deform, RectangleKeyframes)
    for ms in (200, 710, 840, 1260, 1930, 2150, 2300, 2500, 2690):
        time = ms / 1000
        bounds = node.clip.deform.bounds_at(time)
        static = replace(node, state=node.at(time), animations=(), clip=replace(
            node.clip, deform=RectangleKeyframes(((0, bounds), (3, bounds))),
        ))
        expected = Scene(doc).add(static).compile()
        a = rasterize(result.document.dumps(), ms, (128, 96)).rgba
        b = rasterize(expected.document.dumps(), ms, (128, 96)).rgba
        # Integer band/clip edges can differ by one raster pixel. Compare their
        # premultiplied coverage/color error to the independently drawn glyph.
        mass = sum(b[3::4])
        alpha_error = sum(abs(x - y) for x, y in zip(a[3::4], b[3::4], strict=True))
        state = node.at(time)
        perimeter = 2 * (48 * min(time / 2, 1) + 32) * state.scale.x
        # One alpha level from cubic approximation plus one from ASS alpha
        # quantization applies over the whole glyph, including near-zero fades.
        edge_allowance = perimeter * 255 * state.opacity + 2 * 48 * 32 * state.scale.x ** 2
        assert alpha_error <= max(255, edge_allowance)
        color_error = sum(
            abs(a[i + c] * a[i + 3] - b[i + c] * b[i + 3]) / 255
            for i in range(0, len(a), 4) for c in range(3)
        )
        assert color_error <= max(765, edge_allowance * 3 + mass * 0.02)


@pytest.mark.parametrize("duration", (0.01, 0.255))
def test_unrepresentable_cubic_or_source_clocks_keep_original_sampling(duration):
    node = subject(duration)
    scene = Scene(Document.create(width=128, height=96)).add(node)
    leaf = _leaves(scene, scene.evaluator())[0][0]
    assert _eased_rectangle_leaf(leaf) is leaf


def test_sampled_departure_omits_held_transparent_tail():
    node = subject()
    result = Scene(Document.create(width=128, height=96)).add(node).compile()
    assert max(line.end_time for line in result.document.lines) <= 2700
    assert node.lifetime.end == 3


def test_linear_travel_does_not_hide_eased_pivot_curvature_by_endpoint_cancellation():
    motion = DriftOut(offset=Vec2(-100, -50), pivot=Vec2(1000, 500),
                      scale=0.9, travel_rate=linear_rate)
    node = replace(subject(), animations=()).animate(motion, duration=1)
    scene = Scene(Document.create(width=128, height=96)).add(node)
    original = _leaves(scene, scene.evaluator())[0][0]
    lowered = _eased_rectangle_leaf(original)
    assert lowered is not original
    for time in motion_probes(lowered.node.animations):
        a, b = node.at(time), lowered.node.at(time)
        assert abs(a.position.x - b.position.x) <= 0.1 + 1e-9
        assert abs(a.position.y - b.position.y) <= 0.1 + 1e-9
    custom = replace(node, animations=()).animate(
        replace(motion, travel_rate=lambda p: p * p), duration=1,
    )
    scene = Scene(scene.document).add(custom)
    leaf = _leaves(scene, scene.evaluator())[0][0]
    assert _eased_rectangle_leaf(leaf) is leaf
