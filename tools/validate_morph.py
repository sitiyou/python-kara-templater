"""E10 ring morph against independent analytic-circle / square polygons.

uv run python -m tools.validate_morph OUTPUT
The reference bypasses VectorPath, resample_path, MorphPath and Scene lowering.
"""

import argparse
import hashlib
import json
from math import cos, sin, tau
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from examples.scene_morph import build
from kara_templater import (
    Document,
    Line,
    MorphPath,
    PathObject,
    Style,
    Vec2,
    VectorPath,
    load_font,
    smooth_rate,
)
from kara_templater.geometry import CubicSegment
from tools.validate_case_geometry import compare, mask
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT


def square(radius: float, progress: float) -> tuple[float, float]:
    vertices = (
        (radius, 0),
        (radius, radius),
        (-radius, radius),
        (-radius, -radius),
        (radius, -radius),
        (radius, 0),
    )
    distance = progress * 8 * radius
    for a, b in zip(vertices, vertices[1:], strict=False):
        length = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if distance <= length:
            fraction = distance / length
            return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
        distance -= length
    return vertices[-1]


def progress(ms: int) -> float:
    sample = ms // 20 * 20 + 10 if 1000 <= ms < 4000 else ms
    p = max(0, min(1, (sample - 1000) / 3000))
    return p * p * (3 - 2 * p)


def reference(ms: int) -> str:
    p = progress(ms)
    contours = []
    for radius, direction in ((100, 1), (40, -1)):
        points = []
        for i in range(64):
            fraction = i / 64
            x, y = radius * cos(tau * fraction), radius * sin(tau * fraction)
            tx, ty = square(radius, fraction)
            points.append(
                (440 + direction * (x + (tx - x) * p), 350 + y + (ty - y) * p)
            )
        contours.append("m " + " l ".join(f"{x:.6f} {y:.6f}" for x, y in points))
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    document.records.append(
        Line(
            start_time=0, end_time=5000, text=r"{\an7\pos(0,0)\p1}" + " ".join(contours)
        )
    )
    return document.dumps()


def color_reference(ms: int) -> str:
    """Analytic ring plus native B with the independently specified affine map."""
    document = Document.parse(reference(ms))
    for line in document.lines:
        line.text = line.text.replace("}", r"\1c&HFFFF00&}", 1)
    p = progress(ms)
    sx, sy = 1 + 0.5 * p, 1 - 0.25 * p
    shear = 0.12 * p / sx
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            text=rf"{{\an7\fnDejaVu Sans\fs180\pos(730,260)\fscx{sx * 100:.6f}\fscy{sy * 100:.6f}\fax{shear:.6f}\1c&HCBC0FF&}}B",
        )
    )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    face = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    scene = build()
    compiled = scene.compile()
    if (
        max(item.sample_interval or 0 for item in compiled.objects) > 0.020000001
        or compiled.max_time_quantization > 1e-9
    ):
        raise AssertionError("time bound requires an exact 20ms midpoint grid")

    def controls(path: VectorPath) -> tuple[Vec2, ...]:
        values: list[Vec2] = []
        for contour in path.contours:
            values.append(contour.start)
            for segment in contour.segments:
                if isinstance(segment, CubicSegment):
                    values.extend((segment.control1, segment.control2))
                values.append(segment.end)
        return tuple(values)

    bounds = {}
    for node in scene.objects:
        assert isinstance(node, PathObject) and isinstance(node.deform, MorphPath)
        assert (
            node.deform.rate is smooth_rate
            and node.deform.start == 1
            and node.deform.duration == 3
        )
        assert not node.animations and node.reference is None
        assert (
            node.state.scale == Vec2(1, 1)
            and node.state.rotation == 0
            and node.state.skew == Vec2()
        )
        displacement = max(
            (b - a).length
            for a, b in zip(
                controls(node.path), controls(node.deform.target), strict=True
            )
        )
        bounds[node.id] = {
            "max_control_displacement_px": displacement,
            "max_position_error_px": displacement * 1.5 / 3 * 0.01,
        }

    script = compiled.document.dumps()
    intervals = static_intervals(script)
    (output / "E10.ass").write_text(script)
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
    glyph_doc = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=180, align=7, outline=0, shadow=0),
        )
    )
    glyph_doc.records.append(
        Line(start_time=0, end_time=5000, text=r"{\pos(730,260)}B")
    )
    (output / "glyph-native-reference.ass").write_text(glyph_doc.dumps())
    glyph = mask(glyph_doc.dumps(), 0)
    checks = []
    glyph_checks = []
    native_color_glyph_checks = []
    sheet = Image.new("RGB", (1200, 800), "#141824")
    crop = (240, 150, 640, 550)
    for ms in times:
        plain = reference(ms)
        actual = mask(script, ms).crop(crop)
        expected = mask(plain, ms).crop(crop)
        if actual.getpixel((200, 200)) != 0:
            raise AssertionError(f"hole filled at {ms}ms")
        checks.append({"time_ms": ms, **compare(actual, expected)})
        p = progress(ms)
        sx, sy, shear = 1 + 0.5 * p, 1 - 0.25 * p, 0.12 * p
        # Inverse affine mapping of independently rendered native text coverage.
        transformed = glyph.transform(
            glyph.size,
            Image.Transform.AFFINE,
            (
                1 / sx,
                -shear / (sx * sy),
                730 - 730 / sx + shear * 260 / (sx * sy),
                0,
                1 / sy,
                260 - 260 / sy,
            ),
            resample=Image.Resampling.BICUBIC,
        )
        glyph_crop = (680, 200, 1100, 500)
        glyph_actual = mask(script, ms).crop(glyph_crop)
        glyph_expected = transformed.crop(glyph_crop)
        glyph_checks.append({"time_ms": ms, **compare(glyph_actual, glyph_expected)})
        native_color_glyph_checks.append(
            {
                "time_ms": ms,
                **compare(glyph_actual, mask(color_reference(ms), ms).crop(glyph_crop)),
            }
        )
        if ms in (0, 2500, 4000):
            column = (0, 2500, 4000).index(ms)
            sheet.paste(actual.resize((200, 200)), (column * 400, 24))
            sheet.paste(expected.resize((200, 200)), (column * 400 + 200, 24))
            sheet.paste(
                ImageChops.difference(actual, expected).resize((200, 200)),
                (column * 400, 224),
            )
            ImageDraw.Draw(sheet).text(
                (column * 400 + 5, 5),
                f"{ms}ms: actual / reference; difference below",
                fill="white",
            )
            sheet.paste(glyph_actual.resize((200, 143)), (column * 400, 448))
            sheet.paste(glyph_expected.resize((200, 143)), (column * 400 + 200, 448))
            sheet.paste(
                ImageChops.difference(glyph_actual, glyph_expected).resize((200, 143)),
                (column * 400, 620),
            )
            ImageDraw.Draw(sheet).text(
                (column * 400 + 5, 428),
                "B: actual / affine native reference; difference below",
                fill="white",
            )
            (output / f"reference-{ms}.ass").write_text(plain)
    for ms in (5000, 5001, 5010):
        if mask(script, ms).getbbox() is not None:
            raise AssertionError(f"E10 remains visible at {ms}ms")
    # A filled hole must fail even if the outer bounding box is unchanged.
    expected = mask(reference(4999), 4999).crop(crop)
    broken = expected.copy()
    ImageDraw.Draw(broken).rectangle((185, 185, 215, 215), fill=255)
    try:
        compare(broken, expected)
    except AssertionError:
        pass
    else:
        raise AssertionError("oracle failed to detect a filled hole")
    sheet.save(output / "morph-reference.png")
    report = {
        "scope": "E10 ring vs independent analytic-circle / square interpolation; glyph B vs inverse affine transform of independently rendered native text",
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "font_sha256": face.sha256,
        "geometry_tolerance": "symmetric one-pixel Chebyshev distance at coverage >=128",
        "sampling": "20 ms midpoint hold during 1-4s; cubic smoothstep computed independently",
        "checks": checks,
        "glyph_checks": glyph_checks,
        "native_color_glyph_checks": native_color_glyph_checks,
        "blank_times_ms": [5000, 5001, 5010],
        "filled_hole_fault_rejected": True,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "continuous_geometry_bounds": bounds,
        "bound_derivation": "actual fixed source/target control polygons; smoothstep maximum derivative 1.5 over 3s, midpoint age <=0.01s; lines and cubic Beziers are convex combinations of corresponding controls. Excludes font/source approximation, rasterization and lifetime discontinuities.",
        "remaining": [
            "glyph antialias reconstruction differs from direct path rasterization",
            "other renderers",
        ],
    }
    (output / "morph-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_edge_difference": max(
                    c["max_coverage_difference"] for c in checks
                ),
                "max_relative_coverage_l1": max(
                    c["coverage_l1_over_reference_mass"] for c in checks
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
