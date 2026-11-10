"""Song cost baseline: synthetic by default, or --input SONG.ass --style STYLE."""

import argparse
import hashlib
import json
import platform
import statistics
import time
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    Document,
    DynamicEffect,
    DynamicProperties,
    Glow,
    ImportSettings,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Line,
    OutputSettings,
    Paint,
    PaintPair,
    Pulse,
    Segment,
    Style,
    TextRange,
    TextUnit,
    TrackStyle,
    import_karaoke,
    layout_characters,
    load_font,
    render_karaoke,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT

ROOT = Path(__file__).resolve().parents[1]


def workload(lines, fontname="DejaVu Sans"):
    style = Style(fontname=fontname, fontsize=48)
    document = Document.parse(
        "[Script Info]\nPlayResX: 1920\nPlayResY: 1080\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + style.serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    items = tuple(
        KaraokeItem(
            f"line:{i}",
            KaraokeLine(
                (TextUnit("Karaoke", (Segment(i * 2500 + 500, i * 2500 + 2000),)),)
            ),
            "Default",
            DisplayWindow(i * 2500, i * 2500 + 2500),
        )
        for i in range(lines)
    )
    return document, items


def effect(kind):
    red, blue = Paint(Color(255, 60, 60)), Paint(Color(60, 100, 255))

    def build(target, context):
        base = KaraokeEffect(paints=PaintPair(after=red))
        if kind == "colors":
            chars = layout_characters(context.layout, style=context.style)
            if chars:
                unit = chars[0].source.unit_index
                selected = [c for c in chars if c.source.unit_index == unit][:3]
                base = replace(
                    base,
                    spans=(
                        ColorSpan(
                            TextRange(
                                unit, selected[0].source.start, selected[-1].source.end
                            ),
                            after=blue,
                        ),
                    ),
                )
        elif kind == "sampled_constant":
            base = replace(base, dynamic=DynamicEffect(lambda ctx: DynamicProperties()))
        elif kind in {"union4", "priority4"}:
            tracks = tuple(
                replace(
                    track,
                    id=f"{track.id}/{i}",
                    passes=tuple(
                        replace(
                            p,
                            start_ms=min(
                                p.end_ms,
                                p.start_ms + (i * 100 if kind == "priority4" else 0),
                            ),
                        )
                        for p in track.passes
                    ),
                )
                for track in tracks_from_layout(context.layout)
                for i in range(4)
            )
            styles = (
                tuple(
                    TrackStyle(t.id, red if i % 2 else blue, i % 4)
                    for i, t in enumerate(tracks)
                )
                if kind == "priority4"
                else ()
            )
            base = replace(
                base,
                tracks=tracks,
                track_styles=styles,
                overlap="priority" if kind == "priority4" else "union",
            )
        elif kind == "pulse_glow":
            base = replace(
                base,
                paints=PaintPair(
                    after=replace(red, glow=Glow(red.fill, blur=8, border=3))
                ),
                pulses=(Pulse.each_char(),),
            )
        return base.build(target, context)

    return build


def ass_workload(path, *, styles=None, karaoke_comments=False, font_family=None):
    document = Document.load(path)
    if karaoke_comments:
        # Select only original Aegisub karaoke sources, never generated fx or
        # template comments. No embedded code or external application is run.
        document.records = [
            replace(r, comment=False, effect="") if isinstance(r, Line) else r
            for r in document.records
            if not isinstance(r, Line) or (r.comment and r.effect == "karaoke")
        ]
    imported = import_karaoke(document, settings=ImportSettings(styles=styles))
    if not imported.items:
        raise ValueError("selected input has no timed karaoke lines")
    document.records = [
        replace(r, fontname=font_family) if isinstance(r, Style) and font_family else r
        for r in document.records
        if not isinstance(r, Line)
    ]
    return document, imported.items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lines", type=int, default=120)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-events", type=int, default=200000)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--style", action="append")
    parser.add_argument("--karaoke-comments", action="store_true")
    parser.add_argument(
        "--font", type=Path, default=ROOT / "tests/fonts/DejaVuSans.ttf"
    )
    args = parser.parse_args()
    if args.lines <= 0 or args.runs <= 0 or args.max_events <= 0:
        parser.error("lines, runs and max-events must be positive")
    font = load_font(args.font)
    document, items = (
        ass_workload(
            args.input,
            styles=tuple(args.style) if args.style else None,
            karaoke_comments=args.karaoke_comments,
            font_family=font.family,
        )
        if args.input
        else workload(args.lines, font.family)
    )
    results = {}
    for kind in (
        "plain",
        "colors",
        "union4",
        "priority4",
        "pulse_glow",
        "sampled_constant",
    ):
        timings = []
        estimates = []
        for _ in range(args.runs):
            started = time.perf_counter()
            result = render_karaoke(
                document,
                items,
                effect=effect(kind),
                settings=OutputSettings(
                    resolution=(int(document.meta.res_x), int(document.meta.res_y)),
                    max_events=args.max_events,
                ),
                on_estimate=estimates.append,
            )
            elapsed = time.perf_counter() - started
            timings.append(elapsed * 1000)
        results[kind] = {
            "median_ms": statistics.median(timings),
            "runs_ms": timings,
            "events": result.event_count,
            "planned_layers": result.layer_count,
            "bytes": len(result.document.dumps().encode()),
            "events_per_line": result.event_count / len(items),
            "diagnostics": len(result.diagnostics),
            "estimated_events": estimates[-1].estimated_events,
            "target_samples": estimates[-1].target_samples,
        }
        print(kind, results[kind], flush=True)
    assert results["union4"]["events"] == results["plain"]["events"], (
        "identical tracks must not duplicate output"
    )
    assert results["sampled_constant"]["events"] == results["plain"]["events"]
    fingerprint = hashlib.sha256()
    for path in sorted((ROOT / "kara_templater").glob("*.py")):
        fingerprint.update(path.name.encode() + path.read_bytes())
    report = {
        "workload": "imported ASS song"
        if args.input
        else "synthetic 7-character lyrics, 1.5-second singing, 2.5-second display",
        "lines": len(items),
        "resolution": [int(document.meta.res_x), int(document.meta.res_y)],
        "max_events": args.max_events,
        "units": sum(len(i.source.units) for i in items),
        "segments": sum(len(u.segments) for i in items for u in i.source.units),
        "duration_ms": max(i.window.end_ms for i in items),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest()
        if args.input
        else None,
        "input": str(args.input) if args.input else None,
        "styles": args.style,
        "karaoke_comments": args.karaoke_comments,
        "font_family": font.family,
        "font": str(args.font),
        "font_sha256": font.sha256,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_sha256": fingerprint.hexdigest(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "timing_scope": "render_karaoke including layout/build/compile; excludes import, font registration and serialization",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
