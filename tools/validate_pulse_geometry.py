"""Compare common lyric pulses with independently calculated static ASS frames.

Run: python -m tools.validate_pulse_geometry OUTPUT
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from examples.output_layers import highlights, pulse
from kara_templater import (
    Document,
    HighlightArrival,
    Layout,
    Line,
    LyricLine,
    LyricRule,
    LyricTarget,
    ScalePulse,
    SceneBudget,
    Style,
    Track,
    Vec2,
    load_font,
    prepare_tracks,
)
from kara_templater._raster import rasterize


def scaling(line: LyricLine, target: LyricTarget) -> ScalePulse:
    animation = pulse(line, target)
    assert isinstance(animation, ScalePulse)
    return replace(animation, peak=1.4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf")
    style = Style(fontname=font.family, fontsize=64, spacing=12, outline=0, shadow=0)
    source = Document.create(width=640, height=480, styles=(style,))
    source.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}W i"))
    track = Track(
        id="word", preview=0.5, tail=0.8, layout=Layout(position=Vec2(100, 200))
    )
    plain = prepare_tracks(source, tracks=(track,))
    line = plain.lines[0]
    box = line.layout.body.bounds
    evaluator = plain.evaluator()
    characters = tuple(
        (target, character, evaluator.at(target.node_id, 0.5))
        for target, character in zip(
            line.query("character"), line.layout.body.characters, strict=True
        )
        if not character.object.text.isspace()
    )
    assert [item.object.text for _, item, _ in characters] == ["W", "i"]
    times = (990, 1000, 1100, 1250, 1400, 1500, 1600, 1800, 1990, 2000, 2400)
    checks = []
    counts = {}
    for mode in ("each", "simultaneous", "whole"):
        rule = LyricRule(
            "syllable" if mode == "whole" else "character",
            HighlightArrival(highlights=highlights) if mode == "each" else "singing",
            scaling,
            duration=0.4 if mode == "each" else 1,
        )
        scene = prepare_tracks(source, tracks=(replace(track, animations=(rule,)),))
        result = scene.compile(budget=SceneBudget(fps=100, max_events=100_000))
        result.document.save(output / f"{mode}.ass")
        counts[mode] = result.event_count
        for time in times:
            # Sampled ASS exposures use their 10 ms midpoint, not the frame edge.
            sample = (time + 5) / 1000
            reference = Document.create(width=640, height=480, styles=(style,))
            for target, character, base in characters:
                start = (
                    1 + (character.bounds.left - box.left) / box.width
                    if mode == "each"
                    else 1
                )
                duration = 0.4 if mode == "each" else 1
                progress = (sample - start) / duration
                factor = 1 + 0.4 * max(0, 1 - abs(2 * progress - 1))
                pivot = (
                    line.state.position + Vec2(box.center, box.middle)
                    if mode == "whole"
                    else base.position
                    + Vec2(character.bounds.width / 2, character.bounds.height / 2)
                )
                position = pivot + (base.position - pivot) * factor
                actual = scene.evaluator().at(target.node_id, sample)
                assert abs(actual.position.x - position.x) < 1e-8
                assert abs(actual.position.y - position.y) < 1e-8
                assert abs(actual.scale.x - base.scale.x * factor) < 1e-8
                reference.records.append(
                    Line(
                        start_time=0,
                        end_time=3000,
                        text=(
                            rf"{{\an7\q2\pos({position.x:.3f},{position.y:.3f})"
                            rf"\fscx{100 * base.scale.x * factor:.3f}\fscy{100 * base.scale.y * factor:.3f}}}"
                            + character.object.text
                        ),
                    )
                )
            actual = rasterize(result.document.dumps(), time, (640, 480)).rgba
            expected = rasterize(reference.dumps(), time, (640, 480)).rgba
            maximum = max(abs(a - b) for a, b in zip(actual, expected, strict=True))
            checks.append(
                {
                    "mode": mode,
                    "time_ms": time,
                    "max_channel_difference": maximum,
                    "passed": maximum == 0,
                }
            )
            if maximum:
                reference.save(output / f"{mode}-{time}-reference.ass")
                Image.frombytes("RGBA", (640, 480), actual).save(
                    output / f"{mode}-{time}-actual.png"
                )
                Image.frombytes("RGBA", (640, 480), expected).save(
                    output / f"{mode}-{time}-expected.png"
                )
    report = {
        "font_sha256": font.sha256,
        "events": counts,
        "checks": checks,
        "reference": "Measured glyph geometry, independent triangular scale and pivot math, direct static ASS tags.",
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{sum(1 for check in checks if check['passed'])}/{len(checks)} pulse reference frames passed"
    )
    if not all(check["passed"] for check in checks):
        raise SystemExit("Pulse geometry validation failed")


if __name__ == "__main__":
    main()
