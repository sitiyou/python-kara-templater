"""Compare sung-clipped glow with independently rendered full/body references.

python -m tools.validate_halo_clip /tmp/halo-clip-review
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops

from examples.alternating_colors import document
from kara_templater import (
    BLUE,
    RED,
    WHITE,
    Body,
    DisplayWindow,
    Effect,
    Halo,
    KaraokeItem,
    KaraokeLine,
    Line,
    Lyrics,
    Segment,
    TextUnit,
    layout_line,
    load_font,
    render_karaoke,
)

TIMES = (500, 1250, 1500, 1750, 2000, 2500)


class Reference(Effect):
    clip = None

    def compose(self):
        children = [Body(fill=WHITE, stroke_width=0)]
        if self.clip is not None:
            children.append(Halo(color=RED, width=6, blur=8, clip=self.clip))
        yield Lyrics(*children)

    def configure(self):
        self.text.sweep(fill=WHITE)


class Full(Reference):
    clip = "none"


class Sung(Reference):
    clip = "sung"


class Blue(Full):
    def configure(self):
        super().configure()
        self.query_one("halo").style.fill = BLUE


class Stateful(Full):
    def configure(self):
        super().configure()
        self.query_one("halo").style.sung.fill = BLUE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--states", action="store_true", help="compare red-to-blue state colors"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    font = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    source = document(fontname=registered.family, text="W")
    source.records[:] = [r for r in source.records if not isinstance(r, Line)]
    item = KaraokeItem(
        "halo",
        KaraokeLine((TextUnit("W", (Segment(1000, 2000),)),)),
        "Default",
        DisplayWindow(0, 3000),
    )
    box = (
        layout_line(item.source, style=source.styles["Default"], resolution=(640, 480))
        .units[0]
        .box
    )
    frames = {}
    report = {"font_sha256": registered.sha256, "filter_threads": 1, "frames": []}
    variants = (("body", Reference), ("full", Full), ("sung", Sung))
    if args.states:
        variants = (("body", Full), ("full", Blue), ("sung", Stateful))
        report["mode"] = "red-to-blue state colors"
    for name, effect in variants:
        result = render_karaoke(source, (item,), effect=effect)
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
                "color=c=black:s=640x480:r=100:d=4",
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
        frames[name] = [
            Image.open(output / f"{name}-{i:02d}.png").convert("RGB")
            for i in range(1, len(TIMES) + 1)
        ]
    for i, time in enumerate(TIMES):
        body, full, sung = (frames[name][i] for name in ("body", "full", "sung"))
        assert ImageChops.difference(body, full).getbbox(), "reference glow missing"
        if time < 1000 or time >= 2000:
            reference = body if time < 1000 else full
            assert ImageChops.difference(reference, sung).getbbox() is None, time
            ignored = None
        else:
            # Native ASS clip edges round to integer coordinates; YUV420 chroma
            # reconstruction affects neighbouring pixels. Exclude only this strip.
            front = round(box.left + box.width * (time - 1000) / 1000)
            ignored = [front - 2, front + 2]
            left, right = (0, 0, front - 2, 480), (front + 2, 0, 640, 480)
            assert (
                ImageChops.difference(full.crop(left), sung.crop(left)).getbbox()
                is None
            ), (time, "sung side")
            assert (
                ImageChops.difference(body.crop(right), sung.crop(right)).getbbox()
                is None
            ), (time, "unsung side")
        report["frames"].append(
            {
                "time_ms": time,
                "matches_reference": True,
                "excluded_x": ignored,
                "sha256": hashlib.sha256(sung.tobytes()).hexdigest(),
            }
        )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
