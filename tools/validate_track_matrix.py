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
from typing import TypedDict

from PIL import Image, ImageChops, ImageDraw

from examples._lyrics import document
from kara_templater import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    Color,
    Coverage,
    Glow,
    Highlight,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    ObjectGroup,
    RasterSettings,
    Region,
    SceneBudget,
    SceneObject,
    StatePatch,
    TimeSpan,
    Track,
    Tween,
    Vec2,
    _metrics,
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


def static_paint(
    line: LyricLine, fill: Color, glow: Glow, *, raster: bool
) -> LyricLine:
    """Independent static reference: no highlight masks or ownership partitions."""
    components = []
    glows = {}

    def paint(node: SceneObject) -> SceneObject:
        if isinstance(node, ObjectGroup):
            return replace(
                node, children=tuple(paint(child) for child in node.children)
            )
        body = replace(node, state=replace(node.state, fill=fill))
        identity = f"{node.id}/static-material"
        if raster:
            components.append(identity)
            glows[node.id] = glow
            children = (body,)
        else:
            halo = replace(
                body.copy(id=f"{node.id}/static-glow"),
                layer=body.layer - 1,
                state=replace(
                    body.state,
                    fill=glow.color,
                    outline=glow.color,
                    blur=glow.blur,
                    border=glow.border,
                    opacity=body.state.opacity * glow.opacity,
                    shadow=Vec2(),
                ),
            )
            children = (body, halo)
        return ObjectGroup(
            id=identity, lifetime=node.lifetime, children=children, origin=node.origin
        )

    result = paint(line)
    assert isinstance(result, LyricLine)
    return (
        replace(
            result,
            coverage=Coverage(
                components=tuple(components),
                glows=glows,
                settings=RasterSettings(max_output_chars=256_000_000, max_frames=500),
            ),
        )
        if raster
        else result
    )


def generate(
    case: Case,
    mode: str,
    destination: Path,
    *,
    raster: bool = False,
    font_size: float = 56,
) -> dict[str, object]:
    source = document(fontname=case.font, text=case.text)
    source.records = [r for r in source.records if not isinstance(r, Line)]
    style = source.styles["Default"]
    style.italic, style.fontsize, style.outline, style.shadow = (
        case.italic,
        font_size,
        2,
        0,
    )
    source.records.append(
        replace(style, name="Default-furigana", fontsize=24, outline=1)
    )
    text = (
        r"{\kt100\k50}A{\k50}B"
        if case.adjacent
        else r"{\kt100\k100}"
        + case.text
        + ("|ka ra" if case.ruby and mode != "geometry" else "")
    )
    source.records.append(Line(text=text, start_time=0, end_time=3000))
    glow = Glow(RED, blur=case.radius, border=4, opacity=0.5)

    def paint(line: LyricLine) -> LyricLine:
        def opacity(node: SceneObject) -> SceneObject:
            if isinstance(node, ObjectGroup):
                return replace(node, children=tuple(opacity(c) for c in node.children))
            return replace(
                node,
                state=replace(
                    node.state, fill=WHITE, outline=BLACK, opacity=case.opacity
                ),
            )

        base = opacity(line)
        assert isinstance(base, LyricLine)
        if mode != "sweep":
            return static_paint(
                base,
                BLUE if mode == "after" else WHITE,
                replace(glow, color=BLUE) if mode == "after" else glow,
                raster=raster,
            )
        highlights = tuple(
            Highlight(
                str(index),
                index,
                tuple(
                    HighlightPass(
                        TimeSpan(s.singing.start, s.singing.end),
                        Region(box.left, box.right),
                    )
                    for s in unit.segments
                ),
                StatePatch(fill=BLUE),
                glow=replace(glow, color=BLUE),
            )
            for index, unit in enumerate(line.layout.lyrics.units)
            for box in (line.layout.body.range_bounds(unit.start, unit.end),)
        )
        return LyricHighlights(
            highlights=highlights,
            glow=glow,
            strategy="coverage" if raster else "clip",
            settings=RasterSettings(max_output_chars=256_000_000, max_frames=500),
        ).apply(base)

    geometry = mode == "geometry"
    if geometry:
        style.outline = 0
    config = Track(
        id="matrix",
        layout=Layout(position=Vec2(0, 220), alignment="center"),
        preview=0,
        tail=0,
        factory=None if geometry else paint,
    )
    # Bind display-wide motion directly; it does not reserve a pre-singing entrance.
    start = perf_counter()
    scene = prepare_tracks(source, tracks=(config,), owner="matrix")
    line = scene.lines[0]
    if case.dynamic and not geometry:
        scene.objects[0] = line.animate(
            Tween(StatePatch(scale=Vec2(1.2, 1.2))), duration=3
        )
    if geometry:
        position = line.state.position
        box = line.layout.body.bounds
        reference = document(fontname=case.font, text=case.text)
        reference.styles["Default"].italic = case.italic
        reference.styles["Default"].fontsize = font_size
        reference.records = [r for r in reference.records if not isinstance(r, Line)]
        reference.records.append(
            Line(
                text=rf"{{\an5\pos({position.x + box.center},{position.y + box.middle})\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}"
                + case.text,
                start_time=0,
                end_time=3000,
            )
        )
        reference.save(destination.parent / "whole.ass")
    result = scene.compile(
        budget=SceneBudget(
            max_events=2_000_000 if raster else 30_000,
            max_bytes=256_000_000 if raster else 10 * 1024 * 1024,
            max_active=50_000 if raster else 1000,
        )
    )
    result.document.save(destination)
    return {
        "compile_seconds": perf_counter() - start,
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


class PixelDifference(TypedDict):
    max_channel_error: int
    mean_channel_error: float
    changed_pixels: int


class BoundaryDifference(PixelDifference):
    background: str
    time_ms: int
    phase: str


def compare(first: Image.Image, second: Image.Image) -> PixelDifference:
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
    failures = []
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
        comparisons: list[BoundaryDifference] = []
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
        static_error = max(
            c["max_channel_error"] for c in comparisons if c["phase"] == "static"
        )
        shape_passed = (
            shape_error["max_channel_error"] <= 32
            and shape_error["changed_pixels"] <= 500
        )
        if static_error > 1 or not shape_passed:
            failures.append(case.name)
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
                "static_endpoints_passed": static_error <= 1,
                "geometry_passed": shape_passed,
                "frames": hashes,
            }
        )
        print(
            case.name,
            "max static endpoint error",
            static_error,
            "geometry error",
            shape_error["max_channel_error"],
            flush=True,
        )
    report = {
        "font_sha256": registered.sha256,
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "backend": "coverage" if args.raster else "clip",
        "font_size": args.font_size,
        "compositing_format": "rgb24" if args.rgb else "yuv420p",
        "times_ms": TIMES,
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        "contract": "Static endpoints match independent static paints within 1/255 on both backgrounds. Whole-text geometry allows 32/255 at up to 500 pixels for split-glyph positioning quantization. Onset may already show the sampled interval's midpoint; it and intermediate frames are captured, not certified against an independent material compositor.",
        "cases": results,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        raise SystemExit(f"validation failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
