"""Render native/keyframe/function variants of combined author effects."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from examples.alternating_colors import document
from examples.composed_glow import ComposedGlow
from kara_templater import (
    DisplayWindow,
    KaraokeItem,
    KaraokeLine,
    Line,
    Segment,
    TextUnit,
    layout_characters,
    layout_line,
    load_font,
    render_karaoke,
)

TIMES = (500, 1000, 1250, 1500, 1750, 1800, 2000, 2500)
CASES = {
    "group_follow": ("group", True, False),
    "group_detached": ("group", False, False),
    "group_sung": ("group", True, True),
    "characters": ("characters", False, False),
    "characters_sung": ("characters", False, True),
}


def scene(effect):
    source = document(fontname="DejaVu Sans", text="AB")
    source.records[:] = [r for r in source.records if not isinstance(r, Line)]
    source.styles["Default"].fontsize = 64
    item = KaraokeItem(
        "combined",
        KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "ab"),)),)),
        "Default",
        DisplayWindow(0, 3000),
    )
    return render_karaoke(source, (item,), effect=effect)


def sweep_fronts(target, follow, time, translate=False):
    if not 1000 <= time < 2000:
        return ()
    source = document(fontname="DejaVu Sans", text="AB")
    style = replace(source.styles["Default"], fontsize=64)
    lyrics = KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "ab"),)),))
    layout = layout_line(
        lyrics,
        style=style,
        ruby_style=replace(style, fontsize=32),
        resolution=(640, 480),
    )
    box = layout.units[0].box
    # Union of the main pass and the echo while the echo is active.
    progress = (time - 1000) / 1000
    if 1200 <= time < 1800:
        progress = max(progress, (time - 1200) / 600)
    scale = 1 + 0.2 * (1 - abs(2 * (time - 1000) / 1000 - 1))
    original = box.left + box.width * progress
    centers = (
        [box.center]
        if target == "group"
        else [c.box.center for c in layout_characters(layout, style=style)]
    )
    fronts = [center + (original - center) * scale for center in centers]
    ruby = layout.units[0].segments[0].ruby
    ruby_front = ruby.left + ruby.width * progress
    if follow:
        ruby_front = box.center + (ruby_front - box.center) * scale
    elif target == "characters":
        ruby_front = ruby.center + (ruby_front - ruby.center) * scale
    if translate:
        dx = 20 * (time - 1000) / 1000
        fronts = [front + dx for front in fronts]
        if follow or target == "characters":
            ruby_front += dx
    return (*fronts, ruby_front)


def front_error(result, target, follow, time, translate=False):
    if not 1000 <= time < 2000:
        return 0
    fronts = sweep_fronts(target, follow, time, translate)
    errors = []
    for event, _ in result.event_origins:
        if (
            event.layer != 5
            or not event.start_time <= time < event.end_time
            or r"\1c&HFFFF00&" not in event.text
        ):
            continue
        initial = re.search(r"\\clip\((-?\d+),0,(-?\d+),480\)", event.text)
        if initial is None:
            continue
        right = float(initial[2])
        change = re.search(
            r"\\t\((-?\d+),(-?\d+),1,\\clip\((-?\d+),0,(-?\d+),480\)\)", event.text
        )
        if change is not None:
            start, end = int(change[1]), int(change[2])
            fraction = min(1, max(0, (time - event.start_time - start) / (end - start)))
            right += (float(change[4]) - right) * fraction
        text = event.text.rsplit("}", 1)[1]
        expected = (
            fronts[-1]
            if text == "ab"
            else fronts[0 if text == "A" or target == "group" else 1]
        )
        errors.append(abs(right - expected))
    if time > 1000:
        assert errors, (target, time, "missing sung clip events")
    return max(errors, default=0)


def capture(output, name, result):
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
    return [
        Image.open(output / f"{name}-{i:02d}.png").convert("RGB")
        for i in range(1, len(TIMES) + 1)
    ]


def maximum(image):
    return max(hi for _, hi in image.getextrema())


def compare(a, b, fronts):
    # Native transformed clips approximate to <= .25 px before integer clip
    # rounding. Allow one pixel spatial uncertainty in either direction, plus
    # three channel levels for alpha/color conversion rounding. No image shift.
    # Near a sweep front, a subpixel edge can reveal a bright strip absent in
    # the other image, so spatial dilation alone is insufficient. Exclude the
    # independently computed front +/- 2 px (integer clip + YUV420 chroma);
    # front_error separately verifies the emitted coordinates to <= .75 px.
    forward = ImageChops.subtract(a, b.filter(ImageFilter.MaxFilter(3)))
    reverse = ImageChops.subtract(b, a.filter(ImageFilter.MaxFilter(3)))
    residual = ImageChops.lighter(forward, reverse)
    bands = []
    for front in fronts:
        left, right = round(front) - 2, round(front) + 2
        bands.append((left, right))
        residual.paste((0, 0, 0), (left, 0, right + 1, residual.height))
    return {
        "max_channel_error": maximum(ImageChops.difference(a, b)),
        "one_pixel_residual": maximum(residual),
        "excluded_front_bands": bands,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--offsets",
        action="store_true",
        help="combine x/y translation with scale and sweeps",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    font = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    registered = load_font(font)
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(font, output / "fonts" / font.name)
    report = {
        "translation": args.offsets,
        "font_sha256": registered.sha256,
        "filter_threads": 1,
        "spatial_tolerance_px": 1,
        "excluded_front_half_width_px": 2,
        "front_coordinate_tolerance_px": 0.75,
        "channel_tolerance": 3,
        "cases": {},
    }
    failures = []
    for name, (target, follow, clip) in CASES.items():
        frames, evidence = {}, {}
        variants = ("native", "keyframes", "function", "product")
        if args.offsets:
            variants += ("additive",)
        for curve in variants:
            result = scene(
                ComposedGlow(
                    target,
                    follow,
                    clip,
                    "native" if curve == "additive" else curve,
                    args.offsets,
                    curve == "additive",
                )
            )
            frames[curve] = capture(output, f"{name}-{curve}", result)
            front_errors = [
                front_error(result, target, follow, time, args.offsets)
                for time in TIMES
            ]
            assert max(front_errors) <= 0.75, (
                name,
                curve,
                "clip coordinates",
                front_errors,
            )
            evidence[curve] = {
                "events": result.event_count,
                "layers": result.layer_count,
                "front_error_px": front_errors,
                "diagnostics": result.diagnostics,
                "frames": [
                    hashlib.sha256(im.tobytes()).hexdigest() for im in frames[curve]
                ],
            }
            assert {
                ref.item_id
                for _, origin in result.event_origins
                for ref in origin.sources
            } == {"combined"}
        differences = []
        for i, time in enumerate(TIMES):
            native = frames["native"][i]
            assert maximum(native) > 100, (name, time, "missing glyph")
            exact = maximum(ImageChops.difference(native, frames["keyframes"][i]))
            if exact:
                failures.append((name, time, "keyframes", exact))
            product = maximum(ImageChops.difference(native, frames["product"][i]))
            if product:
                failures.append((name, time, "product", product))
            additive = (
                maximum(ImageChops.difference(native, frames["additive"][i]))
                if args.offsets
                else None
            )
            if additive:
                failures.append((name, time, "additive", additive))
            delta = compare(
                native,
                frames["function"][i],
                sweep_fronts(target, follow, time, args.offsets),
            )
            if delta["one_pixel_residual"] > 3:
                failures.append((name, time, "function", delta))
            if time in (500, 1000, 2000, 2500) and delta["max_channel_error"]:
                failures.append((name, time, "endpoint", delta))
            differences.append(
                {
                    "time_ms": time,
                    "keyframes_max_error": exact,
                    "product_max_error": product,
                    "additive_max_error": additive,
                    **delta,
                }
            )
        report["cases"][name] = {"variants": evidence, "comparison": differences}
    report["failures"] = failures
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not failures, failures
    print(
        json.dumps(
            {
                name: {
                    curve: values["events"]
                    for curve, values in case["variants"].items()
                }
                for name, case in report["cases"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
