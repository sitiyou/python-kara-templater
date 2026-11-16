"""Layered lyric glow and syllable emphasis using ordinary Scene objects.

python -m examples.layered_glow tests/fixtures/layered_glow.ass output.ass
The direct command reframes at 1920x1080; CLI --effect preserves input resolution.
"""

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from kara_templater import (
    WHITE,
    Color,
    Document,
    FadeIn,
    FadeOut,
    Glow,
    Highlight,
    HighlightPass,
    Layout,
    LayoutContext,
    LayoutLine,
    LyricHighlights,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricTarget,
    ObjectGroup,
    Placement,
    ProgressCurve,
    RasterSettings,
    Region,
    SceneBudget,
    SceneObject,
    SceneResult,
    StatePatch,
    Style,
    Timeline,
    TimeSpan,
    Track,
    Tween,
    Vec2,
    prepare_tracks,
)
from kara_templater.scene_animation import AnimationSequence

BASE_GLOW = Color.hex("#9e6d64")
SUNG_GLOW = Color.hex("#67e5ff")
SUNG_FILL = Color.hex("#01829d")
CURVE = ProgressCurve.two_stage(time_fraction=3 / 17, progress_fraction=0.3)
BUDGET = SceneBudget(max_events=30_000)


@dataclass(frozen=True, kw_only=True)
class SourceLayout(Layout):
    """This fixture uses style margins and bottom alignment, with free overlap."""

    align: int = 2
    left: float = 10
    right: float = 10
    bottom: float = 10

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        region = context.region
        result = []
        for line in lines:
            box = line.bounds
            x = (
                region.left + self.left - box.left
                if self.align == 1
                else region.right - self.right - box.right
                if self.align == 3
                else region.left + (region.width - box.width) / 2 - box.left
            )
            result.append(
                Placement(
                    line.id,
                    Vec2(
                        x,
                        region.top + region.height - self.bottom - box.top - box.height,
                    ),
                    line.display,
                )
            )
        return tuple(result)


def base_glow(line: LyricLine, target: LyricTarget) -> Glow:
    return Glow(
        BASE_GLOW, blur=10, border=6 if target.role == "ruby" else 10, opacity=0.8
    )


def sung_glow(line: LyricLine, target: LyricTarget) -> Glow:
    return replace(base_glow(line, target), color=SUNG_GLOW)


def pulse(line: LyricLine, target: LyricTarget) -> AnimationSequence:
    """Attack, sustain through singing, then release; the layout reserves release."""
    span = target.singing[0]
    duration = span.end - span.start
    attack = min(0.08, duration)
    timeline = Timeline()
    if attack:
        timeline.play(Tween(StatePatch(scale=Vec2(1.1, 1.1))), duration=attack)
    timeline.wait(duration - attack)
    timeline.play(Tween(StatePatch(scale=Vec2(1, 1))), duration=0.16)
    return timeline.animation


def highlights(line: LyricLine) -> tuple[Highlight, ...]:
    curve = ProgressCurve() if "lead" in line.query("line")[0].tags else CURVE
    return tuple(
        Highlight(
            f"unit:{index}",
            index,
            tuple(
                HighlightPass(
                    TimeSpan(segment.singing.start, segment.singing.end),
                    Region(box.left, box.right),
                    round=round_id,
                    rate=curve.at,
                    inverse_rate=curve.arrival,
                    breakpoints=tuple(
                        t * (segment.singing.end - segment.singing.start)
                        for t, _ in curve.knots[1:-1]
                    ),
                )
                for round_id, segment in enumerate(unit.segments)
                if segment.singing.end > segment.singing.start
            ),
            StatePatch(fill=SUNG_FILL, outline=WHITE),
            glow=sung_glow,
            repeat="reset",
        )
        for index, unit in enumerate(line.layout.lyrics.units)
        if any(s.singing.end > s.singing.start for s in unit.segments)
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )


@dataclass(frozen=True)
class Paint:
    strategy: Literal["clip", "coverage"] = "clip"
    settings: RasterSettings = RasterSettings()

    def __call__(self, line: LyricLine) -> LyricLine:
        ruby_ids = {target.node_id for target in line.query("ruby")}

        def lower_readings(node: SceneObject) -> SceneObject:
            if isinstance(node, ObjectGroup):
                return replace(
                    node, children=tuple(lower_readings(c) for c in node.children)
                )
            if node.id in ruby_ids:
                return replace(
                    node,
                    state=replace(
                        node.state, position=node.state.position + Vec2(0, 10)
                    ),
                )
            return node

        shifted = lower_readings(line)
        assert isinstance(shifted, LyricLine)
        return LyricHighlights(
            highlights=highlights,
            glow=base_glow,
            strategy=self.strategy,
            settings=self.settings,
        ).apply(shifted)


def configuration(style: Style, *, paint: Paint | None = None) -> Track:
    """Ordinary typed configuration, reusable by the subclass example."""
    lead = style.name == "LEAD"
    body = replace(style, outline=5, shadow=0, fields=dict(style.fields))
    body.fields.update(PrimaryColour="&H00FFFFFF", OutlineColour="&H00000000")
    ruby = replace(
        body, name=style.name + "-furigana", fontsize=style.fontsize / 2, outline=3
    )
    rules = (
        LyricRule("line", "enter", FadeIn(), duration=0.8),
        LyricRule("line", "exit", FadeOut(), duration=0.2),
    )
    return Track(
        id=style.name,
        source=lambda source: source.style == style.name,
        layout=SourceLayout(
            align=style.align,
            left=style.margin_l,
            right=style.margin_r,
            bottom=style.margin_v,
        ),
        preview=0,
        tail=0,
        tags=frozenset(("lead",)) if lead else frozenset(),
        styles=(body, ruby),
        factory=Paint() if paint is None else paint,
        animations=rules if lead else (*rules, LyricRule("syllable", "singing", pulse)),
    )


def build(document: Document) -> LyricScene:
    return prepare_tracks(
        document,
        tracks=tuple(
            configuration(document.styles[name]) for name in ("K1", "K2", "LEAD")
        ),
        owner="layered-glow",
    )


def apply(input_path: str | Path, output_path: str | Path) -> SceneResult:
    source = deepcopy(Document.load(input_path))
    document = Document.create(
        width=1920, height=1080, styles=tuple(source.styles.values())
    )
    document.records.extend(line for line in source.lines if not line.comment)
    for name, style in document.styles.items():
        style.fontsize, style.spacing, style.shadow = 96, 0, 0
        style.margin_l = style.margin_r = 64
        style.align, style.margin_v = {"K1": (1, 240), "K2": (3, 48), "LEAD": (1, 432)}[
            name
        ]
    result = build(document).compile(budget=SceneBudget(max_events=1_000_000))
    result.document.save(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = apply(args.input, args.output)
    print(f"{result.event_count} events, {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
