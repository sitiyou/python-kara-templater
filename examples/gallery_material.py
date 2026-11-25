"""Apply an animated WGSL ribbon to the fill of a text object."""

import argparse
from pathlib import Path

from kara_templater import (
    Color,
    Document,
    Lifetime,
    MaterialClip,
    MaterialEffect,
    PaintInput,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)


class Ribbon(MaterialEffect):
    wgsl = """
fn shade(
    material: vec4<f32>, context: KaraPaintContext,
    tint: vec3<f32>, strength: f32,
) -> vec4<f32> {
    let wave = sin(context.local.x * 0.035 + context.local.y * 0.06 - context.time * 4.0);
    let ribbon = smoothstep(0.25, 0.96, wave);
    return vec4<f32>(mix(material.rgb, tint, ribbon * strength), material.a);
}
"""

    def parameters(self) -> tuple[PaintInput, PaintInput]:
        return (
            PaintInput("ribbon_color", Color.hex("#6CDBFF")),
            PaintInput("ribbon_strength", 0.9),
        )


def build() -> Scene:
    scene = Scene(Document.create(width=720, height=405))
    return scene.add(
        TextObject(
            id="lettering",
            text="揺らめく旋律",
            font="Noto Sans CJK JP",
            font_size=72,
            alignment=5,
            lifetime=Lifetime(0, 3.5),
            state=VisualState(position=Vec2(360, 202), fill=Color.hex("#8B72E8")),
            material_effects=(MaterialClip(effect=Ribbon()),),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build().export(parser.parse_args().output, fps=30)


if __name__ == "__main__":
    main()
