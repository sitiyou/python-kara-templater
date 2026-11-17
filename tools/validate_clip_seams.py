"""Compare common highlight partitions with one fully painted glyph.

Run: python -m tools.validate_clip_seams OUTPUT [--scale] [--fade]
Use --strategy coverage to diagnose fractional material partitions instead.
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops

from kara_templater import (
    BLUE,
    RED,
    WHITE,
    Document,
    FadeIn,
    FadeOut,
    Glow,
    Highlight,
    HighlightPass,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    Region,
    ScalePulse,
    Scene,
    SceneBudget,
    StatePatch,
    Style,
    TimeSpan,
    Vec2,
    layout_document_lyrics,
    load_font,
)
from kara_templater._raster import rasterize


def subjects(
    *,
    font: str = "DejaVu Sans",
    scale: bool = False,
    fade: bool = False,
    strategy: Literal["clip", "coverage"] = "coverage",
) -> tuple[Scene, Scene]:
    source = Document.create(
        width=160,
        height=120,
        styles=(Style(fontname=font, fontsize=32, outline=0, shadow=0),),
    )
    source.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}M"))
    line = LyricLine.from_layout(
        layout_document_lyrics(
            source, len(source.records) - 1, display=Lifetime(0.5, 2.5)
        )
    )
    line = replace(line, state=replace(line.state, position=Vec2(50, 40), opacity=0.5))
    box = line.layout.body.bounds
    halo = Glow(WHITE, blur=2, opacity=0.5)
    whole = Region(box.left, box.right)
    highlights = (
        Highlight(
            "main",
            0,
            (HighlightPass(TimeSpan(1, 2), whole),),
            StatePatch(outline=RED),
            glow=halo,
        ),
        Highlight(
            "cover",
            0,
            (
                HighlightPass(
                    TimeSpan(1.23, 1.81),
                    Region(
                        box.left + box.width * 0.1 + 0.2,
                        box.right - box.width * 0.1 + 0.3,
                    ),
                ),
            ),
            StatePatch(outline=BLUE),
            priority=1,
            end="hide",
            glow=halo,
        ),
    )
    reference = (
        Highlight(
            "whole",
            0,
            (HighlightPass(TimeSpan(0.5, 0.5), whole),),
            StatePatch(outline=RED),
            glow=halo,
        ),
    )
    result = []
    for selected in (highlights, reference):
        decorated = LyricHighlights(
            highlights=selected, mode="priority", strategy=strategy, glow=halo
        )(line)
        if scale:
            decorated = decorated.animate(
                ScalePulse(Vec2(box.center, box.middle), peak=1.4), at=0.5, duration=1
            )
        if fade:
            decorated = decorated.animate(FadeIn(), duration=1).animate(
                FadeOut(), at=1, duration=1
            )
        result.append(
            Scene(source, replace_records={len(source.records) - 1}).add(decorated)
        )
    return result[0], result[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", action="store_true")
    parser.add_argument("--fade", action="store_true")
    parser.add_argument("--strategy", choices=("clip", "coverage"), default="clip")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf")
    scenes = subjects(
        font=font.family, scale=args.scale, fade=args.fade, strategy=args.strategy
    )
    outputs = tuple(
        scene.compile(
            budget=SceneBudget(
                fps=100,
                max_events=500_000,
                max_active=100_000,
                max_bytes=128 * 1024 * 1024,
            )
        )
        for scene in scenes
    )
    for name, compiled in zip(("partitioned", "reference"), outputs, strict=True):
        compiled.document.save(output / f"{name}.ass")
    scripts = tuple(compiled.document.dumps() for compiled in outputs)
    checks = []
    for time in range(1000, 2010, 10):
        frames = tuple(
            Image.frombytes(
                "RGBA", (160, 120), rasterize(script, time, (160, 120)).rgba
            )
            for script in scripts
        )
        difference = ImageChops.difference(*frames)
        maximum = max(difference.tobytes())
        checks.append(
            {"time_ms": time, "max_channel_difference": maximum, "passed": maximum == 0}
        )
        if maximum:
            difference.save(output / f"failure-{time}.png")
    report = {
        "scale": args.scale,
        "fade": args.fade,
        "strategy": args.strategy,
        "font_sha256": font.sha256,
        "events": [item.event_count for item in outputs],
        "checks": checks,
        "reference": "Same visible paint without moving internal partitions; detects cracks and extra alpha.",
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{sum(1 for check in checks if check['passed'])}/{len(checks)} seam frames passed"
    )
    if not all(check["passed"] for check in checks):
        raise SystemExit("Clip seams detected")


if __name__ == "__main__":
    main()
