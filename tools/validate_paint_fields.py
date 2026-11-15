"""Compare standard libass paint bands on black, white and patterned backgrounds.

uv run python -m tools.validate_paint_fields /tmp/paint-fields-validation
"""

import argparse
import json
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Literal

from PIL import Image

from kara_templater import (
    BLACK,
    RED,
    WHITE,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    PaintBand,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)

ROOT = Path(__file__).resolve().parents[1]


class Slices:
    axis: Literal["x"] = "x"
    max_bands: int = 320
    breakpoints: tuple[float, ...] = ()

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        return tuple(
            PaintBand(x, x + 1, base.fill, base.outline) for x in range(start, end)
        )


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    doc = Document.create(width=320, height=160)
    # Disable historical VSFilter color mangling for a direct RGB reference.
    doc.records.insert(1, "YCbCr Matrix: None")
    text = TextObject(
        id="text",
        text="AV ffi",
        font_size=64,
        lifetime=Lifetime(0, 1),
        state=VisualState(
            position=Vec2(30, 30),
            fill=WHITE,
            outline=RED,
            border=3,
            blur=2,
            rotation=8,
            opacity=0.7,
        ),
    )
    gradient = PathObject(
        id="gradient",
        path=VectorPath.rectangle(320, 160),
        lifetime=Lifetime(0, 1),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(0, BLACK), ColorStop(320, WHITE)))
        ),
    )
    comparisons: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="kara-paint-check-") as directory:
        work = Path(directory)
        (work / "font.ttf").write_bytes(
            (ROOT / "tests/fonts/DejaVuSans.ttf").read_bytes()
        )
        scenes = {
            "whole": Scene(doc).add(text),
            "slices": Scene(doc).add(replace(text, material=Slices())),
            "gradient": Scene(doc).add(gradient),
        }
        for name, scene in scenes.items():
            scene.compile().document.save(work / f"{name}.ass")

        def render(name: str, background: str) -> bytes:
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    background,
                    "-vf",
                    f"format=rgb24,setparams=range=full,ass={name}.ass:fontsdir=.",
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "rgb24",
                    "-f",
                    "rawvideo",
                    "-",
                ],
                cwd=work,
                capture_output=True,
                check=True,
            )
            if len(completed.stdout) != 320 * 160 * 3:
                raise AssertionError("unexpected frame dimensions")
            return completed.stdout

        for background, source in {
            "black": "color=black:s=320x160:r=50:d=0.02",
            "white": "color=white:s=320x160:r=50:d=0.02",
            "pattern": "testsrc2=s=320x160:r=50:d=0.02",
        }.items():
            whole, slices = render("whole", source), render("slices", source)
            difference = max(abs(a - b) for a, b in zip(whole, slices, strict=True))
            if difference != 0:
                raise AssertionError(f"clip seams on {background}: {difference}")
            comparisons[background] = difference
            Image.frombytes("RGB", (320, 160), slices).save(
                output / f"slices-{background}.png"
            )
        pixels = render("gradient", "color=black:s=320x160:r=50:d=0.02")
        error = max(
            abs(pixels[(80 * 320 + x) * 3 + c] - round((x + 0.5) * 255 / 320))
            for x in range(320)
            for c in range(3)
        )
        if error > 2:
            raise AssertionError(f"gradient RGB error exceeds 2/255: {error}")
        Image.frombytes("RGB", (320, 160), pixels).save(output / "gradient.png")
    report = {
        "renderer": "system ffmpeg/libass, RGB24 input/output, YCbCr Matrix: None",
        "clip_seam_max_channel_difference": comparisons,
        "gradient_pixel_center_max_channel_error": error,
        "scope": "320x160, unit script/video scale; fixed rotated translucent blurred text and opaque grayscale ramp",
        "remaining": [
            "scaled output resolutions",
            "colored-front blur semantics",
            "temporal reference errors",
        ],
    }
    (output / "paint-fields-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
