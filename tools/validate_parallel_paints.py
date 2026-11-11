"""Compare simultaneous sweep policies to manually partitioned static ASS.

Run: python -m tools.validate_parallel_paints OUTPUT
"""

import argparse
import json
import shutil
from itertools import combinations, pairwise
from math import floor
from pathlib import Path

from PIL import Image, ImageChops

from kara_templater import (
    Color,
    DisplayWindow,
    Document,
    EffectPlan,
    Fade,
    Glow,
    HighlightTrack,
    KaraokeItem,
    KaraokeLine,
    Line,
    Paint,
    PaintPair,
    Region,
    RubyPolicy,
    Segment,
    SingingPass,
    Style,
    Sweep,
    TextUnit,
    TrackStyle,
    layout_characters,
    load_font,
    render_karaoke,
)
from kara_templater._compiler import _compile_targets, _prepare_targets
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from tools.render_effects import render

TIMES = (900, 1000, 1200, 1250, 1500, 1750, 1800, 1850, 2000, 2400)
GRAY, CYAN, PINK = Color(160, 160, 160), Color(40, 220, 255), Color(255, 70, 150)


def tracks(kind, decorated=False):
    # Integer boundaries and sampled front positions keep this comparison
    # independent of subpixel-to-integer clip rounding choices.
    if decorated:
        if kind == "disjoint":
            return ((240, 280, 1000, 2000, False), (320, 360, 1000, 2000, False))
        if kind in {"union", "layer_sync"}:
            return ((240, 360, 1000, 2000, False),) * 2
        return ((240, 360, 1000, 2000, False), (240, 360, 1200, 1800, True))
    if kind == "disjoint":
        return ((200, 280, 1000, 2000, False), (360, 440, 1000, 2000, False))
    if kind == "union":
        return ((200, 440, 1000, 2000, False),) * 2
    return ((200, 440, 1000, 2000, False), (200, 440, 1200, 1800, True))


def scene(kind, reference=False, *, decorated=False):
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
    item = KaraokeItem(
        "parallel",
        KaraokeLine((TextUnit("MMMM", (Segment(1000, 2000),)),)),
        "Default",
        DisplayWindow(500, 2500),
    )
    opacity = 0.5 if kind in {"union", "layer", "layer_sync"} else 1
    colors = (CYAN, CYAN if kind == "union" else PINK)
    before = Paint(
        GRAY,
        opacity=0.5,
        border=4 if decorated else 0,
        glow=Glow(GRAY, blur=12, border=4, opacity=0.3) if decorated else None,
    )
    after = tuple(
        Paint(
            c,
            opacity=opacity,
            border=4 if decorated else 0,
            glow=(
                Glow(
                    c,
                    blur=6 if i == 0 or kind == "union" else 24,
                    border=3 if i == 0 or kind == "union" else 8,
                    opacity=0.6,
                )
                if decorated
                else None
            ),
        )
        for i, c in enumerate(colors)
    )

    def build(target, context):
        if not reference:
            singing = tuple(
                HighlightTrack(
                    str(i),
                    0,
                    (SingingPass(start, end, Region(left, right)),),
                    end_behavior="hide" if hide else "hold",
                )
                for i, (left, right, start, end, hide) in enumerate(
                    tracks(kind, decorated)
                )
            )
            # Exercise the backend's complete-paint overlap policies directly;
            # the reference below independently emits static ASS rectangles.
            sweep = Sweep()
            styles = tuple(
                TrackStyle(str(i), paint, i) for i, paint in enumerate(after)
            )
            prepared = _prepare_targets(
                target,
                context,
                paints=PaintPair(before, after[0]),
                tracks=singing,
                track_styles=styles,
                sweep=sweep,
                ruby=RubyPolicy(enabled=False),
                origin_effect="ParallelPaints",
            )
            return _compile_targets(
                target,
                context,
                prepared,
                sweep=sweep,
                fade=Fade(),
                track_styles=styles,
                overlap=(
                    "union"
                    if kind == "disjoint"
                    else "layer" if kind == "layer_sync" else kind
                ),
                origin_effect="ParallelPaints",
            )
        characters = layout_characters(context.layout, style=context.style)
        lines = []
        for time in TIMES:
            active = []
            for i, (left, right, start, end, hide) in enumerate(
                tracks(kind, decorated)
            ):
                if time < start or (hide and time >= end):
                    continue
                front = left + (right - left) * min(1, (time - start) / (end - start))
                if front > left:
                    active.append((left, round(front), i))
            boundaries = sorted({0, 640, *(x for l, r, _ in active for x in (l, r))})
            for left, right in pairwise(boundaries):
                selected = [i for l, r, i in active if l <= left and right <= r]
                if kind in {"layer", "layer_sync"}:
                    stack = [before, *(after[i] for i in selected)]
                elif selected:
                    chosen = selected[-1] if kind == "priority" else selected[0]
                    stack = [after[chosen]]
                else:
                    stack = [before]
                for order, paint in enumerate(stack):
                    passes = [
                        (1, paint.fill, paint.outline, paint.border, 0, paint.opacity)
                    ]
                    if paint.glow is not None:
                        glow = paint.glow
                        passes.insert(
                            0,
                            (
                                0,
                                glow.color,
                                glow.color,
                                glow.border,
                                glow.blur,
                                paint.opacity * glow.opacity,
                            ),
                        )
                    for char in characters:
                        # No compose_masks, ClipSpan or output compiler in this
                        # reference. Each rectangle/state is explicit static ASS.
                        for sublayer, color, outline, border, blur, alpha in passes:
                            lines.append(
                                Line(
                                    start_time=time,
                                    end_time=time + 10,
                                    layer=2 * order + sublayer,
                                    text=(
                                        rf"{{\an5\q2\shad0\pos({char.box.center:.9f},{char.box.middle:.9f})"
                                        rf"\fscx100\fscy100\bord{border}\blur{blur}\clip({left},0,{right},480)"
                                        rf"\1c&H{color.blue:02X}{color.green:02X}{color.red:02X}&"
                                        rf"\3c&H{outline.blue:02X}{outline.green:02X}{outline.red:02X}&"
                                        rf"\alpha&H{floor(255 * (1 - alpha) + 0.5):02X}&}}{char.text}"
                                    ),
                                )
                            )
        return EffectPlan(raw_lines=tuple(lines))

    return render_karaoke(document, (item,), effect=build)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--decorated", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copy2(font_path, output / "fonts" / font_path.name)
    checks, counts, frames = [], {}, {}
    kinds = ("disjoint", "union", "priority", "layer") + (
        ("layer_sync",) if args.decorated else ()
    )
    for kind in kinds:
        for reference in (False, True):
            name = kind + ("-reference" if reference else "")
            result = scene(kind, reference, decorated=args.decorated)
            counts[name] = result.event_count
            result.document.save(output / (name + ".ass"))
            render(name + ".ass", str(output / f"{name}-%02d.png"), TIMES)
            frames[name] = [
                Image.open(output / f"{name}-{i + 1:02d}.png").convert("RGB")
                for i in range(len(TIMES))
            ]
        for i, time in enumerate(TIMES):
            difference = ImageChops.difference(
                frames[kind][i], frames[kind + "-reference"][i]
            )
            maximum = max(difference.tobytes())
            checks.append(
                {
                    "name": f"{kind}-{time}",
                    "max_channel_difference": maximum,
                    "passed": maximum == 0,
                }
            )
            if maximum:
                difference.save(output / f"failure-{kind}-{time}.png")
    middle = TIMES.index(1500)
    for first, second in combinations(("disjoint", "union", "priority", "layer"), 2):
        checks.append(
            {
                "name": f"distinct-{first}-{second}",
                "passed": ImageChops.difference(
                    frames[first][middle], frames[second][middle]
                ).getbbox()
                is not None,
            }
        )
    checks.append(
        {
            "name": "disjoint-gap-stays-unsung",
            "passed": ImageChops.difference(
                frames["disjoint"][middle].crop(
                    (282, 0, 318 if args.decorated else 358, 480)
                ),
                frames["disjoint"][0].crop(
                    (282, 0, 318 if args.decorated else 358, 480)
                ),
            ).getbbox()
            is None,
        }
    )
    manifest = {
        "font_sha256": font.sha256,
        "decorated": args.decorated,
        "times_ms": TIMES,
        "frames": len(TIMES) * len(frames),
        "events": counts,
        "checks": checks,
        "renderer": sorted(
            {
                line[line.index("libass") :]
                for line in (output / "layer-%02d.log").read_text().splitlines()
                if "libass" in line
            }
        ),
        "limitations": [
            "Static references share layout only; rectangle selection, colors and stack alpha are calculated independently.",
            "Decorated mode compares native hard-clipped stacks, not hypothetical smooth recoloring across different glows.",
        ],
    }
    (output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if not all(c["passed"] for c in checks):
        raise SystemExit("Parallel paint validation failed")


if __name__ == "__main__":
    main()
