"""Compare whole glow, hard clipping and completion release on one scene.

Run: python -m tools.validate_glow_strategies OUTPUT
Requires ffmpeg/libass and Pillow. Retains frames, ASS and renderer logs.
"""

import argparse
import json
import shutil
from dataclasses import replace
from math import ceil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from examples.staggered_path import scene
from examples.whole_glow import WholeGlow
from kara_templater import (
    Color,
    EffectPlan,
    Glow,
    KaraokeEffect,
    Paint,
    PaintPair,
    RubyPolicy,
    Sweep,
    load_font,
)
from tools.render_effects import render

TIMES = (990, 1000, 1200, 1480, 1500, 1990, 2000, 2010, 2400)
GLOW = Glow(Color(40, 220, 255), blur=24, border=3, opacity=0.8)


def recipe(kind, geometry=None):
    def build(target, context):
        if geometry is not None:
            geometry["body"] = context.layout.units[0].box
        whole = WholeGlow(glow=GLOW).build(target, context)
        if kind == "whole":
            return whole
        body = tuple(l for l in whole.layers if l.component != "glow")
        if kind == "body":
            return EffectPlan(layers=body)
        if kind.startswith("reference_"):
            # A static reference at the exact held opacity. No dynamic callback
            # or sampling compiler participates in producing this reference.
            opacity = float(kind.removeprefix("reference_"))
            glows = tuple(
                replace(l, paint=Paint(glow=replace(GLOW, opacity=opacity)))
                for l in whole.layers
                if l.component == "glow"
            )
        else:
            local = KaraokeEffect(
                paints=PaintPair(Paint(), Paint(glow=GLOW)),
                ruby=RubyPolicy(enabled=False),
                sweep=Sweep(completion="clip" if kind == "clip" else "release"),
            ).build(target, context)
            glows = tuple(
                replace(l, component="glow", order=-1)
                for l in local.layers
                if l.paint.glow is not None
            )
        return EffectPlan(layers=(*glows, *body))

    return build


def held_opacity(time):
    # Global 40 ms sampling grid; original window begins at 500 ms.
    sample = max(500, time // 40 * 40)
    return 0.2 + 0.6 * min(1, max(0, (sample - 1000) / 1000))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copy2(font_path, output / "fonts" / font_path.name)
    kinds = ["whole", "clip", "release", "body"]
    kinds += [
        f"reference_{value}" for value in sorted({held_opacity(t) for t in TIMES})
    ]
    frames, results, geometry = {}, {}, {}
    for kind in kinds:
        results[kind] = scene(recipe(kind, geometry))
        results[kind].document.save(output / f"{kind}.ass")
        render(f"{kind}.ass", str(output / f"{kind}-%02d.png"), TIMES)
        frames[kind] = [
            Image.open(output / f"{kind}-{i + 1:02d}.png").convert("RGB")
            for i in range(len(TIMES))
        ]
    checks = []

    def compare(name, left, right, *, equal=True):
        difference = ImageChops.difference(left, right)
        maximum = max(difference.tobytes())
        checks.append(
            {
                "name": name,
                "max_channel_difference": maximum,
                "passed": (maximum == 0) if equal else (maximum > 0),
            }
        )
        if maximum and equal:
            difference.save(output / f"failure-{name}.png")

    for i, time in enumerate(TIMES):
        compare(
            f"whole-static-{time}",
            frames["whole"][i],
            frames[f"reference_{held_opacity(time)}"][i],
        )
        compare(f"clip-release-{time}", frames["clip"][i], frames["release"][i])
        if time >= 2000:
            compare(
                f"released-full-glow-{time}", frames["release"][i], frames["whole"][i]
            )
        elif time in (990, 1200, 1480):
            compare(
                f"whole-versus-front-{time}",
                frames["whole"][i],
                frames["clip"][i],
                equal=False,
            )
            body = geometry["body"]
            front = body.left + body.width * max(0, (time - 1000) / 1000)
            # Exclude two pixels around the ASS integer clip boundary to avoid
            # YUV chroma subsampling spreading color across that boundary.
            crop = (ceil(front) + 2, 0, 640, 480)
            compare(
                f"hard-clip-unreached-{time}",
                frames["clip"][i].crop(crop),
                frames["body"][i].crop(crop),
            )
            compare(
                f"whole-glow-unreached-{time}",
                frames["whole"][i].crop(crop),
                frames["body"][i].crop(crop),
                equal=False,
            )
    # Native event evidence distinguishes release from a merely generous clip
    # even when both render identically for the fixed font and decoration.
    for kind in ("clip", "release"):
        active = [
            e
            for e, _ in results[kind].event_origins
            if e.layer == 0 and e.start_time <= 2400 < e.end_time
        ]
        checks.append(
            {
                "name": f"{kind}-completion-tags",
                "passed": bool(active)
                and all((r"\clip" in e.text) == (kind == "clip") for e in active),
            }
        )

    montage = Image.new("RGB", (640 * len(TIMES), 150 * 3))
    draw = ImageDraw.Draw(montage)
    for row, kind in enumerate(("whole", "clip", "release")):
        for col, time in enumerate(TIMES):
            montage.paste(
                frames[kind][col].crop((0, 180, 640, 310)), (640 * col, 150 * row + 20)
            )
            draw.text((640 * col + 5, 150 * row + 3), f"{kind} {time}ms", fill="white")
    montage.save(output / "comparisons.png")
    manifest = {
        "font_sha256": font.sha256,
        "times_ms": TIMES,
        "frames": len(kinds) * len(TIMES),
        "renderer": sorted(
            {
                line[line.index("libass") :]
                for line in (output / "whole-%02d.log").read_text().splitlines()
                if "libass" in line
            }
        ),
        "events": {kind: result.event_count for kind, result in results.items()},
        "checks": checks,
        "limitations": [
            "Body-only fixed-font scene; ruby and mixed-color glow seams are separate checks.",
            "Whole glow uses a 40 ms hold; 1500 and 1990 ms explicitly verify held values.",
            "Static references share layout geometry but bypass dynamic sampling.",
            "Clipped and released final images can agree despite different ASS clipping tags.",
        ],
    }
    (output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not all(c["passed"] for c in checks):
        raise SystemExit("Glow strategy validation failed; inspect retained frames")


if __name__ == "__main__":
    main()
