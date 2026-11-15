"""E04 complete scene export vs independent per-object source-over composition.

uv run python -m tools.validate_particle_composite OUTPUT
Geometry references are separate; this checks ordering, opacity and combination.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageMath

from examples.scene_sakura import build
from kara_templater import (
    Document,
    ObjectGroup,
    PathObject,
    Scene,
    TextObject,
    _metrics,
    load_font,
)
from tools.validate_engine_backgrounds import ROOT, SIZE, backgrounds


def finish(channels: tuple[Image.Image, ...]) -> Image.Image:
    return Image.merge(
        "RGB",
        tuple(
            channel.point(lambda value: value + 0.5).convert("L")
            for channel in channels
        ),
    )


def over(channels: tuple[Image.Image, ...], script: str, time_ms: int) -> Image.Image:
    """Float source-over of libass tiles; quantize once at the final RGB image."""
    presence = Image.new("L", SIZE)
    for left, top, width, height, _, color, data in _metrics.rasterize(
        script, time_ms, *SIZE, 4_000_000, 10_000
    ):
        if not width or not height:
            continue
        alpha = 255 - (color & 255)
        mask = Image.frombytes("L", (width, height), data).point(
            [round(value * alpha / 255) for value in range(256)]
        )
        rgb = tuple((color >> shift) & 255 for shift in (24, 16, 8))
        weight = (
            Image.frombytes("L", (width, height), data)
            .convert("F")
            .point(lambda value, opacity=alpha: value * opacity / 65025)
        )
        for channel, value in zip(channels, rgb, strict=True):
            previous = channel.crop((left, top, left + width, top + height))
            blended = ImageMath.lambda_eval(
                lambda args: (
                    args["base"] * (1 - args["alpha"]) + args["alpha"] * args["color"]
                ),
                base=previous,
                alpha=weight,
                color=value,
            )
            channel.paste(blended, (left, top))
        tile = Image.new("L", SIZE)
        tile.paste(mask.point(lambda value: 255 if value else 0), (left, top))
        presence = ImageChops.lighter(presence, tile)
    return presence


def rendered(
    output: Path, background: str, time_ms: int
) -> tuple[Image.Image, tuple[str, ...]]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            background + ".png",
            "-vf",
            f"format=rgb24,settb=1/1000,setpts={time_ms},ass=particles.ass:fontsdir=fonts",
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        cwd=output,
        capture_output=True,
        check=True,
    )
    renderer = tuple(
        line
        for line in result.stderr.decode().splitlines()
        if "libass source" in line or "Shaper:" in line
    )
    return Image.frombytes("RGB", SIZE, result.stdout), renderer


def validate(output: Path) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    (output / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(
        ROOT / "tests/fonts/DejaVuSans.ttf", output / "fonts/DejaVuSans.ttf"
    )
    nodes = tuple(
        node
        for node in build().objects
        if isinstance(node, (PathObject, TextObject, ObjectGroup))
    )
    assert len(nodes) == 42
    combined = Scene(Document.create()).add(*nodes).compile()
    combined.document.save(output / "particles.ass")
    ordered = sorted(nodes, key=lambda node: node.layer)
    scripts = tuple(
        Scene(Document.create()).add(node).compile().document.dumps()
        for node in ordered
    )
    background_hashes = backgrounds(output)
    checks: list[dict[str, str | int]] = []
    reversed_order_detected = False
    renderer: set[str] = set()
    sheet = Image.new("RGB", (960, 1080))
    for row, time_ms in enumerate((501, 1301, 2501, 3001, 3501, 4501)):
        for column, name in enumerate(background_hashes):
            with Image.open(output / (name + ".png")) as background:
                channels = tuple(
                    band.convert("F") for band in background.convert("RGB").split()
                )
            seen = Image.new("L", SIZE)
            overlap = Image.new("L", SIZE)
            for script in scripts:
                presence = over(channels, script, time_ms)
                overlap = ImageChops.lighter(overlap, ImageChops.darker(seen, presence))
                seen = ImageChops.lighter(seen, presence)
            expected = finish(channels)
            actual, environment = rendered(output, name, time_ms)
            renderer.update(environment)
            histogram = ImageChops.difference(actual, expected).histogram()
            maximum = max(i % 256 for i, count in enumerate(histogram) if count)
            if maximum > 2:
                actual.save(output / "failed-actual.png")
                expected.save(output / "failed-reference.png")
                raise AssertionError(
                    f"composite differs by {maximum}/255 at {time_ms} on {name}"
                )
            checks.append(
                {
                    "time_ms": time_ms,
                    "background": name,
                    "max_rgb_difference": maximum,
                    "overlap_pixels": overlap.histogram()[255],
                }
            )
            if column == 2:
                with Image.open(output / (name + ".png")) as background:
                    reverse_channels = tuple(
                        band.convert("F") for band in background.convert("RGB").split()
                    )
                for script in reversed(scripts):
                    over(reverse_channels, script, time_ms)
                reversed_difference = ImageChops.difference(
                    expected, finish(reverse_channels)
                ).histogram()
                reversed_order_detected |= any(
                    count and index % 256 > 2
                    for index, count in enumerate(reversed_difference)
                )
                difference = ImageChops.difference(actual, expected).point(
                    lambda value: min(255, value * 32)
                )
                for col, picture in enumerate((actual, expected, difference)):
                    sheet.paste(picture.resize((320, 180)), (col * 320, row * 180))
                ImageDraw.Draw(sheet).text(
                    (5, row * 180 + 5),
                    f"{time_ms} ms actual | reference | diff x32",
                    fill="red",
                )
    if not reversed_order_detected or not any(c["overlap_pixels"] for c in checks):
        raise AssertionError(
            "fixture must contain visible order-sensitive particle overlaps"
        )
    sheet.save(output / "particle-composite.png")
    report = {
        "scope": "Complete E04 scene: 36 particles, lyric group, cursor and four echoes; combined ASS via FFmpeg vs isolated object ASS coverage painted independently in stable layer/source order; geometry validation is separate",
        "background_sha256": background_hashes,
        "font_sha256": font.sha256,
        "renderer": sorted(renderer),
        "ass_sha256": hashlib.sha256(
            (output / "particles.ass").read_bytes()
        ).hexdigest(),
        "isolated_sha256": {
            node.id: hashlib.sha256(script.encode()).hexdigest()
            for node, script in zip(ordered, scripts, strict=True)
        },
        "reference_arithmetic": "float source-over per RGB channel; coverage times opacity without intermediate 8-bit alpha or RGB rounding; final nearest-integer conversion",
        "checks": checks,
        "reversed_order_fault_detected": reversed_order_detected,
        "remaining": [
            "continuous-time bounds",
            "other players",
        ],
    }
    (output / "particle-composite-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_rgb_difference": max(int(c["max_rgb_difference"]) for c in checks),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
