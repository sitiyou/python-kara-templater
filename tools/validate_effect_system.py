"""Render the code-only RGB example and compare its three input routes.

Requires Pillow and ffmpeg with libass. Example:
python -m tools.validate_effect_system /tmp/effect-system-review --font path/to/cjk.ttf
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops

from examples.alternating_colors import AlternatingColors, document
from kara_templater import (
    BLUE,
    GREEN,
    RED,
    DisplayWindow,
    Document,
    KaraokeItem,
    KaraokeLine,
    Segment,
    TextUnit,
    import_karaoke,
    layout_characters,
    layout_line,
    load_font,
    render_karaoke,
)

TIMES = (0, 490, 510, 1490, 1510, 3500)


class DirectColors(AlternatingColors):
    def configure(self):
        for index in range(6):
            self.body.text_range(index, index + 1).style.sung.fill = (RED, GREEN, BLUE)[
                index % 3
            ]
        self.text.sweep()


def render(directory, name):
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
        check=False,
        cwd=directory,
        text=True,
        capture_output=True,
    )
    (directory / f"{name}.log").write_text(process.stderr)
    process.check_returncode()
    return [
        Image.open(directory / f"{name}-{i:02}.png").convert("RGB")
        for i in range(1, len(TIMES) + 1)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    registered = load_font(args.font)
    shutil.copyfile(args.font, output / "fonts" / args.font.name)
    source = document(fontname=registered.family)
    parsed = Document.parse(source.dumps())
    explicit = KaraokeItem(
        "explicit",
        KaraokeLine((TextUnit("星月风星月风", (Segment(0, 3000),)),)),
        "Default",
        DisplayWindow(0, 4000),
    )
    results = {
        "constructed": render_karaoke(source, effect=AlternatingColors),
        "parsed": render_karaoke(parsed, effect=AlternatingColors),
        "items": render_karaoke(source, (explicit,), effect=AlternatingColors),
        "direct": render_karaoke(source, effect=DirectColors),
    }
    frames = {}
    for name, result in results.items():
        result.document.save(output / f"{name}.ass")
        frames[name] = render(output, name)
    for name, variant_frames in frames.items():
        assert all(
            ImageChops.difference(a, b).getbbox() is None
            for a, b in zip(frames["constructed"], variant_frames, strict=True)
        ), name
    item = import_karaoke(source).items[0]
    layout = layout_line(
        item.source, style=source.styles["Default"], resolution=(640, 480)
    )
    characters = layout_characters(layout, style=source.styles["Default"])
    initial, final = frames["constructed"][0], frames["constructed"][-1]
    for index, char in enumerate(characters):
        box = char.box
        crop = (
            round(box.left),
            round(box.top),
            round(box.right),
            round(box.top + box.height),
        )
        before = [
            initial.getpixel((x, y))
            for y in range(crop[1], crop[3])
            for x in range(crop[0], crop[2])
        ]
        after = [
            final.getpixel((x, y))
            for y in range(crop[1], crop[3])
            for x in range(crop[0], crop[2])
        ]
        assert any(min(pixel) > 200 for pixel in before), (index, "missing white")
        assert not any(max(pixel) - min(pixel) > 100 for pixel in before), (
            index,
            "premature color",
        )
        channel = index % 3
        assert any(
            pixel[channel] > 180
            and all(pixel[c] < 80 for c in range(3) if c != channel)
            for pixel in after
        ), (index, "wrong final color")
        for time, frame in zip(TIMES, frames["constructed"], strict=True):
            pixels = [
                frame.getpixel((x, y))
                for y in range(crop[1], crop[3])
                for x in range(crop[0], crop[2])
            ]
            assert any(max(pixel) > 180 for pixel in pixels), (
                time,
                index,
                "missing glyph",
            )
            front = layout.units[0].box.left + layout.units[0].box.width * min(
                time / 3000, 1
            )
            if time < 3000 and box.left > front + 3:
                assert any(min(pixel) > 200 for pixel in pixels), (
                    time,
                    index,
                    "unsung glyph must stay white",
                )
            if box.right < front - 3:
                assert any(
                    pixel[channel] > 180
                    and all(pixel[c] < 80 for c in range(3) if c != channel)
                    for pixel in pixels
                ), (time, index, "sung glyph must retain color")
    # The effect must preserve the original one-segment timing and layout.
    _bound, body_style, ruby_style = AlternatingColors()._prepare(
        item, source.styles["Default"], source.styles["Default"]
    )
    colored_layout = layout_line(
        item.source, style=body_style, ruby_style=ruby_style, resolution=(640, 480)
    )
    assert colored_layout == layout
    assert item.source.units[0].segments == (Segment(0, 3000),)
    report = {
        "ffmpeg_filter_threads": 1,
        "all_glyphs_visible_during_sweep": True,
        "ffmpeg_version": subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        "font_family": registered.family,
        "font_sha256": registered.sha256,
        "frames_ms": TIMES,
        "event_counts": {name: r.event_count for name, r in results.items()},
        "input_frames_identical": True,
        "initial_white_final_rgb": True,
        "layout_and_timing_unchanged": True,
        "diagnostics": {name: r.diagnostics for name, r in results.items()},
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
