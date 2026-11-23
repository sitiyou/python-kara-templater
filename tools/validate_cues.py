"""E12 native-label reference, inline translation and independent cue isolation.

uv run python -m tools.validate_cues OUTPUT
"""

import argparse
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_lyric_cues import build
from kara_templater import (
    Document,
    Line,
    ObjectGroup,
    Style,
    Vec2,
    _ass_preview,
    _metrics,
    load_font,
)
from tools.validate_case_geometry import compare, mask
from tools.validate_engine_backgrounds import ROOT, SIZE


def labels_reference() -> str:
    labels = ("READY", "SET", "GO")
    widths = tuple(
        _metrics.text_extents("DejaVu Sans", 32, 0, 0, 100, 100, 0, 1, label)[0]
        for label in labels
    )
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=32, align=7, outline=0, shadow=0),
        )
    )
    for label, width, start, end in zip(
        labels, widths, (0, 330, 670), (330, 670, 1000), strict=True
    ):
        document.records.append(
            Line(
                start_time=start,
                end_time=end,
                text=rf"{{\pos({1000 + (max(widths) - width) / 2},100)\1c&HFFFF00&}}{label}",
            )
        )
    return document.dumps()


def inline_reference() -> str:
    """Measure whole native runs, then place cue/body/ruby with scalar formulas."""

    def extent(text: str, size: float) -> tuple[float, float, float, float]:
        return _metrics.text_extents("DejaVu Sans", size, 0, 0, 100, 100, 0, 1, text)

    first_width = extent("SING ", 72)[0]
    second_width = extent("ALONG", 72)[0]
    digit_width = max(extent(label, 48)[0] for label in ("3", "2", "1"))
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", align=7, shadow=0),)
    )

    def add(
        text: str, x: float, y: float, size: float, border: float, start: int, end: int
    ) -> None:
        document.records.append(
            Line(
                start_time=start,
                end_time=end,
                text=rf"{{\an7\pos({x:.6f},{y:.6f})\fs{size}\bord{border}}}" + text,
            )
        )

    for start, end in ((0, 1000), (1000, 2500), (2500, 5000)):
        first_x = 260 + (84 if start < 1000 else 0)
        second_x = first_x + first_width + (digit_width + 12 if start < 2500 else 0)
        for word, ruby, x, width in (
            ("SING ", "sing", first_x, first_width),
            ("ALONG", "along", second_x, second_width),
        ):
            add(word, x, 340, 72, 2, start, end)
            add(
                ruby,
                x + (width - extent(ruby, 36)[0]) / 2,
                340 - 36 - 8,
                36,
                1,
                start,
                end,
            )
    for index, end in enumerate((330, 670, 1000)):
        height = 48 - 8 * index
        x, y = 260 + 24 * index, 340 + (72 - height) / 2
        document.records.append(
            Line(
                start_time=0,
                end_time=end,
                text=(
                    rf"{{\an7\pos({x},{y})\p1\bord2\1c&HFFFF00&\3c&HFFFFFF&}}"
                    + f"m 0 0 l 10.8 0 l 10.8 {height} l 0 {height} l 0 0"
                ),
            )
        )
    for label, start, end in zip(
        ("3", "2", "1"), (1500, 1830, 2170), (1830, 2170, 2500), strict=True
    ):
        x = 260 + first_width + (digit_width - extent(label, 48)[0]) / 2
        add(r"{\1c&HFFFF00&}" + label, x, 352, 48, 0, start, end)
    return document.dumps()


def outline_mask(script: str, ms: int) -> Image.Image:
    result = Image.new("L", SIZE)
    for x, y, width, height, kind, color, data in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind != 1 or not width or not height:
            continue
        if color & 255:
            raise AssertionError("E12 reference requires opaque outlines")
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (x, y))
        result = ImageChops.lighter(result, tile)
    return result


def static_intervals(script: str) -> list[dict[str, int | bool]]:
    """Prove the fixed output is time-independent inside each event interval."""
    lines = tuple(line for line in Document.parse(script).lines if not line.comment)
    number = r"-?\d+(?:\.\d+)?"
    tag = re.compile(
        rf"(?:r[A-Za-z0-9_]+|fn[^\\{{}}]+|"
        rf"(?:q|an|fe|fs|b|i|u|s|fsp|pbo|p|fscx|fscy|frz|frx|fry|fax|fay|bord|blur|be|xshad|yshad){number}|"
        rf"[1-4]c&H[0-9A-F]+&|alpha&H[0-9A-F]+&|pos\({number},{number}\)|clip\({number},{number},{number},{number}\))"
    )
    for line in lines:
        block, separator, content = line.text.partition("}")
        if (
            not separator
            or not block.startswith("{\\")
            or "{" in content
            or "}" in content
        ):
            raise AssertionError("static proof requires one leading override block")
        if any(tag.fullmatch(value) is None for value in block[2:].split("\\")):
            raise AssertionError(
                "time-varying or unknown override invalidates static proof"
            )
        if not line.effect.startswith("kara:"):
            raise AssertionError("unexpected ASS Effect may change rendering over time")
    points = sorted(
        {
            0,
            6000,
            *(round(t) for line in lines for t in (line.start_time, line.end_time)),
        }
    )
    result = []
    for start, end in zip(points, points[1:], strict=False):
        active = tuple(
            line for line in lines if line.start_time <= start < line.end_time
        )
        first = _ass_preview.rasterize(script, start, *SIZE, 4_000_000, 10_000)
        for time in ((start + end) // 2, end - 1):
            if _ass_preview.rasterize(script, time, *SIZE, 4_000_000, 10_000) != first:
                raise AssertionError(f"static interval changed at {time} ms")
        result.append(
            {
                "start_ms": start,
                "end_ms": end,
                "active_events": len(active),
                "first_middle_last_identical": True,
            }
        )
    return result


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    face = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    scene = build()
    result = scene.compile()
    script = result.document.dumps()
    root = scene.objects[0]
    if not isinstance(root, ObjectGroup):
        raise AssertionError("E12 lyric root must remain an editable ObjectGroup")
    scene.objects[0] = replace(
        root, state=replace(root.state, position=root.state.position + Vec2(40, 20))
    )
    shifted = scene.compile().document.dumps()
    intervals = static_intervals(script)
    if result.max_time_quantization > 1 / 300 + 1e-12:
        raise AssertionError(
            "fixed countdown exceeds its third-second quantization bound"
        )
    try:
        static_intervals(script.replace(r"\pos(", r"\move(", 1))
    except AssertionError:
        pass
    else:
        raise AssertionError("dynamic-tag fault was not rejected")
    reference = labels_reference()
    inline = inline_reference()
    for name, text in (
        ("E12", script),
        ("E12-translated", shifted),
        ("labels-reference", reference),
        ("inline-reference", inline),
    ):
        (output / f"{name}.ass").write_text(text)
    times = (
        0,
        1,
        329,
        330,
        331,
        669,
        670,
        671,
        990,
        999,
        1000,
        1001,
        1499,
        1500,
        1501,
        1829,
        1830,
        1831,
        2169,
        2170,
        2171,
        2499,
        2500,
        2501,
        3999,
        4000,
        4999,
        5000,
        5001,
    )
    for interval in intervals:
        if not any(
            int(interval["start_ms"]) <= ms < int(interval["end_ms"]) for ms in times
        ):
            raise AssertionError(
                "reference times do not cover every static state interval"
            )
    checks = []
    top = (900, 50, 1250, 200)
    lyric = (100, 240, 1250, 600)
    sheet = Image.new("RGB", (1150, 720))
    previews = (0, 1000, 1500, 2500)
    for ms in times:
        before = mask(script, ms)
        after = mask(shifted, ms)
        label = before.crop(top)
        expected = mask(reference, ms).crop(top)
        if ms < 1000:
            quality = compare(label, expected)
        else:
            if label.getbbox() is not None:
                raise AssertionError(f"independent label remains at {ms}ms")
            quality = None
        if ImageChops.difference(label, after.crop(top)).getbbox() is not None:
            raise AssertionError(f"independent label moved with lyric at {ms}ms")
        inline_actual = before.crop(lyric)
        inline_expected = mask(inline, ms).crop(lyric)
        inline_quality = compare(inline_actual, inline_expected) if ms < 5000 else None
        actual_outline = outline_mask(script, ms).crop(lyric)
        expected_outline = outline_mask(inline, ms).crop(lyric)
        outline_quality = (
            compare(
                ImageChops.lighter(inline_actual, actual_outline),
                ImageChops.lighter(inline_expected, expected_outline),
            )
            if ms < 5000
            else None
        )
        outline_difference = ImageChops.difference(
            actual_outline, expected_outline
        ).histogram()
        if ms in previews:
            row = previews.index(ms)
            for col, picture in enumerate((inline_actual, inline_expected)):
                sheet.paste(
                    picture.convert("RGB").resize((575, 180)), (col * 575, row * 180)
                )
        translated = ImageChops.offset(before, 40, 20).crop(lyric)
        if ImageChops.difference(translated, after.crop(lyric)).getbbox() is not None:
            raise AssertionError(
                f"body/ruby/inline cue did not translate together at {ms}ms"
            )
        if ms < 5000 and before.crop(lyric).getbbox() is None:
            raise AssertionError(f"missing lyric at {ms}ms")
        if ms >= 5000 and before.getbbox() is not None:
            raise AssertionError(f"E12 remains after lifetime at {ms}ms")
        checks.append(
            {
                "time_ms": ms,
                "label_geometry": quality,
                "body_ruby_inline_geometry": inline_quality,
                "outline_envelope_geometry": outline_quality,
                "max_outline_coverage_difference": max(
                    i for i, count in enumerate(outline_difference) if count
                ),
                "independent_unchanged": True,
                "lyric_translation_exact": True,
            }
        )
    expected = mask(inline, 1500).crop(lyric)
    try:
        compare(ImageChops.offset(expected, 5, 0), expected)
    except AssertionError:
        pass
    else:
        raise AssertionError("five-pixel layout drift was not detected")
    thick = inline.replace(r"\bord2", r"\bord8")
    expected_envelope = ImageChops.lighter(
        mask(inline, 0), outline_mask(inline, 0)
    ).crop(lyric)
    thick_envelope = ImageChops.lighter(mask(thick, 0), outline_mask(thick, 0)).crop(
        lyric
    )
    try:
        compare(thick_envelope, expected_envelope)
    except AssertionError:
        pass
    else:
        raise AssertionError("eight-pixel outline fault was not detected")
    sheet.save(output / "cues-reference.png")
    for line in result.document.lines:
        if not line.comment and ("kara:v1 cue" in line.text or "|!" in line.text):
            raise AssertionError("generated Dialogue retains source cue/ruby markers")
    report = {
        "scope": "E12 body/ruby/inline bars and numbers vs whole-run native measurements and scalar placement; independent READY/SET/GO vs native text; group translation isolation",
        "inline_reference_sha256": hashlib.sha256(inline.encode()).hexdigest(),
        "five_pixel_layout_drift_detected": True,
        "eight_pixel_outline_fault_detected": True,
        "outline_method": "unweighted fill/outline outer envelope with symmetric 1px half-coverage tolerance; raw ring coverage differences reported separately",
        "font_sha256": face.sha256,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
        "checks": checks,
        "static_intervals": intervals,
        "dynamic_tag_fault_detected": True,
        "max_time_quantization_seconds": result.max_time_quantization,
        "time_scope": "Fixed E12 contains only whitelisted static tags and ignored owner Effects; event intervals exhaust the output states. Native bitmap equality checked at first/middle/last integer millisecond. Ideal third-second countdown boundaries quantize by at most 1/300 second; no time approximation within each emitted interval.",
        "generated_dialogue_without_source_markers": True,
        "remaining": [
            "full-color composition",
            "generic animated cue continuous-time bounds (not the static E12 fixture)",
            "other renderers",
        ],
    }
    (output / "cues-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"checks": len(checks), "labels_and_group_isolation": "passed"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
