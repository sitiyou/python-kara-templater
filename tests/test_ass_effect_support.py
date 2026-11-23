"""ASS export accepts native effects and rejects expensive approximations in preflight."""

import pytest

from examples.lyric_particles import build
from kara_templater import (
    RED,
    AnimationClip,
    ColorRamp,
    ColorStop,
    Coverage,
    Document,
    Lifetime,
    LinearGradient,
    ObjectGroup,
    Scene,
    SceneBudget,
    SceneCompileError,
    StateFunction,
    TextObject,
)


def test_particle_support_depends_on_motion_and_is_independent_of_fps(tmp_path):
    sparkle = build("sparkle")
    assert sparkle.ass.compile(budget=SceneBudget(fps=1)).document.dumps() == sparkle.ass.compile(
        budget=SceneBudget(fps=100)
    ).document.dumps()

    petal = build("petal")
    original = petal.document.dumps()
    with pytest.raises(SceneCompileError, match="frame sampling") as error:
        petal.ass.compile(budget=SceneBudget(fps=1))
    assert error.value.object_id and error.value.origin
    hook = tmp_path / "petal.hook"
    petal.export(hook, fps=24)
    assert "//!HOOK MAIN" in hook.read_text()
    assert petal.document.dumps() == original


def test_ass_rejects_callbacks_before_sampling_or_estimate():
    def unexpected(*_args):
        pytest.fail("unsupported animation executed")

    scene = Scene(Document.create()).add(TextObject(
        id="animated", text="A", lifetime=Lifetime(0, 1),
        animations=(AnimationClip(0, 1, StateFunction(unexpected)),),
    ))
    with pytest.raises(SceneCompileError, match="frame sampling") as error:
        scene.ass.compile(on_estimate=unexpected)
    assert error.value.object_id == "animated"


def test_gradient_requires_hook_even_for_one_glyph(tmp_path):
    scene = Scene(Document.create()).add(TextObject(
        id="gradient", text="A", lifetime=Lifetime(0, 1),
        material=LinearGradient(fill=ColorRamp((ColorStop(0, RED), ColorStop(32, RED)))),
    ))
    with pytest.raises(SceneCompileError, match="LinearGradient") as error:
        scene.ass.compile()
    assert error.value.object_id == "gradient"
    scene.export(tmp_path / "gradient.hook", fps=24)


def test_ass_rejects_even_static_coverage_groups():
    scene = Scene(Document.create()).add(ObjectGroup(
        id="composite", lifetime=Lifetime(0, 1), coverage=Coverage(),
        children=(TextObject(id="glyph", text="A", lifetime=Lifetime(0, 1)),),
    ))
    with pytest.raises(SceneCompileError, match="coverage groups") as error:
        scene.ass.compile()
    assert error.value.object_id == "composite"
