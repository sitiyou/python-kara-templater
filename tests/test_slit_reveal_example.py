"""The documented reveal clips the lyrics without drawing a frame around them."""

import pytest

from examples.slit_reveal import FPS, UNSUNG, build
from kara_templater import LyricLine, PathObject, RectangleClip, TextObject


def test_default_reveal_has_invisible_clips_and_hands_off_to_the_singing_line():
    scene = build()
    assert not any(isinstance(node, PathObject) for node in scene.objects)
    line = next(node for node in scene.objects if isinstance(node, LyricLine))
    entries = [node for node in scene.objects if isinstance(node, TextObject)]
    assert [node.text for node in entries] == list(reversed("春が来た"))
    poses = scene.evaluator()
    cells = {
        f"{cell.object.id}/entrance": cell.object.id
        for cell in line.layout.body.characters
    }
    for index, node in enumerate(entries):
        assert isinstance(node.clip, RectangleClip) and node.clip.space == "screen"
        assert node.lifetime.start == pytest.approx((10 + index) / FPS)
        assert node.lifetime.end == line.lifetime.start
        assert node.state.fill == UNSUNG
        resting = poses.at(node.id, line.lifetime.start - 1 / FPS)
        assert (
            resting.position == poses.at(cells[node.id], line.lifetime.start).position
        )
