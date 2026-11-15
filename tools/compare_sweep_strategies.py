"""Render the fixed sweep experiment; measure differences, not presumed equivalence.

uv run python -m tools.compare_sweep_strategies OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageChops, ImageFilter

from examples.scene_sweep_strategies import BUDGET, RESOLUTION, Strategy, build
from kara_templater import _metrics, load_font

STRATEGIES: tuple[Strategy, ...] = ("bands", "layers", "raster", "diffused")
TIMES = tuple(50 + i * 100 for i in range(20))


def render(
    output: Path, strategy: Strategy, background: str
) -> tuple[tuple[Image.Image, ...], float, tuple[str, ...]]:
    start = perf_counter()
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-loop",
            "1",
            "-framerate",
            "10",
            "-i",
            background + ".png",
            "-vf",
            f"format=rgb24,settb=1/1000,setpts=N*100+50,ass={strategy}.ass:fontsdir=fonts",
            "-frames:v",
            "20",
            "-fps_mode",
            "passthrough",
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
    size = RESOLUTION[0] * RESOLUTION[1] * 3
    assert len(result.stdout) == 20 * size
    frames = tuple(
        Image.frombytes("RGB", RESOLUTION, result.stdout[i * size : (i + 1) * size])
        for i in range(20)
    )
    renderer = tuple(
        line.strip()
        for line in result.stderr.decode().splitlines()
        if "libass source" in line or "Shaper:" in line
    )
    return frames, perf_counter() - start, renderer


def interior(script: str, ms: int) -> Image.Image:
    mask = Image.new("L", RESOLUTION)
    for x, y, w, h, _, color, data in _metrics.rasterize(
        script, ms, *RESOLUTION, 4_000_000, 50_000
    ):
        if color & 255 or not w or not h:
            continue
        tile = Image.new("L", RESOLUTION)
        tile.paste(Image.frombytes("L", (w, h), data), (x, y))
        mask = ImageChops.lighter(mask, tile)
    return mask.filter(ImageFilter.MinFilter(3)).point(lambda v: 255 if v == 255 else 0)


def maximum(image: Image.Image) -> int:
    return max(i % 256 for i, n in enumerate(image.histogram()) if n)


def compare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font_path = Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf"
    font = load_font(font_path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(font_path.read_bytes())
    costs = []
    scripts: dict[Strategy, str] = {}
    for strategy in STRATEGIES:
        start = perf_counter()
        compiled = build(strategy).compile(budget=BUDGET)
        scripts[strategy] = compiled.document.dumps()
        compiled.document.save(output / (strategy + ".ass"))
        costs.append(
            {
                "strategy": strategy,
                "events": compiled.event_count,
                "peak_active": compiled.peak_active,
                "bytes": compiled.byte_count,
                "generation_seconds": perf_counter() - start,
            }
        )
    width, height = RESOLUTION
    backgrounds = {
        "black": Image.new("RGB", RESOLUTION),
        "white": Image.new("RGB", RESOLUTION, "white"),
    }
    for name in ("checker", "gradient"):
        picture = Image.new("RGB", RESOLUTION)
        picture.putdata(
            [
                (
                    tuple([64 if (x // 12 + y // 12) % 2 else 192] * 3)
                    if name == "checker"
                    else (
                        round(x * 255 / (width - 1)),
                        round(y * 255 / (height - 1)),
                        round((x + y) * 255 / (width + height - 2)),
                    )
                )
                for y in range(height)
                for x in range(width)
            ]
        )
        backgrounds[name] = picture
    hashes = {}
    for name, picture in backgrounds.items():
        picture.save(output / (name + ".png"))
        hashes[name] = hashlib.sha256(
            (output / (name + ".png")).read_bytes()
        ).hexdigest()
    masks = tuple(interior(scripts["bands"], ms) for ms in TIMES)
    checks = []
    black_frames: dict[Strategy, tuple[Image.Image, ...]] = {}
    render_times = []
    versions: set[str] = set()
    sheet = Image.new("RGB", (1280, 720))
    for name in backgrounds:
        frames_by_strategy = {}
        for strategy in STRATEGIES:
            frames, seconds, renderer = render(output, strategy, name)
            frames_by_strategy[strategy] = frames
            versions.update(renderer)
            render_times.append(
                {
                    "strategy": strategy,
                    "background": name,
                    "seconds": seconds,
                    "frames": 20,
                }
            )
        if name == "black":
            black_frames = frames_by_strategy
        for strategy in STRATEGIES[1:]:
            for i, (actual, baseline, mask) in enumerate(
                zip(
                    frames_by_strategy[strategy],
                    frames_by_strategy["bands"],
                    masks,
                    strict=True,
                )
            ):
                difference = ImageChops.difference(actual, baseline)
                inside = Image.new("RGB", RESOLUTION)
                inside.paste(difference, (0, 0), mask)
                checks.append(
                    {
                        "strategy": strategy,
                        "background": name,
                        "time_ms": TIMES[i],
                        "max_rgb_difference": maximum(difference),
                        "max_interior_rgb_difference": maximum(inside),
                        "interior_pixels": mask.histogram()[255],
                        "pixels_different": sum(
                            ImageChops.lighter(
                                ImageChops.lighter(
                                    difference.getchannel("R"),
                                    difference.getchannel("G"),
                                ),
                                difference.getchannel("B"),
                            ).histogram()[1:]
                        ),
                    }
                )
        if name == "checker":
            for col, strategy in enumerate(STRATEGIES):
                for row, index in enumerate((3, 7, 11, 17)):
                    sheet.paste(
                        frames_by_strategy[strategy][index], (col * 320, row * 180)
                    )
        print(name + ": measured", flush=True)
    opacity_checks = []
    # Every authored color has red=255, so the black-background red plane
    # is the effective alpha coverage (up to renderer rounding).
    for strategy in STRATEGIES[1:]:
        for i, (actual, baseline) in enumerate(
            zip(black_frames[strategy], black_frames["bands"], strict=True)
        ):
            a, b = actual.getchannel("R"), baseline.getchannel("R")
            loss = ImageChops.subtract(b, a)
            gain = ImageChops.subtract(a, b)
            interior_loss = ImageChops.multiply(loss, masks[i])
            opacity_checks.append(
                {
                    "strategy": strategy,
                    "time_ms": TIMES[i],
                    "max_alpha_loss": maximum(loss),
                    "max_alpha_gain": maximum(gain),
                    "max_interior_alpha_loss": maximum(interior_loss),
                }
            )
    sheet.save(output / "sweep-strategies.png")
    report = {
        "scope": "320x180 fixed two-second sweep, 10Hz shared midpoint grid; RGB comparison to bands is an experimental comparison, not proof of alternate strategies matching the requested semantics",
        "strategy_column_order": STRATEGIES,
        "preview_times_ms": [TIMES[i] for i in (3, 7, 11, 17)],
        "font_sha256": font.sha256,
        "renderer": sorted(versions),
        "background_sha256": hashes,
        "ass_sha256": {
            s: hashlib.sha256(text.encode()).hexdigest() for s, text in scripts.items()
        },
        "costs": costs,
        "render_times": render_times,
        "checks": checks,
        "opacity_checks": opacity_checks,
        "remaining": [
            "independent RGBA reconstruction reference for raster modes",
            "interpretation of interior/edge differences and default strategy selection",
        ],
    }
    (output / "sweep-strategies-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    for strategy in STRATEGIES[1:]:
        rows = [r for r in checks if r["strategy"] == strategy]
        print(
            strategy,
            "whole",
            max(r["max_rgb_difference"] for r in rows),
            "interior",
            max(r["max_interior_rgb_difference"] for r in rows),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    compare(parser.parse_args().output)


if __name__ == "__main__":
    main()
