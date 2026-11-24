"""Stationary ornament and text have independent, opposing exit schedules."""

import pytest

from examples.lyric_ornament import build


def test_ornament_stays_fixed_and_outlives_the_opposite_text_exit():
    scene = build()
    line = scene.lines[0]
    targets = line.query("character")
    evaluator = scene.evaluator()
    assert evaluator.at(targets[0].node_id, 3.1).opacity < evaluator.at(targets[-1].node_id, 3.1).opacity
    assert all(evaluator.at(target.node_id, 3.7).opacity == 0 for target in targets)
    left, right = f"{line.id}/arch:0", f"{line.id}/arch:8"
    assert evaluator.at(left, 3.7).opacity == 1
    assert evaluator.at(right, 3.7).opacity == 0
    assert evaluator.at(left, 1).position == evaluator.at(left, 3.9).position
    assert evaluator.at(right, 1).position == evaluator.at(right, 3.4).position
    assert scene.plans[0].layout_request.required_display.end == pytest.approx(4.16)
    result = scene.ass.compile(native_tweens=True)
    assert result.event_count < 100
