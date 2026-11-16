"""Capture the layered glow effect on a self-contained input.

python -m tools.capture_layered_glow /tmp/layered-glow-baseline
Requires ffmpeg with libass and Pillow, as do the other visual validators.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from examples.layered_glow import BUDGET, build
from kara_templater import Document, load_font

TIMES = (0, 500, 800, 1000, 1300, 1600, 1700, 1800, 1850, 2400, 2700, 3000, 3900)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--compare",
        type=Path,
        help="compare frames and event counts with a saved report",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    font = root / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    output = args.output.resolve()
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    source = root / "tests/fixtures/layered_glow.ass"
    result = build(Document.load(source)).compile(budget=BUDGET)
    result.document.save(output / "layered-glow.ass")
    selection = "+".join(f"eq(n,{t // 10})" for t in TIMES)
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
            "color=c=black:s=640x480:r=100:d=4",
            "-vf",
            f"subtitles=layered-glow.ass:fontsdir=fonts,select='{selection}'",
            "-fps_mode",
            "vfr",
            "-y",
            "frame-%02d.png",
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "render.log").write_text(process.stderr)
    process.check_returncode()
    frames = []
    for index, time in enumerate(TIMES, 1):
        frame = Image.open(output / f"frame-{index:02d}.png").convert("RGB")
        frames.append(
            {
                "time_ms": time,
                "pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                "bbox": frame.getbbox(),
            }
        )
    report = {
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "font_sha256": registered.sha256,
        "ffmpeg_filter_threads": 1,
        "ffmpeg_version": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        "event_count": result.event_count,
        "objects": len(result.objects),
        "diagnostics": result.diagnostics,
        "events_by_style": {
            style: sum(event.style == style for event, _ in result.event_origins)
            for style in result.document.styles
        },
        "frames": frames,
    }
    mismatches = []
    event_delta = 0
    if args.compare:
        baseline = json.loads(args.compare.read_text())
        assert baseline["input_sha256"] == report["input_sha256"], "different input"
        assert baseline["font_sha256"] == report["font_sha256"], "different font"
        mismatches = [
            old["time_ms"]
            for old, new in zip(baseline["frames"], frames, strict=True)
            if old["time_ms"] != new["time_ms"]
            or old["pixel_sha256"] != new["pixel_sha256"]
        ]
        event_delta = result.event_count - baseline["event_count"]
        report["comparison"] = {
            "baseline": str(args.compare),
            "mismatched_frames_ms": mismatches,
            "event_delta": event_delta,
        }
    (output / "report.json").write_text(json.dumps(report, indent=2))
    if args.compare:
        assert not mismatches, f"frame differences at {mismatches} ms"
        assert event_delta == 0, "event count changed"

    print(
        json.dumps(
            {
                "events": result.event_count,
                "objects": len(result.objects),
                "frames": len(frames),
                "output": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
