"""Render the layer example and retain environment/frame evidence.

Run from the repository root: python -m tools.render_effects /tmp/kara-review
Requires ffmpeg with libass and Pillow; neither is a library runtime dependency.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from examples.output_layers import build
from kara_templater import KaraokeLine, Segment, TextUnit, layout_line
from kara_templater.ass import Document, Line
from kara_templater.fonts import load_font


def render(script, destination, times):
    # Paths stay relative to cwd, so ffmpeg filter escaping is unnecessary.
    expression = "+".join(f"eq(n,{time // 10})" for time in times)
    if times and tuple(times) == tuple(range(times[0], times[-1] + 10, 10)):
        expression = f"between(n,{times[0] // 10},{times[-1] // 10})"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=640x480:r=100:d=3",
        "-vf",
        f"subtitles={script}:fontsdir=fonts,select='{expression}'",
        "-fps_mode",
        "vfr",
        "-y",
        destination,
    ]
    process = subprocess.run(
        command,
        cwd=Path(destination).parent if Path(destination).is_absolute() else None,
        check=False,
        capture_output=True,
        text=True,
    )
    Path(destination).with_suffix(".log").write_text(process.stderr)
    process.check_returncode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--text", default="Karaoke")
    parser.add_argument("--spacing", type=float, default=0)
    parser.add_argument(
        "--font",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf",
    )
    parser.add_argument("--italic", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = args.font.resolve()
    registered = load_font(font)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    script, result = build(
        args.text, spacing=args.spacing, fontname=registered.family, italic=args.italic
    )
    (output / "layers.ass").write_text(script, encoding="utf-8-sig")
    times = (500, 1000, 1250, 1500, 1750, 2000, 2200)
    render("layers.ass", str(output / "frame-%02d.png"), times)

    # Compare independently positioned glyphs with a whole-text reference.
    document = Document.parse(script)
    document.records = [r for r in document.records if not isinstance(r, Line)]
    for index in range(3):
        style = document.styles[f"Mode{index}"]
        layout = layout_line(
            KaraokeLine((TextUnit(args.text, (Segment(1000, 2000),)),)),
            style=style,
            resolution=(640, 480),
        )
        document.records.append(
            Line(
                text=rf"{{\an5\pos({layout.box.center},{layout.box.middle})\bord0\shad0\1c&HDDDDDD&}}{args.text}",
                start_time=0,
                end_time=3000,
                style=style.name,
            )
        )
    document.save(output / "reference.ass")
    render("reference.ass", str(output / "reference-%02d.png"), (500,))
    first = Image.open(output / "frame-01.png").convert("RGB")
    reference = Image.open(output / "reference-01.png").convert("RGB")
    difference = ImageChops.difference(first, reference)
    difference.save(output / "static-difference.png")
    pixels = difference.tobytes()
    maximum = max(pixels)
    changed = sum(any(pixels[i : i + 3]) for i in range(0, len(pixels), 3))
    montage = Image.new("RGB", (640 * len(times), 510))
    draw = ImageDraw.Draw(montage)
    for index, time in enumerate(times):
        with Image.open(output / f"frame-{index + 1:02d}.png") as frame:
            montage.paste(frame, (index * 640, 30))
        draw.text((index * 640 + 10, 8), f"{time} ms", fill="white")
    montage.save(output / "keyframes.png")
    manifest = {
        "text": args.text,
        "spacing": args.spacing,
        "italic": args.italic,
        "font_family": registered.family,
        "resolution": [640, 480],
        "times_ms": times,
        "events": len(result.events),
        "diagnostics": result.diagnostics,
        "font_file": str(font),
        "font_sha256": hashlib.sha256(font.read_bytes()).hexdigest(),
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True
        ).splitlines()[0],
        "libass": subprocess.check_output(
            ["pkg-config", "--modversion", "libass"], text=True
        ).strip(),
        "static_comparison": {
            "max_channel_difference": maximum,
            "changed_pixels": changed,
            "tolerance": {"max_channel_difference": 32, "changed_pixels": 500},
            "passed": maximum <= 32 and changed <= 500,
        },
        "limitations": [
            "System libass renders frames; bundled patched libass measures layout.",
            "Clip interpolation error <= 0.25 px plus integer-coordinate rounding <= 0.5 px.",
            "Timeline boundaries use nearest 10 ms; character outlines use 1/64 px positions.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not manifest["static_comparison"]["passed"]:
        raise SystemExit(
            "Static split-layout comparison failed; inspect static-difference.png"
        )


if __name__ == "__main__":
    main()
