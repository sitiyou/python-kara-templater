"""Compare a complete raster output with exact-time and held lossless snapshots.

This isolates temporal holding and color quantization, using the same material
renderer. It is not an independent shader reference; those live in
tests/test_track_material_reference.py. Input is validate_track_cost's directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

from examples.layered_glow import tracks
from kara_templater import (
    Document,
    Line,
    OutputSettings,
    RasterSettings,
    SceneBudget,
    load_font,
    prepare_tracks,
)
from kara_templater._track_raster import TrackRasterPlan
from tools.capture_layered_glow import TIMES
from tools.validate_track_cost import capture_output


def snapshot_evaluator(time: int, held: bool, ages: list[int]):
    original = TrackRasterPlan.evaluate

    def snapshot(
        plan: TrackRasterPlan,
        *,
        style: str,
        layer: int,
        max_events: int,
        max_chars: int,
    ) -> tuple[Line, ...]:
        interval = next(
            ((start, end) for start, end in plan.intervals if start <= time < end),
            None,
        )
        if interval is None:
            return ()
        state_time = interval[0] if held else time
        ages.append(time - state_time)
        # Restrict output work, without rebinding source clocks or changing
        # animation anchors. Native alpha still runs at the requested time.
        plan.intervals = ((state_time, time + 10),)
        return original(
            plan,
            style=style,
            layer=layer,
            max_events=max_events,
            max_chars=max_chars,
        )

    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    registered = load_font(root / "tests/fonts/DejaVuSans.ttf")
    source_path = root / "tests/fixtures/layered_glow.ass"
    measured = json.loads((output / "report.json").read_text())
    if (
        measured["source_sha256"]
        != hashlib.sha256(source_path.read_bytes()).hexdigest()
    ):
        raise ValueError("cost report uses a different source fixture")
    if measured["font_sha256"] != registered.sha256:
        raise ValueError("cost report uses a different font")
    source = Document.load(source_path)
    report = {
        "scope": "Same material renderer; exact-time vs held states isolates sampling. Full raster vs held lossless states isolates quantization plus final ASS/video conversion.",
        "references": {},
        "comparisons": [],
    }
    for mode in ("held", "exact"):
        combined: Document | None = None
        ages: dict[int, list[int]] = {}
        for time in TIMES:
            ages[time] = []

            with patch.object(
                TrackRasterPlan,
                "evaluate",
                snapshot_evaluator(time, mode == "held", ages[time]),
            ):
                result = prepare_tracks(
                    source,
                    tracks=tracks,
                    settings=OutputSettings(
                        resolution=(640, 480),
                        max_events=1_000_000,
                        raster=RasterSettings(max_output_chars=256_000_000),
                    ),
                    mode="native",
                ).compile(
                    budget=SceneBudget(
                        max_events=1_000_000,
                        max_bytes=256_000_000,
                        max_active=50_000,
                    )
                )
            if combined is None:
                combined = result.document
            else:
                combined.records.extend(line for line, _ in result.event_origins)
        assert combined is not None
        combined.save(output / f"{mode}.ass")
        report["references"][mode] = {
            "state_age_ms": ages,
            "capture": capture_output(output, mode),
        }
        print(mode, "captured", flush=True)
    for index, time in enumerate(TIMES, 1):
        images = {
            name: Image.open(output / f"{name}-{index:02d}.png").convert("RGB")
            for name in ("raster", "held", "exact")
        }
        entry = {"time_ms": time}
        for label, first, second in (
            ("spatial_and_output", "raster", "held"),
            ("temporal_hold", "held", "exact"),
        ):
            data = ImageChops.difference(images[first], images[second]).tobytes()
            entry[label] = {
                "max_channel_error": max(data),
                "mean_channel_error": sum(data) / len(data),
                "changed_pixels": sum(
                    any(data[i : i + 3]) for i in range(0, len(data), 3)
                ),
            }
        report["comparisons"].append(entry)
    (output / "sampling-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
