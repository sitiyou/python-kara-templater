"""A second-syllable count-in follows a rotating lyric anchor, staying upright.

uv run python -m examples.scene_cue_follow output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    CueMarker,
    CuePreset,
    Document,
    FollowObject,
    Lifetime,
    Line,
    PathObject,
    Scene,
    StateKeyframe,
    StatePatch,
    Style,
    TextCue,
    Timeline,
    Vec2,
    VectorPath,
    VisualState,
    bind_cues,
    layout_document_text,
)


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    document.records.append(
        Line(
            text=CueMarker("second", "count", placement="independent").markup()
            + r"{\k150}FOLLOW {\k150}ME",
            start_time=1000,
            end_time=4000,
        )
    )
    record = len(document.records) - 1
    layout = layout_document_text(document, record, id="lyric", display=Lifetime(0, 5))
    second = layout.singing[1]
    bound = bind_cues(
        layout,
        {
            "count": CuePreset(
                factory=TextCue(
                    labels=("READY", "SET", "GO"), font_size=28, color=CYAN
                ),
                trigger=second.start,
            ),
        },
    )
    # An ordinary invisible child supplies a world anchor under the chosen unit.
    box = layout.range_bounds(second.start_offset, second.end_offset)
    cue_width = bound.cues[0].content.width
    anchor = PathObject(
        id="count-anchor",
        lifetime=layout.lifetime,
        path=VectorPath.circle(1),
        state=VisualState(
            position=Vec2(
                box.left + (box.width - cue_width) / 2, box.top + box.height + 24
            ),
            opacity=0,
        ),
    )
    lyric = bound.group(position=Vec2(300, 300))
    motion = Timeline().keyframes(
        StateKeyframe(2.5, StatePatch(position=Vec2(520, 260), rotation=12)),
        StateKeyframe(5, StatePatch(position=Vec2(300, 300), rotation=0)),
    )
    lyric = replace(lyric, children=(*lyric.children, anchor), animations=motion.clips)
    count = replace(bound.independent[0], reference=FollowObject(anchor.id))
    scene = Scene(document).add(lyric, count)
    scene.replace_source(record)
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
