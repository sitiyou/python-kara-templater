"""Run `python -m examples.characters` to inspect measured, source-mapped plans."""

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    KaraokeLine,
    Paint,
    PaintPair,
    Pulse,
    RubyPaint,
    Segment,
    Style,
    TextRange,
    TextUnit,
    layout_characters,
    layout_line,
    plan_pulses,
    resolve_paints,
    resolve_ruby_paints,
    tracks_from_layout,
)


def main():
    style = Style(fontname="DejaVu Sans", fontsize=40)
    source = KaraokeLine((TextUnit("a\u0301B", (Segment(1000, 2000, "reading"),)),))
    layout = layout_line(source, style=style)
    characters = layout_characters(layout, style=style)
    red, blue = Paint(Color.hex("#ff5555")), Paint(Color.hex("#5599ff"))
    paints = resolve_paints(
        characters,
        spans=(
            ColorSpan(TextRange(0, 0, 2), after=red),
            ColorSpan(TextRange(0, 2, 3), after=blue),
        ),
    )
    ruby = resolve_ruby_paints(
        layout, paints, overrides=(RubyPaint(0, 0, PaintPair(after=red)),)
    )
    animations = plan_pulses(
        (Pulse.each_char(),),
        layout=layout,
        characters=tuple(c.target for c in characters),
        tracks=tracks_from_layout(layout),
        window=DisplayWindow(500, 2500),
    )
    for character in paints:
        print(
            character.character.id,
            repr(character.character.text),
            character.character.box,
            character.paints,
        )
    print("ruby:", ruby)
    print("pulses:", animations.animations)


if __name__ == "__main__":
    main()
