"""E06/E12 custom vector cue against independently transformed native ASS.

uv run python -m tools.validate_custom_cue OUTPUT
"""

import argparse
import hashlib
import json
from math import cos, pi, sin
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from examples.scene_cues import build
from kara_templater import Document, Line, Style, _metrics, load_font
from tools.validate_case_geometry import compare
from tools.validate_engine_backgrounds import ROOT, SIZE

CROP = (600, 430, 680, 510)
POINTS = ((0, -20), (6, -6), (20, 0), (6, 6), (0, 20), (-6, 6), (-20, 0), (-6, -6))


def reference(ms: int, *, offset: float = 0) -> str:
    # The fixed example requests 50 Hz midpoint sampling over its one-second life.
    progress = (ms // 20 * 20 + 10) / 1000
    angle = pi * progress
    points = tuple(
        (
            (640 + offset + x * cos(angle) - y * sin(angle)) * 8,
            (470 + x * sin(angle) + y * cos(angle)) * 8,
        )
        for x, y in POINTS
    )
    drawing = "m " + " l ".join(f"{x:.4f} {y:.4f}" for x, y in points) + " c"
    document = Document.create(styles=(Style(align=7, outline=1, shadow=0),))
    document.records.append(
        Line(
            start_time=0,
            end_time=1000,
            text=rf"{{\an7\pos(0,0)\p4\bord1\1c&HCBC0FF&\3c&HFFFFFF&\alpha&H{round(progress * 255):02X}&}}"
            + drawing,
        )
    )
    return document.dumps()


def coverage(script: str, ms: int, role: int) -> tuple[Image.Image, set[int]]:
    result = Image.new("L", SIZE)
    alpha: set[int] = set()
    for left, top, width, height, kind, color, data in _metrics.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind != role or not width or not height:
            continue
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (left, top))
        if tile.crop(CROP).getbbox() is not None:
            alpha.add(color & 255)
        result = ImageChops.lighter(result, tile)
    return result.crop(CROP), alpha


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    script = build().compile().document.dumps()
    (output / "custom-cue.ass").write_text(script)
    times = sorted({*range(0, 1000, 10), 19, 21, 329, 331, 669, 671, 999, 1000, 1001})
    checks = []
    sheet = Image.new("RGB", (720, 240), "black")
    preview = (0, 250, 500, 750, 990)
    for ms in times:
        expected_script = reference(ms)
        (output / f"reference-{ms}.ass").write_text(expected_script)
        for role in (0, 1):
            actual, actual_alpha = coverage(script, ms, role)
            expected, expected_alpha = coverage(expected_script, ms, role)
            if actual_alpha != expected_alpha:
                raise AssertionError(
                    f"cue alpha mismatch at {ms}: {actual_alpha}, {expected_alpha}"
                )
            if ms >= 1000:
                if actual.getbbox() is not None or expected.getbbox() is not None:
                    raise AssertionError("custom cue survives its trigger")
                quality = None
            else:
                quality = compare(actual, expected)
            checks.append(
                {
                    "time_ms": ms,
                    "role": role,
                    "alpha": sorted(actual_alpha),
                    "geometry": quality,
                }
            )
            if role == 0 and ms in preview:
                col = preview.index(ms)
                for row, picture in enumerate(
                    (actual, expected, ImageChops.difference(actual, expected))
                ):
                    sheet.paste(picture.convert("RGB"), (col * 140, row * 80))
                ImageDraw.Draw(sheet).text((col * 140, 0), str(ms), fill="red")
    actual, _ = coverage(script, 250, 0)
    shifted, _ = coverage(reference(250, offset=5), 250, 0)
    try:
        compare(actual, shifted)
    except AssertionError:
        pass
    else:
        raise AssertionError("five-pixel drift was not detected")
    sheet.save(output / "custom-cue-reference.png")
    report = {
        "scope": "E06/E12 custom sparkle factory: absolute position, clockwise rotation, fill/outline geometry and sampled opacity; independent scalar rotation of handwritten polygon",
        "clock": "50 Hz midpoint hold, 0–1000 ms lifetime, boundary probes",
        "font_sha256": font.sha256,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "checks": checks,
        "five_pixel_drift_detected": True,
        "remaining": ["continuous-time bounds", "other renderers"],
    }
    (output / "custom-cue-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({"checks": len(checks), "custom_vector_cue": "passed"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
