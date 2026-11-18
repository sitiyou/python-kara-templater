from typing import assert_type

from kara_templater import Document, Scene, render_enhanced


def export(scene: Scene, fallback: Document) -> Document:
    return assert_type(scene.enhance(fallback, fps=60), Document)


def video(document: Document) -> None:
    assert_type(
        render_enhanced(document, "input.mp4", "output.mp4", start=1, duration=2), None
    )


def standalone_shader(scene: Scene) -> None:
    assert_type(scene.export_hook("song.hook", fps=60, start=36, duration=8), None)
