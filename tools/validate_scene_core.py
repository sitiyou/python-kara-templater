"""Export the initial object scene and preview its real ASS with system libass.

uv run python -m tools.validate_scene_core /tmp/scene-core-validation
Use --scene native-tween to check native interpolation.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Literal

from PIL import Image, ImageDraw

from examples.scene_cues import build as build_cues
from examples.scene_native_tween import build as build_native_tween
from kara_templater import load_font

ROOT = Path(__file__).resolve().parents[1]


def playback_check(
    work: Path, times: tuple[float, ...], resolution: str = "1280x720"
) -> tuple[int, dict[str, str]]:
    """Compare a continuous filter run against fresh libass tracks at seek PTS."""

    def hashes(arguments: list[str]) -> tuple[str, ...]:
        completed = subprocess.run(
            arguments, cwd=work, capture_output=True, text=True, check=True
        )
        return tuple(
            line.rsplit(",", 1)[1].strip()
            for line in completed.stdout.splitlines()
            if line and not line.startswith("#")
        )

    common = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i"]
    continuous = hashes(
        [
            *common,
            f"color=c=0x141824:s={resolution}:r=50:d=6",
            "-vf",
            "ass=scene.ass:fontsdir=.",
            "-fps_mode",
            "passthrough",
            "-f",
            "framemd5",
            "-",
        ]
    )
    if len(continuous) != 300:
        raise AssertionError(f"expected 300 continuous frames, got {len(continuous)}")
    samples: dict[str, str] = {}
    for time in reversed(times):
        index = round(time * 50)
        if abs(time * 50 - index) > 1e-8:
            raise ValueError("seek checks require times on the 50 fps frame grid")
        seek = hashes(
            [
                *common,
                f"color=c=0x141824:s={resolution}:r=50:d=0.02",
                "-vf",
                f"setpts=PTS+{index},ass=scene.ass:fontsdir=.",
                "-fps_mode",
                "passthrough",
                "-frames:v",
                "1",
                "-f",
                "framemd5",
                "-",
            ]
        )
        if seek != (continuous[index],):
            raise AssertionError(
                f"fresh seek at {time}s differs from continuous rendering"
            )
        samples[str(time)] = seek[0]
    return len(continuous), samples


def validate(
    output: Path,
    scene_name: Literal["cues", "native-tween"] = "cues",
) -> None:
    build = build_cues if scene_name == "cues" else build_native_tween
    artifact = f"scene-{scene_name}"
    path = ROOT / "tests/fonts/DejaVuSans.ttf"
    assets = [path]
    font = load_font(path)
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    result = build().ass.compile()
    resolution = f"{result.document.meta.res_x}x{result.document.meta.res_y}"
    generation_seconds = perf_counter() - started
    script = output / f"scene-{scene_name}.ass"
    result.document.save(script)
    script_bytes = script.read_bytes()
    script_hash = hashlib.sha256(script_bytes).hexdigest()
    assert build().ass.compile().document.dumps() == result.document.dumps()
    times = (
        (0.0, 0.5, 1.5, 2.5, 4.5, 5.0)
        if scene_name != "cues"
        else (0.0, 0.2, 0.5, 0.8, 1.0, 2.5, 4.5, 5.0)
    )
    sheet = Image.new("RGB", (1280, ((len(times) + 1) // 2) * 384), "#141824")
    render_started = perf_counter()
    renderer_log = ""
    with tempfile.TemporaryDirectory(prefix="kara-scene-preview-") as directory:
        work = Path(directory)
        # Filter syntax receives predictable local names, without user path interpolation.
        preview_script = work / "scene.ass"
        preview_script.write_bytes(script_bytes)
        assert hashlib.sha256(preview_script.read_bytes()).hexdigest() == script_hash
        for index, path in enumerate(assets):
            (work / f"font-{index}.ttf").write_bytes(path.read_bytes())
        for index, time in enumerate(times):
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x141824:s={resolution}:r=50:d=6",
                    "-vf",
                    "ass=scene.ass:fontsdir=.",
                    "-ss",
                    str(time),
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    "-y",
                    "frame.png",
                ],
                cwd=work,
                capture_output=True,
                text=True,
                check=True,
            )
            renderer_log = completed.stderr
            with Image.open(work / "frame.png") as source:
                frame = source.convert("RGB").resize((640, 360))
            x, y = (index % 2) * 640, (index // 2) * 384
            sheet.paste(frame, (x, y + 24))
            ImageDraw.Draw(sheet).text((x + 12, y + 5), f"{time:.2f} s", fill="white")
        continuous_frames, seek_hashes = playback_check(work, times, resolution)
        assert preview_script.read_bytes() == script_bytes
    assert script.read_bytes() == script_bytes
    sheet.save(output / f"{artifact}.png")
    report = {
        "scope": f"{scene_name} actual ASS preview and playback; independent visual acceptance is recorded separately",
        "ass_sha256": script_hash,
        "preview_ass_sha256": script_hash,
        "preview_uses_exported_bytes": True,
        "resolution": resolution,
        "generation_seconds": generation_seconds,
        "render_seconds": perf_counter() - render_started,
        "event_count": result.event_count,
        "peak_active": result.peak_active,
        "byte_count": result.byte_count,
        "estimated_events": result.estimated_events,
        "max_time_quantization_seconds": result.max_time_quantization,
        "repeat_generation_identical": True,
        "continuous_frames": continuous_frames,
        "fresh_seek_matches_continuous": True,
        "seek_frame_md5": seek_hashes,
        "preview_seconds": times,
        "renderer": [
            line.strip()
            for line in renderer_log.splitlines()
            if "libass source:" in line or "Shaper:" in line
        ],
        "font": "tests/fonts/DejaVuSans.ttf (repository license)",
        "font_family": font.family,
        "font_sha256": font.sha256,
        "strategies": [
            {
                "id": item.id,
                "strategy": item.strategy,
                "events": item.events,
                "peak_path_points": item.peak_path_points,
                "peak_clip_points": item.peak_clip_points,
            }
            for item in result.objects
        ],
        "outside_this_check": [
            "all-background comparisons",
            "reference error measurements",
            "other scene fixtures and other renderers",
        ],
    }
    (output / f"{artifact}-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "event_count",
                    "peak_active",
                    "byte_count",
                    "repeat_generation_identical",
                )
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--scene",
        choices=("cues", "native-tween"),
        default="cues",
    )
    args = parser.parse_args()
    validate(args.output, args.scene)


if __name__ == "__main__":
    main()
