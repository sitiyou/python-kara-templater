"""E05: local glyph fragments assemble from seeded offsets, then hold uncut ink.

uv run python -m examples.scene_fragments output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    AnimationClip,
    Document,
    Lifetime,
    ParticleContext,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    path_bounds,
    smooth_rate,
    split_path,
    text_to_path,
)


def build() -> Scene:
    word = text_to_path(
        TextObject(
            id="word",
            text="KARA",
            font_size=150,
            lifetime=Lifetime(0, 5),
            state=VisualState(fill=CYAN),
        )
    )
    box = path_bounds(word.path)
    word = replace(
        word,
        state=replace(word.state, position=Vec2(640 - box.center, 360 - box.middle)),
    )
    pieces = split_path(word, columns=4, rows=3, tolerance=0.15)
    scene = Scene(Document.create())
    assembled = 1.6
    for index, piece in enumerate(pieces):
        birth = index * 0.025
        random = ParticleContext(piece.id, birth, 37, Vec2(), piece.origin)
        offset = Vec2(random.uniform("x", -240, 240), random.uniform("y", -180, 180))
        scene.add(
            replace(
                piece,
                lifetime=Lifetime(birth, assembled),
                state=replace(
                    piece.state, position=piece.state.position + offset, opacity=0
                ),
                animations=(
                    AnimationClip(
                        0,
                        assembled - birth,
                        Tween(StatePatch(position=word.state.position), smooth_rate),
                    ),
                    AnimationClip(0, 0.2, Tween(StatePatch(opacity=1))),
                ),
            )
        )
    # Rejoin into the original cubic outline, avoiding permanent anti-alias seams.
    scene.add(replace(word, lifetime=Lifetime(assembled, 5)))
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
