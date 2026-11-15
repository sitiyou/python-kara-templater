"""E07 dynamic polygon contours against independent scalar perturbation.

uv run python -m tools.validate_outline_motion OUTPUT
WAVE in the fixed DejaVu font consists only of straight outline segments.
The reference bypasses text_to_path, VectorPath.map and PathFunction.
"""

import argparse
import hashlib
import json
from math import hypot, pi, sin, tau
from pathlib import Path
from random import Random

from PIL import Image, ImageChops, ImageDraw

from examples.scene_outlines import build
from kara_templater import Document, Line, Style, _metrics, load_font
from tools.validate_case_geometry import compare, mask
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT


def reference(ms: int, *, amplitude: float = 4) -> str:
    time = (ms // 20 * 20 + 10) / 1000
    weight = sin(max(0, min(1, (time - 1) / 3)) * pi) ** 2
    random = Random(17)
    phase_x, phase_y = random.uniform(0, tau), random.uniform(0, tau)
    _, _, _, baseline, glyphs = _metrics.text_shape(
        "DejaVu Sans", 120, 0, 0, 100, 100, 0, 1, "WAVE"
    )
    commands = []
    contour_count = 0
    for points, orders, _, _ in glyphs:
        if len(points) != len(orders) or any(code not in (1, 5) for code in orders):
            raise AssertionError(
                "fixed WAVE fixture no longer has polygon-only outlines"
            )
        first = True
        for (x, y), code in zip(points, orders, strict=True):
            y += baseline
            px = 430 + x + amplitude * weight * sin(y * 0.08 + time * 11 + phase_x)
            py = 280 + y + amplitude * weight * sin(x * 0.06 + time * 9 + phase_y)
            commands.append(f"{'m' if first else 'l'} {px:.6f} {py:.6f}")
            if first:
                contour_count += 1
            first = code == 5
        if not first:
            raise AssertionError("native glyph contour was not closed")
    if contour_count != 5:
        raise AssertionError("WAVE must retain four outer contours and A's hole")
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            text=r"{\an7\pos(0,0)\p1\1c&HFFFF00&}" + " ".join(commands),
        )
    )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    compiled = build().compile()
    script = compiled.document.dumps()
    interval = max(item.sample_interval or 0 for item in compiled.objects)
    if interval > 0.020000001 or compiled.max_time_quantization > 1e-9:
        raise AssertionError(
            "analytic time bound requires the declared 20ms exact grid"
        )
    (output / "E07.ass").write_text(script)
    intervals = static_intervals(script)
    times = sorted(
        {
            *range(0, 5000, 100),
            *(int(item["start_ms"]) for item in intervals if item["start_ms"] < 5000),
            999,
            1000,
            1001,
            3999,
            4000,
            4001,
            4999,
        }
    )
    checks = []
    sheet = Image.new("RGB", (1200, 330), "#141824")
    for ms in times:
        plain = reference(ms)
        actual, expected = mask(script, ms), mask(plain, ms)
        checks.append({"time_ms": ms, **compare(actual, expected)})
        if ms in (1500, 2500, 3500):
            column = (1500, 2500, 3500).index(ms)
            crop = (410, 290, 770, 410)
            for row, (name, frame) in enumerate(
                (
                    ("actual", actual),
                    ("reference", expected),
                    ("difference", ImageChops.difference(actual, expected)),
                )
            ):
                sheet.paste(
                    frame.crop(crop).resize((300, 100)), (column * 400, row * 110 + 10)
                )
                ImageDraw.Draw(sheet).text(
                    (column * 400, row * 110), f"{ms}ms {name}", fill="white"
                )
            (output / f"reference-{ms}.ass").write_text(plain)
    # Omitting the deformation must fail even though font and position match.
    try:
        compare(mask(script, 2500), mask(reference(2500, amplitude=0), 2500))
    except AssertionError:
        pass
    else:
        raise AssertionError("oracle failed to detect missing ripple")
    sheet.save(output / "outline-motion-reference.png")
    report = {
        "scope": "E07 all polygon vertices and hole against native font outlines plus independent scalar sine perturbation; no scene/path animation evaluator reused",
        "font_sha256": font.sha256,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "seed": 17,
        "amplitude_px": 4,
        "contours": 5,
        "sampling": "20ms midpoint held; 1s/4s envelope boundaries",
        "checks": checks,
        "missing_ripple_fault_rejected": True,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "continuous_geometry_bound": {
            "max_position_error_px": hypot(4 * (pi / 3 + 11), 4 * (pi / 3 + 9)) * 0.01,
            "derivation": "envelope derivative <= pi/3; vertex x speed <=4*(pi/3+11), y speed <=4*(pi/3+9); midpoint age error <=0.01s; line segments are convex combinations of corresponding vertices",
            "excludes": "rasterization, font outline approximation, and time outside the half-open visible lifetime",
        },
        "remaining": [
            "other fonts or renderers",
        ],
    }
    (output / "outline-motion-validation.json").write_text(
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
