"""Generate a native ASS example: python -m examples.output_layers /tmp/layers.ass."""

import argparse
from pathlib import Path

from kara_templater import (
    Color,
    DisplayWindow,
    KaraokeLine,
    Paint,
    Pulse,
    Segment,
    Style,
    TextUnit,
    layout_characters,
    layout_line,
    plan_pulses,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from kara_templater.ass_output import (
    Fade,
    OutputSettings,
    TextLayer,
    compile_layers,
    sweep_spans,
)
from kara_templater.timeline import EdgeSweep, Region


def build(text="Karaoke", *, spacing=0, fontname="DejaVu Sans", italic=False):
    window = DisplayWindow(0, 3000)
    layers, styles = [], []
    modes = (Pulse.each_char(), Pulse.simultaneous_chars(), Pulse.whole_syllable())
    for index, pulse in enumerate(modes):
        style = Style(
            name=f"Mode{index}",
            fontname=fontname,
            italic=italic,
            fontsize=52,
            align=8,
            margin_v=60 + 140 * index,
            spacing=spacing,
        )
        styles.append(style)
        source = KaraokeLine((TextUnit(text, (Segment(1000, 2000),)),))
        layout = layout_line(source, style=style, resolution=(640, 480))
        chars = layout_characters(layout, style=style)
        tracks = tracks_from_layout(layout)
        plan = plan_pulses(
            (pulse,),
            layout=layout,
            characters=tuple(c.target for c in chars),
            tracks=tracks,
            window=window,
        )
        spans = sweep_spans(
            tracks[0].passes[0],
            paint=Region(layout.box.left - 12, layout.box.right + 12),
            window=window,
            edges=EdgeSweep(lead_ms=100, tail_ms=100),
        )
        for char in chars:
            animations = tuple(a for a in plan.animations if a.target_id == char.id)
            for highlight in (False, True):
                layers.append(
                    TextLayer(
                        f"row:{index}/{char.id}/{'after' if highlight else 'before'}",
                        char.text,
                        style,
                        char.box,
                        window,
                        Paint(Color.hex("#33ddff" if highlight else "#dddddd")),
                        Fade(300, 300),
                        spans if highlight else None,
                        animations,
                        index * 2 + int(highlight),
                    )
                )
    result = compile_layers(tuple(layers), settings=OutputSettings((640, 480)))
    script = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 480\nScaledBorderAndShadow: yes\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
    )
    script += "\n".join(style.serialize() for style in styles)
    script += "\n\n[Events]\nFormat: " + EVENT_FORMAT + "\n"
    script += "\n".join(event.serialize() for event in result.events) + "\n"
    return script, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    script, result = build()
    args.output.write_text(script, encoding="utf-8-sig")
    print(
        f"{len(result.events)} events; {len(result.diagnostics)} diagnostics; {args.output}"
    )


if __name__ == "__main__":
    main()
