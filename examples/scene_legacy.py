"""Historical Python templates and new scene objects share one ASS compiler.

uv run python -m examples.scene_legacy output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    AnimationClip,
    Document,
    Engine,
    Lifetime,
    Line,
    Scene,
    StatePatch,
    Style,
    TextObject,
    Tween,
    Vec2,
    VisualState,
)


def build() -> Scene:
    document = Document.create(
        styles=(
            Style(
                fontname="DejaVu Sans",
                fontsize=96,
                align=5,
                outline=2,
                shadow=0,
            ),
        )
    )
    document.records.extend(
        (
            Line(
                comment=True,
                effect="code once",
                text='palette = ("&HFFFF33&", "&HCC88FF&")',
            ),
            Line(
                comment=True,
                effect="template pre-line",
                text=r"{\an5\pos($lcenter,$lmiddle)\1c&HBBBBBB&}",
            ),
            Line(
                comment=True,
                effect="template syl noblank",
                text=r"!retime('syl', 0, 150)!{\an5\pos($scenter,$smiddle)\1c!palette[(syl.i-1)%2]!\t(0,150,\fscx110\fscy110)}",
            ),
            Line(
                comment=True,
                effect="template furi noblank",
                text=r"{\an5\pos($scenter,$smiddle)\1c&HFFFFFF&}",
            ),
            Line(
                text=r"{\k75}Ka|ka{\k75}ra|ra{\k75}o|o{\k75}ke|ke",
                start_time=1000,
                end_time=4000,
            ),
        )
    )
    scene = Engine().to_scene(document)
    scene.add(
        TextObject(
            id="caption",
            text="PYTHON TEMPLATES + SCENE",
            font_size=32,
            alignment=5,
            lifetime=Lifetime(0, 5),
            state=VisualState(position=Vec2(640, 500), fill=CYAN, opacity=0),
            animations=(
                AnimationClip(0, 0.5, Tween(StatePatch(opacity=1))),
                AnimationClip(4.5, 0.5, Tween(StatePatch(opacity=0))),
            ),
        )
    )
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().compile()
    result.document.save(parser.parse_args().output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
