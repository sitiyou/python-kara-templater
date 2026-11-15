"""Inline cue releases keep ruby anchored; independent labels stay screen-fixed.

uv run python -m examples.scene_lyric_cues output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    Scene,
    Style,
    TextCue,
    Vec2,
    bind_lyric_cues,
    layout_document_lyrics,
)


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=72, shadow=0),)
    )
    document.records.append(
        Line(
            text=(
                CueMarker("intro", "bars").markup()
                + CueMarker("labels", "labels", placement="independent").markup()
                + r"{\k150}SING |!sing"
                + CueMarker("next", "numbers").markup()
                + r"{\k150}ALONG|!along"
            ),
            start_time=1000,
            end_time=4000,
        )
    )
    index = len(document.records) - 1
    layout = layout_document_lyrics(document, index, display=Lifetime(0, 5), ruby_gap=8)
    cued = bind_lyric_cues(
        layout,
        {
            "bars": CuePreset(factory=BarsCue(), keep_space=False),
            "numbers": CuePreset(
                factory=TextCue(font_size=48), trigger=2.5, keep_space=False
            ),
            "labels": CuePreset(
                factory=TextCue(labels=("READY", "SET", "GO"), font_size=32),
                position=Vec2(1000, 100),
            ),
        },
    )
    scene = Scene(document)
    scene.replace_source(index)
    return scene.add(cued.group(position=Vec2(260, 340)), *cued.independent)


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
