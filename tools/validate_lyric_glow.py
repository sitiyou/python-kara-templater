"""E01 isolated two-layer glow against independently placed native glyphs.

uv run python -m tools.validate_lyric_glow OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from math import pi, sin
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_lyrics import build
from kara_templater import (
    Document,
    Line,
    ObjectGroup,
    Scene,
    Style,
    _metrics,
    load_font,
)
from tools.validate_engine_backgrounds import ROOT, backgrounds, preview

INDICES = (
    0,
    99,
    100,
    130,
    160,
    190,
    219,
    220,
    279,
    280,
    310,
    340,
    370,
    399,
    400,
    499,
    500,
)


def reference(ms: int) -> str:
    def width(text: str, font: str, size: float) -> float:
        return _metrics.text_extents(font, size, 0, 0, 100, 100, 0, 1, text)[0]

    document = Document.create(styles=(Style(align=7, shadow=0),))
    body_width = width("時", "Kara Test CJK", 120)
    for index, (body, ruby, start) in enumerate(
        (("時", "toki", 1000), ("々", "doki", 2800))
    ):
        scale = 1.0
        if start <= ms < start + 1200:
            scale += 0.08 * sin(pi * (ms // 20 * 20 + 10 - start) / 1200) ** 2
        center = 640 + (index - 0.5) * body_width
        for border, blur, alpha in ((5, 10, 166), (3, 3, 102)):
            for text, font, size, y in (
                (body, "Kara Test CJK", 120, -60),
                (ruby, "DejaVu Sans", 40, -108),
            ):
                shaped = _metrics.text_shape(font, size, 0, 0, 100, 100, 0, 1, text)[4]
                if len(shaped) != len(text):
                    raise AssertionError(
                        "fixed reference expects one drawable glyph per code point"
                    )
                positions = []
                for character, glyph in zip(text, shaped, strict=True):
                    isolated = _metrics.text_shape(
                        font, size, 0, 0, 100, 100, 0, 1, character
                    )[4]
                    if len(isolated) != 1:
                        raise AssertionError(
                            "fixed reference expects one isolated glyph"
                        )
                    dx = glyph[0][0][0] - isolated[0][0][0][0]
                    positions.append((character, dx, width(character, font, size)))
                total = max(dx + advance for _, dx, advance in positions)
                for character, dx, _ in positions:
                    x = center + (dx - total / 2) * scale
                    top = 400 + y * scale
                    document.records.append(
                        Line(
                            start_time=0,
                            end_time=5000,
                            text=(
                                rf"{{\an7\pos({x:.6f},{top:.6f})\fn{font}\fs{size}\fscx{scale * 100:.6f}\fscy{scale * 100:.6f}"
                                rf"\1c&HCBC0FF&\3c&HCBC0FF&\bord{border}\blur{blur}\alpha&H{alpha:02X}&}}{character}"
                            ),
                        )
                    )
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "fonts").mkdir(exist_ok=True)
    fonts = {}
    for name in ("DejaVuSans.ttf", "KaraTestCJK.ttf"):
        path = ROOT / "tests/fonts" / name
        fonts[name] = load_font(path).sha256
        (output / "fonts" / name).write_bytes(path.read_bytes())
    source = build()
    root = source.objects[0]
    assert isinstance(root, ObjectGroup)
    glows = replace(
        root,
        children=tuple(
            child for child in root.children if child.id.startswith(("wide:", "near:"))
        ),
    )
    if len(glows.children) != 4:
        raise AssertionError("E01 must contain wide/near glow for both units")
    result = Scene(Document.create()).add(glows).compile()
    script = result.document.dumps()
    (output / "glow.ass").write_text(script)
    refs = {i: reference(i * 10 + 1) for i in INDICES}
    for i, text in refs.items():
        (output / f"reference-{i}.ass").write_text(text)
    hashes = backgrounds(output)
    reference_document = Document.create(styles=(Style(align=7, shadow=0),))
    for index, text in refs.items():
        if index >= 500:
            continue
        for line in Document.parse(text).lines:
            reference_document.records.append(
                replace(line, start_time=index * 10, end_time=(index + 1) * 10)
            )
    reference_document.save(output / "reference.ass")
    checks = []
    sheet = Image.new("RGB", (960, 720))
    for name in hashes:
        frames = preview(output, name, "glow.ass", INDICES)
        expected_frames = preview(output, name, "reference.ass", INDICES)
        for index, actual, expected in zip(
            INDICES, frames, expected_frames, strict=True
        ):
            diff = ImageChops.difference(actual, expected)
            maximum = max(i % 256 for i, n in enumerate(diff.histogram()) if n)
            if maximum > 2:
                actual.save(output / "failed-actual.png")
                expected.save(output / "failed-reference.png")
                raise AssertionError(
                    f"glow differs by {maximum}/255 at {index * 10 + 1} ms on {name}"
                )
            if name == "checker" and index in (0, 160, 340, 499):
                row = (0, 160, 340, 499).index(index)
                for col, picture in enumerate((actual, expected, diff)):
                    sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
            checks.append(
                {
                    "time_ms": index * 10 + 1,
                    "background": name,
                    "max_rgb_difference": maximum,
                }
            )
    sheet.save(output / "lyric-glow.png")
    (output / "wrong-opacity.ass").write_text(
        reference_document.dumps().replace(r"\alpha&H66&", r"\alpha&HA6&")
    )
    correct = preview(output, "black", "glow.ass", (0,))[0]
    wrong = preview(output, "black", "wrong-opacity.ass", (0,))[0]
    fault = ImageChops.difference(correct, wrong).histogram()
    if max(i % 256 for i, n in enumerate(fault) if n) <= 2:
        raise AssertionError("wrong near-glow opacity was not detected")
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
            "ass=glow.ass:fontsdir=fonts",
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
        "scope": "E01 isolated wide/near pink glow layers, including ruby glyph overlap and shared pulse; independent scalar pulse and native outline-derived glyph placement; handwritten standard ASS rendered with the same FFmpeg/libass",
        "font_sha256": fonts,
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "wrong_opacity_fault_detected": True,
        "reference_sha256": hashlib.sha256(
            (output / "reference.ass").read_bytes()
        ).hexdigest(),
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "checks": checks,
        "remaining": [
            "foreground sweep/outline and complete layered scene",
            "continuous ideal pulse error",
            "other renderers",
        ],
    }
    (output / "lyric-glow-validation.json").write_text(
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
