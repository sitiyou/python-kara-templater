"""Compare native opacity frames against independently evaluated static paints."""

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from examples.alternating_colors import document
from kara_templater import (
    DisplayWindow,
    Line,
    OpacityAnimation,
    Paint,
    TextLayer,
    compile_layers,
    import_karaoke,
    layout_line,
    load_font,
)

TIMES = (500, 1000, 1250, 1500, 1750, 2000, 2500)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    font = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    source = document(fontname=registered.family, text="W")
    item = import_karaoke(source).items[0]
    style = source.styles["Default"]
    box = layout_line(item.source, style=style, resolution=(640, 480)).units[0].box
    layer = TextLayer(
        "native", "W", style, box, DisplayWindow(0, 3000), Paint(border=0)
    )
    native = replace(
        layer,
        opacity_animations=(OpacityAnimation(((1000, 0.2), (2000, 0.8)), keep=True),),
    )
    references = []
    for time in TIMES:
        # Independent analytic ramp, rather than the native evaluator.
        opacity = 1 if time < 1000 else 0.2 + 0.6 * min(1, (time - 1000) / 1000)
        references.append(
            replace(
                layer,
                source_id=f"reference-{time}",
                window=DisplayWindow(time, time + 10),
                paint=replace(layer.paint, opacity=opacity),
            )
        )
    frames = {}
    counts = {}
    for name, layers in (("native", (native,)), ("reference", tuple(references))):
        doc = document(fontname=registered.family, text="W")
        doc.records[:] = [r for r in doc.records if not isinstance(r, Line)]
        result = compile_layers(layers)
        doc.records.extend(result.events)
        doc.save(output / f"{name}.ass")
        counts[name] = len(result.events)
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
            text=True,
            capture_output=True,
            check=False,
        )
        (output / f"{name}.log").write_text(process.stderr)
        process.check_returncode()
        frames[name] = [
            Image.open(output / f"{name}-{i:02d}.png").convert("RGB")
            for i in range(1, len(TIMES) + 1)
        ]
    report = {
        "font_sha256": registered.sha256,
        "filter_threads": 1,
        "max_channel_tolerance": 3,
        "events": counts,
        "frames": [],
    }
    for time, actual, expected in zip(
        TIMES, frames["native"], frames["reference"], strict=True
    ):
        assert max(hi for _, hi in actual.getextrema()) > 20, (time, "missing glyph")
        difference = ImageChops.difference(actual, expected)
        error = max(hi for _, hi in difference.getextrema())
        # ASS interpolates integer alpha endpoints; the static reference rounds
        # the exact value once. Allow one alpha unit plus RGB conversion rounding.
        assert error <= 3, (time, error)
        if time in (500, 1000, 2000, 2500):
            assert error == 0, (time, "endpoint mismatch")
        report["frames"].append(
            {
                "time_ms": time,
                "max_channel_error": error,
                "sha256": hashlib.sha256(actual.tobytes()).hexdigest(),
            }
        )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
