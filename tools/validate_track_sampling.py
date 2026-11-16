"""Compare common coverage output against lossless held and centisecond samples.

Input is validate_track_cost's output directory. This isolates quantization and
sampling using the same material renderer, not an independent shader reference.
The 100 fps reference evaluates every representable ASS time; it makes no claim
about unrepresentable sub-centisecond behavior.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

from examples.layered_glow import Paint, configuration
from kara_templater import Document, RasterSettings, SceneBudget, load_font
from kara_templater.orchestration import prepare_tracks
from tools.capture_layered_glow import TIMES
from tools.validate_track_cost import capture_output


def main() -> None:
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
    if measured["outputs"]["coverage"]["status"] != "generated":
        raise ValueError("coverage output must fit the cost-report budget first")
    source = Document.load(source_path)
    report = {
        "scope": "Same common coverage renderer. Lossless 50 fps vs 100 fps isolates temporal holding at ASS clocks; measured coverage vs lossless 50 fps isolates quantization and final ASS conversion.",
        "references": {},
        "comparisons": [],
    }
    capture_output(output, "coverage")
    for mode, fps in (("held", 50), ("exact", 100)):
        settings = RasterSettings(max_output_chars=256_000_000, max_frames=1000)
        scene = prepare_tracks(
            source,
            tracks=tuple(
                configuration(source.styles[name], paint=Paint("coverage", settings))
                for name in ("K1", "K2", "LEAD")
            ),
            owner="layered-glow",
        )
        result = scene.compile(
            budget=SceneBudget(
                fps=fps,
                max_events=1_000_000,
                max_bytes=256_000_000,
                max_active=50_000,
            )
        )
        result.document.save(output / f"{mode}.ass")
        report["references"][mode] = {
            "fps": fps,
            "events": result.event_count,
            "capture": capture_output(output, mode),
        }
        print(mode, "captured", flush=True)
    for index, time in enumerate(TIMES, 1):
        images = {
            name: Image.open(output / f"{name}-{index:02d}.png").convert("RGB")
            for name in ("coverage", "held", "exact")
        }
        entry = {"time_ms": time}
        for label, first, second in (
            ("spatial_and_output", "coverage", "held"),
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
