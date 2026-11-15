"""A cue can track a lyric anchor without changing layout or singing time."""

from math import cos, pi, sin

import pytest

from examples.scene_cue_follow import build
from kara_templater import ObjectGroup, TextObject, Vec2, _metrics


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


def test_export_cue_is_visible_only_before_selected_syllable():
    scene = build()
    result = scene.compile()
    script = result.document.dumps()
    for ms in (1499, 1500, 1829, 1830, 2169, 2170, 2499, 2500):
        colored = [
            data
            for _, _, width, height, kind, color, data in _metrics.rasterize(
                script, ms, 1280, 720, 4_000_000, 10_000
            )
            if width and height and kind == 0 and color >> 8 == 0x00FFFF
        ]
        assert bool(colored) == (1500 <= ms < 2500)
    assert any(line.comment and r"\k150" in line.text for line in result.document.lines)
    assert all(
        "kara:v1" not in line.text for line in result.document.lines if not line.comment
    )
