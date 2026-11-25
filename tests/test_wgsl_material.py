"""The material function is shared by standalone Hook and preview resources."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from kara_templater import (
    Color,
    Document,
    KaraokeEffects,
    Lifetime,
    Line,
    MaterialClip,
    MaterialEffect,
    PaintInput,
    PathObject,
    Scene,
    SceneCompileError,
    Style,
    TextObject,
    Track,
    VectorPath,
    build_lyric_scene,
    text_to_path,
)


@dataclass(frozen=True)
class Tint(MaterialEffect):
    amount: float
    color: Color

    wgsl = """
fn helper(x: f32) -> f32 { return x; }
fn shade(m: vec4<f32>, c: KaraPaintContext, amount: f32, tint: vec3<f32>) -> vec4<f32> {
    return vec4<f32>(mix(m.rgb, tint, helper(amount)), m.a);
}
"""

    def parameters(self) -> tuple[float, PaintInput]:
        return (self.amount, PaintInput("ink", self.color))


class Dim(MaterialEffect):
    wgsl = """
fn helper(t: f32) -> f32 { return 0.5 + t; }
fn shade(m: vec4<f32>, c: KaraPaintContext) -> vec4<f32> {
    return vec4<f32>(m.rgb * helper(c.progress), m.a);
}
"""


def _scene(color: Color) -> Scene:
    scene = Scene(Document.create(width=32, height=32))
    for i, amount in enumerate((0.25, 0.9)):
        scene.add(PathObject(
            id=f"shape-{i}", lifetime=Lifetime(0, 2), layer=i, path=VectorPath.rectangle(18, 18),
            material_effects=(MaterialClip(effect=Tint(amount, color)),
                              MaterialClip(effect=Dim(), start=0.25, duration=1)),
        ))
    return scene


def test_effects_share_program_and_keep_live_parameters_out_of_scene_data(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    red, green = _scene(Color(255, 0, 0)), _scene(Color(0, 255, 0))
    red.export_resources(first, fps=4)
    green.export_resources(second, fps=4)
    shader = (first / "scene.frag").read_text()
    assert shader.count("vec4 kara_effect_") == 4  # two effect functions and their adapters
    assert (second / "scene.frag").read_text() == shader
    assert (first / "KARADATA.bin").read_bytes() == (second / "KARADATA.bin").read_bytes()
    assert (first / "KARAMASK.bin").read_bytes() == (second / "KARAMASK.bin").read_bytes()
    manifest = json.loads((first / "textures.json").read_text())
    slot = manifest["parameters"]["ink"]
    assert slot["default"] == [1, 0, 0]
    assert len(slot["uniforms"]) == 3
    output = tmp_path / "scene.hook"
    red.export(output, fps=4)
    assert all(f"//!PARAM {name}\n" in output.read_text() for name in slot["uniforms"])


def test_scanline_strength_and_color_keep_the_prepared_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    def export(name: str, strength: float, color: Color) -> Path:
        doc = Document.create(width=640, height=360, styles=(Style(fontsize=40),))
        doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k50}AB|ab{\k50}C"))
        effect = KaraokeEffects(
            entry="none", exit="none", highlight="scanline", hook_feather=4,
            scanline_color=PaintInput("shine", color),
            scanline_strength=PaintInput("strength", strength),
        )
        scene = build_lyric_scene(doc, tracks=(Track(id="main", effects=(effect,)),))
        parts = tmp_path / name
        scene.export_resources(parts, fps=30)
        scene.export(tmp_path / f"{name}.hook", fps=30)
        return parts

    full = export("full", 1, Color(255, 0, 0))
    dim = export("dim", 0.35, Color(0, 255, 0))
    for filename in ("KARAMASK.bin", "KARADATA.bin", "scene.frag"):
        assert (full / filename).read_bytes() == (dim / filename).read_bytes()
    slots = json.loads((dim / "textures.json").read_text())["parameters"]
    assert {name: slot["default"] for name, slot in slots.items()} == {
        "shine": [0, 1, 0], "strength": [0.35],
    }


def test_material_is_preserved_by_copy_and_conversion_and_rejected_by_ass() -> None:
    node = TextObject(id="text", text="Q", lifetime=Lifetime(0, 2),
                      material_effects=(MaterialClip(effect=Dim()),))
    path = text_to_path(node.copy(id="copy", delay=1), path=VectorPath.rectangle(18, 18))
    assert path.material_effects == node.material_effects
    with pytest.raises(SceneCompileError, match="ASS does not support shader paint"):
        Scene(Document.create(width=32, height=32)).add(path).ass.compile()


def test_invalid_wgsl_reports_owner_and_leaves_previous_hook(tmp_path: Path) -> None:
    class MissingReturn(MaterialEffect):
        wgsl = "fn shade(m: vec4<f32>, c: KaraPaintContext) -> vec4<f32> { return missing; }"

    scene = Scene(Document.create(width=32, height=32)).add(PathObject(
        id="named-shape", lifetime=Lifetime(0, 2), path=VectorPath.rectangle(18, 18),
        material_effects=(MaterialClip(effect=MissingReturn()),),
    ))
    destination = tmp_path / "previous.hook"
    destination.write_text("previous")
    with pytest.raises(SceneCompileError, match="MissingReturn.*", check=lambda error: error.object_id == "named-shape"):
        scene.export(destination, fps=4)
    assert destination.read_text() == "previous"


def test_unused_material_is_excluded_from_a_disjoint_export_window(tmp_path: Path) -> None:
    class Invalid(MaterialEffect):
        wgsl = "this is invalid"

    scene = Scene(Document.create(width=32, height=32)).add(PathObject(
        id="timed-shape", lifetime=Lifetime(0, 3), path=VectorPath.rectangle(18, 18),
        material_effects=(
            MaterialClip(effect=Invalid(), start=0.5, duration=0.5),
            MaterialClip(effect=Tint(0.5, Color(255, 0, 0)), start=1.5, duration=0.5),
        ),
    ))
    assert scene.prepare_hook().material_inputs() == {"ink": Color(255, 0, 0)}
    before = tmp_path / "before"
    scene.export_resources(before, fps=4, duration=0.5)
    assert "parameters" not in json.loads((before / "textures.json").read_text())
    assert "applyMaterials" not in (before / "scene.frag").read_text()

    during = tmp_path / "during"
    scene.export_resources(during, fps=4, start=1.75, duration=0.5)
    assert "ink" in json.loads((during / "textures.json").read_text())["parameters"]
    with pytest.raises(SceneCompileError, match="Invalid.*"):
        scene.export(tmp_path / "invalid.hook", fps=4, start=0.5, duration=0.5)
