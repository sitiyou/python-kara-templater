"""The visible E04 color front and particle cursor share authored coordinates."""

import pytest

from examples.scene_sakura import build
from kara_templater import (
    Document,
    ObjectGroup,
    PathObject,
    Scene,
    SoftSweep,
    TextObject,
    _metrics,
)


def test_visible_sweep_and_particle_cursor_share_time_and_span():
    scene = build()
    lyrics = next(node for node in scene.objects if node.id == "lyric")
    cursor = next(node for node in scene.objects if node.id == "cursor")
    assert isinstance(lyrics, ObjectGroup)
    assert isinstance(cursor, PathObject)
    first = lyrics.children[0]
    assert isinstance(first, TextObject)
    front = first.material
    assert isinstance(front, SoftSweep)
    assert all(
        isinstance(child, TextObject) and child.material == front
        for child in lyrics.children
    )
    for time in (1, 1.25, 1.5, 1.75, 2):
        expected = (
            front.left
            - 16
            + (front.right - front.left + 32) * (time - front.start) / front.duration
        )
        assert cursor.at(time).position.x == pytest.approx(expected)
        assert front.front_at(time) == pytest.approx(expected)
    assert front.width == 24
    assert front.outline_width == 32

    script = Scene(Document.create()).add(lyrics).compile().document.dumps()

    def colors(time_ms: int) -> set[int]:
        return {
            color >> 8
            for _, _, width, height, kind, color, _ in _metrics.rasterize(
                script, time_ms, 1280, 720, 4_000_000, 10_000
            )
            if kind == 0 and width and height
        }

    assert colors(500) == {0xFFFFFF}
    assert colors(2500) == {0xFFC0CB}
    assert len(colors(1500)) > 2
