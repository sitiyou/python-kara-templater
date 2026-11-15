"""Compile and render the fixed 180-second fixture under the predeclared budget.

uv run python -m tools.validate_whole_song /tmp/whole-song-validation
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from examples.scene_whole_song import BUDGET, CASES, SLOT_SECONDS, SLOTS, build
from kara_templater import load_font

ROOT = Path(__file__).resolve().parents[1]


def hashes(arguments: list[str], work: Path) -> tuple[tuple[str, ...], str]:
    result = subprocess.run(
        arguments, cwd=work, capture_output=True, text=True, check=True
    )
    return tuple(
        line.rsplit(",", 1)[1].strip()
        for line in result.stdout.splitlines()
        if line and not line.startswith("#")
    ), result.stderr


def validate(output: Path) -> None:
    if tuple(case.id for case in CASES) != tuple(f"E{i:02}" for i in range(1, 13)):
        raise AssertionError("whole-song fixture must contain E01–E12 in order")
    if len(CASES) > SLOTS:
        raise AssertionError("not every case has a whole-song slot")
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    assets = []
    for filename in ("DejaVuSans.ttf", "KaraTestCJK.ttf"):
        path = ROOT / "tests/fonts" / filename
        font = load_font(path)
        (output / filename).write_bytes(path.read_bytes())
        assets.append(
            {
                "path": str(path.relative_to(ROOT)),
                "family": font.family,
                "sha256": font.sha256,
            }
        )
    started = perf_counter()
    result = build().compile(budget=BUDGET)
    generation_seconds = perf_counter() - started
    script = output / "scene.ass"
    result.document.save(script)
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    stats = {
        "event_count": result.event_count,
        "peak_active": result.peak_active,
        "byte_count": result.byte_count,
        "estimated_events": result.estimated_events,
        "max_time_quantization_seconds": result.max_time_quantization,
    }
    del result
    print(json.dumps({"phase": "compiled", **stats}), flush=True)
    started = perf_counter()
    repeated = build().compile(budget=BUDGET)
    repeated.document.save(output / "repeat.ass")
    if hashlib.sha256((output / "repeat.ass").read_bytes()).hexdigest() != digest:
        raise AssertionError("whole-song repeated generation changed bytes")
    del repeated
    (output / "repeat.ass").unlink()
    repeat_seconds = perf_counter() - started
    duration = SLOT_SECONDS * SLOTS
    common = ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i"]
    started = perf_counter()
    continuous, renderer = hashes(
        [
            *common,
            f"color=c=0x141824:s=1280x720:r=50:d={duration}",
            "-vf",
            "settb=1/1000,setpts=PTS+1,ass=scene.ass:fontsdir=.",
            "-fps_mode",
            "passthrough",
            "-f",
            "framemd5",
            "-",
        ],
        output,
    )
    playback_seconds = perf_counter() - started
    if len(continuous) != duration * 50:
        raise AssertionError(f"wrong frame count: {len(continuous)}")
    print(
        json.dumps(
            {
                "phase": "continuous",
                "frames": len(continuous),
                "seconds": playback_seconds,
            }
        ),
        flush=True,
    )
    period_frames = len(CASES) * SLOT_SECONDS * 50
    for index in range(period_frames, len(continuous)):
        if continuous[index] != continuous[index % period_frames]:
            raise AssertionError(f"copied case differs at frame {index}")
    (output / "frame-hashes.txt").write_text("\n".join(continuous) + "\n")
    # Compare each first slot with the actual standalone example, not merely
    # another copied slot: a consistently omitted child must not pass this gate.
    standalone_cases = []
    standalone_frames = 0
    started = perf_counter()
    for case_index, case in enumerate(CASES):
        standalone = case.factory().compile()
        filename = f"reference-{case.id}.ass"
        standalone.document.save(output / filename)
        reference, _ = hashes(
            [
                *common,
                f"color=c=0x141824:s=1280x720:r=50:d={SLOT_SECONDS}",
                "-vf",
                f"settb=1/1000,setpts=PTS+1,ass={filename}:fontsdir=.",
                "-fps_mode",
                "passthrough",
                "-f",
                "framemd5",
                "-",
            ],
            output,
        )
        first = case_index * SLOT_SECONDS * 50
        if (
            len(reference) != SLOT_SECONDS * 50
            or reference != continuous[first : first + len(reference)]
        ):
            raise AssertionError(
                f"{case.id}: whole-song slot differs from standalone example"
            )
        if len(set(reference)) < 2:
            raise AssertionError(f"{case.id}: expected a changing visible example")
        standalone_frames += len(reference)
        standalone_cases.append(
            {
                "id": case.id,
                "name": case.name,
                "factory": case.factory.__module__,
                "frames": len(reference),
                "matches_whole_song": True,
                "ass_sha256": hashlib.sha256(
                    (output / filename).read_bytes()
                ).hexdigest(),
            }
        )
    standalone_seconds = perf_counter() - started
    print(
        json.dumps({"phase": "standalone", "cases": len(standalone_cases)}), flush=True
    )
    # Visit every slot, every transition and its immediate neighbors, in reverse.
    indices = {0, len(continuous) - 1}
    for slot in range(SLOTS):
        first = slot * SLOT_SECONDS * 50
        indices.update((first, first + 1, first + 75, first + 125))
        if first:
            indices.add(first - 1)
    started = perf_counter()
    seek_hashes: dict[str, str] = {}
    for index in sorted(indices, reverse=True):
        seek, _ = hashes(
            [
                *common,
                "color=c=0x141824:s=1280x720:r=50:d=0.02",
                "-vf",
                f"settb=1/1000,setpts=PTS+{index * 20 + 1},ass=scene.ass:fontsdir=.",
                "-fps_mode",
                "passthrough",
                "-frames:v",
                "1",
                "-f",
                "framemd5",
                "-",
            ],
            output,
        )
        if seek != (continuous[index],):
            raise AssertionError(f"seek differs at frame {index}")
        seek_hashes[f"{index / 50 + 0.001:.3f}"] = seek[0]
    report = {
        "scope": "180-second fixed composition cost and determinism; individual visual acceptance remains separate",
        "duration_seconds": duration,
        "fps": 50,
        "render_clock": "1/1000 time base, 20 ms steps, +1 ms offset avoids floating boundary truncation in the ffmpeg ASS filter",
        "resolution": [1280, 720],
        "budget": asdict(BUDGET),
        **stats,
        "generation_seconds": generation_seconds,
        "repeat_generation_seconds": repeat_seconds,
        "continuous_render_seconds": playback_seconds,
        "continuous_frames": len(continuous),
        "fresh_seek_seconds": perf_counter() - started,
        "fresh_seek_count": len(seek_hashes),
        "copied_case_frame_comparisons": len(continuous) - period_frames,
        "copied_cases_identical": True,
        "standalone_case_seconds": standalone_seconds,
        "standalone_case_frame_comparisons": standalone_frames,
        "standalone_cases": standalone_cases,
        "fresh_seek_matches_continuous": True,
        "seek_frame_md5": seek_hashes,
        "repeat_generation_identical": True,
        "ass_sha256": digest,
        "rss_measurement_note": "Linux resource ru_maxrss; child aggregate may include inherited memory before exec and is not isolated steady-state ffmpeg RSS",
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "renderer": [
            line.strip()
            for line in renderer.splitlines()
            if "libass source:" in line or "Shaper:" in line
        ],
        "font_assets": assets,
        "slots": [
            {
                "start_seconds": slot * SLOT_SECONDS,
                "case_id": CASES[slot % len(CASES)].id,
                "case": CASES[slot % len(CASES)].name,
            }
            for slot in range(SLOTS)
        ],
    }
    (output / "whole-song-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({"phase": "complete", "seeks": len(seek_hashes)}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
