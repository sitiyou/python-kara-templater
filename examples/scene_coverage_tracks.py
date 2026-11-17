"""Lyric ruby/sweep/glow with common parent motion and vector decoration.

uv run python -m examples.scene_coverage_tracks output.ass
Coverage is an explicit Scene strategy with an explicit pixel-output budget.
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Glow,
    GlowFunction,
    Highlight,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    ObjectGroup,
    PathObject,
    RasterSettings,
    Region,
    Scene,
    SceneBudget,
    SceneResult,
    StateFunction,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_tracks,
)

BUDGET = SceneBudget(
    fps=10, max_events=200_000, max_active=5000, max_bytes=64 * 1024 * 1024
)
RASTER_SETTINGS = RasterSettings(max_channel_error=8, max_frames=100)


def drift(state: VisualState, progress: float) -> VisualState:
    return replace(state, position=state.position + Vec2(0, 5 * sin(tau * progress)))


def glow(state: VisualState, seconds: float) -> Glow:
    """Animate glow color on the same local-seconds clock as other materials."""
    color = (
        StatePatch(fill=PINK)
        .interpolate(VisualState(fill=CYAN), min(1, max(0, seconds / 2.5)))
        .fill
    )
    return Glow(color=color, border=2, blur=2)


def ruby_glow(state: VisualState, seconds: float) -> Glow:
    return replace(glow(state, seconds), border=1, blur=1)


BODY_GLOW = GlowFunction(glow, max_blur=2, max_border=2, breakpoints=(2.5,))
RUBY_GLOW = GlowFunction(ruby_glow, max_blur=1, max_border=1, breakpoints=(2.5,))


def paint(line: LyricLine) -> LyricLine:
    highlights = tuple(
        Highlight(
            f"unit:{index}",
            index,
            tuple(
                HighlightPass(
                    TimeSpan(segment.singing.start, segment.singing.end),
                    Region(box.left, box.right),
                    round=round_id,
                )
                for round_id, segment in enumerate(unit.segments)
            ),
            StatePatch(fill=PINK),
            glow=BODY_GLOW,
            repeat="reset",
        )
        for index, unit in enumerate(line.layout.lyrics.units)
        if unit.segments
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )
    line = LyricHighlights(
        highlights=highlights,
        strategy="coverage",
        glow=BODY_GLOW,
        settings=RASTER_SETTINGS,
    )(line)
    config = line.coverage
    assert config is not None
    glows = dict(config.glows)
    for target in line.query("ruby"):
        for identity in (target.node_id, *target.aliases):
            glows[identity] = RUBY_GLOW
    return replace(line, coverage=replace(config, glows=glows))


def build_scene() -> Scene:
    document = Document.create(
        width=240,
        height=135,
        styles=(
            Style(fontname="DejaVu Sans", fontsize=40, shadow=0, align=5),
            Style(
                name="Default-furigana",
                fontname="DejaVu Sans",
                fontsize=20,
                shadow=0,
                outline=0,
            ),
        ),
    )
    document.records.append(
        Line(text=r"{\k100}Fly|fly{\k100} on|on", start_time=500, end_time=3500)
    )
    scene = prepare_tracks(
        document,
        tracks=(
            Track(
                id="lyrics",
                layout=Layout(position=Vec2(50, 35)),
                preview=0,
                tail=0,
                effects=(paint,),
            ),
        ),
    )
    line = scene.lines[0]
    underline = PathObject(
        id="underline",
        lifetime=line.lifetime,
        path=VectorPath.rectangle(140, 2),
        state=VisualState(position=Vec2(50, 112), fill=PINK),
    )
    # Coverage lyrics and an ordinary path share one ordinary parent animation.
    scene.objects[0] = ObjectGroup(
        id="floating",
        lifetime=line.lifetime,
        children=(line, underline),
    ).animate(
        StateFunction(drift, frozenset(("position",))),
        duration=line.lifetime.end - line.lifetime.start,
    )
    return scene


def build() -> SceneResult:
    return build_scene().compile(budget=BUDGET)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(
        f"{len(result.objects[0].sample_times)} samples, {result.event_count} events, "
        f"{result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
