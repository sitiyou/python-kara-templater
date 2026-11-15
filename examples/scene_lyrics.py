"""E01: Document ruby, separate color fronts, layered glow and shared singing pulse.

uv run python -m examples.scene_lyrics output.ass
"""

import argparse
from dataclasses import replace
from math import pi, sin
from pathlib import Path

from kara_templater import (
    PINK,
    WHITE,
    AnimationClip,
    Document,
    Lifetime,
    Line,
    ObjectGroup,
    Scene,
    SoftSweep,
    StateFunction,
    Style,
    TextObject,
    Vec2,
    VisualState,
    layout_document_lyrics,
    load_font,
)


def pulse(state: VisualState, progress: float) -> VisualState:
    scale = 1 + 0.08 * sin(pi * progress) ** 2
    return replace(state, scale=Vec2(scale, scale))


def glow(
    source: ObjectGroup, *, id: str, border: float, blur: float, opacity: float
) -> ObjectGroup:
    copied = source.copy(id=id)
    return replace(
        copied,
        layer=-1,
        children=tuple(
            replace(
                child,
                material=None,
                state=replace(
                    child.state,
                    fill=PINK,
                    outline=PINK,
                    border=border,
                    blur=blur,
                    opacity=opacity,
                ),
            )
            for child in copied.children
        ),
    )


def build() -> Scene:
    load_font(Path(__file__).resolve().parents[1] / "tests/fonts/KaraTestCJK.ttf")
    document = Document.create(
        styles=(
            Style(fontname="Kara Test CJK", fontsize=120, outline=2, shadow=0),
            Style(
                name="Default-furigana",
                fontname="DejaVu Sans",
                fontsize=40,
                outline=1,
                shadow=0,
            ),
        )
    )
    document.records.append(
        Line(
            text=r"{\k120}時|!toki{\kt180\k120}々|!doki",
            start_time=1000,
            end_time=4000,
        )
    )
    index = len(document.records) - 1
    layout = layout_document_lyrics(document, index, display=Lifetime(0, 5), ruby_gap=8)
    offset = Vec2(640 - layout.body.bounds.center, 340)
    scene = Scene(document)
    scene.replace_source(index)
    groups: list[ObjectGroup] = []
    for ui, unit in enumerate(layout.lyrics.units):
        segment = unit.segments[0]
        body_box = layout.body.range_bounds(unit.start, unit.end)
        ruby_box = next(r.layout.bounds for r in layout.ruby if r.unit_index == ui)
        group = layout.unit_group(ui)
        children: list[TextObject] = []
        for child in group.children:
            assert isinstance(child, TextObject) and child.origin is not None
            box = ruby_box if child.origin.effect == "document ruby" else body_box
            children.append(
                replace(
                    child,
                    material=SoftSweep(
                        left=offset.x + box.left,
                        right=offset.x + box.right,
                        start=segment.singing.start,
                        duration=segment.singing.end - segment.singing.start,
                        fill=(WHITE, PINK),
                        outline=(PINK, WHITE),
                        width=24,
                        outline_width=16,
                    ),
                )
            )
        group = replace(
            group,
            children=tuple(children),
            animations=(
                AnimationClip(
                    segment.singing.start,
                    segment.singing.end - segment.singing.start,
                    StateFunction(pulse, frozenset(("scale",))),
                ),
            ),
        )
        groups.extend(
            (
                glow(group, id=f"wide:{ui}", border=5, blur=10, opacity=0.35),
                glow(group, id=f"near:{ui}", border=3, blur=3, opacity=0.6),
                group,
            )
        )
    return scene.add(
        ObjectGroup(
            id="lyrics",
            lifetime=layout.body.lifetime,
            state=VisualState(position=offset),
            children=tuple(groups),
        )
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
