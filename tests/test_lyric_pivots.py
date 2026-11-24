"""Semantic centers come from undecorated layout and survive material expansion."""

import pytest

from kara_templater import (
    BLUE,
    RED,
    Document,
    DriftOut,
    Glow,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    ScalePulse,
    Scene,
    StatePatch,
    Style,
    Timeline,
    Transform,
    Vec2,
    layout_document_lyrics,
)


def subject():
    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=40),))
    doc.records.append(Line(text=r"{\k100}AB|ab", start_time=1000, end_time=2000))
    layout = layout_document_lyrics(
        doc, len(doc.records) - 1, id="line", display=Lifetime(0, 3)
    )
    return doc, LyricLine.from_layout(layout)


@pytest.mark.parametrize("role", ("line", "syllable", "character", "ruby"))
def test_default_pulse_keeps_measured_center_stationary(role):
    doc, original = subject()
    bound = original.bind(LyricRule(role, "timing", ScalePulse(peak=1.3)))
    before = Scene(doc).add(original).evaluator()
    after = Scene(doc).add(bound).evaluator()
    for target in bound.query(role):
        anchor = before.at(target.node_id, 1.5).transform.apply(target.center)
        for time in (1.5, 1.2, 1.8, 1):
            point = after.at(target.node_id, time).transform.apply(target.center)
            assert (point.x, point.y) == pytest.approx((anchor.x, anchor.y))
    # The character center independently matches half its measured local box.
    for target, measured in zip(
        original.query("character"), original.layout.body.characters, strict=True
    ):
        assert measured.layout_scale is not None
        assert target.center == Vec2(
            measured.bounds.width / measured.layout_scale.x / 2,
            measured.bounds.height / measured.layout_scale.y / 2,
        )


def test_sweep_and_glow_share_center_through_delayed_copy_and_sequence():
    doc, original = subject()
    painted = LyricHighlights.from_timing(
        StatePatch(fill=RED), glow=Glow(BLUE, blur=12, border=8, opacity=0.3)
    )(original).copy(id="copy", offset=Vec2(20, 30), delay=0.2)
    animation = Timeline().play(Transform(scale=lambda p: 1 + 0.2 * p), duration=1).animation
    bound = painted.bind(LyricRule("character", "timing", animation))
    before = Scene(doc).add(painted).evaluator()
    after = Scene(doc).add(bound).evaluator()
    for target in bound.query("character"):
        assert target.aliases
        expected = before.at(target.node_id, 1.7).transform.apply(target.center)
        for identity in (target.node_id, *target.aliases):
            state = after.at(identity, 1.7)
            point = state.transform.apply(target.center)
            assert (point.x, point.y) == pytest.approx((expected.x, expected.y))
            assert state.scale.x == pytest.approx(1.1)
    # Reusable declarations remain unresolved and caller-owned.
    assert isinstance(animation.clips[0].animation, Transform)
    assert animation.clips[0].animation.pivot is None


@pytest.mark.parametrize("animation", (
    ScalePulse(pivot=Vec2()), Transform(scale=1.2, pivot=Vec2()),
    DriftOut(pivot=Vec2()),
))
def test_explicit_origin_is_not_replaced_by_center(animation):
    _, line = subject()
    bindings = line._resolve((LyricRule("character", "timing", animation),))
    assert all(binding.animation is animation for binding in bindings)


def test_drift_default_center_translates_by_authored_offset_only():
    doc, original = subject()
    bound = original.bind(LyricRule(
        "character", "after_timing", DriftOut(offset=Vec2(12, -20)), duration=0.5,
    ))
    before = Scene(doc).add(original).evaluator()
    after = Scene(doc).add(bound).evaluator()
    for target in bound.query("character"):
        anchor = before.at(target.node_id, 2.25).transform.apply(target.center)
        point = after.at(target.node_id, 2.25).transform.apply(target.center)
        assert (point.x, point.y) == pytest.approx((anchor.x + 6, anchor.y - 10))
