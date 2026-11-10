"""Render visual invariants with a pinned font: python -m tools.validate_effects OUTPUT."""

import argparse
import json
import shutil
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    Document,
    DynamicEffect,
    DynamicProperties,
    EdgeSweep,
    EffectPlan,
    Fade,
    Glow,
    HighlightTrack,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Line,
    Paint,
    PaintPair,
    ProgressCurve,
    Pulse,
    Region,
    RenderResult,
    RubyPaint,
    RubyPolicy,
    Segment,
    SingingPass,
    Style,
    Sweep,
    TextLayer,
    TextRange,
    TextUnit,
    TrackStyle,
    layout_characters,
    load_font,
    render_karaoke,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT

FONT = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
PHASE_TIMES = {
    "pre_sweep_start": (890, 900, 910),
    "singing_start": (990, 1000),
    "guide_start": (1190, 1200),
    "curve_pause_start": (1240, 1250, 1260),
    "curve_pause_end": (1490, 1500, 1510),
    "ruby_second_segment": (1590, 1600),
    "priority_exit": (1690, 1700),
    "guide_end": (1790, 1800, 1810),
    "singing_and_pulse_end": (1990, 2000, 2010),
    "decoration_tail_end": (2190, 2200, 2210),
    "display_end": (2490, 2500),
}
# 1380/1480 are the linear reference times for the nonlinear 1190/1240 frames.
TIMES = tuple(
    sorted(
        {1380, 1400, 1480, 2400, *(t for times in PHASE_TIMES.values() for t in times)}
    )
)
MONTAGE_TIMES = (900, 1000, 1250, 1500, 1700, 2000, 2200, 2500)
RED, BLUE = Color(255, 40, 40), Color(40, 90, 255)
RESOLUTIONS = {
    "wide": (960, 540),
    "size_large_tall": (1280, 1440),
    "size_large_control": (1280, 720),
    "size_small_short": (640, 360),
    "size_small_control": (640, 480),
}


def scene(kind, resolution=(640, 480)):
    if kind in {"arc_path", "arc_reference"}:
        from examples.staggered_path import ArcWave
        from examples.staggered_path import scene as arc_scene

        return arc_scene(
            ArcWave(width=0, height=0) if kind == "arc_reference" else ArcWave()
        )
    style = Style(
        fontname="DejaVu Sans", fontsize=64, align=5, italic=kind.startswith("oblique_")
    )
    if kind.startswith("size_"):
        large = kind.startswith("size_large_")
        style = replace(
            style, fontsize=96 if large else 32, align=2, margin_v=60 if large else 30
        )
    document = Document.parse(
        f"[Script Info]\nPlayResX: {resolution[0]}\nPlayResY: {resolution[1]}\n"
        "ScaledBorderAndShadow: yes\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + style.serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    if kind.startswith("stack_"):
        body = KaraokeItem(
            "body",
            KaraokeLine((TextUnit("M", (Segment(1000, 2000),)),)),
            "Default",
            DisplayWindow(500, 2500),
        )
        guide = KaraokeItem(
            "guide",
            KaraokeLine((TextUnit("M", (Segment(1200, 1600),)),)),
            "Default",
            DisplayWindow(1200, 1800),
        )
        reverse = kind.endswith("reverse")
        if "reference" in kind:
            position = r"\an5\q2\shad0\pos(320,240)\fscx100\fscy100"
            lines = (
                Line(
                    layer=2 if reverse else 0,
                    start_time=500,
                    end_time=2500,
                    text="{"
                    + position
                    + r"\bord4\blur12\1c&H2828FF&\3c&H2828FF&\alpha&H80&}M",
                ),
                Line(
                    layer=3 if reverse else 1,
                    start_time=500,
                    end_time=2500,
                    text="{"
                    + position
                    + r"\bord0\blur0\1c&H2828FF&\3c&H000000&\alpha&H00&}M",
                ),
                Line(
                    layer=1 if reverse else 3,
                    start_time=1200,
                    end_time=1800,
                    text="{"
                    + position
                    + r"\bord0\blur0\1c&HFF5A28&\3c&H000000&\alpha&H80&}M",
                ),
            )
            document.records.extend(lines)
            return RenderResult(document, (), len(lines), len(lines))
        body_paint = Paint(RED, glow=Glow(RED, blur=12, border=4, opacity=0.5))
        guide_paint = Paint(BLUE, opacity=0.5)

        def build(target, context):
            recipe = (
                KaraokeEffect.guide(paints=PaintPair(guide_paint, guide_paint))
                if target.id == "guide"
                else KaraokeEffect(
                    paints=PaintPair(body_paint, body_paint),
                    ruby=RubyPolicy(enabled=False),
                )
            )
            return recipe.build(target, context)

        items = (
            (body,)
            if kind == "stack_body"
            else (guide, body)
            if reverse
            else (body, guide)
        )
        return render_karaoke(document, items, effect=build)
    item = KaraokeItem(
        "visual",
        KaraokeLine((TextUnit("Karaoke", (Segment(1000, 2000),)),)),
        "Default",
        DisplayWindow(500, 2500),
    )
    if kind.startswith("colors_"):
        inherited = kind.startswith("colors_inherit")
        item = replace(
            item,
            source=KaraokeLine(
                (
                    TextUnit("A", (Segment(1000, 2000, "a"),)),
                    TextUnit("B", (Segment(1000, 2000, "b"),)),
                )
                if inherited
                else (TextUnit("AB", (Segment(1000, 2000, "ab"),)),),
            ),
        )
    if kind.startswith("ruby_"):
        item = replace(
            item,
            source=KaraokeLine(
                (
                    TextUnit(
                        "Karaoke",
                        (
                            Segment(1000, 1400, "ka"),
                            Segment(1600, 2000, "raoke"),
                        ),
                    ),
                )
            ),
        )
    if kind.startswith("adjacent_"):
        item = replace(
            item,
            source=KaraokeLine(
                (
                    TextUnit(
                        "Karaoke",
                        (Segment(1000, 1500), Segment(1500, 2000)),
                    ),
                )
            ),
        )
    if kind.endswith("_cropped"):
        item = replace(item, window=DisplayWindow(1200, 1800))
    if kind.startswith(("decorated_", "oblique_")):
        item = replace(
            item, source=KaraokeLine((TextUnit("AV fj", (Segment(1000, 2000),)),))
        )

    def build(target, context):
        if kind.startswith("colors_"):
            inherited = kind.startswith("colors_inherit")
            theme = PaintPair(Paint(Color(255, 255, 255)), Paint(RED))
            alternate = PaintPair(Paint(BLUE), Paint(Color(255, 40, 200)))
            reading = PaintPair(Paint(Color(40, 255, 80)), Paint(Color(40, 255, 255)))
            if kind.endswith(("_before", "_after")):
                state = "before" if kind.endswith("_before") else "after"
                layers = [
                    TextLayer(
                        c.id,
                        c.text,
                        context.style,
                        c.box,
                        target.window,
                        getattr(alternate if c.text == "B" else theme, state),
                    )
                    for c in layout_characters(context.layout, style=context.style)
                ]
                for ui, unit in enumerate(context.layout.units):
                    for si, segment in enumerate(unit.segments):
                        pair = (
                            (alternate if ui == 1 else theme) if inherited else reading
                        )
                        layers.append(
                            TextLayer(
                                f"ruby:{ui}:{si}",
                                segment.source.ruby,
                                context.ruby_style,
                                segment.ruby,
                                target.window,
                                getattr(pair, state),
                            )
                        )
                return EffectPlan(tuple(layers))
            return KaraokeEffect(
                paints=theme,
                spans=(
                    ColorSpan(
                        TextRange(1, 0, 1) if inherited else TextRange(0, 1, 2),
                        before=alternate.before,
                        after=alternate.after,
                    ),
                ),
                ruby_paints=() if inherited else (RubyPaint(0, 0, reading),),
            ).build(target, context)
        region = Region(context.layout.box.left, context.layout.box.right)
        base = HighlightTrack("base", 0, (SingingPass(1000, 2000, region),))
        tracks, styles, overlap = (base,), (), "union"
        dynamic = None
        before, after = Paint(Color(255, 255, 255)), Paint(RED)
        if kind.startswith(("adjacent_", "whole_")):
            after = Paint(RED, glow=Glow(RED, blur=30, border=3))
            if kind.startswith("adjacent_"):
                tracks = (
                    replace(
                        base,
                        passes=(
                            SingingPass(1000, 1500, Region(region.left, region.center)),
                            SingingPass(
                                1500, 2000, Region(region.center, region.right)
                            ),
                        ),
                    ),
                )
        if kind.startswith(("decorated_", "oblique_")):
            after = Paint(
                RED, outline=BLUE, border=8, glow=Glow(RED, blur=30, border=12)
            )
            if kind.endswith("reference"):
                return EffectPlan(
                    tuple(
                        TextLayer(
                            f"{target.id}/{c.id}",
                            c.text,
                            context.style,
                            c.box,
                            target.window,
                            after,
                        )
                        for c in layout_characters(context.layout, style=context.style)
                    )
                )
        if kind == "union":
            tracks = (base, replace(base, id="duplicate"))
        elif kind in {"speed_pause", "speed_pause_glow", "manual_partition"}:
            if kind == "manual_partition":
                passes = (
                    SingingPass(1000, 1250, Region(region.left, region.center)),
                    SingingPass(1500, 2000, Region(region.center, region.right)),
                )
            else:
                passes = (
                    SingingPass(
                        1000,
                        2000,
                        region,
                        ProgressCurve(((0, 0), (0.25, 0.5), (0.5, 0.5), (1, 1))),
                    ),
                )
            tracks = (replace(base, passes=passes),)
            if kind == "speed_pause_glow":
                after = Paint(RED, glow=Glow(RED, blur=30, border=3))
        elif kind in {"glow_union", "glow_partition", "glow_priority"}:
            after = Paint(RED, glow=Glow(RED, blur=30, border=3))
            if kind == "glow_union":
                tracks = (base, replace(base, id="duplicate"))
            elif kind == "glow_partition":
                tracks = (
                    replace(
                        base,
                        passes=(
                            SingingPass(1000, 2000, Region(region.left, region.center)),
                        ),
                    ),
                    HighlightTrack(
                        "right",
                        0,
                        (SingingPass(1000, 2000, Region(region.center, region.right)),),
                    ),
                )
            else:
                tracks = (
                    base,
                    HighlightTrack(
                        "top",
                        0,
                        (SingingPass(1100, 1700, region),),
                        end_behavior="hide",
                    ),
                )
                styles = (
                    TrackStyle(
                        "top", Paint(BLUE, glow=Glow(BLUE, blur=40, border=5)), 10
                    ),
                )
                overlap = "priority"
        elif kind == "priority":
            tracks = (
                base,
                HighlightTrack(
                    "top", 0, (SingingPass(1100, 1700, region),), end_behavior="hide"
                ),
            )
            styles, overlap = (TrackStyle("top", Paint(BLUE), 10),), "priority"
        elif kind in {"layer_once", "layer_twice"}:
            before, after, overlap = Paint(opacity=0), Paint(RED, opacity=0.5), "layer"
            if kind == "layer_twice":
                tracks = (base, replace(base, id="duplicate"))
                styles = (TrackStyle("duplicate", priority=1),)
        elif kind in {"glow_small", "glow_large", "glow_dynamic"}:
            after = Paint(
                RED, glow=Glow(RED, blur=3 if kind == "glow_small" else 30, border=3)
            )
            if kind == "glow_dynamic":
                dynamic = DynamicEffect(
                    lambda ctx: DynamicProperties(
                        glow_blur=3 if ctx.time_ms // 200 % 2 == 0 else 30
                    ),
                    max_glow_blur=30,
                )
        elif kind == "sampled_plain" or kind == "sampled_pulse_fade":
            dynamic = DynamicEffect(lambda ctx: DynamicProperties())
        elif kind == "sampled_pulse_offset":
            dynamic = DynamicEffect(
                lambda ctx: DynamicProperties(
                    offset_x=16 if ctx.time_ms // 200 % 2 == 0 else -16,
                    offset_y=8,
                )
            )
        elif kind in {"pulse_glow_small", "pulse_glow_large", "sampled_pulse_glow"}:
            after = Paint(
                RED,
                glow=Glow(RED, blur=3 if kind == "pulse_glow_small" else 30, border=3),
            )
            if kind == "sampled_pulse_glow":
                dynamic = DynamicEffect(
                    lambda ctx: DynamicProperties(
                        glow_blur=3 if ctx.time_ms // 200 % 2 == 0 else 30,
                    ),
                    max_glow_blur=30,
                )
        animated = "pulse" in kind
        ruby = RubyPolicy()
        if kind.startswith("ruby_"):
            tracks = tracks_from_layout(context.layout)
            animated = True
            ruby = RubyPolicy(
                offset_y=-30,
                follow="syllable"
                if kind in {"ruby_follow", "ruby_sampled"}
                else "none",
            )
            if kind == "ruby_sampled":
                dynamic = DynamicEffect(lambda ctx: DynamicProperties())
        return KaraokeEffect(
            paints=PaintPair(before, after),
            tracks=tracks,
            track_styles=styles,
            overlap=overlap,
            dynamic=dynamic,
            fade=Fade(800, 800) if animated else Fade(),
            pulses=(Pulse.whole_syllable(scale=1.3),)
            if animated and kind != "ruby_static"
            else (),
            ruby=ruby,
            sweep=Sweep(edges=EdgeSweep(lead_ms=100, tail_ms=200))
            if kind.endswith(("_tail", "_cropped"))
            else Sweep(completion="clip" if kind.endswith("_clipped") else "release"),
        ).build(target, context)

    return render_karaoke(document, (item,), effect=build)


def render(output, kind, resolution=(640, 480)):
    result = scene(kind, resolution)
    result.document.save(output / f"{kind}.ass")
    expression = "+".join(f"eq(n,{t // 10})" for t in TIMES)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={resolution[0]}x{resolution[1]}:r=100:d=3",
        "-vf",
        f"subtitles={kind}.ass:fontsdir=fonts,select='{expression}'",
        "-fps_mode",
        "vfr",
        "-y",
        f"{kind}-%02d.png",
    ]
    process = subprocess.run(
        command, cwd=output, capture_output=True, text=True, check=True
    )
    (output / f"{kind}-renderer.log").write_text(process.stderr)
    images = [
        Image.open(output / f"{kind}-{i + 1:02d}.png").convert("RGB")
        for i in range(len(TIMES))
    ]
    return (
        result,
        images,
        sorted(
            {
                line[line.index("libass") :]
                for line in process.stderr.splitlines()
                if "libass" in line
            }
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    (output / "fonts").mkdir(parents=True, exist_ok=True)
    font = load_font(FONT)
    shutil.copyfile(FONT, output / "fonts/DejaVuSans.ttf")
    oblique_path = FONT.with_name("DejaVuSans-Oblique.ttf")
    oblique = load_font(oblique_path)
    shutil.copyfile(oblique_path, output / "fonts" / oblique_path.name)
    kinds = (
        "stack_normal",
        "stack_reverse",
        "stack_reference",
        "stack_reference_reverse",
        "stack_body",
        "arc_path",
        "arc_reference",
        "colors_inherit",
        "colors_inherit_before",
        "colors_inherit_after",
        "colors_override",
        "colors_override_before",
        "colors_override_after",
        "plain",
        "union",
        "priority",
        "layer_once",
        "layer_twice",
        "glow_small",
        "glow_large",
        "glow_dynamic",
        "speed_pause",
        "speed_pause_glow",
        "manual_partition",
        "whole_tail",
        "adjacent_tail",
        "whole_cropped",
        "adjacent_cropped",
        "glow_union",
        "glow_partition",
        "glow_priority",
        "sampled_plain",
        "pulse_fade",
        "sampled_pulse_fade",
        "sampled_pulse_offset",
        "pulse_glow_small",
        "pulse_glow_large",
        "sampled_pulse_glow",
        "ruby_static",
        "ruby_none",
        "ruby_follow",
        "ruby_sampled",
        "decorated_sweep",
        "decorated_clipped",
        "decorated_reference",
        "oblique_sweep",
        "oblique_clipped",
        "oblique_reference",
        "decorated_tail",
        "oblique_tail",
        "size_large_tall",
        "size_large_control",
        "size_small_short",
        "size_small_control",
        "wide",
    )
    data = {
        kind: render(output, kind, RESOLUTIONS.get(kind, (640, 480))) for kind in kinds
    }
    checks = []

    def equality(label, a, b):
        difference = ImageChops.difference(a, b)
        difference.save(output / f"{label}-difference.png")
        checks.append({"name": label, "passed": difference.getbbox() is None})

    for i, time in enumerate(TIMES):
        for variant, reference in (
            ("stack_normal", "stack_reference"),
            ("stack_reverse", "stack_reference_reverse"),
        ):
            equality(f"{variant}-{time}", data[variant][1][i], data[reference][1][i])
        if time < 1200 or time >= 1800:
            equality(
                f"guide-absent-{time}",
                data["stack_normal"][1][i],
                data["stack_body"][1][i],
            )
        else:
            checks.append(
                {
                    "name": f"stack-order-visible-{time}",
                    "passed": ImageChops.difference(
                        data["stack_normal"][1][i], data["stack_reverse"][1][i]
                    ).getbbox()
                    is not None,
                }
            )
        equality(
            f"large-resolution-{time}",
            data["size_large_tall"][1][i].crop((0, 1200, 1280, 1440)),
            data["size_large_control"][1][i].crop((0, 480, 1280, 720)),
        )
        equality(
            f"small-resolution-{time}",
            data["size_small_short"][1][i].crop((0, 240, 640, 360)),
            data["size_small_control"][1][i].crop((0, 360, 640, 480)),
        )
        checks.append(
            {
                "name": f"visible-below-1080-{time}",
                "passed": (
                    data["size_large_tall"][1][i].crop((0, 1080, 1280, 1440)).getbbox()
                    is not None
                )
                == (time < 2500),
            }
        )
        if time in {990, 2400}:
            equality(
                f"arc-rest-{time}",
                data["arc_path"][1][i],
                data["arc_reference"][1][i],
            )
        if time in {1200, 1600}:
            checks.append(
                {
                    "name": f"arc-motion-{time}",
                    "passed": ImageChops.difference(
                        data["arc_path"][1][i],
                        data["arc_reference"][1][i],
                    ).getbbox()
                    is not None,
                }
            )
        for variant in ("colors_inherit", "colors_override"):
            if time < 1000 or time >= 2000:
                state = "before" if time < 1000 else "after"
                equality(
                    f"{variant}-{state}-{time}",
                    data[variant][1][i],
                    data[f"{variant}_{state}"][1][i],
                )

            def silhouette(frame):
                r, g, b = frame.split()
                return ImageChops.lighter(ImageChops.lighter(r, g), b).point(
                    lambda value: 255 if value else 0
                )

            # YUV video conversion gives differently coloured antialiased edges
            # different nonzero supports even in the two static references.
            # Require the common support and forbid pixels outside their union.
            actual_shape = silhouette(data[variant][1][i])
            before_shape = silhouette(data[f"{variant}_before"][1][i])
            after_shape = silhouette(data[f"{variant}_after"][1][i])
            required = ImageChops.darker(before_shape, after_shape)
            allowed = ImageChops.lighter(before_shape, after_shape)
            equality(
                f"{variant}-layout-required-{time}",
                ImageChops.darker(actual_shape, required),
                required,
            )
            equality(
                f"{variant}-layout-allowed-{time}",
                ImageChops.lighter(actual_shape, allowed),
                allowed,
            )
        for variant in ("decorated", "oblique"):
            equality(
                f"release-vs-clip-{variant}-{time}",
                data[f"{variant}_sweep"][1][i],
                data[f"{variant}_clipped"][1][i],
            )
        for suffix in ("tail", "cropped"):
            equality(
                f"adjacent-{suffix}-{time}",
                data[f"adjacent_{suffix}"][1][i],
                data[f"whole_{suffix}"][1][i],
            )
        if 1200 <= time < 1800:
            equality(
                f"cropped-original-progress-{time}",
                data["adjacent_cropped"][1][i],
                data["whole_tail"][1][i],
            )
        else:
            checks.append(
                {
                    "name": f"cropped-hidden-{time}",
                    "passed": data["adjacent_cropped"][1][i].getbbox() is None,
                }
            )
        reference_time = (
            1000 + (time - 1000) * 2
            if 1000 <= time < 1250
            else 1500
            if 1250 <= time < 1500
            else time
        )
        reference_index = TIMES.index(reference_time)
        equality(
            f"speed-position-{time}",
            data["speed_pause"][1][i],
            data["plain"][1][reference_index],
        )
        equality(
            f"speed-glow-position-{time}",
            data["speed_pause_glow"][1][i],
            data["glow_large"][1][reference_index],
        )
        equality(
            f"manual-partition-position-{time}",
            data["manual_partition"][1][i],
            data["speed_pause"][1][i],
        )
        equality(
            f"glow-union-{time}", data["glow_large"][1][i], data["glow_union"][1][i]
        )
        if time >= 1700:
            equality(
                f"glow-priority-exit-{time}",
                data["glow_large"][1][i],
                data["glow_priority"][1][i],
            )
        if time >= 2000:
            equality(
                f"glow-partition-complete-{time}",
                data["glow_large"][1][i],
                data["glow_partition"][1][i],
            )
        if time >= 2000:
            for variant in ("decorated", "oblique"):
                equality(
                    f"{variant}-unclipped-{time}",
                    data[f"{variant}_sweep"][1][i],
                    data[f"{variant}_reference"][1][i],
                )
                if time >= 2200:
                    equality(
                        f"{variant}-tail-complete-{time}",
                        data[f"{variant}_tail"][1][i],
                        data[f"{variant}_reference"][1][i],
                    )
        equality(
            f"ruby-sampling-{time}",
            data["ruby_follow"][1][i],
            data["ruby_sampled"][1][i],
        )
        equality(
            f"ruby-independent-{time}",
            data["ruby_static"][1][i].crop((0, 0, 640, 190)),
            data["ruby_none"][1][i].crop((0, 0, 640, 190)),
        )
        equality(
            f"ruby-body-unchanged-{time}",
            data["ruby_none"][1][i].crop((0, 200, 640, 480)),
            data["ruby_follow"][1][i].crop((0, 200, 640, 480)),
        )
        equality(f"union-{time}", data["plain"][1][i], data["union"][1][i])
        equality(
            f"sampling-identity-{time}",
            data["plain"][1][i],
            data["sampled_plain"][1][i],
        )
        equality(
            f"sampling-pulse-fade-{time}",
            data["pulse_fade"][1][i],
            data["sampled_pulse_fade"][1][i],
        )
        dx = 16 if (time // 40 * 40) // 200 % 2 == 0 else -16
        equality(
            f"sampling-pulse-offset-{time}",
            ImageChops.offset(data["pulse_fade"][1][i], dx, 8),
            data["sampled_pulse_offset"][1][i],
        )
        glow_kind = "pulse_glow_small" if dx == 16 else "pulse_glow_large"
        equality(
            f"sampling-pulse-glow-{time}",
            data[glow_kind][1][i],
            data["sampled_pulse_glow"][1][i],
        )
        if time >= 1700:
            equality(
                f"priority-exit-{time}", data["plain"][1][i], data["priority"][1][i]
            )
    single = data["layer_once"][1][TIMES.index(2400)].tobytes()[::3]
    index = TIMES.index(1690)
    checks.append(
        {
            "name": "glow-priority-visible-before-exit",
            "passed": ImageChops.difference(
                data["glow_priority"][1][index], data["glow_large"][1][index]
            ).getbbox()
            is not None,
        }
    )
    for variant in ("decorated", "oblique"):
        index = TIMES.index(2000)
        checks.append(
            {
                "name": f"{variant}-tail-visible-at-body-end",
                "passed": ImageChops.difference(
                    data[f"{variant}_tail"][1][index],
                    data[f"{variant}_reference"][1][index],
                ).getbbox()
                is not None,
            }
        )
    peak = TIMES.index(1500)
    checks.append(
        {
            "name": "ruby-follow-is-visible",
            "passed": ImageChops.difference(
                data["ruby_none"][1][peak].crop((0, 0, 640, 190)),
                data["ruby_follow"][1][peak].crop((0, 0, 640, 190)),
            ).getbbox()
            is not None,
        }
    )
    double = data["layer_twice"][1][TIMES.index(2400)].tobytes()[::3]
    checks.append(
        {
            "name": "intentional-layer-intensity",
            "passed": sum(double) > sum(single) * 1.3,
        }
    )
    reference_raw = data["plain"][1][TIMES.index(1500)].tobytes()
    core_colors = {
        color
        for color, _ in Counter(
            reference_raw[j : j + 3]
            for j in range(0, len(reference_raw), 3)
            if max(reference_raw[j : j + 3]) > 150
        ).most_common(2)
    }
    for i, time in enumerate(TIMES):
        reference = data["plain"][1][i]
        raw = reference.tobytes()
        pixels = [raw[j : j + 3] for j in range(0, len(raw), 3)]
        # Select fixed opaque before/after colors from the half-sung reference.
        # Re-selecting late in the song would mistake an antialiased edge shade
        # for a second fill color after all before-singing pixels disappear.
        for kind in ("glow_small", "glow_large", "glow_dynamic"):
            actual = data[kind][1][i].tobytes()
            errors = [
                max(
                    abs(a - b)
                    for a, b in zip(pixel, actual[j * 3 : j * 3 + 3], strict=True)
                )
                for j, pixel in enumerate(pixels)
                if pixel in core_colors
            ]
            maximum = max(errors, default=0)
            checks.append(
                {
                    "name": f"{kind}-body-{time}",
                    "passed": maximum <= 3,
                    "max_channel_error": maximum,
                }
            )
        # Independent static paints, without property callbacks or sampling.
        # Compare the fully sung frame including the outer glow, not just fill.
        if time >= 2000:
            expected = (
                "glow_small" if (time // 40 * 40) // 200 % 2 == 0 else "glow_large"
            )
            equality(
                f"dynamic-glow-envelope-{time}",
                data[expected][1][i],
                data["glow_dynamic"][1][i],
            )
    # Same font size at a different resolution should differ only in translation.
    equality(
        "resolution-centering",
        data["plain"][1][TIMES.index(2400)].crop((160, 160, 480, 320)),
        data["wide"][1][TIMES.index(2400)].crop((320, 190, 640, 350)),
    )
    checks.append(
        {
            "name": "pinned-renderer-api",
            "passed": any(
                "API version: 0x1705000" in line for line in data["plain"][2]
            ),
        }
    )
    montage = Image.new("RGB", (640 * len(MONTAGE_TIMES), 140 * (len(kinds) - 1)))
    draw = ImageDraw.Draw(montage)
    for row, kind in enumerate(kinds[:-1]):
        for column, time in enumerate(MONTAGE_TIMES):
            index = TIMES.index(time)
            if kind.startswith("size_"):
                width, height = RESOLUTIONS[kind]
                bottom = height - (60 if kind.startswith("size_large_") else 30)
                frame = data[kind][1][index].crop(
                    (width // 2 - 320, bottom - 110, width // 2 + 320, bottom + 10)
                )
            else:
                frame = data[kind][1][index].crop((0, 180, 640, 300))
            montage.paste(frame, (column * 640, row * 140 + 20))
            draw.text(
                (column * 640 + 5, row * 140 + 3), f"{kind}: {time} ms", fill="white"
            )
    montage.save(output / "comparisons.png")
    manifest = {
        "font_sha256": font.sha256,
        "oblique_font_sha256": oblique.sha256,
        "times_ms": TIMES,
        "phase_times_ms": PHASE_TIMES,
        "montage_times_ms": MONTAGE_TIMES,
        "renderer": data["plain"][2],
        "ffmpeg": subprocess.check_output(
            ["ffmpeg", "-version"], text=True
        ).splitlines()[0],
        "events": {kind: value[0].event_count for kind, value in data.items()},
        "size_cases": {
            kind: {
                "resolution": value[1][0].size,
                "font_size": value[0].document.styles["Default"].fontsize,
            }
            for kind, value in data.items()
            if kind.startswith("size_")
        },
        "checks": checks,
    }
    (output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if any(not check["passed"] for check in checks):
        raise SystemExit(
            "Visual invariants failed; inspect validation.json and retained frames"
        )


if __name__ == "__main__":
    main()
