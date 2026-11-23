from typing import assert_type

from kara_templater import Scene, ShaderMotion


def standalone_shader(scene: Scene) -> None:
    assert_type(scene.export("song.hook", fps=60, start=36, duration=8), None)

    motion = ShaderMotion(lambda base, p: base, frozenset({"opacity"}), "alpha *= item(data);", (1.0,))
    assert_type(motion, ShaderMotion)
    assert_type(scene.export_resources("preview", duration=1), None)
