"""E08 pen visibility and trajectory against independent scalar arc lengths.

uv run python -m tools.validate_writing OUTPUT
The reference uses dense cubic evaluation, not WritePath/flatten/tip.
"""

import argparse
import bisect
import hashlib
import json
from math import hypot
from pathlib import Path

from examples.scene_writing import build
from kara_templater import _ass_preview

STROKES = ((300, 1200), (1350, 2250), (2400, 2900), (3050, 4500))
Point = tuple[float, float]


def cubic(points: tuple[Point, Point, Point, Point], t: float) -> Point:
    weights = ((1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t**3)
    return (
        sum(p[0] * w for p, w in zip(points, weights, strict=True)),
        sum(p[1] * w for p, w in zip(points, weights, strict=True)),
    )


def curve_reference() -> tuple[list[Point], list[float]]:
    curves = (
        ((190.0, 120.0), (260.0, 200.0), (330.0, -30.0), (235.0, 10.0)),
        ((235.0, 10.0), (170.0, 40.0), (220.0, 190.0), (330.0, 130.0)),
    )
    points = [curves[0][0]]
    for curve in curves:
        points.extend(cubic(curve, i / 10000) for i in range(1, 10001))
    lengths: list[float] = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        lengths.append(lengths[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    return points, lengths


def position(ms: float, points: list[Point], lengths: list[float]) -> Point:
    lines = (((0, 170), (65, 0)), ((65, 0), (130, 170)), ((27, 100), (103, 100)))
    for i, (start, end) in enumerate(STROKES):
        if start <= ms < end:
            p = (ms - start) / (end - start)
            if i < 3:
                a, b = lines[i]
            else:
                distance = p * lengths[-1]
                index = max(1, bisect.bisect_left(lengths, distance))
                a, b = points[index - 1], points[index]
                p = (distance - lengths[index - 1]) / (
                    lengths[index] - lengths[index - 1]
                )
            return (470 + a[0] + (b[0] - a[0]) * p, 250 + a[1] + (b[1] - a[1]) * p)
    raise AssertionError("position queried while pen is raised")


def pen(script: str, ms: int) -> Point | None:
    weight = xsum = ysum = 0.0
    for left, top, width, height, kind, color, mask in _ass_preview.rasterize(
        script, ms, 1280, 720, 4_000_000, 10_000
    ):
        if kind != 0 or color != 0xFFC0CB00:
            continue
        for y in range(height):
            for x in range(width):
                alpha = mask[y * width + x]
                weight += alpha
                xsum += (left + x + 0.5) * alpha
                ysum += (top + y + 0.5) * alpha
    return (xsum / weight, ysum / weight) if weight else None


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    result = build().compile()
    script = result.document.dumps()
    (output / "E08.ass").write_text(script)
    points, lengths = curve_reference()
    boundaries = sorted(
        {*range(0, 5001, 20), *(t for stroke in STROKES for t in stroke)}
    )
    times = sorted(
        {
            *range(0, 5011, 10),
            *(t + d for stroke in STROKES for t in stroke for d in (-1, 0, 1)),
        }
    )
    maximum = continuous = 0.0
    visible = absent = 0
    for ms in times:
        actual = pen(script, ms)
        down = any(start <= ms < end for start, end in STROKES)
        if (actual is not None) != down:
            raise AssertionError(f"pen visibility mismatch at {ms}ms: {actual}")
        if actual is None:
            absent += 1
            continue
        visible += 1
        interval = bisect.bisect_right(boundaries, ms) - 1
        sample = (boundaries[interval] + boundaries[interval + 1]) / 2
        expected = position(sample, points, lengths)
        error = hypot(actual[0] - expected[0], actual[1] - expected[1])
        maximum = max(maximum, error)
        if error > 1:
            raise AssertionError(f"pen drift {error}px at {ms}ms")
        ideal = position(ms, points, lengths)
        continuous = max(continuous, hypot(actual[0] - ideal[0], actual[1] - ideal[1]))
    report = {
        "scope": "E08 pen visibility at stroke boundaries and sampled trajectory vs independent dense cubic arc length",
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "times_ms": times,
        "visible_checks": visible,
        "raised_checks": absent,
        "stroke_intervals_ms": STROKES,
        "max_sampled_position_error_px": maximum,
        "max_observed_continuous_position_error_px": continuous,
        "position_tolerance_px": 1,
        "reference_cubic_steps_per_segment": 10000,
        "sampling": "20 ms grid plus declared stroke boundaries; interval midpoint held",
        "event_count": result.event_count,
        "peak_active": result.peak_active,
        "byte_count": result.byte_count,
        "remaining": [
            "full ink coverage reference",
            "continuous-time global error bound",
            "other renderers",
        ],
    }
    (output / "writing-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "times_ms"}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
