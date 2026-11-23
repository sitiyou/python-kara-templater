"""Export the initial object scene and preview its real ASS with system libass.

uv run python -m tools.validate_scene_core /tmp/scene-core-validation
This is a core smoke/visual report, not acceptance of all E01–E12 cases.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Literal

from PIL import Image, ImageDraw

from examples.scene_affine import build as build_affine
from examples.scene_bilingual import build as build_bilingual
from examples.scene_boolean import build as build_boolean
from examples.scene_coverage import BUDGET as COVERAGE_BUDGET
from examples.scene_coverage import RASTER_SETTINGS as COVERAGE_SETTINGS
from examples.scene_coverage import build as build_coverage
from examples.scene_coverage_tracks import BUDGET as COVERAGE_TRACKS_BUDGET
from examples.scene_coverage_tracks import RASTER_SETTINGS as COVERAGE_TRACKS_SETTINGS
from examples.scene_coverage_tracks import build as build_coverage_tracks
from examples.scene_cue_follow import build as build_cue_follow
from examples.scene_cues import build as build_cues
from examples.scene_follow import build as build_follow
from examples.scene_fragments import build as build_fragments
from examples.scene_gradient import build as build_gradient
from examples.scene_group_masks import build as build_group_masks
from examples.scene_keyframes import build as build_keyframes
from examples.scene_lyric_cues import build as build_lyric_cues
from examples.scene_lyrics import build as build_lyrics
from examples.scene_masks import build as build_masks
from examples.scene_mirror import build as build_mirror
from examples.scene_morph import build as build_morph
from examples.scene_native_tween import build as build_native_tween
from examples.scene_outlines import build as build_outlines
from examples.scene_rectangle import build as build_rectangle
from examples.scene_round import build as build_round
from examples.scene_sakura import build as build_sakura
from examples.scene_staggered import build as build_staggered
from examples.scene_sweep import build as build_sweep
from examples.scene_tracks import build as build_tracks
from examples.scene_word_glow import build as build_word_glow
from examples.scene_writing import build as build_writing
from kara_templater import SceneResult, load_font

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
    scene_name: Literal[
        "staggered",
        "cues",
        "outlines",
        "writing",
        "morph",
        "sakura",
        "fragments",
        "round",
        "gradient",
        "sweep",
        "lyrics",
        "lyric-cues",
        "masks",
        "follow",
        "tracks",
        "affine",
        "group-masks",
        "mirror",
        "boolean",
        "word-glow",
        "rectangle",
        "keyframes",
        "bilingual",
        "cue-follow",
        "native-tween",
        "coverage",
        "coverage-tracks",
    ] = "staggered",
) -> None:
    build = {
        "staggered": build_staggered,
        "cues": build_cues,
        "outlines": build_outlines,
        "writing": build_writing,
        "morph": build_morph,
        "sakura": build_sakura,
        "fragments": build_fragments,
        "round": build_round,
        "gradient": build_gradient,
        "sweep": build_sweep,
        "lyrics": build_lyrics,
        "lyric-cues": build_lyric_cues,
        "masks": build_masks,
        "follow": build_follow,
        "tracks": build_tracks,
        "affine": build_affine,
        "group-masks": build_group_masks,
        "mirror": build_mirror,
        "boolean": build_boolean,
        "word-glow": build_word_glow,
        "rectangle": build_rectangle,
        "keyframes": build_keyframes,
        "bilingual": build_bilingual,
        "cue-follow": build_cue_follow,
        "native-tween": build_native_tween,
    }.get(scene_name)
    artifact = "scene-core" if scene_name == "staggered" else f"scene-{scene_name}"
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    assets = [ROOT / "tests/fonts/DejaVuSans.ttf"]
    if scene_name in ("round", "lyrics", "bilingual"):
        assets.append(ROOT / "tests/fonts/KaraTestCJK.ttf")
    font_assets = [
        {
            "path": str(path.relative_to(ROOT)),
            "family": load_font(path).family,
            "sha256": load_font(path).sha256,
        }
        for path in assets
    ]
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    budget = COVERAGE_TRACKS_BUDGET if scene_name == "tracks" else None
    resolution = (
        "320x180" if scene_name in ("coverage", "tracks") else "1280x720"
    )
    if scene_name == "coverage-tracks":
        resolution = "240x135"

    def generate() -> SceneResult:
        if scene_name == "coverage":
            return build_coverage()
        if scene_name == "coverage-tracks":
            return build_coverage_tracks()
        assert build is not None
        return build().compile(
            budget=budget
        )

    result = generate()
    generation_seconds = perf_counter() - started
    script = output / f"scene-{scene_name}.ass"
    result.document.save(script)
    script_bytes = script.read_bytes()
    script_hash = hashlib.sha256(script_bytes).hexdigest()
    assert generate().document.dumps() == result.document.dumps()
    times = (
        (0.0, 0.5, 1.5, 2.5, 4.5, 5.0)
        if scene_name != "cues"
        else (0.0, 0.2, 0.5, 0.8, 1.0, 2.5, 4.5, 5.0)
    )
    if scene_name == "coverage-tracks":
        times = (0.0, 0.5, 0.8, 1.2, 1.8, 2.5, 3.0, 3.5)
    elif scene_name in ("coverage", "tracks"):
        times = (0.0, 0.8, 1.2, 2.5, 3.8, 4.2, 5.0)
    elif scene_name == "bilingual":
        times = (0.0, 0.5, 1.3, 1.8, 2.5, 3.4, 4.5, 5.0)
    elif scene_name == "native-tween":
        times = (0.0, 0.5, 1.5, 2.5, 3.5, 4.0, 4.5, 5.0)
    elif scene_name == "cue-follow":
        times = (0.0, 1.48, 1.5, 1.82, 1.84, 2.16, 2.18, 2.48, 2.5, 4.5, 5.0)
    elif scene_name == "keyframes":
        times = (0.0, 0.32, 0.66, 1.7, 2.4, 2.94, 3.2)
    elif scene_name == "sakura":
        times = (0.0, 0.5, 1.0, 1.5, 2.5, 3.5, 4.5, 5.0)
    elif scene_name == "fragments":
        times = (0.0, 0.5, 1.5, 1.58, 1.6, 1.62, 2.5, 5.0)
    elif scene_name == "lyric-cues":
        times = (0.0, 0.5, 0.98, 1.0, 1.02, 1.5, 2.48, 2.5, 2.52, 4.5, 5.0)
    elif scene_name == "lyrics":
        times = (0.0, 0.5, 1.0, 1.5, 2.2, 2.5, 2.8, 3.4, 4.0, 4.5, 5.0)
    elif scene_name == "round":
        times = (0.0, 1.0, 1.5, 2.2, 3.3, 4.0, 4.5, 5.0)
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
        "font_assets": font_assets,
        "strategies": [
            {
                "id": item.id,
                "strategy": item.strategy,
                "events": item.events,
                "sample_interval": item.sample_interval,
                "peak_path_points": item.peak_path_points,
                "peak_bands": item.peak_bands,
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
    if scene_name in ("coverage", "coverage-tracks", "tracks"):
        counts = Counter(item.strategy for item in result.objects)
        report["strategies"] = [
            {"strategy": strategy, "objects": count}
            for strategy, count in sorted(counts.items())
        ]
        report["raster_settings"] = asdict(
            COVERAGE_SETTINGS if scene_name == "coverage" else COVERAGE_TRACKS_SETTINGS
        )
        report["scene_budget"] = asdict(
            COVERAGE_BUDGET if scene_name == "coverage" else COVERAGE_TRACKS_BUDGET
        )
        if scene_name in ("coverage-tracks", "tracks"):
            report["raster_settings"] = asdict(COVERAGE_TRACKS_SETTINGS)
            report["scene_budget"] = asdict(COVERAGE_TRACKS_BUDGET)
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
        choices=(
            "staggered",
            "cues",
            "outlines",
            "writing",
            "morph",
            "sakura",
            "fragments",
            "round",
            "gradient",
            "sweep",
            "lyrics",
            "lyric-cues",
            "masks",
            "follow",
            "tracks",
            "affine",
            "group-masks",
            "mirror",
            "boolean",
            "word-glow",
            "rectangle",
            "keyframes",
            "bilingual",
            "cue-follow",
            "native-tween",
            "coverage",
            "coverage-tracks",
        ),
        default="staggered",
    )
    args = parser.parse_args()
    validate(args.output, args.scene)


if __name__ == "__main__":
    main()
