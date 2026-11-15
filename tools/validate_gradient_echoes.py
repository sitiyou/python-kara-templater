"""E09 per-letter colors and delayed echoes against handwritten native ASS.

uv run python -m tools.validate_gradient_echoes OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops

from examples.scene_gradient import build
from kara_templater import Document, Line, Scene, Style, load_font
from tools.validate_case_colors import expected as gradient_color
from tools.validate_engine_backgrounds import ROOT, backgrounds, preview

INDICES = (
    0,
    7,
    8,
    15,
    16,
    23,
    24,
    49,
    50,
    58,
    66,
    74,
    100,
    200,
    300,
    399,
    400,
    408,
    416,
    424,
    469,
    470,
    478,
    486,
    493,
    494,
    499,
    500,
)


def reference(*, omit_echo: bool = False) -> str:
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=72, align=5, outline=0, shadow=0),
        )
    )
    for i, letter in enumerate("COLOR"):
        x = 440 + i * 75
        rgb = (round(255 * i / 4), round(255 - 63 * i / 4), round(255 - 52 * i / 4))
        color = f"&H{rgb[2]:02X}{rgb[1]:02X}{rgb[0]:02X}&"
        document.records.append(
            Line(
                start_time=0,
                end_time=4700,
                text=rf"{{\move({x},470,{x + 100},470,500,4000)\1c{color}}}{letter}",
            )
        )
        for echo in range(1, 4):
            if omit_echo and echo == 1:
                continue
            delay = echo * 80
            alpha = round((1 - 0.35 * 0.7 ** (echo - 1)) * 255)
            for index in INDICES:
                ms = index * 10 + 1
                if not delay <= ms < 4700 + delay:
                    continue
                sample = ms // 20 * 20 + 10
                p = max(0, min(1, (sample - delay - 500) / 3500))
                document.records.append(
                    Line(
                        start_time=index * 10,
                        end_time=index * 10 + 10,
                        layer=-echo,
                        text=rf"{{\pos({x + 100 * p:.6f},470)\1c{color}\alpha&H{alpha:02X}&}}{letter}",
                    )
                )
    return document.dumps()


def upper_reference(*, wrong_outline: bool = False) -> str:
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=112, align=5, outline=3, shadow=0),
        )
    )
    pairs = [
        (
            gradient_color("E09", "fill", x, 0),
            gradient_color("E09", "fill" if wrong_outline else "outline", x, 0),
        )
        for x in range(1280)
    ]
    start = 0
    for end in range(1, 1281):
        if end < 1280 and pairs[end] == pairs[start]:
            continue
        fill, outline = pairs[start]
        fill_tag = f"&H{fill[2]:02X}{fill[1]:02X}{fill[0]:02X}&"
        outline_tag = f"&H{outline[2]:02X}{outline[1]:02X}{outline[0]:02X}&"
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                text=rf"{{\move(580,270,700,270,500,4500)\clip({start},0,{end},720)\1c{fill_tag}\3c{outline_tag}}}GRADIENT",
            )
        )
        start = end
    return document.dumps()


def complete_reference(*, omit_echo: bool = False) -> str:
    document = Document.parse(upper_reference())
    lower = Document.parse(reference(omit_echo=omit_echo))
    for line in lower.lines:
        line.text = line.text.replace("{", r"{\fs72\bord0", 1)
        document.records.append(line)
    return document.dumps()


def validate(
    output: Path, part: Literal["echoes", "bands", "complete"] = "echoes"
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font_path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(font_path.read_bytes())
    source = build()
    objects = (
        source.objects
        if part == "complete"
        else source.objects[1:]
        if part == "echoes"
        else source.objects[:1]
    )
    compiled = Scene(Document.create()).add(*objects).compile()
    script = compiled.document.dumps()
    expected = (
        complete_reference()
        if part == "complete"
        else reference()
        if part == "echoes"
        else upper_reference()
    )
    artifact = f"gradient-{part}"
    crop = (300, 390, 940, 550) if part == "echoes" else (180, 170, 1100, 370)
    (output / "scene.ass").write_text(script)
    (output / "reference.ass").write_text(expected)
    if part == "complete":
        crop = (180, 160, 1100, 560)
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 480))
    for name in hashes:
        actual_frames = preview(output, name, "scene.ass", INDICES)
        reference_frames = preview(output, name, "reference.ass", INDICES)
        for index, actual, target in zip(
            INDICES, actual_frames, reference_frames, strict=True
        ):
            diff = ImageChops.difference(actual, target)
            maximum = max(i % 256 for i, n in enumerate(diff.histogram()) if n)
            assert maximum <= 2, (name, index, maximum)
            checks.append(
                {
                    "time_ms": index * 10 + 1,
                    "background": name,
                    "max_rgb_difference": maximum,
                }
            )
            if name == "checker" and index in (100, 300, 470, 486):
                row = (100, 300, 470, 486).index(index)
                for col, picture in enumerate(
                    (actual, target, diff.point(lambda v: min(255, v * 8)))
                ):
                    sheet.paste(
                        picture.crop(crop).resize((320, 120)),
                        (col * 320, row * 120),
                    )
    (output / "wrong.ass").write_text(
        complete_reference(omit_echo=True)
        if part == "complete"
        else reference(omit_echo=True)
        if part == "echoes"
        else upper_reference(wrong_outline=True)
    )
    actual = preview(output, "black", "scene.ass", (470,))[0]
    wrong = preview(output, "black", "wrong.ass", (470,))[0]
    assert (
        max(
            i % 256
            for i, n in enumerate(ImageChops.difference(actual, wrong).histogram())
            if n
        )
        > 2
    )
    sheet.save(output / f"{artifact}.png")
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
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "scope": (
            "E09 complete upper gradient and lower COLOR/echo scene; independently authored native ASS"
            if part == "complete"
            else "E09 isolated COLOR row, scalar per-letter RGB and 80/160/240ms delayed midpoint echoes with independent alpha/layer formulas"
            if part == "echoes"
            else "E09 upper GRADIENT row, independent per-column fill/outline RGB with only identical adjacent pairs merged; native whole-text move and fixed screen clips"
        )
        + "; actual/reference share FFmpeg/libass",
        "font_sha256": font.sha256,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": hashlib.sha256(expected.encode()).hexdigest(),
        "checks": checks,
        "fault_detected": "missing echo"
        if part == "echoes"
        else "outline replaced with fill color",
        "remaining": [
            "complete E09 scene acceptance",
            "continuous ideal echo error",
            "other renderers",
        ],
    }
    (output / f"{artifact}-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_rgb_difference": max(c["max_rgb_difference"] for c in checks),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--part", choices=("echoes", "bands", "complete"), default="echoes"
    )
    args = parser.parse_args()
    validate(args.output, args.part)


if __name__ == "__main__":
    main()
