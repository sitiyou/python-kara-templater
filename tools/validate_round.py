"""E03 analytic arc and single-transform ruby reference, bypassing layout_path.

uv run python -m tools.validate_round OUTPUT
"""

import argparse
import hashlib
import json
from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from examples.scene_round import build
from kara_templater import Document, Line, Style, _ass_preview, load_font
from tools.validate_case_geometry import compare, mask
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT


def reference(ms: int, family: str, *, double_ruby_scale: bool = False) -> str:
    document = Document.create(styles=(Style(align=5, outline=0, shadow=0),))
    if ms >= 5000:
        return document.dumps()
    for index, character in enumerate("時々時々時々"):
        progress = 0.0
        for start in (1000 + index * 250, 3000 + index * 150):
            end = start + 250
            if start <= ms < end:
                sample = (max(start, ms // 20 * 20) + min(end, (ms // 20 + 1) * 20)) / 2
                progress = (sample - start) / 250
        scale = 1 + 0.12 * progress
        angle = -160 + 140 * (index + 0.5) / 6
        tangent = angle + 90
        x, y = 640 + 240 * cos(radians(angle)), 470 + 240 * sin(radians(angle))
        green, blue = round(255 - 63 * progress), round(255 - 52 * progress)
        for text, font, size, offset in (
            (character, family, 64, 0),
            ("toki" if character == "時" else "doki", "DejaVu Sans", 20, -52),
        ):
            factor = scale * scale if offset and double_ruby_scale else scale
            px = x - offset * factor * sin(radians(tangent))
            py = y + offset * factor * cos(radians(tangent))
            document.records.append(
                Line(
                    start_time=0,
                    end_time=5000,
                    text=rf"{{\an5\fn{font}\fs{size}\pos({px:.6f},{py:.6f})\frz{-tangent:.6f}\fscx{factor * 100:.6f}\fscy{factor * 100:.6f}\1c&H{blue:02X}{green:02X}FF&}}{text}",
                )
            )
    return document.dumps()


def colored_fill(script: str, ms: int) -> tuple[Image.Image, Image.Image]:
    color_plane = Image.new("RGB", (1280, 720))
    coverage = Image.new("L", (1280, 720))
    for left, top, width, height, kind, color, data in _ass_preview.rasterize(
        script, ms, 1280, 720, 4_000_000, 10_000
    ):
        if kind != 0 or not width or not height:
            continue
        if color & 255:
            raise AssertionError("round reference requires opaque fills")
        tile = Image.frombytes("L", (width, height), data)
        rgb = tuple((color >> shift) & 255 for shift in (24, 16, 8))
        color_plane.paste(Image.new("RGB", tile.size, rgb), (left, top), tile)
        full = Image.new("L", coverage.size)
        full.paste(tile, (left, top))
        coverage = ImageChops.lighter(coverage, full)
    return color_plane, coverage


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    latin = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    cjk = load_font(ROOT / "tests/fonts/KaraTestCJK.ttf")
    compiled = build().compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    (output / "E03.ass").write_text(script)
    boundaries = {
        value
        for i in range(6)
        for start in (1000 + i * 250, 3000 + i * 150)
        for value in (start, start + 250)
    }
    times = sorted(
        {
            *range(0, 5000, 100),
            *(int(item["start_ms"]) for item in intervals if item["start_ms"] < 5000),
            *(value + delta for value in boundaries for delta in (-1, 0, 1)),
            4999,
        }
    )
    checks = []
    sheet = Image.new("RGB", (1200, 450), "#141824")
    for ms in times:
        plain = reference(ms, cjk.family)
        actual, expected = mask(script, ms), mask(plain, 0)
        actual_rgb, actual_coverage = colored_fill(script, ms)
        expected_rgb, expected_coverage = colored_fill(plain, 0)
        interior = (
            ImageChops.darker(actual_coverage, expected_coverage)
            .filter(ImageFilter.MinFilter(3))
            .point([0] * 255 + [255])
        )
        pixel_count = interior.histogram()[255]
        if not pixel_count:
            raise AssertionError(f"empty color reference at {ms}ms")
        delta = ImageChops.difference(actual_rgb, expected_rgb)
        checked = Image.new("RGB", delta.size)
        checked.paste(delta, (0, 0), interior)
        error = max(i % 256 for i, count in enumerate(checked.histogram()) if count)
        if error > 2:
            raise AssertionError(
                f"round interior color mismatch at {ms}ms: {error}/255"
            )
        checks.append(
            {
                "time_ms": ms,
                **compare(actual, expected),
                "interior_color_pixels": pixel_count,
                "max_interior_rgb_error": error,
            }
        )
        if ms in (0, 1200, 3200):
            column = (0, 1200, 3200).index(ms)
            crop = (320, 130, 960, 500)
            sheet.paste(actual.crop(crop).resize((200, 116)), (column * 400, 24))
            sheet.paste(
                expected.crop(crop).resize((200, 116)), (column * 400 + 200, 24)
            )
            sheet.paste(
                ImageChops.difference(actual, expected).crop(crop).resize((400, 232)),
                (column * 400, 160),
            )
            ImageDraw.Draw(sheet).text(
                (column * 400 + 5, 5),
                f"{ms}ms actual / reference; difference below",
                fill="white",
            )
            (output / f"reference-{ms}.ass").write_text(plain)
    # Verify that this tolerance rejects the original architectural failure mode.
    wrong = mask(reference(1249, cjk.family, double_ruby_scale=True), 0)
    try:
        compare(mask(script, 1249), wrong)
    except AssertionError:
        pass
    else:
        raise AssertionError("double ruby scaling was not detected")
    for ms in (5000, 5001):
        if mask(script, ms).getbbox() is not None:
            raise AssertionError(f"E03 remains at {ms}ms")
    sheet.save(output / "round-reference.png")
    report = {
        "scope": "E03 six equal-advance glyphs on analytic radius-240 arc; tangent alignment and ruby offset/scale applied once, with both repeated 250ms pulses",
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "font_sha256": [latin.sha256, cjk.sha256],
        "geometry_tolerance": "symmetric one-pixel Chebyshev distance at coverage >=128; analytic circle reference vs one-degree polyline implementation",
        "checks": checks,
        "double_ruby_scale_fault_rejected": True,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "blank_times_ms": [5000, 5001],
        "remaining": [
            "continuous-time sampling error",
            "other renderers",
        ],
    }
    (output / "round-validation.json").write_text(json.dumps(report, indent=2) + "\n")
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
