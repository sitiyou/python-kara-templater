"""Run with `python -m examples.timeline`; evaluates plans, does not write ASS yet."""

from kara_templater import (
    Box,
    CharacterTarget,
    Color,
    DisplayWindow,
    EdgeSweep,
    HighlightTrack,
    LaidOutLine,
    LaidOutUnit,
    Paint,
    ProgressCurve,
    Pulse,
    Region,
    SingingPass,
    TextUnit,
    TrackPaint,
    compose_highlights,
    plan_pulses,
)


def main():
    # Explicit geometry makes this domain example independent of installed fonts.
    # The future character-layout backend will provide these drawable clusters.
    box = Box(100, 400, 100, 40)
    layout = LaidOutLine(box, (LaidOutUnit(TextUnit("今天"), box, ()),))
    chars = (
        CharacterTarget("today:0", 0, Region(100, 140), 420),
        CharacterTarget("today:1", 0, Region(140, 200), 420),
    )
    main_track = HighlightTrack(
        "main",
        0,
        (
            SingingPass(
                1000,
                2000,
                Region(100, 200),
                ProgressCurve.two_stage(time_fraction=0.25, progress_fraction=0.4),
            ),
        ),
    )
    for pulse in (
        Pulse.each_char(),
        Pulse.simultaneous_chars(),
        Pulse.whole_syllable(),
    ):
        plan = plan_pulses(
            (pulse,),
            layout=layout,
            characters=chars,
            tracks=(main_track,),
            window=DisplayWindow(500, 2500),
        )
        print(
            pulse.target,
            [(a.target_id, a.start_ms, a.end_ms, a.pivot) for a in plan.animations],
        )

    edges = EdgeSweep(padding_px=10, lead_ms=150, tail_ms=100)
    singing = main_track.passes[0]
    for paint in (Region(95, 205), Region(0, 300)):
        print(
            "decoration:",
            paint,
            "front at 1500:",
            edges.position_at(singing, paint, 1500),
            "second character arrival:",
            singing.arrival(chars[1].region.left),
        )

    echo = HighlightTrack(
        "echo", 0, (SingingPass(1300, 1700, Region(140, 200)),), end_behavior="hide"
    )
    layers = (
        TrackPaint(main_track, Paint(Color.hex("#ff5555")), 0),
        TrackPaint(echo, Paint(Color.hex("#5599ff")), 1),
    )
    for time in (1400, 1600, 1800):
        print(time, compose_highlights(layers, time, overlap="priority"))


if __name__ == "__main__":
    main()
