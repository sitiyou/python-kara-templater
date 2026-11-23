"""Render the design studies on dark, light and moving high-contrast backgrounds.

uv run python -m tools.render_karaoke_designs
Source videos are not needed or redistributed. Requires FFmpeg and DejaVu fonts.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageDraw

from examples.karaoke_designs import Design, build
from kara_templater import SceneBudget
from tools.preview_frames import encode_preview

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/karaoke-design-study/rendered"
ASSETS = ROOT / "docs/examples/assets"
DESIGNS: tuple[Design, ...] = ("broadcast", "amber", "candy")
BACKGROUNDS = {
    "dark": "color=c=0x202630:s=1280x720:r=60:d=14",
    "light": "color=c=0xF6EDD9:s=1280x720:r=60:d=14",
    "busy": "testsrc2=s=1280x720:r=60:d=14",
}
BUDGET = SceneBudget(fps=60, max_events=40_000, max_bytes=20 * 1024 * 1024)


def ffmpeg(*args: str) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", *args], cwd=OUTPUT, check=True
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", action="store_true")
    args = parser.parse_args()
    suffix = "-ja" if args.japanese else ""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "source_sha256": digest(ROOT / "examples/karaoke_designs.py"),
        "japanese": args.japanese,
        "fps": 60,
        "duration": 14,
        "resolution": [1280, 720],
        "renderer": subprocess.check_output(
            ["ffmpeg", "-version"], text=True
        ).splitlines()[0],
        "fonts": {
            font: subprocess.check_output(
                ["fc-match", "-f", "%{family}: %{file}", font], text=True
            )
            for font in (
                ("Sarasa UI J", "Noto Serif CJK JP")
                if args.japanese
                else ("DejaVu Sans", "DejaVu Serif")
            )
        },
    }
    montage = Image.new("RGB", (1280, 3 * 390), "#202630")
    pen = ImageDraw.Draw(montage)
    for row, design in enumerate(DESIGNS):
        start = perf_counter()
        scene = build(design, japanese=args.japanese)
        result = scene.compile(budget=BUDGET, native_tweens=True)
        compile_seconds = perf_counter() - start
        ass = OUTPUT / f"{design}{suffix}.ass"
        result.document.save(ass)
        render_seconds: dict[str, float] = {}
        for background, source in BACKGROUNDS.items():
            start = perf_counter()
            video = f"{design}{suffix}-{background}.mp4"
            encode_preview(result.document.dumps(), (1280, 720), 60, 14, source, "",
                           ["-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20", video], OUTPUT)
            render_seconds[background] = perf_counter() - start
            for time in (1.5, 3.1, 6.5, 10.3):
                frame = OUTPUT / f"{design}{suffix}-{background}-{time}.png"
                ffmpeg("-ss", str(time), "-i", video, "-frames:v", "1", str(frame))
                if background != "busy" and time == 6.5:
                    with Image.open(frame) as image:
                        montage.paste(
                            image.resize((640, 360)),
                            (0 if background == "dark" else 640, row * 390 + 30),
                        )
        gif = ASSETS / f"karaoke-{design}{suffix}.gif"
        ffmpeg(
            "-i",
            f"{design}{suffix}-dark.mp4",
            "-filter_complex",
            "fps=15,scale=640:-2,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=bayer",
            "-loop",
            "0",
            str(gif),
        )
        pen.text(
            (12, row * 390 + 8), f"{design} / 6.5 s / dark and light", fill="white"
        )
        report[design] = {
            "events": result.event_count,
            "active": result.peak_active,
            "bytes": result.byte_count,
            "compile_seconds": compile_seconds,
            "render_seconds": render_seconds,
            "ass_sha256": digest(ass),
            "gif_sha256": digest(gif),
            "diagnostics": result.diagnostics,
        }
        print(design, report[design], flush=True)
    montage.save(ASSETS / f"karaoke-design-comparison{suffix}.jpg", quality=90)
    (OUTPUT / f"report{suffix}.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
