"""A cue can track a lyric anchor without changing layout or singing time."""

from math import cos, pi, sin

import pytest

from examples.scene_cue_follow import build
from kara_templater import ObjectGroup, TextObject, Vec2


def test_second_syllable_cue_tracks_world_anchor_but_stays_upright():
    scene = build()
    lyric, cue = scene.objects
    assert isinstance(lyric, ObjectGroup)
    assert isinstance(cue, ObjectGroup)
    assert (cue.lifetime.start, cue.lifetime.end) == (1.5, 2.5)
    assert [child.text for child in cue.children if isinstance(child, TextObject)] == [
        "READY",
        "SET",
        "GO",
    ]
    anchor = next(child for child in lyric.children if child.id == "count-anchor")
    evaluator = scene.evaluator()
    for time in (2.49, 1.5, 2, 1.5):
        progress = time / 2.5
        theta = 12 * progress * pi / 180
        point = anchor.state.position
        expected = Vec2(
            300 + 220 * progress + point.x * cos(theta) - point.y * sin(theta),
            300 - 40 * progress + point.x * sin(theta) + point.y * cos(theta),
        )
        actual = evaluator.at(cue.id, time)
        assert actual.position.x == pytest.approx(expected.x)
        assert actual.position.y == pytest.approx(expected.y)
        assert actual.rotation == 0
        assert actual.scale == Vec2(1, 1)
        # The invisible anchor's alpha must not make the following cue invisible.
        assert actual.opacity == 1
    assert len(lyric.children) == len("FOLLOW ME") + 1
