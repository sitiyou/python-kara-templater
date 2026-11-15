"""Measure native and bounded raster output for the layered_glow fixture."""

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from PIL import Image

from examples.layered_glow import tracks
from kara_templater import (
    Document,
    OutputCapabilityError,
    OutputSettings,
    RasterSettings,
    SceneBudget,
    SceneCompileError,
    load_font,
    prepare_tracks,
)


def capture_output(output: Path, mode: str) -> dict[str, object]:
    from tools.capture_layered_glow import TIMES

    font = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    selection = "+".join(f"eq(n,{time // 10})" for time in TIMES)
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
            "color=black:s=640x480:r=100:d=4",
            "-vf",
            f"format=rgb24,subtitles={mode}.ass:fontsdir=fonts,select='{selection}'",
            "-fps_mode",
            "vfr",
            "-y",
            f"{mode}-%02d.png",
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = perf_counter() - start
    (output / f"{mode}-render.log").write_text(process.stderr)
    process.check_returncode()
    frames = []
    for index, time in enumerate(TIMES, 1):
        image = Image.open(output / f"{mode}-{index:02d}.png").convert("RGB")
        frames.append(
            {
                "time_ms": time,
                "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                "bbox": image.getbbox(),
            }
        )
    return {
        "compositing_format": "rgb24",
        "background": "black",
        "renderer_seconds": elapsed,
        "frames": frames,
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--color-error", type=int, default=0)
    parser.add_argument("--max-events", type=int, default=1_000_000)
    parser.add_argument("--max-output-chars", type=int, default=64_000_000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    source_path = root / "tests/fixtures/layered_glow.ass"
    source = Document.load(source_path)
    registered = load_font(root / "tests/fonts/DejaVuSans.ttf")
    raster = RasterSettings(
        max_channel_error=args.color_error, max_output_chars=args.max_output_chars
    )
    report = {
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "font_sha256": registered.sha256,
        "max_events": args.max_events,
        "raster_settings": asdict(raster),
        "scope": "Complete layered_glow fixture at source font sizes and resolution; raster color error is spatial, before ASS transforms, and assumes RGB/full-chroma compositing.",
        "outputs": {},
    }
    for mode, settings in (("native", None), ("raster", raster)):
        estimates = []
        start = perf_counter()
        try:
            result = prepare_tracks(
                source,
                tracks=tracks,
                settings=OutputSettings(
                    resolution=(int(source.meta.res_x), int(source.meta.res_y)),
                    max_events=args.max_events,
                    raster=settings,
                ),
                on_estimate=estimates.append,
                mode="native",
            ).compile(
                budget=SceneBudget(
                    max_events=args.max_events,
                    max_bytes=args.max_output_chars,
                    max_active=args.max_events,
                )
            )
            compile_seconds = perf_counter() - start
            destination = args.output / f"{mode}.ass"
            result.document.save(destination)
            output = {
                "status": "generated",
                "compile_seconds": compile_seconds,
                "events": result.event_count,
                "objects": len(result.objects),
                "ass_bytes": destination.stat().st_size,
                "ass_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "diagnostics": result.diagnostics,
            }
            if args.capture:
                output["capture"] = capture_output(args.output.resolve(), mode)
        except (OutputCapabilityError, SceneCompileError) as error:
            output = {
                "status": "budget_rejected",
                "compile_seconds": perf_counter() - start,
                "error": str(error),
                "notes": getattr(error, "__notes__", ()),
            }
        output["preflight"] = [asdict(estimate) for estimate in estimates]
        report["outputs"][mode] = output
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(mode, output["status"], flush=True)


if __name__ == "__main__":
    main()
