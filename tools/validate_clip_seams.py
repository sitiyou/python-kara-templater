"""Check crossing fractional clip clocks against an unpartitioned glyph.

Run: python -m tools.validate_clip_seams OUTPUT
"""

import argparse
import json
import shutil
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from kara_templater import (
    Box,
    ClipSpan,
    Color,
    DisplayWindow,
    Document,
    Fade,
    Glow,
    OutputSettings,
    Paint,
    Region,
    ScaleAnimation,
    Style,
    TextLayer,
    compile_layers,
    load_font,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from kara_templater.masks import PaintedMask, compose_masks
from tools.render_effects import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", action="store_true")
    parser.add_argument("--fade", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copy2(font_path, output / "fonts" / font_path.name)
    style = Style(fontname=font.family, fontsize=160, align=5)
    window = DisplayWindow(500, 2500)
    paint = Paint(opacity=0.5, glow=Glow(blur=8, opacity=0.5))
    # Zero-width outline colors distinguish semantic regions without changing
    # their visible appearance. Any partition seam is therefore extra output.
    masks = (
        PaintedMask(
            "main",
            replace(paint, outline=Color(255, 0, 0)),
            0,
            (ClipSpan(1000, 2000, Region(0, 180.3), Region(0, 460.7)),),
        ),
        PaintedMask(
            "cover",
            replace(paint, outline=Color(0, 0, 255)),
            1,
            (ClipSpan(1230, 1810, Region(0, 210.2), Region(0, 440.6)),),
        ),
    )
    regions = compose_masks(
        masks, domain=Region(0, 640), window=window, before=paint, overlap="priority"
    )
    base = TextLayer("reference", "M", style, Box(220, 180, 200, 120), window, paint)
    if args.fade:
        base = replace(base, fade=Fade(1000, 1000))
    if args.scale:
        base = replace(
            base,
            animations=(
                ScaleAnimation("reference", "main", 0, 1000, 2000, 1.4, (320, 240)),
            ),
        )
    from kara_templater.ass_output import quantize

    layers = tuple(
        replace(
            base,
            source_id=f"region:{i}",
            paint=r.paints[0],
            clips=(r.interpolation_span or r.span,),
            active_window=DisplayWindow(
                quantize(r.span.start_ms), quantize(r.span.end_ms)
            ),
        )
        for i, r in enumerate(regions)
        if quantize(r.span.end_ms) > quantize(r.span.start_ms)
    )
    header = (
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + style.serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    times = tuple(range(1000, 2010, 10))
    events, frames = {}, {}
    for name, group in (("partitioned", layers), ("reference", (base,))):
        compiled = compile_layers(group, settings=OutputSettings(resolution=(640, 480)))
        document = Document.parse(header)
        document.records.extend(compiled.events)
        document.save(output / f"{name}.ass")
        events[name] = len(compiled.events)
        render(name + ".ass", str(output / f"{name}-%03d.png"), times)
        frames[name] = [
            Image.open(output / f"{name}-{i + 1:03d}.png").convert("RGB")
            for i in range(len(times))
        ]
    checks = []
    for index, time in enumerate(times):
        difference = ImageChops.difference(
            frames["partitioned"][index], frames["reference"][index]
        )
        maximum = max(difference.tobytes())
        checks.append(
            {"time_ms": time, "max_channel_difference": maximum, "passed": maximum == 0}
        )
        if maximum:
            difference.save(output / f"failure-{time}.png")
    report = {
        "scale": args.scale,
        "fade": args.fade,
        "font_sha256": font.sha256,
        "frames": 2 * len(times),
        "events": events,
        "local_clock_regions": sum(r.shared_local_clock for r in regions),
        "checks": checks,
        "limitations": [
            "Same visible paint across semantic partitions; unpartitioned reference detects extra cracks or overdraw.",
            "--scale adds a 1.4x pulse and checks that adaptive clip cuts preserve the native animation clock.",
        ],
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not all(c["passed"] for c in checks):
        raise SystemExit("Clip seams detected")


if __name__ == "__main__":
    main()
