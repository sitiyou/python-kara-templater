"""E02 four-background letter compositing, including antialiased fading text.

uv run python -m tools.validate_staggered_colors OUTPUT
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from examples.scene_staggered import build
from kara_templater import load_font
from tools.validate_engine_backgrounds import ROOT, SIZE, backgrounds, preview
from tools.validate_particle_composite import finish, over
from tools.validate_staggered import fill, orbit_reference, reference

INDICES = (
    0,
    1,
    8,
    16,
    24,
    32,
    50,
    65,
    80,
    100,
    120,
    136,
    200,
    399,
    400,
    420,
    440,
    450,
    460,
    480,
    486,
    499,
    500,
)


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    path = ROOT / "tests/fonts/DejaVuSans.ttf"
    font = load_font(path)
    (output / "fonts").mkdir(exist_ok=True)
    (output / "fonts/DejaVuSans.ttf").write_bytes(path.read_bytes())
    script = build().compile().document.dumps()
    (output / "scene.ass").write_text(script)
    refs = {
        index: (reference(index * 10 + 1), orbit_reference(index * 10 + 1))
        for index in INDICES
    }
    for index, scripts in refs.items():
        for part, text in enumerate(scripts):
            (output / f"reference-{index}-{part}.ass").write_text(text)
    hashes = backgrounds(output)
    checks = []
    sheet = Image.new("RGB", (960, 720))
    for name in hashes:
        frames = preview(output, name, "scene.ass", INDICES)
        for index, actual in zip(INDICES, frames, strict=True):
            ms = index * 10 + 1
            actual_orbit = fill(script, ms, 0xFFC0CB)
            expected_orbit = fill(refs[index][1], ms, 0xFFC0CB)
            # Orbit rasterization uses a separate scalar polygon reference with
            # a 1px silhouette tolerance; keep its edge error separate from text.
            exclusion = (
                ImageChops.lighter(actual_orbit, expected_orbit)
                .point(lambda v: 255 if v else 0)
                .filter(ImageFilter.MaxFilter(3))
            )
            common = ImageChops.darker(actual_orbit, expected_orbit).point(
                lambda v: 255 if v == 255 else 0
            )
            with Image.open(output / (name + ".png")) as bg:
                channels = tuple(b.convert("F") for b in bg.convert("RGB").split())
            for text in refs[index]:
                over(channels, text, ms)
            expected = finish(channels)
            difference = ImageChops.difference(actual, expected)
            letters = difference.copy()
            letters.paste((0, 0, 0), (0, 0), exclusion)
            maximum = max(i % 256 for i, n in enumerate(letters.histogram()) if n)
            if maximum > 2:
                raise AssertionError(
                    f"text composite differs by {maximum}/255 at {ms}ms on {name}"
                )
            orbit_diff = ImageChops.difference(
                actual, Image.new("RGB", SIZE, (255, 192, 203))
            )
            orbit_diff.paste((0, 0, 0), (0, 0), ImageChops.invert(common))
            orbit_max = max(i % 256 for i, n in enumerate(orbit_diff.histogram()) if n)
            if orbit_max:
                raise AssertionError("solid orbit color changed")
            if 500 <= ms < 4500 and not common.getbbox():
                raise AssertionError("orbit has no compared solid interior")
            checks.append(
                {
                    "time_ms": ms,
                    "background": name,
                    "max_text_composite_rgb_difference": maximum,
                    "orbit_interior_pixels": common.histogram()[255],
                    "max_orbit_interior_rgb_difference": orbit_max,
                    "max_whole_frame_rgb_difference": max(
                        i % 256 for i, n in enumerate(difference.histogram()) if n
                    ),
                }
            )
            if name == "checker" and index in (32, 100, 420, 460):
                row = (32, 100, 420, 460).index(index)
                for col, image in enumerate(
                    (actual, expected, difference.point(lambda v: min(255, v * 8)))
                ):
                    sheet.paste(image.resize((320, 180)), (col * 320, row * 180))
    sheet.save(output / "staggered-colors.png")
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
        "scope": "E02 complete text compositing including antialiased edges and alpha on four backgrounds; independent scalar orbit edges excluded with a one-pixel envelope, solid orbit color checked separately",
        "renderer": [
            line.strip()
            for line in renderer.stderr.splitlines()
            if "libass source" in line or "Shaper:" in line
        ],
        "font_sha256": font.sha256,
        "background_sha256": hashes,
        "ass_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "reference_sha256": {
            str(i): [hashlib.sha256(s.encode()).hexdigest() for s in scripts]
            for i, scripts in refs.items()
        },
        "checks": checks,
        "remaining": [
            "orbit edge differences separately measured, not pixel identity",
            "continuous ideal motion error",
            "other renderers",
        ],
    }
    (output / "staggered-colors-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_text_rgb_difference": max(
                    c["max_text_composite_rgb_difference"] for c in checks
                ),
                "max_whole_frame_rgb_difference": max(
                    c["max_whole_frame_rgb_difference"] for c in checks
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
