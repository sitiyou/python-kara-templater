"""Code-only color ranges on an ordinary single-segment karaoke line.

python -m examples.alternating_colors output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    BLUE,
    GREEN,
    RED,
    WHITE,
    Body,
    Document,
    Effect,
    Line,
    Lyrics,
    Record,
    Style,
    StyleSheet,
    render_karaoke,
    rule,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


class AlternatingColors(Effect):
    styles = StyleSheet(
        rule("body", fill=WHITE, stroke=BLACK, stroke_width=3),
        rule(".red:sung", fill=RED),
        rule(".green:sung", fill=GREEN),
        rule(".blue:sung", fill=BLUE),
    )

    def compose(self):
        yield Lyrics(Body())

    def configure(self):
        if self.syllables.text == "星月风星月风":
            for index in range(len(self.syllables.text)):
                role = ("red", "green", "blue")[index % 3]
                self.body.text_range(index, index + 1).add_class(role)
        self.text.sweep()


def document(*, fontname="Sarasa Gothic SC", text="星月风星月风"):
    # Construct directly; no custom ASS fields, roles, or per-character k tags.
    return Document(
        [
            "[Script Info]",
            "PlayResX: 640",
            "PlayResY: 480",
            "[V4+ Styles]",
            "Format: " + STYLE_FORMAT,
            Style(fontname=fontname, fontsize=56, shadow=0, margin_v=180),
            "[Events]",
            "Format: " + EVENT_FORMAT,
            Line(text=r"{\k300}" + text, start_time=0, end_time=4000),
        ],
        Record(res_x=640, res_y=480),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = render_karaoke(document(), effect=AlternatingColors)
    result.document.save(args.output)
    print(f"{result.event_count} events → {args.output}")


if __name__ == "__main__":
    main()
