"""E01 foreground body/ruby geometry vs hand-authored native text.

uv run python -m tools.validate_lyric_geometry OUTPUT
Glow/outline composition is deliberately excluded from this geometry oracle.
"""

import argparse
import hashlib
import json
from math import pi, sin
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_lyrics import build
from kara_templater import Document, Line, Style, _ass_preview, _metrics, load_font
from tools.validate_case_geometry import compare
from tools.validate_engine_backgrounds import ROOT, SIZE


def foreground(script: str, ms: int) -> Image.Image:
    result = Image.new("L", SIZE)
    for left, top, width, height, kind, color, data in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind != 0 or color & 255 or not width or not height:
            continue
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (left, top))
        result = ImageChops.lighter(result, tile)
    return result


def reference(ms: int) -> str:
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    body_width = _metrics.text_extents(
        "Kara Test CJK", 120, 0, 0, 100, 100, 0, 1, "時"
    )[0]
    for i, (body, ruby, start) in enumerate(
        (("時", "toki", 1000), ("々", "doki", 2800))
    ):
        scale = 1.0
        if start <= ms < start + 1200:
            sample = ms // 20 * 20 + 10
            scale += 0.08 * sin(pi * (sample - start) / 1200) ** 2
        center = 640 + (i - 0.5) * body_width
        ruby_width = _metrics.text_extents(
            "DejaVu Sans", 40, 0, 0, 100, 100, 0, 1, ruby
        )[0]
        for text, font, size, width, y in (
            (body, "Kara Test CJK", 120, body_width, -60),
            (ruby, "DejaVu Sans", 40, ruby_width, -108),
        ):
            x = center - width / 2 * scale
            top = 400 + y * scale
            document.records.append(
                Line(
                    start_time=0,
                    end_time=5000,
                    text=rf"{{\fn{font}\fs{size}\an7\pos({x:.6f},{top:.6f})\fscx{100 * scale:.6f}\fscy{100 * scale:.6f}}}{text}",
                )
            )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fonts = [
        load_font(ROOT / "tests/fonts" / name).sha256
        for name in ("DejaVuSans.ttf", "KaraTestCJK.ttf")
    ]
    script = build().compile().document.dumps()
    (output / "E01.ass").write_text(script)
    times = sorted(
        {
            *range(0, 5000, 100),
            *(t + d for t in (1000, 2200, 2800, 4000) for d in (-1, 0, 1)),
            4999,
        }
    )
    checks = []
    for ms in times:
        plain = reference(ms)
        actual, expected = foreground(script, ms), foreground(plain, ms)
        checks.append({"time_ms": ms, **compare(actual, expected)})
        if ms in (0, 1600, 3400):
            (output / f"reference-{ms}.ass").write_text(plain)
            actual.crop((500, 260, 780, 490)).save(output / f"actual-{ms}.png")
            expected.crop((500, 260, 780, 490)).save(output / f"reference-{ms}.png")
    for ms in (5000, 5001):
        if foreground(script, ms).getbbox() is not None:
            raise AssertionError(f"foreground remains at {ms}ms")
    report = {
        "scope": "E01 opaque foreground geometry only, independently measured native whole body/ruby strings and scalar shared pulse; excludes glow/outline/color",
        "font_sha256": fonts,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "geometry_tolerance": "one pixel symmetric Chebyshev distance at half coverage",
        "checks": checks,
        "blank_times_ms": [5000, 5001],
        "remaining": [
            "sweep colors and glow/outline composition",
            "continuous-time error",
            "other renderers",
        ],
    }
    (output / "lyric-geometry-validation.json").write_text(
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
