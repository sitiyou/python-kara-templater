"""E06/E12: measured word backgrounds, inline bars and custom count-in objects.

uv run python -m examples.scene_cues output.ass
All content is fixed here; the library consumes source annotations and emits ASS.
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    AnimationClip,
    BarsCue,
    Color,
    Contour,
    CubicSegment,
    CueContent,
    CueContext,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    ObjectGroup,
    PathObject,
    Record,
    Scene,
    StatePatch,
    Style,
    TextCue,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    bind_cues,
    layout_document_text,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def sparkle(context: CueContext) -> CueContent:
    """Custom content uses exactly the same scene objects as a built-in cue."""
    star = VectorPath.polygon(
        Vec2(0, -20),
        Vec2(6, -6),
        Vec2(20, 0),
        Vec2(6, 6),
        Vec2(0, 20),
        Vec2(-6, 6),
        Vec2(-20, 0),
        Vec2(-6, -6),
    )
    return CueContent(
        (
            PathObject(
                id=context.id + "/sparkle",
                path=star,
                lifetime=context.lifetime,
                state=VisualState(
                    position=Vec2(20, 20), fill=PINK, border=1, outline=WHITE
                ),
                animations=(
                    AnimationClip(
                        0,
                        context.lifetime.end - context.lifetime.start,
                        Tween(StatePatch(rotation=180, opacity=0)),
                    ),
                ),
            ),
        ),
        40,
        40,
    )


def build() -> Scene:
    markers = (
        CueMarker("bars", "bars"),
        CueMarker("numbers", "numbers", placement="independent"),
        CueMarker("sparkle", "sparkle", placement="independent"),
    )
    document = Document(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "YCbCr Matrix: None",
            "PlayResX: 1280",
            "PlayResY: 720",
            "ScaledBorderAndShadow: yes",
            "WrapStyle: 2",
            "[V4+ Styles]",
            "Format: " + STYLE_FORMAT,
            Style(fontname="DejaVu Sans", fontsize=64, outline=1, shadow=0),
            "[Events]",
            "Format: " + EVENT_FORMAT,
            Line(
                text="".join(marker.markup() for marker in markers)
                + r"{\k150\1c&HFFFF00&}Hello {\k150\1c&HBB88FF&}World",
                start_time=1000,
                end_time=5000,
            ),
        ],
        Record(res_x=1280, res_y=720),
    )
    layout = layout_document_text(
        document, len(document.records) - 1, id="lyric", display=Lifetime(0, 5)
    )
    bound = bind_cues(
        layout,
        {
            "bars": CuePreset(factory=BarsCue(color=CYAN)),
            "numbers": CuePreset(
                factory=TextCue(color=PINK, font_size=72), position=Vec2(620, 160)
            ),
            "sparkle": CuePreset(factory=sparkle, position=Vec2(620, 450)),
        },
    )
    backgrounds = tuple(
        bound.text.background(
            start, end, id=f"word:{start}", color=Color(36, 45, 70), padding=Vec2(6, 8)
        )
        for start, end in ((0, 5), (6, 11))
    )
    box = bound.text.range_bounds(0, 11)
    ribbon = VectorPath(
        (
            Contour(
                Vec2(),
                (
                    CubicSegment(
                        Vec2(box.width * 0.3, 20),
                        Vec2(box.width * 0.7, -20),
                        Vec2(box.width, 0),
                    ),
                    CubicSegment(
                        Vec2(box.width * 0.7, -17),
                        Vec2(box.width * 0.3, 23),
                        Vec2(0, 3),
                    ),
                ),
            ),
        )
    )
    decoration = PathObject(
        id="underline",
        lifetime=layout.lifetime,
        path=ribbon,
        state=VisualState(position=Vec2(box.left, box.height + 20), fill=PINK),
    )
    lyric = bound.group()
    combined = ObjectGroup(
        id="caption",
        lifetime=lyric.lifetime,
        state=VisualState(position=Vec2((1280 - box.right) / 2, 310)),
        children=(*backgrounds, decoration, lyric),
    )
    scene = Scene(document).add(combined, *bound.independent)
    assert layout.record_index is not None
    scene.replace_source(layout.record_index)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().compile()
    output = parser.parse_args().output
    result.document.save(output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
