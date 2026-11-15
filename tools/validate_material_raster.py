"""Validate pre-blur material selection and bounded ASS encoding on real glyphs.

This is a backend prototype, not the Track integration. Retains the source mask,
RGBA reference, ASS, native roundtrip, and independently rendered black/white PNGs.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageChops

from examples._lyrics import document
from kara_templater import (
    BLUE,
    RED,
    WHITE,
    DisplayWindow,
    Line,
    Region,
    _metrics,
    load_font,
)
from kara_templater._material_raster import CoverageMask, MaterialBand, paint_coverage
from kara_templater._raster import RasterBudget, RasterCanvas, encode_frame, rasterize


def source_document(text):
    source = document(fontname="DejaVu Sans", text="AB")
    source.records = [
        record for record in source.records if not isinstance(record, Line)
    ]
    source.styles["Default"].outline = 0
    # Compare RGBA directly, without ASS/FFmpeg TV-range color conversion.
    source.records.insert(1, "YCbCr Matrix: None")
    if text:
        source.records.append(Line(text=text, start_time=0, end_time=1000))
    return source


def mask_of(text):
    images = _metrics.rasterize(
        source_document(text).dumps(), 500, 640, 480, 4_000_000, 1000
    )
    left, top = min(i[0] for i in images), min(i[1] for i in images)
    right, bottom = max(i[0] + i[2] for i in images), max(i[1] + i[3] for i in images)
    canvas = RasterCanvas(right - left, bottom - top)
    for x, y, width, height, kind, color, data in images:
        canvas.over((x - left, y - top, width, height, kind, color, data))
    return CoverageMask(
        left, top, right - left, bottom - top, canvas.finish().rgba[3::4]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    glyph = r"{\an5\pos(320,240)\fs72\bord0\shad0\blur0\1c&HFFFFFF&}AB"
    body = mask_of(glyph)
    glow = mask_of(glyph.replace(r"\bord0", r"\bord8\3c&HFFFFFF&"))
    Image.frombytes("L", (glow.width, glow.height), glow.data).save(
        output / "coverage.png"
    )
    canvas = RasterCanvas(640, 480)
    start = perf_counter()
    for mask, radius, before, after, opacity in (
        (glow, 16, RED, BLUE, 0.8),
        (body, 0, WHITE, BLUE, 1),
    ):
        left, top, frame = paint_coverage(
            mask,
            (
                MaterialBand(Region(mask.left, 320), after, opacity),
                MaterialBand(Region(320, mask.left + mask.width), before, opacity),
            ),
            blur_radius=radius,
        )
        canvas.over_frame(frame, left, top)
    composed = canvas.finish(opacity=0.65)
    compose_seconds = perf_counter() - start
    reference = Image.frombytes("RGBA", (640, 480), composed.rgba)
    reference.save(output / "reference.png")
    start = perf_counter()
    budget = RasterBudget(max_events=50_000, max_images=50_000)
    events = encode_frame(composed, DisplayWindow(0, 1000), budget=budget)
    encode_seconds = perf_counter() - start
    source = source_document("")
    source.records.extend(events)
    source.save(output / "material.ass")
    start = perf_counter()
    restored = rasterize(source.dumps(), 500, (640, 480), budget=budget)
    native_seconds = perf_counter() - start
    assert restored == composed, "native RGBA roundtrip changed the material frame"
    native = Image.frombytes("RGBA", (640, 480), restored.rgba)
    native.save(output / "native.png")
    comparisons = {}
    for background in ("black", "white"):
        base = Image.new("RGBA", (640, 480), background)
        expected = Image.alpha_composite(base, reference).convert("RGB")
        expected.save(output / f"reference-{background}.png")
        start = perf_counter()
        process = subprocess.run(
            [
                "ffmpeg",
                "-filter_threads",
                "1",
                "-hide_banner",
                "-loglevel",
                "info",
                "-f",
                "lavfi",
                "-i",
                f"color=c={background}:s=640x480:d=1,format=rgba",
                "-vf",
                "subtitles=material.ass:fontsdir=fonts",
                "-frames:v",
                "1",
                "-y",
                f"ffmpeg-{background}.png",
            ],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed = perf_counter() - start
        (output / f"ffmpeg-{background}.log").write_text(process.stderr)
        process.check_returncode()
        actual = Image.open(output / f"ffmpeg-{background}.png").convert("RGB")
        difference = ImageChops.difference(expected, actual)
        difference.save(output / f"difference-{background}.png")
        values = difference.tobytes()
        comparisons[background] = {
            "max_channel_error": max(values),
            "mean_channel_error": sum(values) / len(values),
            "renderer_seconds": elapsed,
        }
    report = {
        "font_sha256": registered.sha256,
        "ycbcr_matrix": "None",
        "events": len(events),
        "event_budget": budget.max_events,
        "ass_bytes": (output / "material.ass").stat().st_size,
        "compose_seconds": compose_seconds,
        "encode_seconds": encode_seconds,
        "native_render_seconds": native_seconds,
        "native_roundtrip_max_error": 0,
        "rgba_sha256": hashlib.sha256(composed.rgba).hexdigest(),
        "external_render": comparisons,
        "scope": "Single-frame body/glow with common blur per component; Track binding and varying blur materials remain pending.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
