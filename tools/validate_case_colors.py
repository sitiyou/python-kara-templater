"""Independent RGB equations for E09/E11 fill and outline interiors.

uv run python -m tools.validate_case_colors OUTPUT
Masks come from separately authored plain ASS, not the Scene/PaintField compiler.
Antialiased edges and blur are deliberately not claimed by this color oracle.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from examples.scene_gradient import build as gradient
from examples.scene_sweep import build as sweep
from kara_templater import Document, Line, Style, _ass_preview, load_font
from tools.validate_engine_backgrounds import (
    BACKGROUNDS,
    ROOT,
    SIZE,
    backgrounds,
    preview,
)

INDICES = (0, 50, 99, 100, 101, 150, 250, 399, 400, 401, 450, 499, 500)
PINK = (255, 192, 203)
WHITE = (255, 255, 255)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], p: float) -> tuple[int, ...]:
    weight = max(0, min(1, p))
    return tuple(
        round(x * (1 - weight) + y * weight) for x, y in zip(a, b, strict=True)
    )


def expected(case: str, role: str, x: int, ms: int) -> tuple[int, ...]:
    position = x + 0.5
    if case == "E09":
        if role == "outline":
            return mix((0, 0, 255), PINK, (position - 320) / 640)
        if position <= 640:
            return mix((0, 255, 255), PINK, (position - 320) / 320)
        return mix(PINK, WHITE, (position - 640) / 320)
    # E11 output holds 20ms midpoint samples during the 1–4s sweep. The source
    # continuous field is a separate temporal reference; this oracle tests RGB.
    if ms < 1000:
        amount = 0.0
    elif ms >= 4000:
        amount = 1.0
    else:
        sample_ms = ms // 20 * 20 + 10
        front = 222 + 836 * (sample_ms - 1000) / 3000
        width = 24 if role == "fill" else 36
        amount = (front - position) / width + 0.5
    return (
        mix(WHITE, PINK, amount)
        if role == "fill"
        else mix(PINK, (201, 37, 100), amount)
    )


def plain_script(case: str) -> str:
    document = Document.create(
        styles=(
            Style(
                fontname="DejaVu Sans",
                fontsize=112 if case == "E09" else 108,
                align=5,
                outline=3,
                shadow=0,
            ),
        )
    )
    text = (
        r"{\move(580,270,700,270,500,4500)}GRADIENT"
        if case == "E09"
        else r"{\pos(640,340)}SOFT SWEEP"
    )
    document.records.append(Line(text=text, start_time=0, end_time=5000))
    return document.dumps()


def interiors(script: str, ms: int) -> dict[str, tuple[int, ...]]:
    planes = (bytearray(SIZE[0] * SIZE[1]), bytearray(SIZE[0] * SIZE[1]))
    for left, top, width, height, kind, _, mask in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10_000
    ):
        if kind not in (0, 1):
            continue
        for y in range(max(0, -top), min(height, SIZE[1] - top)):
            for x in range(max(0, -left), min(width, SIZE[0] - left)):
                target = (top + y) * SIZE[0] + left + x
                planes[kind][target] = max(planes[kind][target], mask[y * width + x])
    fill, outline = planes
    return {
        "fill": tuple(i for i, alpha in enumerate(fill) if alpha == 255),
        "outline": tuple(
            i for i, alpha in enumerate(outline) if alpha == 255 and fill[i] == 0
        ),
    }


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    (output / "fonts").mkdir(exist_ok=True)
    font_path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts/DejaVuSans.ttf").write_bytes(font_path.read_bytes())
    backgrounds(output)
    results = []
    for case, factory in (("E09", gradient), ("E11", sweep)):
        script = f"{case}.ass"
        factory().compile().document.save(output / script)
        reference = plain_script(case)
        (output / f"{case}-plain-mask.ass").write_text(reference)
        masks = {index: interiors(reference, index * 10 + 1) for index in INDICES}
        for background in BACKGROUNDS:
            images = preview(output, background, script, INDICES)
            background_pixels = (
                Image.open(output / f"{background}.png").convert("RGB").tobytes()
            )
            counts = {"fill": 0, "outline": 0}
            errors = {"fill": 0, "outline": 0}
            for index, image in zip(INDICES, images, strict=True):
                pixels = image.tobytes()
                if index == 500:
                    if pixels != background_pixels:
                        raise AssertionError(
                            f"{case}/{background}: visible after lifetime"
                        )
                    continue
                for role, positions in masks[index].items():
                    if not positions:
                        raise AssertionError(f"{case}: empty {role} reference")
                    counts[role] += len(positions)
                    for position in positions:
                        color = expected(case, role, position % SIZE[0], index * 10 + 1)
                        actual = pixels[position * 3 : position * 3 + 3]
                        error = max(
                            abs(a - b) for a, b in zip(actual, color, strict=True)
                        )
                        errors[role] = max(errors[role], error)
                        if error > 2:
                            raise AssertionError(
                                f"{case}/{background}/{role} at {index * 10 + 1}ms, "
                                f"({position % SIZE[0]}, {position // SIZE[0]}): {tuple(actual)} != {color}"
                            )
            results.append(
                {
                    "case": case,
                    "background": background,
                    "interior_pixels_checked": counts,
                    "max_channel_error": errors,
                    "blank_after_lifetime": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
    report = {
        "scope": "E09/E11 opaque fill/stroke interiors against hand-authored native ASS silhouettes and independent scalar RGB equations",
        "resolution": SIZE,
        "max_allowed_channel_error": 2,
        "times_ms": [i * 10 + 1 for i in INDICES],
        "font_family": font.family,
        "font_sha256": font.sha256,
        "ass_sha256": {
            case: hashlib.sha256((output / f"{case}.ass").read_bytes()).hexdigest()
            for case in ("E09", "E11")
        },
        "results": results,
        "remaining": [
            "antialiased edge and blur error",
            "continuous-time approximation error",
            "other case-specific geometry references",
        ],
    }
    (output / "case-colors-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
