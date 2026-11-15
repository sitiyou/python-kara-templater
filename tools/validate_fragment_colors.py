"""E05 four-background interior compositing against independent moving cuts.

uv run python -m tools.validate_fragment_colors OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from examples.scene_fragments import build
from kara_templater import Document, _metrics, load_font
from tools.validate_case_geometry import reference as settled_reference
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT, SIZE, backgrounds, preview
from tools.validate_fragments import contours, reference
from tools.validate_particle_composite import finish, over

INDICES = (
    0,
    2,
    3,
    5,
    7,
    8,
    10,
    12,
    13,
    15,
    17,
    18,
    20,
    25,
    27,
    28,
    30,
    35,
    40,
    47,
    48,
    50,
    65,
    80,
    100,
    120,
    140,
    159,
    160,
    161,
    250,
    499,
    500,
)


def masks(script: str, ms: int) -> tuple[Image.Image, Image.Image, Image.Image]:
    edges = Image.new("L", SIZE)
    count = Image.new("L", SIZE)
    fading = Image.new("L", SIZE)
    for x, y, width, height, _, color, data in _metrics.rasterize(
        script, ms, *SIZE, 4_000_000, 10000
    ):
        if not width or not height:
            continue
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (x, y))
        # Include hard aligned edges as well as partially covered pixels.
        edge = ImageChops.subtract(
            tile.filter(ImageFilter.MaxFilter(3)), tile.filter(ImageFilter.MinFilter(3))
        )
        edges = ImageChops.lighter(edges, edge.point(lambda v: 255 if v else 0))
        solid = tile.point(lambda v: 1 if v == 255 else 0)
        count = ImageChops.add(count, solid)
        if 0 < color & 255 < 255:
            fading = ImageChops.lighter(fading, solid.point(lambda v: v * 255))
    overlap = count.point(lambda v: 255 if v >= 2 else 0)
    return edges, overlap, ImageChops.darker(overlap, fading)


def maximum(image: Image.Image) -> int:
    return max(i % 256 for i, count in enumerate(image.histogram()) if count)


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font_path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(font_path.read_bytes())
    compiled = build().compile()
    script = compiled.document.dumps()
    (output / "scene.ass").write_text(script)
    intervals = static_intervals(script)
    shapes = contours()
    refs: dict[int, str] = {}
    comparisons: dict[int, tuple[Image.Image, Image.Image, Image.Image]] = {}
    for index in INDICES:
        ms = index * 10 + 1
        if ms < 1600:
            doc = Document.parse(reference(0, ms, shapes))
            for piece in range(1, 12):
                doc.records.extend(Document.parse(reference(piece, ms, shapes)).lines)
        else:
            doc = Document.parse(settled_reference("E05"))
            for line in doc.lines:
                line.text = line.text.replace("}", r"\1c&HFFFF00&}", 1)
        refs[index] = doc.dumps()
        (output / f"reference-{index}.ass").write_text(refs[index])
        a, overlap_a, fade_a = masks(script, ms)
        b, overlap_b, fade_b = masks(refs[index], ms)
        comparisons[index] = (
            ImageChops.lighter(a, b),
            ImageChops.darker(overlap_a, overlap_b),
            ImageChops.darker(fade_a, fade_b),
        )
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 720))
    fault_detected = False
    for name in hashes:
        frames = preview(output, name, "scene.ass", INDICES)
        for index, actual in zip(INDICES, frames, strict=True):
            ms = index * 10 + 1
            with Image.open(output / (name + ".png")) as background:
                channels = tuple(
                    c.convert("F") for c in background.convert("RGB").split()
                )
            over(channels, refs[index], ms)
            expected = finish(channels)
            difference = ImageChops.difference(actual, expected)
            edges, overlap, fading_overlap = comparisons[index]
            interior = difference.copy()
            interior.paste((0, 0, 0), (0, 0), edges)
            error = maximum(interior)
            if error > 2:
                raise AssertionError(
                    f"interior composite differs by {error} at {ms}ms on {name}"
                )
            overlap = ImageChops.subtract(overlap, edges)
            fading_overlap = ImageChops.subtract(fading_overlap, edges)
            checks.append(
                {
                    "time_ms": ms,
                    "background": name,
                    "max_interior_rgb_difference": error,
                    "max_whole_frame_rgb_difference": maximum(difference),
                    "overlap_interior_pixels": overlap.histogram()[255],
                    "fading_overlap_interior_pixels": fading_overlap.histogram()[255],
                }
            )
            if name == "black" and index == 10:
                wrong = Document.parse(refs[index])
                wrong.records.remove(wrong.lines[0])
                channels = tuple(Image.new("F", SIZE) for _ in range(3))
                over(channels, wrong.dumps(), ms)
                diff = ImageChops.difference(actual, finish(channels))
                diff.paste((0, 0, 0), (0, 0), edges)
                fault_detected = maximum(diff) > 2
                assert fault_detected, "missing fragment not detected"
            if name == "checker" and index in (10, 30, 100, 160):
                row = (10, 30, 100, 160).index(index)
                for col, picture in enumerate(
                    (actual, expected, difference.point(lambda v: min(255, v * 8)))
                ):
                    sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
        print(f"{name}: passed", flush=True)
    assert any(c["fading_overlap_interior_pixels"] for c in checks), (
        "no translucent overlap was compared"
    )
    sheet.save(output / "fragment-colors.png")
    renderer = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-f",
            "lavfi",
            "-i",
            "color=s=1280x720:d=0.01",
            "-vf",
            "ass=scene.ass:fontsdir=fonts",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=True,
    )
    report = {
        "scope": "E05 independent dense clipped contours and scalar motion/alpha, native settled text, float source-over vs actual FFmpeg RGB; all per-fragment geometry edges excluded from interior criterion and full-frame differences reported separately",
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "font_sha256": font.sha256,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": {
            str(i): hashlib.sha256(ref.encode()).hexdigest() for i, ref in refs.items()
        },
        "checks": checks,
        "static_intervals": intervals,
        "missing_fragment_detected": fault_detected,
        "remaining": ["continuous ideal motion error", "other renderers"],
    }
    (output / "fragment-colors-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
