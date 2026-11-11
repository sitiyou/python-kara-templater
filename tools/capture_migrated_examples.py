"""Recheck song, dynamic and recipe examples against their migration frames.

python -m tools.capture_migrated_examples OUTPUT
Requires ffmpeg/libass and Pillow. Baselines are never rewritten.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from examples.dynamic_effect import DynamicGlow
from examples.recipes import build
from examples.song_effect import SongEffect
from examples.staggered_path import scene
from kara_templater import load_font

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    font = ROOT / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    shutil.copyfile(font, output / "fonts" / font.name)
    report = {"font_sha256": registered.sha256, "filter_threads": 1, "examples": {}}
    for name, result in (
        ("song-effect", scene(SongEffect())),
        ("dynamic-effect", scene(DynamicGlow())),
        ("recipes", build()),
    ):
        baseline = json.loads((ROOT / f"docs/{name}-migration.json").read_text())
        assert baseline["font_sha256"] == registered.sha256, name
        times = [frame["time_ms"] for frame in baseline["frames"]]
        result.document.save(output / f"{name}.ass")
        select = "+".join(f"eq(n,{time // 10})" for time in times)
        run = subprocess.run(
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
                f"subtitles={name}.ass:fontsdir=fonts,select='{select}'",
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
        (output / f"{name}.log").write_text(run.stderr)
        run.check_returncode()
        frames = []
        for index, expected in enumerate(baseline["frames"], 1):
            with Image.open(output / f"{name}-{index:02d}.png") as image:
                digest = hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()
            assert digest == expected["after_sha256"], (name, expected["time_ms"])
            frames.append({"time_ms": expected["time_ms"], "sha256": digest})
        report["examples"][name] = {
            "events": result.event_count,
            "layers": result.layer_count,
            "frames": frames,
            "ass_file_sha256": hashlib.sha256(
                (output / f"{name}.ass").read_bytes()
            ).hexdigest(),
        }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {name: len(data["frames"]) for name, data in report["examples"].items()}
        )
    )


if __name__ == "__main__":
    main()
