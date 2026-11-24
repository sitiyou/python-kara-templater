"""The concise author recipe keeps short/held-note clocks and layer ownership."""

import pytest

from examples.lyric_pulse_drift import build
from kara_templater import smooth_rate


@pytest.mark.parametrize("custom", (False, True))
def test_short_and_held_notes_use_source_duration_then_independent_exit(custom):
    scene = build(custom=custom)
    line = scene.plans[0].line
    targets = line.query("character")
    evaluator = scene.evaluator()
    assert len(targets) == 4
    windows = ((1, 1.25), (1.25, 1.5), (1.5, 2.5), (2.5, 4.5))
    for target, (start, end) in zip(targets, windows, strict=True):
        assert [(span.start, span.end) for span in target.timing] == [(start, end)]
        before = evaluator.at(target.node_id, start)
        center = before.transform.apply(target.center)
        peak = evaluator.at(target.node_id, start + (end - start) * 0.42)
        actual = peak.transform.apply(target.center)
        assert (actual.x, actual.y) == pytest.approx((center.x, center.y))
        amount = 0.06 * smooth_rate(min(1, (end - start) / 0.6)) if custom else 0.06
        assert peak.scale.x == pytest.approx(before.scale.x * (1 + amount))
        assert evaluator.at(target.node_id, end).scale == before.scale
        assert evaluator.at(target.node_id, end + 0.14).opacity == before.opacity
        midway = evaluator.at(target.node_id, end + 0.42)
        assert midway.opacity == pytest.approx(before.opacity * 0.5)
        moved = midway.transform.apply(target.center)
        assert moved.x == pytest.approx(center.x + 12)
        assert moved.y == pytest.approx(center.y - (9 if custom else 18))
        assert target.aliases
        for alias in target.aliases:
            painted = evaluator.at(alias, end + 0.42)
            assert painted.transform == midway.transform
            assert painted.opacity == midway.opacity
    assert line.lifetime.end == pytest.approx(5.2)
