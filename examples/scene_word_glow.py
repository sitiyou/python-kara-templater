"""Merge overlapping glyph silhouettes before applying a shared outline and glow.

uv run python -m examples.scene_word_glow output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    PINK,
    WHITE,
    Document,
    Lifetime,
    ObjectGroup,
    Scene,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VisualState,
    merge_geometry,
    smooth_rate,
)


def build() -> Scene:
    lifetime = Lifetime(0, 5.5)
    motion = (
        Timeline()
        .wait(0.5)
        .play(
            Tween(StatePatch(rotation=6, scale=Vec2(1.15, 1.15)), smooth_rate),
            duration=2,
        )
        .play(Tween(StatePatch(rotation=-6, scale=Vec2(1, 1)), smooth_rate), duration=2)
    )
    letters = tuple(
        TextObject(
            id=f"letter:{index}",
            text=letter,
            lifetime=lifetime,
            font_size=150,
            alignment=5,
            state=VisualState(position=Vec2((index - 1.5) * 85, 0)),
        )
        for index, letter in enumerate("WAVE")
    )
    word = ObjectGroup(
        id="word",
        lifetime=lifetime,
        children=letters,
        state=VisualState(position=Vec2(640, 330)),
        animations=motion.clips,
    )
    silhouette = merge_geometry(word)
    glow = replace(
        silhouette,
        id="glow",
        layer=0,
        state=replace(silhouette.state, fill=PINK, outline=PINK, border=12, blur=16),
    )
    foreground = replace(
        silhouette,
        id="foreground",
        layer=1,
        state=replace(silhouette.state, fill=WHITE, outline=PINK, border=3),
    )
    caption = TextObject(
        id="caption",
        text="ONE SILHOUETTE • SHARED OUTLINE AND GLOW",
        lifetime=lifetime,
        font_size=28,
        alignment=5,
        state=VisualState(position=Vec2(640, 550)),
    )
    return Scene(Document.create()).add(glow, foreground, caption)


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
