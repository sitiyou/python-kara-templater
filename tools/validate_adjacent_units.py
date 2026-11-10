"""Validate overlapping decoration transitions of neighboring source units.

Run: python -m tools.validate_adjacent_units OUTPUT
Requires ffmpeg/libass and Pillow; retains ASS, frames and renderer logs.
"""

import argparse
import json
import shutil
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    Document,
    EdgeSweep,
    EffectPlan,
    Glow,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Paint,
    PaintPair,
    RubyPolicy,
    Segment,
    Style,
    Sweep,
    TextRange,
    TextUnit,
    load_font,
    render_karaoke,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from tools.render_effects import render

TIMES = (
    1390,
    1400,
    1410,
    1440,
    1450,
    1490,
    1500,
    1550,
    1590,
    1600,
    1610,
    1740,
    1750,
    1790,
    1800,
    1810,
    2090,
    2100,
    2390,
    2400,
)
EDGES = EdgeSweep(lead_ms=200, tail_ms=300)
PAINTS = (
    Paint(Color(255, 70, 50), glow=Glow(Color(255, 70, 50), blur=30, border=3)),
    Paint(Color(50, 140, 255), glow=Glow(Color(50, 140, 255), blur=12, border=6)),
)


def scene(kind, geometry):
    style = Style(fontname="DejaVu Sans", fontsize=64, align=5)
    document = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + style.serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    source = KaraokeLine(
        (TextUnit("AV", (Segment(1000, 1500),)), TextUnit("fj", (Segment(1600, 2100),)))
    )
    target = KaraokeItem(
        "adjacent",
        source,
        "Default",
        DisplayWindow(1450, 1750) if kind == "cropped" else DisplayWindow(500, 2800),
    )

    def build(item, context):
        geometry["tracks"] = tracks_from_layout(context.layout)
        edges = {
            "no_edges": EdgeSweep(),
            "no_lead": replace(EDGES, lead_ms=0),
            "no_tail": replace(EDGES, tail_ms=0),
        }.get(kind, EDGES)
        base = KaraokeEffect(
            paints=PaintPair(Paint(Color(200, 200, 200)), PAINTS[0]),
            spans=(ColorSpan(TextRange(1, 0, 2), after=PAINTS[1]),),
            sweep=Sweep(edges=edges),
            ruby=RubyPolicy(enabled=False),
        )
        if kind != "independent":
            return base.build(item, context)
        # Build each source unit alone at its original absolute layout position.
        # No shared mask composition or cross-unit track processing participates.
        layers = []
        for index, unit in enumerate(context.layout.units):
            isolated = replace(
                item, id=f"reference-{index}", source=KaraokeLine((unit.source,))
            )
            layout = replace(context.layout, box=unit.box, units=(unit,))
            plan = replace(
                base, spans=(), paints=replace(base.paints, after=PAINTS[index])
            ).build(isolated, replace(context, layout=layout))
            layers.extend(plan.layers)
        return EffectPlan(layers=tuple(layers))

    return render_karaoke(document, (target,), effect=build)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copy2(font_path, output / "fonts" / font_path.name)
    frames, results, geometry = {}, {}, {}
    for kind in (
        "combined",
        "independent",
        "cropped",
        "no_edges",
        "no_lead",
        "no_tail",
    ):
        results[kind] = scene(kind, geometry)
        results[kind].document.save(output / f"{kind}.ass")
        render(f"{kind}.ass", str(output / f"{kind}-%02d.png"), TIMES)
        frames[kind] = [
            Image.open(output / f"{kind}-{i + 1:02d}.png").convert("RGB")
            for i in range(len(TIMES))
        ]
    checks = []
    for index, time in enumerate(TIMES):
        for kind in ("independent", "cropped"):
            expected = (
                frames["combined"][index]
                if kind != "cropped" or 1450 <= time < 1750
                else Image.new("RGB", (640, 480))
            )
            diff = ImageChops.difference(frames[kind][index], expected)
            maximum = max(diff.tobytes())
            checks.append(
                {
                    "name": f"{kind}-{time}",
                    "max_channel_difference": maximum,
                    "passed": maximum == 0,
                }
            )
            if maximum:
                diff.save(output / f"failure-{kind}-{time}.png")
    index = TIMES.index(1550)
    for kind in ("no_edges", "no_lead", "no_tail"):
        checks.append(
            {
                "name": f"overlap-differs-from-{kind}-in-singing-gap",
                "passed": ImageChops.difference(
                    frames["combined"][index], frames[kind][index]
                ).getbbox()
                is not None,
            }
        )
    tracks = geometry["tracks"]
    checks.append(
        {
            "name": "gap-has-complete-first-and-unstarted-second-body",
            "passed": tracks[0].passes[0].progress_at(1550) == 1
            and tracks[1].passes[0].progress_at(1550) == 0,
        }
    )
    manifest = {
        "font_sha256": font.sha256,
        "times_ms": TIMES,
        "frames": len(frames) * len(TIMES),
        "renderer": sorted(
            {
                line[line.index("libass") :]
                for line in (output / "combined-%02d.log").read_text().splitlines()
                if "libass" in line
            }
        ),
        "events": {k: v.event_count for k, v in results.items()},
        "checks": checks,
        "limitations": [
            "Independent reference shares per-unit recipe compiler; verifies cross-unit composition and clipping windows.",
            "Different glow colors overlap by ordinary ASS alpha composition; this does not establish seamless spatial recoloring.",
        ],
    }
    (output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not all(c["passed"] for c in checks):
        raise SystemExit("Adjacent unit validation failed")


if __name__ == "__main__":
    main()
