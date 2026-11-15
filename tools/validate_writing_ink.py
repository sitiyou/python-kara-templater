"""E08 ink against dense cubic arc lengths and independently stroked polygons.

uv run python -m tools.validate_writing_ink OUTPUT
No WritePath, flatten, stroke or Scene geometry lowering is used by the reference.
"""

import argparse
import bisect
import hashlib
import json
from math import cos, hypot, sin, tau
from pathlib import Path

from examples.scene_writing import build
from kara_templater import Document, Line, Style
from tools.validate_case_geometry import compare
from tools.validate_cues import static_intervals
from tools.validate_staggered import fill
from tools.validate_writing import STROKES, Point, curve_reference, position


def prefix(points: list[Point], fraction: float) -> list[Point]:
    if fraction <= 0:
        return []
    if fraction >= 1:
        return points
    lengths: list[float] = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        lengths.append(lengths[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    distance = fraction * lengths[-1]
    index = max(1, bisect.bisect_left(lengths, distance))
    a, b = points[index - 1], points[index]
    p = (distance - lengths[index - 1]) / (lengths[index] - lengths[index - 1])
    return [*points[:index], (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)]


def polygon(points: list[Point], width: float) -> str:
    # Independent butt-cap / bevel-join construction from dense segment offsets.
    sides: list[list[Point]] = [[], []]
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = hypot(dx, dy)
        if not length:
            continue
        for side, sign in zip(sides, (1, -1), strict=True):
            nx, ny = -dy * width / (2 * length) * sign, dx * width / (2 * length) * sign
            side.extend(((a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)))
    return "m " + " l ".join(
        f"{x + 470:.6f} {y + 250:.6f}" for x, y in (*sides[0], *reversed(sides[1]))
    )


def reference(ms: int, curve: list[Point], *, width: float = 6) -> str:
    boundaries = sorted(
        {*range(0, 5001, 20), *(t for interval in STROKES for t in interval)}
    )
    interval = min(len(boundaries) - 2, bisect.bisect_right(boundaries, ms) - 1)
    sample = (boundaries[interval] + boundaries[interval + 1]) / 2
    strokes: list[list[Point]] = [
        [(0, 170), (65, 0)],
        [(65, 0), (130, 170)],
        [(27, 100), (103, 100)],
        curve,
    ]
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    for points, (start, end) in zip(strokes, STROKES, strict=True):
        drawn = prefix(points, (sample - start) / (end - start))
        if len(drawn) < 2:
            continue
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                text=r"{\an7\pos(0,0)\p1\1c&HFFFF00&}" + polygon(drawn, width),
            )
        )
    return document.dumps()


def pen_reference(ms: int, points: list[Point], lengths: list[float]) -> str:
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    if not any(start <= ms < end for start, end in STROKES):
        return document.dumps()
    boundaries = sorted({*range(0, 5001, 20), *(t for pair in STROKES for t in pair)})
    index = bisect.bisect_right(boundaries, ms) - 1
    sample = (boundaries[index] + boundaries[index + 1]) / 2
    x, y = position(sample, points, lengths)
    circle = "m " + " l ".join(
        f"{x + 7 * cos(tau * i / 128):.6f} {y + 7 * sin(tau * i / 128):.6f}"
        for i in range(128)
    )
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            layer=1,
            text=r"{\an7\pos(0,0)\p1\1c&HCBC0FF&}" + circle,
        )
    )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    compiled = build().compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    (output / "E08.ass").write_text(script)
    # 500 steps per cubic, independently sampled; production uses adaptive flattening.
    points, lengths = curve_reference()
    curve = points[::20]
    times = sorted(
        {
            *range(0, 5000, 100),
            *(int(item["start_ms"]) for item in intervals if item["start_ms"] < 5000),
            *(t + d for stroke in STROKES for t in stroke for d in (-1, 0, 1)),
            4999,
        }
    )
    checks = []
    pen_checks = []
    for ms in times:
        pen_actual = fill(script, ms, 0xFFC0CB)
        pen_expected = fill(pen_reference(ms, points, lengths), ms, 0xFFC0CB)
        if pen_expected.getbbox() is None:
            assert pen_actual.getbbox() is None, f"pen visible while raised at {ms}"
        else:
            pen_checks.append({"time_ms": ms, **compare(pen_actual, pen_expected)})
        plain = reference(ms, curve)
        actual, expected = fill(script, ms), fill(plain, ms)
        if ms < 300:
            if actual.getbbox() is not None:
                raise AssertionError(f"ink before first stroke at {ms}ms")
            continue
        checks.append({"time_ms": ms, **compare(actual, expected)})
        if ms in (500, 1500, 2500, 3500, 4500):
            (output / f"reference-{ms}.ass").write_text(plain)
    try:
        compare(fill(script, 4500), fill(reference(4500, curve, width=12), 4500))
    except AssertionError:
        pass
    else:
        raise AssertionError("doubled stroke width was not detected")
    for ms in (5000, 5001):
        if fill(script, ms).getbbox() is not None:
            raise AssertionError("ink after lifetime")
    report = {
        "scope": "E08 cyan ink coverage including all four strokes; independent dense cubic prefix and butt/bevel polygon reference; pen compositing separate",
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "curve_steps_per_cubic": 500,
        "checks": checks,
        "pen_geometry_checks": pen_checks,
        "wrong_width_fault_rejected": True,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "blank_times_ms": [5000, 5001],
        "remaining": [
            "continuous-time curve approximation bound",
            "final pen/ink compositing",
            "other renderers",
        ],
    }
    (output / "writing-ink-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_edge_difference": max(
                    c["max_coverage_difference"] for c in checks
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
