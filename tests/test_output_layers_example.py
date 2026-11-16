"""The three pulse authoring modes share evaluation and preserve their pivots."""

import pytest

from examples.output_layers import build, highlights
from kara_templater import HighlightArrival, ScalePulse, Scene, Vec2, VisualState


def test_same_animation_respects_arbitrary_base_transform_and_pivot():
    base = VisualState(
        position=Vec2(10, 20), scale=Vec2(2, 3), rotation=25, skew=Vec2(0.2, 0.1)
    )
    pivot = Vec2(7, 9)
    animation = ScalePulse(pivot)
    middle = animation.sample(base, 0.5)
    assert middle.scale.x == pytest.approx(2.2)
    assert middle.scale.y == pytest.approx(3.3)
    before = base.transform.apply(pivot)
    after = middle.transform.apply(pivot)
    assert after.x == pytest.approx(before.x)
    assert after.y == pytest.approx(before.y)
    assert animation.sample(base, 0) == base
    assert animation.sample(base, 1) == base


def test_three_modes_have_distinct_bindings_in_one_scene():
    scene = build()
    assert isinstance(scene, Scene)
    assert len(scene.lines) == 3
    evaluator = scene.evaluator()
    for index, line in enumerate(scene.lines):
        if index == 2:
            target = line.query("syllable")[0]
            peak = 1.5
        else:
            target = line.query("character")[0]
            if index == 0:
                span = HighlightArrival(highlights=highlights)(line, target)[0]
                peak = (span.start + span.end) / 2
                assert peak < 1.5
            else:
                peak = 1.5
        before = evaluator.at(target.node_id, 0.5)
        middle = evaluator.at(target.node_id, peak)
        after = evaluator.at(target.node_id, 2.5)
        assert middle.scale.x == pytest.approx(before.scale.x * 1.1)
        assert after.scale == before.scale
        # Named paint copies retain the same animation as the primary character.
        for alias in target.aliases:
            assert evaluator.at(alias, peak).position == middle.position
            assert evaluator.at(alias, peak).scale == middle.scale
    result = scene.compile()
    assert all(report.strategy != "native-event" for report in result.objects)
    assert result.peak_active < 100
