"""Capture or compare whole_glow and staggered_path migration evidence."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from examples.staggered_path import ArcWave, scene
from examples.whole_glow import WholeGlow
from kara_templater import load_font

TIMES = (500, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2800)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    font = root / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    report = {"font_sha256": registered.sha256, "filter_threads": 1, "examples": {}}
    for name, effect in (("whole", WholeGlow()), ("arc", ArcWave())):
        result = scene(effect)
        result.document.save(output / f"{name}.ass")
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
                "color=c=black:s=640x480:r=100:d=3",
                "-vf",
                f"subtitles={name}.ass:fontsdir=fonts,select='{selection}'",
                "-fps_mode",
                "vfr",
                "-y",
                f"{name}-%02d.png",
            ],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
        )
        (output / f"{name}.log").write_text(process.stderr)
        process.check_returncode()
        frames = [
            {
                "time_ms": t,
                "sha256": hashlib.sha256(
                    Image.open(output / f"{name}-{i:02d}.png").convert("RGB").tobytes()
                ).hexdigest(),
            }
            for i, t in enumerate(TIMES, 1)
        ]
        events = sorted(
            (e.start_time, e.end_time, e.layer, e.style, e.text)
            for e, _ in result.event_origins
        )
        report["examples"][name] = {
            "events": result.event_count,
            "layers": result.layer_count,
            "event_sha256": hashlib.sha256(json.dumps(events).encode()).hexdigest(),
            "frames": frames,
        }
    if args.compare:
        expected = json.loads(args.compare.read_text())
        assert (
            report == expected
        ), "migration report differs; inspect saved frames and ASS"
    (output / "report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                n: {k: v for k, v in r.items() if k != "frames"}
                for n, r in report["examples"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
