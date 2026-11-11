"""Measure three pulse modes against independently positioned static ASS frames.

Run: python -m tools.validate_pulse_geometry OUTPUT
"""

import argparse
import json
import shutil
from math import floor
from pathlib import Path

from PIL import Image, ImageChops

from kara_templater import (
    DisplayWindow,
    Document,
    KaraokeLine,
    Line,
    Pulse,
    Segment,
    Style,
    TextLayer,
    TextUnit,
    compile_layers,
    layout_characters,
    layout_line,
    load_font,
    plan_pulses,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from tools.render_effects import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copy2(font_path, output / "fonts" / font_path.name)
    style = Style(fontname=font.family, fontsize=64, align=5, spacing=12)
    source = KaraokeLine((TextUnit("W i", (Segment(1000, 2000),)),))
    layout = layout_line(source, style=style, resolution=(640, 480))
    chars = tuple(
        c for c in layout_characters(layout, style=style) if c.target.drawable
    )
    assert [c.text for c in chars] == ["W", "i"]
    window = DisplayWindow(500, 2800)
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
    # Compute expected trigger from the fixed linear body mapping, independently
    # of plan_pulses/ScaleAnimation. Quantize the three ASS animation knots.
    starts = [
        1000 + 1000 * (c.timing_region.left - layout.box.left) / layout.box.width
        for c in chars
    ]
    quantize = lambda value: floor(value / 10 + 0.5) * 10
    times = sorted(
        {
            990,
            1000,
            1100,
            1200,
            1400,
            1500,
            1600,
            2000,
            2400,
            *(
                quantize(s + offset) + delta
                for s in starts
                for offset in (0, 200, 400)
                for delta in (-10, 0, 10)
            ),
            *(t + delta for t in (1000, 1500, 2000) for delta in (-10, 0, 10)),
        }
    )
    modes = {
        "each": Pulse.each_char(scale=1.4, duration_ms=400),
        "simultaneous": Pulse.simultaneous_chars(scale=1.4, duration_ms=1000),
        "whole": Pulse.whole_syllable(scale=1.4, duration_ms=1000),
    }
    checks, geometry, counts = [], {}, {}
    for mode, pulse in modes.items():
        plan = plan_pulses(
            (pulse,),
            layout=layout,
            characters=tuple(c.target for c in chars),
            tracks=tracks_from_layout(layout),
            window=window,
        )
        layers = tuple(
            TextLayer(
                c.id,
                c.text,
                style,
                c.box,
                window,
                animations=tuple(a for a in plan.animations if a.target_id == c.id),
            )
            for c in chars
        )
        compiled = compile_layers(layers)
        document = Document.parse(header)
        document.records.extend(compiled.events)
        document.save(output / f"{mode}.ass")
        reference = Document.parse(header)
        geometry[mode] = []
        for time in times:
            positions, scales = [], []
            for index, char in enumerate(chars):
                start = starts[index] if mode == "each" else 1000
                duration = 400 if mode == "each" else 1000
                a, m, b = [
                    quantize(start + offset) for offset in (0, duration / 2, duration)
                ]
                phase = (
                    0
                    if time <= a or time >= b
                    else (time - a) / (m - a) if time < m else (b - time) / (b - m)
                )
                scale = 1 + 0.4 * phase
                px = layout.box.center if mode == "whole" else char.box.center
                py = layout.box.middle if mode == "whole" else char.box.middle
                x = px + (char.box.center - px) * scale
                y = py + (char.box.middle - py) * scale
                positions.append(x)
                scales.append(scale)
                # Static ASS: no animation planner, moves, transforms or output
                # compiler are used to construct the reference events.
                reference.records.append(
                    Line(
                        start_time=time,
                        end_time=time + 10,
                        text=(
                            rf"{{\an5\q2\shad0\pos({x:.9f},{y:.9f})"
                            rf"\fscx{100 * scale:.9f}\fscy{100 * scale:.9f}"
                            rf"\bord0\blur0\1c&HFFFFFF&\3c&H000000&\alpha&H00&}}{char.text}"
                        ),
                    )
                )
            geometry[mode].append(
                {
                    "time_ms": time,
                    "centers_x": positions,
                    "center_distance": positions[1] - positions[0],
                    "scales": scales,
                }
            )
        reference.save(output / f"{mode}-reference.ass")
        for name in (mode, mode + "-reference"):
            render(name + ".ass", str(output / f"{name}-%02d.png"), times)
        for index, time in enumerate(times):
            actual = Image.open(output / f"{mode}-{index + 1:02d}.png").convert("RGB")
            expected = Image.open(
                output / f"{mode}-reference-{index + 1:02d}.png"
            ).convert("RGB")
            difference = ImageChops.difference(actual, expected)
            maximum = max(difference.tobytes())
            checks.append(
                {
                    "name": f"{mode}-{time}",
                    "max_channel_difference": maximum,
                    "passed": maximum == 0,
                }
            )
            if maximum:
                difference.save(output / f"failure-{mode}-{time}.png")
        counts[mode] = len(compiled.events)
    manifest = {
        "font_sha256": font.sha256,
        "text": "W i",
        "spacing": 12,
        "times_ms": times,
        "frames": len(times) * 6,
        "events": counts,
        "expected_trigger_ms": starts,
        "geometry": geometry,
        "checks": checks,
        "renderer": sorted(
            {
                line[line.index("libass") :]
                for line in (output / "whole-%02d.log").read_text().splitlines()
                if "libass" in line
            }
        ),
        "limitations": [
            "Static references share measured layout but independently calculate trigger, scale, pivot and positions.",
            "This isolates pulse geometry with plain white glyphs; sweep, glow and ruby combinations have separate validation.",
            "ASS animation knots are rounded to 10 ms; geometry records describe rendered, quantized time.",
        ],
    }
    (output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not all(c["passed"] for c in checks):
        raise SystemExit("Pulse geometry validation failed")


if __name__ == "__main__":
    main()
