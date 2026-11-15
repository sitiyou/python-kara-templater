"""Capture Track font/paint boundaries and compare endpoints to static references.

python -m tools.validate_track_matrix /tmp/track-matrix
Requires ffmpeg/libass and Pillow. Use --raster --rgb for the material backend
and RGB subtitle compositing. Intermediate frames are captured for review;
endpoint agreement alone does not certify the complete material pipeline.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageChops, ImageDraw

from examples._lyrics import document
from kara_templater import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    Animate,
    Blur,
    Body,
    Display,
    DisplayWindow,
    KaraokeItem,
    KaraokeLine,
    Line,
    LineMatch,
    On,
    OutputSettings,
    Overlay,
    PaintStyle,
    RasterSettings,
    Ruby,
    SceneBudget,
    Segment,
    TextStyle,
    TextUnit,
    Track,
    _metrics,
    layout_line,
    load_font,
    prepare_tracks,
)

TIMES = (500, 1000, 1240, 1480, 1520, 1760, 2000, 2500)


@dataclass(frozen=True)
class Case:
    name: str
    text: str = "AB"
    italic: bool = False
    font: str = "DejaVu Sans"
    radius: float = 6
    opacity: float = 1
    ruby: bool = False
    dynamic: bool = False
    adjacent: bool = False


CASES = (
    Case("italic", "fj AV", italic=True),
    Case("spaces", " A  B "),
    Case("fallback", "AV", font="KaraMissingFontForValidation"),
    Case("ligature", "office"),
    Case("large_blur", radius=24),
    Case("scale", dynamic=True),
    Case("adjacent", adjacent=True),
    Case("ruby", "kara", ruby=True),
    Case("transparent", opacity=0.35),
)


def generate(case, mode, destination, *, raster=False, font_size=56):
    source = document(fontname=case.font, text=case.text)
    source.records = [r for r in source.records if not isinstance(r, Line)]
    source.styles["Default"].italic = case.italic
    source.styles["Default"].fontsize = font_size
    units = (
        (TextUnit("A", (Segment(1000, 1500),)), TextUnit("B", (Segment(1500, 2000),)))
        if case.adjacent
        else (
            TextUnit(case.text, (Segment(1000, 2000, "ka ra" if case.ruby else ""),)),
        )
    )
    item = KaraokeItem("matrix", KaraokeLine(units), "Default", DisplayWindow(0, 3000))
    base = TextStyle(
        fill=WHITE,
        stroke=BLACK,
        stroke_width=2,
        opacity=case.opacity,
        blur=Blur(color=RED, radius=case.radius, width=4, opacity=0.5),
    )
    after = (
        replace(base, fill=BLUE, blur=replace(base.blur, color=BLUE))
        if isinstance(base.blur, Blur)
        else base
    )
    selected = after if mode == "after" else base
    if mode == "geometry":
        selected = TextStyle(fill=WHITE, stroke_width=0, blur=None)
        layout = layout_line(
            item.source, style=source.styles["Default"], resolution=(640, 480)
        )
        reference = document(fontname=case.font, text=case.text)
        reference.styles["Default"].italic = case.italic
        reference.styles["Default"].fontsize = font_size
        reference.records = [r for r in reference.records if not isinstance(r, Line)]
        reference.records.append(
            Line(
                text=rf"{{\an5\pos({layout.box.center},{layout.box.middle})\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}"
                + case.text,
                start_time=0,
                end_time=3000,
            )
        )
        reference.save(destination.parent / "whole.ass")
    track = Track(
        source=LineMatch(),
        body=Body(style=selected),
        ruby=Ruby(style=replace(selected, font_size=24, stroke_width=1), offset_y=-4)
        if case.ruby and mode != "geometry"
        else None,
        overlay=Overlay(style=PaintStyle(fill=BLUE, blur=Blur(color=BLUE)))
        if mode == "sweep"
        else None,
        animations=(
            On(Display.Start, Animate(scale=lambda p: 1 + 0.2 * p, duration=3000)),
        )
        if case.dynamic and mode != "geometry"
        else (),
    )
    start = perf_counter()
    result = prepare_tracks(
        source,
        items=(item,),
        tracks=(track,),
        settings=OutputSettings(
            resolution=(640, 480),
            max_events=2_000_000 if raster else 10000,
            raster=RasterSettings(max_output_chars=256_000_000) if raster else None,
        ),
        mode="native",
    ).compile(
        budget=SceneBudget(
            max_events=2_000_000 if raster else 10_000,
            max_bytes=256_000_000 if raster else 10 * 1024 * 1024,
            max_active=50_000 if raster else 1000,
        )
    )
    elapsed = perf_counter() - start
    result.document.save(destination)
    return {
        "compile_seconds": elapsed,
        "events": result.event_count,
        "objects": len(result.objects),
        "ass_bytes": destination.stat().st_size,
        "ass_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "diagnostics": result.diagnostics,
    }


def capture(directory, mode, background, *, rgb=False):
    selection = "+".join(f"eq(n,{t // 10})" for t in TIMES)
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
            f"color=c={background}:s=640x480:r=100:d=3",
            "-vf",
            ("format=rgb24," if rgb else "")
            + f"subtitles={mode}.ass:fontsdir=fonts,select='{selection}'",
            "-fps_mode",
            "vfr",
            "-y",
            f"{mode}-{background}-%02d.png",
        ],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    (directory / f"{mode}-{background}.log").write_text(process.stderr)
    process.check_returncode()
    return perf_counter() - start


def compare(first, second):
    difference = ImageChops.difference(first, second)
    pixels = difference.tobytes()
    return {
        "max_channel_error": max(pixels),
        "mean_channel_error": sum(pixels) / len(pixels),
        "changed_pixels": sum(any(pixels[i : i + 3]) for i in range(0, len(pixels), 3)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--raster", action="store_true")
    parser.add_argument(
        "--rgb",
        action="store_true",
        help="Composite subtitles in RGB before PNG output",
    )
    parser.add_argument("--font-size", type=float, default=56)
    parser.add_argument(
        "--case", action="append", choices=[case.name for case in CASES]
    )
    args = parser.parse_args()
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    font = root / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    results = []
    for case in CASES:
        if args.case and case.name not in args.case:
            continue
        directory = output / case.name
        (directory / "fonts").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(font, directory / "fonts" / font.name)
        modes = {
            mode: generate(
                case,
                mode,
                directory / f"{mode}.ass",
                raster=args.raster,
                font_size=args.font_size,
            )
            for mode in ("before", "sweep", "after")
        }
        geometry = generate(
            case,
            "geometry",
            directory / "geometry.ass",
            raster=args.raster,
            font_size=args.font_size,
        )
        for mode in ("geometry", "whole"):
            capture(directory, mode, "black", rgb=args.rgb)
        shape_error = compare(
            Image.open(directory / "geometry-black-01.png").convert("RGB"),
            Image.open(directory / "whole-black-01.png").convert("RGB"),
        )
        outlines = _metrics.text_shape(
            case.font, args.font_size, 0, int(case.italic), 100, 100, 0, 1, case.text
        )[4]
        elapsed = {}
        comparisons = []
        hashes = []
        montage = Image.new("RGB", (640 * len(TIMES), 510 * 2))
        draw = ImageDraw.Draw(montage)
        for row, background in enumerate(("black", "white")):
            for mode in modes:
                elapsed[f"{mode}-{background}"] = capture(
                    directory, mode, background, rgb=args.rgb
                )
            for index, time in enumerate(TIMES, 1):
                frame = Image.open(
                    directory / f"sweep-{background}-{index:02d}.png"
                ).convert("RGB")
                montage.paste(frame, ((index - 1) * 640, row * 510 + 30))
                draw.text(
                    ((index - 1) * 640 + 10, row * 510 + 8),
                    f"{case.name} {background} {time}ms",
                    fill="white",
                )
                hashes.append(
                    {
                        "background": background,
                        "time_ms": time,
                        "sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                    }
                )
                if time <= 1000 or time >= 2000:
                    reference = "before" if time <= 1000 else "after"
                    expected = Image.open(
                        directory / f"{reference}-{background}-{index:02d}.png"
                    ).convert("RGB")
                    comparisons.append(
                        {
                            "background": background,
                            "time_ms": time,
                            "phase": "onset" if time == 1000 else "static",
                            **compare(frame, expected),
                        }
                    )
        montage.save(directory / "montage.png")
        font_selection = list(
            dict.fromkeys(
                line.split("fontselect: ", 1)[1]
                for log in ("sweep-black.log", "whole-black.log")
                for line in (directory / log).read_text().splitlines()
                if "fontselect: " in line
            )
        )
        system_fonts = {}
        for selection in font_selection:
            selected_file = Path(selection.split(" -> ", 1)[1].split(",", 1)[0])
            if selected_file.is_file():
                system_fonts[str(selected_file)] = hashlib.sha256(
                    selected_file.read_bytes()
                ).hexdigest()
        results.append(
            {
                "case": case.name,
                "font_requested": case.font,
                "modes": modes,
                "geometry": {
                    "output": geometry,
                    "whole_text_error": shape_error,
                    "glyphs": [outline[3] for outline in outlines],
                },
                "renderer_font_selection": font_selection,
                "system_font_sha256": system_fonts,
                "renderer_seconds": elapsed,
                "endpoints": comparisons,
                "frames": hashes,
            }
        )
        print(
            case.name,
            "max boundary error",
            max(c["max_channel_error"] for c in comparisons),
            "geometry error",
            shape_error["max_channel_error"],
            flush=True,
        )
    report = {
        "font_sha256": registered.sha256,
        "backend": "raster" if args.raster else "native",
        "font_size": args.font_size,
        "compositing_format": "rgb24" if args.rgb else "yuv420p",
        "times_ms": TIMES,
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        "contract": "Static endpoints and onset compared to static paints on two backgrounds; unstyled geometry compared to independent whole-text ASS. Intermediate frames are captured for review, not certified against an independent material compositor.",
        "cases": results,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
