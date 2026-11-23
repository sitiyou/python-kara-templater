"""E03/E06/E07/E08/E10/E12 color interiors and measured edge differences on four RGB backgrounds.

uv run python -m tools.validate_cue_colors OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops

from examples.scene_cues import build as build_words
from examples.scene_lyric_cues import build
from examples.scene_morph import build as build_morph
from examples.scene_outlines import build as build_outlines
from examples.scene_round import build as build_round
from examples.scene_writing import build as build_writing
from kara_templater import _ass_preview, load_font
from tools.validate_cues import inline_reference, labels_reference
from tools.validate_engine_backgrounds import ROOT, SIZE, backgrounds, preview
from tools.validate_morph import color_reference as morph_reference
from tools.validate_outline_motion import reference as outline_reference
from tools.validate_particle_composite import finish, over
from tools.validate_round import reference as round_reference
from tools.validate_word_backgrounds import complete_reference
from tools.validate_writing import curve_reference
from tools.validate_writing_ink import pen_reference
from tools.validate_writing_ink import reference as ink_reference

INDICES = (0, 32, 33, 66, 67, 99, 100, 149, 150, 182, 183, 216, 217, 249, 250, 499, 500)


def solids(scripts: tuple[str, ...], ms: int) -> dict[int, tuple[int, int, int]]:
    """Visible, exactly opaque single-color pixels after ordered tile overdraw."""
    result: dict[int, tuple[int, int, int]] = {}
    for script in scripts:
        for left, top, width, height, _, color, data in _ass_preview.rasterize(
            script, ms, *SIZE, 4_000_000, 10_000
        ):
            rgb = (color >> 24 & 255, color >> 16 & 255, color >> 8 & 255)
            for y in range(max(0, -top), min(height, SIZE[1] - top)):
                for x in range(max(0, -left), min(width, SIZE[0] - left)):
                    coverage = data[y * width + x]
                    if not coverage or color & 255 == 255:
                        continue
                    index = (top + y) * SIZE[0] + left + x
                    if coverage == 255 and color & 255 == 0:
                        result[index] = rgb
                    else:
                        result.pop(index, None)
    return result


type ColorCase = Literal["E12", "E06", "E03", "E07", "E08", "E10"]


def references_at(case: ColorCase, ms: int) -> tuple[str, ...]:
    match case:
        case "E12":
            return inline_reference(), labels_reference()
        case "E06":
            return (complete_reference(ms),)
        case "E03":
            return (round_reference(ms, "Kara Test CJK"),)
        case "E07":
            return (outline_reference(ms),)
        case "E10":
            return (morph_reference(ms),)
        case "E08":
            points, lengths = curve_reference()
            return ink_reference(ms, points[::20]), pen_reference(ms, points, lengths)


def validate(output: Path, case: ColorCase = "E12") -> None:
    output.mkdir(parents=True, exist_ok=True)
    font_path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(font_path.read_bytes())
    indices = (
        INDICES
        if case not in ("E03", "E07", "E10")
        else tuple(sorted({*INDICES, 120, 224, 300, 312, 324, 350, 374, 399, 400}))
    )
    if case == "E08":
        indices = (
            0,
            29,
            30,
            31,
            50,
            100,
            119,
            120,
            121,
            134,
            135,
            150,
            224,
            225,
            239,
            240,
            250,
            289,
            290,
            304,
            305,
            306,
            350,
            400,
            449,
            450,
            451,
            499,
            500,
        )
    font_hashes = {"DejaVuSans.ttf": font.sha256}
    if case == "E03":
        cjk_path = ROOT / "tests/fonts/KaraTestCJK.ttf"
        font_hashes["KaraTestCJK.ttf"] = load_font(cjk_path).sha256
        (output / "fonts/KaraTestCJK.ttf").write_bytes(cjk_path.read_bytes())
    factory = {
        "E12": build,
        "E06": build_words,
        "E03": build_round,
        "E07": build_outlines,
        "E10": build_morph,
        "E08": build_writing,
    }[case]
    script = factory().compile().document.dumps()
    (output / "scene.ass").write_text(script)
    references = {index: references_at(case, index * 10 + 1) for index in indices}
    for index, scripts in references.items():
        for part, reference in enumerate(scripts):
            (output / f"reference-{index}-{part}.ass").write_text(reference)
    hashes = backgrounds(output)
    expected_solids = {i: solids(references[i], i * 10 + 1) for i in indices}
    actual_solids = {i: solids((script,), i * 10 + 1) for i in indices}
    overlap_pixels = 0
    if case == "E08":
        for index in indices:
            ink = solids((references[index][0],), index * 10 + 1)
            tip = solids((references[index][1],), index * 10 + 1)
            overlap_pixels += len(ink.keys() & tip.keys() & actual_solids[index].keys())
        if not overlap_pixels:
            raise AssertionError("no ink/pen overlap tested")
    checks = []
    colors: dict[str, int] = {}
    sheet = Image.new("RGB", (960, 720))
    preview_indices = (120, 224, 312, 374) if case == "E03" else (0, 100, 150, 250)
    if case == "E08":
        preview_indices = (50, 150, 350, 450)
    for name in hashes:
        frames = preview(output, name, "scene.ass", indices)
        for index, actual in zip(indices, frames, strict=True):
            pixels = actual.tobytes()
            common = expected_solids[index].keys() & actual_solids[index].keys()
            if index < 500 and not (case == "E08" and index < 30) and not common:
                raise AssertionError("missing solid foreground comparison")
            maximum = 0
            for pixel in common:
                expected = expected_solids[index][pixel]
                colors[str(expected)] = colors.get(str(expected), 0) + 1
                maximum = max(
                    maximum,
                    *(abs(pixels[pixel * 3 + c] - expected[c]) for c in range(3)),
                )
            if maximum:
                raise AssertionError(
                    f"interior color differs by {maximum} at {index * 10 + 1} ms on {name}"
                )
            with Image.open(output / (name + ".png")) as background:
                channels = tuple(
                    channel.convert("F")
                    for channel in background.convert("RGB").split()
                )
            for reference in references[index]:
                over(channels, reference, index * 10 + 1)
            expected_image = finish(channels)
            diff = ImageChops.difference(actual, expected_image)
            histogram = diff.histogram()
            whole_max = max(i % 256 for i, count in enumerate(histogram) if count)
            if case == "E08" and (index < 30 or index >= 500) and whole_max:
                raise AssertionError("writing blank interval differs from background")
            checks.append(
                {
                    "time_ms": index * 10 + 1,
                    "background": name,
                    "solid_pixels": len(common),
                    "max_solid_rgb_difference": maximum,
                    "max_whole_frame_rgb_difference": whole_max,
                }
            )
            if name == "checker" and index in preview_indices:
                row = preview_indices.index(index)
                for col, image in enumerate(
                    (actual, expected_image, diff.point(lambda v: min(255, v * 8)))
                ):
                    sheet.paste(image.resize((320, 180)), (col * 320, row * 180))
    palette = {"(0, 0, 0)", "(255, 255, 255)", "(0, 255, 255)"}
    if case == "E06":
        palette |= {"(36, 45, 70)", "(255, 192, 203)", "(255, 136, 187)"}
    if case == "E03":
        palette = {
            str(rgb) for values in expected_solids.values() for rgb in values.values()
        }
        if len(palette) < 3:
            raise AssertionError("round reference misses intermediate pulse colors")
    if case == "E07":
        palette = {"(0, 255, 255)"}
    if case in ("E10", "E08"):
        palette = {"(0, 255, 255)", "(255, 192, 203)"}
    if set(colors) != palette:
        raise AssertionError(f"missing or unexpected solid colors: {colors}")
    artifact = {
        "E12": "cue-colors",
        "E06": "word-colors",
        "E03": "round-colors",
        "E07": "outline-colors",
        "E10": "morph-colors",
        "E08": "writing-colors",
    }[case]
    sheet.save(output / f"{artifact}.png")
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
        "scope": f"{case} exact solid-interior colors on four backgrounds; complete image differences measured separately, including native whole-run vs per-cluster geometry and antialiasing",
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "font_sha256": font.sha256,
        "font_assets_sha256": font_hashes,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": {
            str(i): [hashlib.sha256(r.encode()).hexdigest() for r in scripts]
            for i, scripts in references.items()
        },
        "checks": checks,
        "solid_color_pixel_checks": colors,
        "compared_ink_pen_overlap_pixels": overlap_pixels,
        "remaining": [
            "edge/composite differences are measured, not claimed pixel-identical",
            "continuous-time bounds",
            "other players",
        ],
    }
    (output / f"{artifact}-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "solid_pixels": sum(colors.values()),
                "max_whole_frame_rgb_difference": max(
                    c["max_whole_frame_rgb_difference"] for c in checks
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--case", choices=("E12", "E06", "E03", "E07", "E08", "E10"), default="E12"
    )
    args = parser.parse_args()
    validate(args.output, args.case)


if __name__ == "__main__":
    main()
