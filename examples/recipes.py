"""Standalone application-style fixtures: python -m examples.recipes /tmp/recipes.ass."""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    BLACK,
    Body,
    Color,
    DisplayWindow,
    Document,
    Effect,
    Glow,
    Halo,
    HighlightTrack,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    Paint,
    ProgressCurve,
    Region,
    Ruby,
    Segment,
    SingingPass,
    Style,
    TextUnit,
    TrackStyle,
    render_karaoke,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT

CYAN, PINK = Color.hex("#33ddff"), Color.hex("#ff5599")


class RecipeEffect(Effect):
    def compose(self):
        mode = self.source.style
        children = [Body(fill="#dcdcdc", stroke=BLACK, stroke_width=1)]
        if mode != "LEAD":
            children.append(
                Ruby(
                    stroke_width=1,
                    offset_y=0 if mode == "H2" else -4,
                    follow="syllable" if mode in {"K1", "K2"} else "none",
                )
            )
        if mode == "H2":
            # The pink character has no glow; its reading keeps the cyan theme.
            children.extend(
                (
                    Halo(
                        targets=self.rubies,
                        color=CYAN,
                        blur=3,
                        width=2,
                        opacity=0.5,
                        clip="sung",
                    ),
                    Halo(
                        targets=self.characters[:1],
                        color=CYAN,
                        blur=3,
                        width=2,
                        opacity=0.5,
                        clip="sung",
                    ),
                )
            )
        elif mode != "K2":
            children.append(Halo(color=CYAN, blur=3, width=2, opacity=0.5, clip="sung"))
        yield Lyrics(*children)

    def configure(self):
        mode = self.source.style
        if mode == "K2":
            # Track styles describe the complete paint of a priority region:
            # the echo deliberately replaces the cyan glow with plain pink.
            main = Paint(CYAN, border=1, glow=Glow(CYAN, blur=3, border=2, opacity=0.5))
            self.text.sweep(
                fill=CYAN,
                tracks=self.parallel,
                track_styles=tuple(
                    TrackStyle(f"main-{i}", main) for i in range(len(self.syllables))
                )
                + (TrackStyle("echo", Paint(PINK, border=1), 10),),
                overlap="priority",
                padding=4,
                lead=80,
                tail=100,
            )
        elif mode in {"K1", "H1"}:
            self.text.sweep(
                fill=CYAN,
                curve=ProgressCurve.two_stage(
                    time_fraction=0.25, progress_fraction=0.4
                ),
                padding=4,
                lead=80,
                tail=100,
            )
        else:
            self.text.sweep(fill=CYAN)
        if mode == "H2":
            self.characters[1].style.sung.fill = PINK
            self.characters[1].style.sung.stroke_width = 0
            self.characters.on_highlight(pulse=1.1)
        elif mode == "K1":
            self.syllables.on_singing(pulse=1.1)
        elif mode == "H1":
            self.characters.on_singing(pulse=1.1)
        if mode != "H2":
            self.text.fade(in_ms=200 if mode == "LEAD" else 300, out_ms=300)

    def parallel(self, layout):
        box = layout.units[1].box
        return (
            *(
                replace(t, id=f"main-{i}")
                for i, t in enumerate(tracks_from_layout(layout))
            ),
            HighlightTrack(
                "echo",
                1,
                (SingingPass(1200, 1750, Region(box.left, box.right)),),
                end_behavior="hide",
            ),
        )


def build():
    styles = (
        Style(
            name="K1",
            fontname="DejaVu Sans",
            fontsize=40,
            align=1,
            margin_l=40,
            margin_v=90,
        ),
        Style(
            name="K2",
            fontname="DejaVu Sans",
            fontsize=40,
            align=3,
            margin_r=40,
            margin_v=25,
        ),
        Style(name="H1", fontname="DejaVu Sans", fontsize=32, align=8, margin_v=25),
        Style(name="H2", fontname="DejaVu Sans", fontsize=32, align=8, margin_v=110),
        Style(
            name="LEAD",
            fontname="DejaVu Sans",
            fontsize=40,
            align=1,
            margin_l=40,
            margin_v=160,
        ),
    )
    source = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + "\n".join(s.serialize() for s in styles)
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    window = DisplayWindow(0, 3000)
    lyrics = KaraokeLine(
        (
            TextUnit("Ka", (Segment(1000, 1400, "ka"),)),
            TextUnit("raoke", (Segment(1400, 2000, "raoke"),)),
        )
    )
    items = tuple(
        KaraokeItem(style.name, lyrics, style.name, window) for style in styles[:3]
    )
    items += (
        KaraokeItem(
            "H2",
            KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "ab"),)),)),
            "H2",
            window,
        ),
        KaraokeItem(
            "LEAD",
            KaraokeLine((TextUnit("....", (Segment(500, 1000),)),)),
            "LEAD",
            window,
        ),
    )
    result = render_karaoke(source, items, effect=RecipeEffect, owner="example")
    assert (
        render_karaoke(
            result.document, items, effect=RecipeEffect, owner="example"
        ).document.dumps()
        == result.document.dumps()
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.layer_count} planned layers, {len(result.diagnostics)} diagnostics"
    )
    for diagnostic in dict.fromkeys(result.diagnostics):
        print(diagnostic)


if __name__ == "__main__":
    main()
