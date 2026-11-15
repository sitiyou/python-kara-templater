"""E11 complete soft sweep against scalar colors and handwritten native ASS.

uv run python -m tools.validate_soft_sweep OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_sweep import build
from kara_templater import Document, Line, Style, load_font
from tools.validate_case_colors import expected
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT, backgrounds, preview


def reference(*, glow: bool = True) -> str:
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=108, align=5, outline=3, shadow=0),
        )
    )
    if glow:
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                layer=-1,
                text=r"{\pos(640,340)\1c&HCBC0FF&\3c&HCBC0FF&\bord7\blur9\alpha&H66&}SOFT SWEEP",
            )
        )
    boundaries = (0, *range(1000, 4001, 20), 5000)
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        colors = [
            (expected("E11", "fill", x, start), expected("E11", "outline", x, start))
            for x in range(1280)
        ]
        left = 0
        for right in range(1, 1281):
            if right < 1280 and colors[right] == colors[left]:
                continue
            fill, outline = colors[left]
            a = f"&H{fill[2]:02X}{fill[1]:02X}{fill[0]:02X}&"
            b = f"&H{outline[2]:02X}{outline[1]:02X}{outline[0]:02X}&"
            document.records.append(
                Line(
                    start_time=start,
                    end_time=end,
                    text=rf"{{\pos(640,340)\clip({left},0,{right},720)\1c{a}\3c{b}}}SOFT SWEEP",
                )
            )
            left = right
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(path.read_bytes())
    compiled = build().compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    indices = tuple(
        sorted(
            {
                0,
                99,
                100,
                150,
                250,
                350,
                399,
                400,
                499,
                500,
                *(int(i["start_ms"]) // 10 for i in intervals),
            }
        )
    )
    target = reference()
    (output / "scene.ass").write_text(script)
    (output / "reference.ass").write_text(target)
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 720))
    for name in hashes:
        for offset in range(0, len(indices), 24):
            batch = indices[offset : offset + 24]
            actual_frames = preview(output, name, "scene.ass", batch)
            target_frames = preview(output, name, "reference.ass", batch)
            for index, actual, wanted in zip(
                batch, actual_frames, target_frames, strict=True
            ):
                diff = ImageChops.difference(actual, wanted)
                error = max(i % 256 for i, n in enumerate(diff.histogram()) if n)
                assert error <= 2, (name, index, error)
                checks.append(
                    {
                        "time_ms": index * 10 + 1,
                        "background": name,
                        "max_rgb_difference": error,
                    }
                )
                if name == "checker" and index in (100, 150, 250, 350):
                    row = (100, 150, 250, 350).index(index)
                    for col, picture in enumerate(
                        (actual, wanted, diff.point(lambda v: min(255, v * 8)))
                    ):
                        sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
        print(name + ": passed", flush=True)
    (output / "wrong.ass").write_text(reference(glow=False))
    a = preview(output, "black", "scene.ass", (250,))[0]
    b = preview(output, "black", "wrong.ass", (250,))[0]
    assert (
        max(i % 256 for i, n in enumerate(ImageChops.difference(a, b).histogram()) if n)
        > 2
    )
    sheet.save(output / "soft-sweep.png")
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
        "scope": "E11 all emitted states: independent per-column fill/outline RGB with 24/36px widths, handwritten unsliced constant whole-word glow, same FFmpeg/libass; complete RGB frames",
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "font_sha256": font.sha256,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": hashlib.sha256(target.encode()).hexdigest(),
        "checks": checks,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "missing_glow_detected": True,
        "remaining": [
            "continuous ideal sweep error",
            "alternative glow diffusion/raster strategies",
            "other renderers",
        ],
    }
    (output / "soft-sweep-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
