"""E03: circular lyric layout, grouped annotations and repeated highlights.

uv run python -m examples.scene_round output.ass
Install the bundled KaraTestCJK.ttf for playback (tests/fonts/LICENSE-Sarasa).
"""

import argparse
from math import cos, radians, sin
from pathlib import Path

from kara_templater import (
    PINK,
    WHITE,
    AnimationClip,
    Document,
    EventOrigin,
    Lifetime,
    ObjectGroup,
    PathItem,
    Polyline,
    Scene,
    SourceRef,
    StatePatch,
    Style,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    layout_path,
    load_font,
    text_extents,
)


def build() -> Scene:
    family = load_font(
        Path(__file__).resolve().parents[1] / "tests/fonts/KaraTestCJK.ttf"
    ).family
    style = Style(fontname=family, fontsize=64)
    lifetime = Lifetime(0, 5)
    items: list[PathItem] = []
    for index, character in enumerate("時々時々時々"):
        origin = EventOrigin((SourceRef("round", index),), "circular lyric")
        starts = (1 + index * 0.25, 3 + index * 0.15)
        colors = tuple(
            AnimationClip(time, 0.25, Tween(StatePatch(fill=PINK)), hold=False)
            for time in starts
        )
        body = TextObject(
            id=f"base:{index}",
            text=character,
            font=family,
            font_size=64,
            alignment=5,
            lifetime=lifetime,
            state=VisualState(fill=WHITE),
            animations=colors,
            origin=origin,
        )
        ruby = TextObject(
            id=f"ruby:{index}",
            text="toki" if character == "時" else "doki",
            font_size=20,
            alignment=5,
            lifetime=lifetime,
            state=VisualState(position=Vec2(0, -52), fill=WHITE),
            animations=colors,
            origin=origin,
        )
        syllable = ObjectGroup(
            id=f"syllable:{index}",
            lifetime=lifetime,
            children=(body, ruby),
            origin=origin,
            animations=tuple(
                AnimationClip(
                    time, 0.25, Tween(StatePatch(scale=Vec2(1.12, 1.12))), hold=False
                )
                for time in starts
            ),
        )
        items.append(PathItem(syllable, advance=text_extents(style, character)[0] + 16))
    arc = Polyline(
        tuple(
            Vec2(240 * cos(radians(-160 + index)), 240 * sin(radians(-160 + index)))
            for index in range(141)
        )
    )
    return Scene(Document.create()).add(
        layout_path(items, arc, id="arc", position=Vec2(640, 470))
    )


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
