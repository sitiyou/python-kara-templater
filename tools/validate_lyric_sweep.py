"""E01 complete scene against handwritten native glow and scalar sweep bands.

uv run python -m tools.validate_lyric_sweep OUTPUT
"""

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_lyrics import build
from kara_templater import Document, Line, Style, _metrics, load_font
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT, backgrounds, preview
from tools.validate_lyric_glow import INDICES
from tools.validate_lyric_glow import reference as glow_reference


def foreground(ms: int, *, outline_width: float = 16) -> tuple[Line, ...]:
    # The already verified native reference supplies independent glyph geometry.
    bases = [
        line
        for line in Document.parse(glow_reference(0)).lines
        if r"\blur10" in line.text
    ]
    moving = [
        line
        for line in Document.parse(glow_reference(ms)).lines
        if r"\blur10" in line.text
    ]

    def x(line: Line) -> float:
        match = re.search(r"\\pos\(([-.\d]+),", line.text)
        assert match is not None
        return float(match[1])

    def width(line: Line) -> float:
        text = line.text.split("}", 1)[1]
        font, size = (
            ("Kara Test CJK", 120) if text in ("時", "々") else ("DejaVu Sans", 40)
        )
        return _metrics.text_extents(font, size, 0, 0, 100, 100, 0, 1, text)[0]

    def color(progress: float, *, reverse: bool = False) -> str:
        p = min(1, max(0, progress))
        if reverse:
            p = 1 - p
        red, green, blue = 255, round(255 - 63 * p), round(255 - 52 * p)
        return f"&H{blue:02X}{green:02X}{red:02X}&"

    result = []
    for i, line in enumerate(moving):
        unit, local = divmod(i, 5)
        first, last = (
            (unit * 5, unit * 5) if local == 0 else (unit * 5 + 1, unit * 5 + 4)
        )
        left, right = x(bases[first]), x(bases[last]) + width(bases[last])
        start = 1000 if unit == 0 else 2800
        time = ms // 20 * 20 + 10
        if ms < start:
            p = 0.0
        elif ms >= start + 1200:
            p = 1.0
        else:
            p = (time - start) / 1200
        center = left - 12 + (right - left + 24) * p
        strips: list[tuple[int, int, str, str]] = []
        for column in range(1280):
            fill = color(p if p in (0, 1) else (center - column - 0.5) / 24 + 0.5)
            outline = color(
                p if p in (0, 1) else (center - column - 0.5) / outline_width + 0.5,
                reverse=True,
            )
            if strips and strips[-1][2:] == (fill, outline):
                first_column = strips.pop()[0]
            else:
                first_column = column
            strips.append((first_column, column + 1, fill, outline))
        block, text = line.text.split("}", 1)
        block = re.sub(
            r"\\(?:[13]c&H[0-9A-F]+&|alpha&H[0-9A-F]+&|bord[\d.]+|blur[\d.]+)",
            "",
            block,
        )
        for a, b, fill, outline in strips:
            tags = rf"\bord{2 if local == 0 else 1}\blur0\alpha&H00&\1c{fill}\3c{outline}\clip({a},0,{b},720)"
            result.append(replace(line, text=block + tags + "}" + text))
    return tuple(result)


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "fonts").mkdir(exist_ok=True)
    fonts = {}
    for name in ("DejaVuSans.ttf", "KaraTestCJK.ttf"):
        path = ROOT / "tests/fonts" / name
        fonts[name] = load_font(path).sha256
        (output / "fonts" / name).write_bytes(path.read_bytes())
    compiled = build().compile()
    actual_script = compiled.document.dumps()
    intervals = static_intervals(actual_script)
    indices = tuple(
        sorted({*INDICES, *(int(item["start_ms"]) // 10 for item in intervals)})
    )
    (output / "scene.ass").write_text(actual_script)
    reference = Document.create(styles=(Style(align=7, shadow=0),))
    for index in indices:
        if index >= 500:
            continue
        ms = index * 10 + 1
        glow = tuple(
            replace(line, layer=-1) for line in Document.parse(glow_reference(ms)).lines
        )
        for line in (*glow, *foreground(ms)):
            reference.records.append(
                replace(line, start_time=index * 10, end_time=(index + 1) * 10)
            )
    reference.save(output / "reference.ass")
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 720))
    for name in hashes:
        for offset in range(0, len(indices), 24):
            batch = indices[offset : offset + 24]
            actual = preview(output, name, "scene.ass", batch)
            expected = preview(output, name, "reference.ass", batch)
            for index, a, b in zip(batch, actual, expected, strict=True):
                diff = ImageChops.difference(a, b)
                maximum = max(i % 256 for i, n in enumerate(diff.histogram()) if n)
                if maximum > 2:
                    a.save(output / "failed-actual.png")
                    b.save(output / "failed-reference.png")
                    raise AssertionError(
                        f"E01 composite differs by {maximum}/255 at {index * 10 + 1}ms on {name}"
                    )
                checks.append(
                    {
                        "time_ms": index * 10 + 1,
                        "background": name,
                        "max_rgb_difference": maximum,
                    }
                )
                if name == "checker" and index in (0, 160, 340, 499):
                    row = (0, 160, 340, 499).index(index)
                    for col, picture in enumerate(
                        (a, b, diff.point(lambda v: min(255, v * 8)))
                    ):
                        sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
    sheet.save(output / "lyric-sweep.png")
    wrong = Document.create(styles=(Style(align=7, shadow=0),))
    wrong.records.extend(
        replace(line, layer=-1) for line in Document.parse(glow_reference(1601)).lines
    )
    wrong.records.extend(foreground(1601, outline_width=24))
    wrong.save(output / "wrong-width.ass")
    actual_probe = preview(output, "black", "scene.ass", (160,))[0]
    wrong_probe = preview(output, "black", "wrong-width.ass", (160,))[0]
    fault = ImageChops.difference(actual_probe, wrong_probe).histogram()
    if max(i % 256 for i, n in enumerate(fault) if n) <= 2:
        raise AssertionError("incorrect outline transition width was not detected")
    renderer = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-f",
            "lavfi",
            "-i",
            "color=s=1280x720:d=0.01",
            "-vf",
            "ass=scene.ass:fontsdir=fonts",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=True,
    )
    report = {
        "scope": "E01 complete layered scene vs native glyph placement and scalar 24px fill/16px outline RGB fields; exhaustive column colors merged only when identical, same FFmpeg/libass for actual/reference",
        "font_sha256": fonts,
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "wrong_outline_width_detected": True,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(actual_script.encode()).hexdigest(),
        "reference_sha256": hashlib.sha256(
            (output / "reference.ass").read_bytes()
        ).hexdigest(),
        "checks": checks,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "maximum_sample_hold_seconds": 0.02,
        "remaining": [
            "continuous-time behavior outside the declared midpoint-hold model",
            "continuous ideal pulse/sweep error",
            "other renderers",
        ],
    }
    (output / "lyric-sweep-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_rgb_difference": max(c["max_rgb_difference"] for c in checks),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
