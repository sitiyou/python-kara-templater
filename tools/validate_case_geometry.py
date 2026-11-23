"""Independent native-text silhouettes for E05 assembly and E07 restoration.

uv run python -m tools.validate_case_geometry OUTPUT
References use hand-authored text ASS, never Scene or text_to_path. Checks cover
settled geometry and exact lifetime boundaries, not the animated path between.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from examples.scene_fragments import build as fragments
from examples.scene_outlines import build as outlines
from kara_templater import Document, Line, Style, _ass_preview, load_font
from tools.validate_engine_backgrounds import ROOT, SIZE


def mask(script: str, ms: int) -> Image.Image:
    result = Image.new("L", SIZE)
    for left, top, width, height, kind, color, coverage in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind != 0 or not width or not height:
            continue
        if color & 255:
            raise AssertionError("reference comparison requires opaque fill")
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), coverage), (left, top))
        result = ImageChops.lighter(result, tile)
    return result


def reference(case: str) -> str:
    document = Document.create(
        styles=(
            Style(
                fontname="DejaVu Sans",
                fontsize=150 if case == "E05" else 120,
                align=7,
                outline=0,
                shadow=0,
            ),
        )
    )
    word = "KARA" if case == "E05" else "WAVE"
    line = Line(text=rf"{{\pos(430,280)}}{word}", start_time=0, end_time=5000)
    document.records.append(line)
    if case == "E05":
        # Center the native ink bounding box independently of path_bounds.
        box = mask(document.dumps(), 0).getbbox()
        if box is None:
            raise AssertionError("empty native ink reference")
        x = 430 + 640 - (box[0] + box[2]) / 2
        y = 280 + 360 - (box[1] + box[3]) / 2
        line.text = rf"{{\pos({x},{y})}}{word}"
    return document.dumps()


def compare(actual: Image.Image, expected: Image.Image) -> dict[str, float | int]:
    # Symmetric one-pixel Chebyshev tolerance at the half-coverage silhouette.
    a = actual.point(lambda value: 255 if value >= 128 else 0)
    b = expected.point(lambda value: 255 if value >= 128 else 0)
    unmatched = ImageChops.lighter(
        ImageChops.subtract(a, b.filter(ImageFilter.MaxFilter(3))),
        ImageChops.subtract(b, a.filter(ImageFilter.MaxFilter(3))),
    )
    if unmatched.getbbox() is not None:
        raise AssertionError("native text / path silhouette differs by more than 1 px")
    differences = ImageChops.difference(actual, expected).histogram()
    mass = sum(value * count for value, count in enumerate(expected.histogram()))
    return {
        "silhouette_pixels_outside_one_pixel_tolerance": 0,
        "max_coverage_difference": max(i for i, n in enumerate(differences) if n),
        "coverage_l1_over_reference_mass": sum(i * n for i, n in enumerate(differences))
        / mass,
    }


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    face = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    results = []
    for case, factory, times in (
        ("E05", fragments, (1600, 1601, 2500, 4990, 4999)),
        ("E07", outlines, (0, 1, 990, 999, 1000, 4000, 4001, 4500, 4999)),
    ):
        script = factory().compile().document.dumps()
        plain = reference(case)
        (output / f"{case}.ass").write_text(script)
        (output / f"{case}-native-reference.ass").write_text(plain)
        expected = mask(plain, 0)
        # Fault injection ensures this oracle detects missing ink and drift;
        # it must not pass merely because a bounding rectangle still overlaps.
        rejected = []
        for fault, altered in (
            ("missing ink", Image.new("L", SIZE)),
            ("three-pixel horizontal drift", ImageChops.offset(expected, 3, 0)),
        ):
            try:
                compare(altered, expected)
            except AssertionError:
                rejected.append(fault)
            else:
                raise AssertionError(f"geometry oracle accepted {fault}")
        expected.save(output / f"{case}-reference.png")
        checks = []
        for ms in times:
            actual = mask(script, ms)
            checks.append({"time_ms": ms, **compare(actual, expected)})
            if ms == times[0]:
                actual.save(output / f"{case}-actual.png")
                ImageChops.difference(actual, expected).save(
                    output / f"{case}-difference.png"
                )
        for ms in (5000, 5001, 5010):
            if mask(script, ms).getbbox() is not None:
                raise AssertionError(f"{case}: ink remains at {ms}ms")
        result = {
            "case": case,
            "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
            "reference_sha256": hashlib.sha256(plain.encode()).hexdigest(),
            "checks": checks,
            "fault_injections_rejected": rejected,
            "blank_times_ms": [5000, 5001, 5010],
        }
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {
        "scope": "E05 settled assembly / E07 undeformed and restored outlines vs independently authored native text; integer-ms native libass clock",
        "resolution": SIZE,
        "font_sha256": face.sha256,
        "font_family": face.family,
        "geometry_tolerance": "symmetric one-pixel Chebyshev distance at coverage >=128",
        "edge_policy": "coverage differences reported separately; native hinted text and unhinted paths need not be pixel-identical",
        "results": results,
        "remaining": [
            "animated intermediate geometry",
            "other cases",
            "other renderers",
        ],
    }
    (output / "case-geometry-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
