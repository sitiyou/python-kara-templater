"""E06 measured word boxes and ribbon vs hand-authored native ASS.

uv run python -m tools.validate_word_backgrounds OUTPUT
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_cues import build
from kara_templater import Document, Line, Style, _ass_preview, _metrics, load_font
from tools.validate_case_geometry import compare
from tools.validate_cues import static_intervals
from tools.validate_custom_cue import reference as sparkle_reference
from tools.validate_engine_backgrounds import ROOT, SIZE
from tools.validate_staggered import fill


def reference() -> str:
    def width(text: str) -> float:
        return _metrics.text_extents("DejaVu Sans", 64, 0, 0, 100, 100, 0, 1, text)[0]

    hello, prefix, world, total = (
        width(text) for text in ("Hello", "Hello ", "World", "Hello World")
    )
    # 72px inline bars plus 12px gap retain their reservation after disappearing.
    x = (1280 - 84 - total) / 2 + 84
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=64, align=7, outline=1, shadow=0),
        )
    )
    for left, size in ((x - 6, hello + 12), (x + prefix - 6, world + 12)):
        document.records.append(
            Line(
                start_time=0,
                end_time=5000,
                text=rf"{{\an7\pos({left:.6f},302)\bord0\p1\1c&H462D24&}}m 0 0 l {size:.6f} 0 l {size:.6f} 80 l 0 80",
            )
        )
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            text=rf"{{\an7\pos({x:.6f},394)\bord0\p1\1c&HCBC0FF&}}m 0 0 b {total * 0.3:.6f} 20 {total * 0.7:.6f} -20 {total:.6f} 0 b {total * 0.7:.6f} -17 {total * 0.3:.6f} 23 0 3",
        )
    )
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            text=rf"{{\pos({x:.6f},310)\1c&HFFFF00&}}Hello {{\1c&HBB88FF&}}World",
        )
    )
    return document.dumps()


def complete_reference(ms: int) -> str:
    document = Document.parse(reference())
    total = _metrics.text_extents(
        "DejaVu Sans", 64, 0, 0, 100, 100, 0, 1, "Hello World"
    )[0]
    left = (1280 - 84 - total) / 2
    for index, end in enumerate((330, 670, 1000)):
        height = 48 - index * 8
        x, y = left + index * 24, 310 + (64 - height) / 2
        document.records.append(
            Line(
                start_time=0,
                end_time=end,
                text=(
                    rf"{{\an7\pos({x:.6f},{y})\p1\bord2\1c&HFFFF00&\3c&HFFFFFF&}}"
                    + f"m 0 0 l 10.8 0 l 10.8 {height} l 0 {height} l 0 0"
                ),
            )
        )
    for label, start, end in zip(
        ("3", "2", "1"), (0, 330, 670), (330, 670, 1000), strict=True
    ):
        document.records.append(
            Line(
                start_time=start,
                end_time=end,
                text=rf"{{\an7\pos(620,160)\fs72\bord0\1c&HCBC0FF&}}{label}",
            )
        )
    document.records.extend(Document.parse(sparkle_reference(ms)).lines)
    return document.dumps()


def unweighted_envelope(script: str, ms: int) -> Image.Image:
    result = Image.new("L", SIZE)
    for left, top, width, height, kind, _, data in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind not in (0, 1) or not width or not height:
            continue
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (left, top))
        result = ImageChops.lighter(result, tile)
    return result


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    compiled = build().compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    plain = reference()
    (output / "E06.ass").write_text(script)
    (output / "word-reference.ass").write_text(plain)
    checks = []
    probes = (
        0,
        1,
        19,
        20,
        21,
        250,
        329,
        330,
        331,
        500,
        669,
        670,
        671,
        990,
        999,
        1000,
        1001,
        1500,
        2500,
        3999,
        4000,
        4999,
    )
    times = sorted(
        {
            *probes,
            *(int(item["start_ms"]) for item in intervals if item["start_ms"] < 5000),
        }
    )
    for ms in times:
        plain = complete_reference(ms)
        (output / f"complete-reference-{ms}.ass").write_text(plain)
        roles = [
            ("backgrounds", 0x242D46, 0),
            ("ribbon-and-pink-cues", 0xFFC0CB, 0),
            ("hello-and-inline-bars", 0x00FFFF, 0),
            ("world", 0xFF88BB, 0),
            ("text-outlines", 0x000000, 1),
        ]
        if ms < 1000:
            roles.append(("cue-outlines", 0xFFFFFF, 1))
        for role, rgb, kind in roles:
            actual, expected = fill(script, ms, rgb, kind), fill(plain, ms, rgb, kind)
            if actual.getbbox() is None or expected.getbbox() is None:
                raise AssertionError(f"missing {role} at {ms}ms")
            raw_difference = ImageChops.difference(actual, expected).histogram()
            raw_max = max(i for i, count in enumerate(raw_difference) if count)
            if role == "cue-outlines":
                # Faded thin rings fragment at the half-alpha threshold. Compare
                # geometry before opacity, and retain the actual ring difference.
                actual = unweighted_envelope(script, ms)
                expected = unweighted_envelope(plain, ms)
            try:
                quality = compare(actual, expected)
            except AssertionError as error:
                error.add_note(f"E06 role={role}, time={ms}ms")
                raise
            checks.append(
                {
                    "time_ms": ms,
                    "role": role,
                    "max_role_coverage_difference": raw_max,
                    "uses_unweighted_scene_envelope": role == "cue-outlines",
                    **quality,
                }
            )
    for ms in (5000, 5001):
        for rgb in (0x242D46, 0xFFC0CB, 0x00FFFF, 0xFF88BB):
            if fill(script, ms, rgb).getbbox() is not None:
                raise AssertionError(f"E06 remains at {ms}ms")
    probe = complete_reference(440)
    baseline = unweighted_envelope(probe, 440)
    missing = Document.parse(probe)
    missing.records = [
        record
        for record in missing.records
        if not isinstance(record, Line) or r"\p4" not in record.text
    ]
    for name, changed in (
        ("missing sparkle", missing.dumps()),
        ("thick sparkle outline", probe.replace(r"\bord1", r"\bord8")),
    ):
        try:
            compare(unweighted_envelope(changed, 440), baseline)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"envelope oracle did not detect {name}")
    report = {
        "scope": "E06 backgrounds, colored text, ribbon, inline bars, independent numbers and animated sparkle; whole-run measurement and handwritten scalar geometry bypass DocumentLayout/CuedLayout/range_bounds",
        "font_sha256": font.sha256,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.glob("complete-reference-*.ass"))
        },
        "cue_outline_method": "Unweighted scene fill/outline outer envelope for fading cue geometry; original alpha-weighted white ring differences remain separately reported. Other color roles have separate comparisons.",
        "geometry_tolerance": "one pixel symmetric Chebyshev distance at half coverage; native whole-word measurements may differ subpixel from clustered layout",
        "checks": checks,
        "blank_times_ms": [5000, 5001],
        "static_intervals": intervals,
        "envelope_faults_detected": ["missing sparkle", "thick sparkle outline"],
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "sparkle_sample_interval_seconds": 0.02,
        "sampling_scope": "All emitted states checked; sparkle is midpoint sample-and-hold, not continuous interpolation. The independent scalar reference evaluates the same midpoints; continuous ideal motion is not claimed identical between samples.",
        "remaining": [
            "full-color layer compositing",
            "continuous-time approximation bounds",
            "other renderers",
        ],
    }
    (output / "word-backgrounds-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_edge_difference": max(
                    c["max_coverage_difference"] for c in checks
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
