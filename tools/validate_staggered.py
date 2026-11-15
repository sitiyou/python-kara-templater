"""E02 letter fill positions/opacity vs independently authored static ASS frames.

uv run python -m tools.validate_staggered OUTPUT
Reference formulas do not call SceneTimeline, Tween or the example's bounce.
"""

import argparse
import hashlib
import json
from math import cos, sin, tau
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_staggered import build
from kara_templater import Document, Line, Style, _metrics, load_font
from tools.validate_case_geometry import compare
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT, SIZE


def midpoint(ms: int, start: int, end: int) -> float:
    return (max(start, ms // 20 * 20) + min(end, (ms // 20 + 1) * 20)) / 2


def reference(ms: int) -> str:
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=64, align=7, outline=1, shadow=0),
        )
    )
    for index, letter in enumerate("Tiny stars"):
        birth, entered = index * 80, index * 80 + 650
        leave, gone = 4000 + index * 40, 4500 + index * 40
        if letter == " " or ms < birth or ms >= gone:
            continue
        if ms < entered:
            p = (midpoint(ms, birth, entered) - birth) / 650
            q = p - 1
            ease = 1 + 2.70158 * q**3 + 1.70158 * q**2
            y, opacity = 300 + 60 * (1 - ease), p
        elif ms < leave:
            y, opacity = 300, 1
        else:
            p = (midpoint(ms, leave, gone) - leave) / 500
            ease = p * p * (3 - 2 * p)
            y, opacity = 300 - 40 * ease, 1 - ease
        alpha = round((1 - opacity) * 255)
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                text=rf"{{\pos({350 + index * 59},{y:.6f})\1c&HFFFF00&\alpha&H{alpha:02X}&}}{letter}",
            )
        )
    return document.dumps()


def fill(script: str, ms: int, rgb: int = 0x00FFFF, role: int = 0) -> Image.Image:
    image = Image.new("L", SIZE)
    for left, top, width, height, kind, color, coverage in _metrics.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind != role or color >> 8 != rgb or not width or not height:
            continue
        alpha = 255 - (color & 255)
        tile = Image.new("L", SIZE)
        mask = Image.frombytes("L", (width, height), coverage).point(
            [round(value * alpha / 255) for value in range(256)]
        )
        tile.paste(mask, (left, top))
        image = ImageChops.lighter(image, tile)
    return image


def orbit_reference(ms: int) -> str:
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    if 500 <= ms < 4500:
        p = (midpoint(ms, 500, 4500) - 500) / 4000
        angle = tau * p
        x, y = 390 + 480 * p, 420 + 32 * sin(angle)
        points = tuple(
            (x + u * cos(angle) - v * sin(angle), y + u * sin(angle) + v * cos(angle))
            for u, v in ((0, -9), (7, 0), (0, 9), (-7, 0))
        )
        path = "m " + " l ".join(f"{a:.6f} {b:.6f}" for a, b in points)
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                text=r"{\an7\pos(0,0)\p1\1c&HCBC0FF&}" + path,
            )
        )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    compiled = build().compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    (output / "E02.ass").write_text(script)
    boundaries = {
        t
        for i in range(10)
        for t in (i * 80, i * 80 + 650, 4000 + i * 40, 4500 + i * 40)
    }
    times = sorted(
        {
            *range(0, 5011, 100),
            *(int(item["start_ms"]) for item in intervals),
            *(t + delta for t in boundaries for delta in (-1, 0, 1) if t + delta >= 0),
            4999,
            5000,
            5001,
        }
    )
    checks = []
    maximum = 0
    for ms in times:
        actual = fill(script, ms)
        plain = reference(ms)
        expected = fill(plain, 0)
        difference = ImageChops.difference(actual, expected)
        error = max(i for i, count in enumerate(difference.histogram()) if count)
        maximum = max(maximum, error)
        # Same native text rasterizer: tolerate only one coverage level of rounding.
        if error > 1:
            (output / f"failed-reference-{ms}.ass").write_text(plain)
            raise AssertionError(
                f"letter geometry/opacity differs at {ms}ms by {error}/255"
            )
        outline_error = max(
            i
            for i, count in enumerate(
                ImageChops.difference(
                    fill(script, ms, 0, 1), fill(plain, 0, 0, 1)
                ).histogram()
            )
            if count
        )
        if outline_error > 1:
            raise AssertionError(f"outline mismatch at {ms}ms: {outline_error}")
        orbit_actual = fill(script, ms, 0xFFC0CB)
        orbit_expected = fill(orbit_reference(ms), 0, 0xFFC0CB)
        if 500 <= ms < 4500:
            orbit_quality = compare(orbit_actual, orbit_expected)
        else:
            if orbit_actual.getbbox() is not None:
                raise AssertionError(f"orbit outside lifetime at {ms}ms")
            orbit_quality = None
        checks.append(
            {
                "time_ms": ms,
                "max_fill_coverage_difference": error,
                "max_outline_coverage_difference": outline_error,
                "orbit_geometry": orbit_quality,
            }
        )
    report = {
        "scope": "E02 all visible letters vs hand-authored ASS positions and opacity; 80ms entry / 40ms exit stagger; space keeps its index and draws no ink; orbit vs independent trigonometric polygon",
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "font_sha256": font.sha256,
        "sampling": "20ms grid clipped at each letter's explicit 650ms entry and 500ms exit boundaries; interval midpoint held",
        "checks": checks,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "max_fill_coverage_difference": maximum,
        "remaining": [
            "final multilayer compositing on other backgrounds",
            "continuous-time sampling error",
            "other renderers",
        ],
    }
    (output / "staggered-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({"checks": len(checks), "max_fill_coverage_difference": maximum}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
