from typing import assert_type

from kara_templater import Scene


def standalone_shader(scene: Scene) -> None:
    assert_type(scene.export_hook("song.hook", fps=60, start=36, duration=8), None)
