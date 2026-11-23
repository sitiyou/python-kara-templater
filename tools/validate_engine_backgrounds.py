"""Render word backgrounds on four RGB backgrounds at every ASS centisecond.

uv run python -m tools.validate_engine_backgrounds OUTPUT
This checks actual exported ASS and seek-order determinism, not an independent
geometric/color oracle. Historical independent reference gates remain separate.
"""

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageDraw

from examples.scene_cues import build
from kara_templater import SceneBudget, load_font

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1280, 720)
FRAMES = 600
FPS = 100
PREVIEW_INDICES = (50, 250, 450)
BACKGROUNDS = ("black", "white", "checker", "gradient")


def hashes(arguments: list[str], work: Path) -> tuple[tuple[str, ...], str]:
    result = subprocess.run(
        arguments, cwd=work, capture_output=True, text=True, check=True
    )
    return tuple(
        line.rsplit(",", 1)[1].strip()
        for line in result.stdout.splitlines()
        if line and not line.startswith("#")
    ), result.stderr


def backgrounds(output: Path) -> dict[str, str]:
    """Fixed authored RGB assets, with no video conversion or random state."""
    images = {
        "black": Image.new("RGB", SIZE, "black"),
        "white": Image.new("RGB", SIZE, "white"),
        "checker": Image.new("RGB", SIZE, "#303030"),
    }
    draw = ImageDraw.Draw(images["checker"])
    for y in range(0, SIZE[1], 40):
        for x in range(0, SIZE[0], 40):
            if (x // 40 + y // 40) % 2:
                draw.rectangle((x, y, x + 39, y + 39), fill="#D0D0D0")
    pixels = bytearray(SIZE[0] * SIZE[1] * 3)
    for y in range(SIZE[1]):
        for x in range(SIZE[0]):
            offset = (y * SIZE[0] + x) * 3
            pixels[offset : offset + 3] = bytes(
                (
                    round(x * 255 / (SIZE[0] - 1)),
                    round(y * 255 / (SIZE[1] - 1)),
                    round((1 - x / (SIZE[0] - 1)) * 180 + y / (SIZE[1] - 1) * 75),
                )
            )
    images["gradient"] = Image.frombytes("RGB", SIZE, bytes(pixels))
    result = {}
    for name, picture in images.items():
        path = output / f"{name}.png"
        picture.save(path)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def arguments(background: str, script: str, *, seek: bool = False) -> list[str]:
    clock = f"mod(N*137\\,{FRAMES})*10+1" if seek else "N*10+1"
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-loop",
        "1",
        "-framerate",
        str(FPS),
        "-i",
        f"{background}.png",
        "-vf",
        f"format=rgb24,setparams=range=full,settb=1/1000,setpts={clock},"
        f"ass={script}:fontsdir=fonts,setpts=N*10+1",
        "-frames:v",
        str(FRAMES),
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "framemd5",
        "-",
    ]


def preview(
    output: Path,
    background: str,
    script: str,
    indices: tuple[int, ...] = PREVIEW_INDICES,
) -> tuple[Image.Image, ...]:
    command = arguments(background, script)
    index = command.index("-vf") + 1
    selected = "+".join(f"eq(n\\,{n})" for n in indices)
    command[index] += f",select={selected}"
    command[command.index("-frames:v") + 1] = str(len(indices))
    command[command.index("-f") + 1] = "rawvideo"
    result = subprocess.run(command, cwd=output, capture_output=True, check=True)
    length = SIZE[0] * SIZE[1] * 3
    if len(result.stdout) != length * len(indices):
        raise AssertionError("unexpected preview size")
    return tuple(
        Image.frombytes("RGB", SIZE, result.stdout[i : i + length])
        for i in range(0, len(result.stdout), length)
    )


def validate(output: Path, case_id: str | None = None) -> None:
    if case_id not in (None, "E06"):
        raise ValueError(f"unknown case: {case_id}")
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    fonts = output / "fonts"
    fonts.mkdir(exist_ok=True)
    assets = []
    for name in ("DejaVuSans.ttf", "KaraTestCJK.ttf"):
        path = ROOT / "tests/fonts" / name
        face = load_font(path)
        (fonts / name).write_bytes(path.read_bytes())
        assets.append(
            {
                "path": str(path.relative_to(ROOT)),
                "family": face.family,
                "sha256": face.sha256,
            }
        )
    background_hashes = backgrounds(output)
    renderer: list[str] = []
    cases = []
    start = perf_counter()
    result = build().ass.compile()
    script = "E06.ass"
    result.document.save(output / script)
    sheet = Image.new("RGB", (1280, 3 * 204), "#141824")
    checks = []
    for column, background in enumerate(BACKGROUNDS):
        continuous, log = hashes(arguments(background, script), output)
        visited, _ = hashes(arguments(background, script, seek=True), output)
        if len(continuous) != FRAMES or len(visited) != FRAMES:
            raise AssertionError(f"E06/{background}: unexpected frame count")
        if any(visited[i] != continuous[i * 137 % FRAMES] for i in range(FRAMES)):
            raise AssertionError(
                f"E06/{background}: seek order changed a frame"
            )
        (output / f"E06-{background}-hashes.txt").write_text(
            "\n".join(continuous) + "\n"
        )
        renderer.extend(
            line.strip()
            for line in log.splitlines()
            if "libass source:" in line or "Shaper:" in line
        )
        for row, frame in enumerate(preview(output, background, script)):
            x, y = column * 320, row * 204
            sheet.paste(frame.resize((320, 180)), (x, y + 24))
            ImageDraw.Draw(sheet).text(
                (x + 6, y + 6),
                f"E06 / {background} / {PREVIEW_INDICES[row] / FPS + 0.001:.3f}s",
                fill="white",
            )
        checks.append(
            {
                "background": background,
                "frames": FRAMES,
                "permuted_seek_frames": FRAMES,
                "all_hashes_equal": True,
            }
        )
        print(
            json.dumps(
                {"case": "E06", "background": background, "phase": "passed"}
            ),
            flush=True,
        )
    sheet.save(output / "E06-backgrounds.png")
    cases.append(
        {
            "id": "E06",
            "factory": build.__module__,
            "ass_sha256": hashlib.sha256(
                (output / script).read_bytes()
            ).hexdigest(),
            "event_count": result.event_count,
            "peak_active": result.peak_active,
            "byte_count": result.byte_count,
            "seconds": perf_counter() - start,
            "background_checks": checks,
        }
    )
    report = {
        "scope": "Word backgrounds ASS on four authored backgrounds; exhaustive centisecond-grid seek-order check, not independent semantic reference acceptance",
        "selected_cases": [case["id"] for case in cases],
        "resolution": SIZE,
        "duration_seconds": FRAMES / FPS,
        "fps": FPS,
        "clock": "integer millisecond time base; 10 ms steps with +1 ms offset to avoid ffmpeg floating boundary truncation",
        "seek_order": "(frame index * 137) modulo 600; every timestamp once, in a separate renderer instance from continuous playback",
        "pixel_format": "RGB24 input/output, full range; exported ASS metadata unchanged",
        "scene_budget": asdict(SceneBudget()),
        "font_assets": assets,
        "background_sha256": background_hashes,
        "cases": cases,
        "renderer": sorted(set(renderer)),
        "remaining": [
            "independent geometric/color reference errors",
            "exact-boundary time checks separate from the +1ms rendering clock",
            "scaled playback and other renderers",
        ],
    }
    (output / "engine-backgrounds-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", choices=("E06",))
    args = parser.parse_args()
    validate(args.output, args.case)


if __name__ == "__main__":
    main()
