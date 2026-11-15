"""E04 lyric layout and sweep against scalar colors and handwritten native ASS.

uv run python -m tools.validate_sakura_lyrics OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops

from examples.scene_sakura import build
from kara_templater import Document, Line, Scene, Style, _metrics, load_font
from tools.validate_cues import static_intervals
from tools.validate_engine_backgrounds import ROOT, backgrounds, preview


def reference(*, wrong_color: bool = False) -> str:
    word = "SAKURA"
    _, _, _, _, glyphs = _metrics.text_shape(
        "DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, word
    )
    placements: list[tuple[str, float, float, float]] = []
    for letter, glyph in zip(word, glyphs, strict=True):
        solo = _metrics.text_shape("DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, letter)[4][
            0
        ]
        x, y = glyph[0][0][0] - solo[0][0][0], glyph[0][0][1] - solo[0][0][1]
        width = _metrics.text_extents("DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, letter)[
            0
        ]
        placements.append((letter, x, y, width))
    width = max(x + w for _, x, _, w in placements)
    left = (1280 - width) / 2
    document = Document.create(
        styles=(
            Style(fontname="DejaVu Sans", fontsize=72, align=7, outline=1, shadow=0),
        )
    )
    boundaries = (0, *range(1000, 2001, 20), 5000)
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        p = 0 if start < 1000 else 1 if start >= 2000 else (start + 10 - 1000) / 1000
        front = left - 16 + (width + 32) * p

        def color(x: int, transition: int, center: float) -> str:
            t = max(0, min(1, (center - (x + 0.5)) / transition + 0.5))
            red = 0 if wrong_color else 255
            return f"&H{round(255 - 52 * t):02X}{round(255 - 63 * t):02X}{red:02X}&"

        pairs = [(color(x, 24, front), color(x, 32, front)) for x in range(1280)]
        a = 0
        for b in range(1, 1281):
            if b < 1280 and pairs[b] == pairs[a]:
                continue
            fill, outline = pairs[a]
            for letter, x, y, _ in placements:
                document.records.append(
                    Line(
                        start_time=start,
                        end_time=end,
                        text=rf"{{\pos({left + x:.6f},{300 + y:.6f})\clip({a},0,{b},720)\1c{fill}\3c{outline}}}{letter}",
                    )
                )
            a = b
    return document.dumps()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(path.read_bytes())
    compiled = Scene(Document.create()).add(build().objects[0]).compile()
    script = compiled.document.dumps()
    intervals = static_intervals(script)
    indices = tuple(
        sorted(
            {
                0,
                99,
                100,
                150,
                250,
                350,
                399,
                400,
                499,
                500,
                *(int(i["start_ms"]) // 10 for i in intervals),
            }
        )
    )
    target = reference()
    (output / "scene.ass").write_text(script)
    (output / "reference.ass").write_text(target)
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 720))
    for name in hashes:
        for offset in range(0, len(indices), 24):
            batch = indices[offset : offset + 24]
            actual_frames = preview(output, name, "scene.ass", batch)
            target_frames = preview(output, name, "reference.ass", batch)
            for index, actual, wanted in zip(
                batch, actual_frames, target_frames, strict=True
            ):
                diff = ImageChops.difference(actual, wanted)
                error = max(i % 256 for i, n in enumerate(diff.histogram()) if n)
                assert error <= 2, (name, index, error)
                checks.append(
                    {
                        "time_ms": index * 10 + 1,
                        "background": name,
                        "max_rgb_difference": error,
                    }
                )
                if name == "checker" and index in (100, 150, 250, 350):
                    row = (100, 150, 250, 350).index(index)
                    for col, picture in enumerate(
                        (actual, wanted, diff.point(lambda v: min(255, v * 8)))
                    ):
                        sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
        print(name + ": passed", flush=True)
    (output / "wrong.ass").write_text(reference(wrong_color=True))
    a = preview(output, "black", "scene.ass", (250,))[0]
    b = preview(output, "black", "wrong.ass", (250,))[0]
    assert (
        max(i % 256 for i, n in enumerate(ImageChops.difference(a, b).histogram()) if n)
        > 2
    )
    sheet.save(output / "sakura-lyrics.png")
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
        "scope": "E04 isolated lyrics: native glyph displacement and advance measurements, independent centering and 24/32px sweep formulas; same FFmpeg/libass complete RGB frames",
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "font_sha256": font.sha256,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": hashlib.sha256(target.encode()).hexdigest(),
        "checks": checks,
        "static_intervals": intervals,
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "wrong_color_detected": True,
        "remaining": [
            "continuous ideal sweep error",
            "complete E04 scene acceptance",
            "other renderers",
        ],
    }
    (output / "sakura-lyrics-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
