"""Measure inverse paint-mask error using system libass on RGB backgrounds.

uv run python -m tools.validate_boolean_masks /tmp/boolean-masks-validation
"""

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    PathObject,
    RectangleClip,
    Scene,
    Vec2,
    VectorClip,
    VectorPath,
)


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    document = Document.create(width=320, height=240)
    document.records.insert(1, "YCbCr Matrix: None")
    leaf = PathObject(
        id="field",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(120, 80),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(0, CYAN), ColorStop(320, PINK))), step=8
        ),
    )
    scenes = {
        "empty": Scene(document),
        "unmasked": Scene(document).add(leaf),
        "rectangle": Scene(document).add(
            replace(leaf, clip=RectangleClip(20, 10, 60, 40, inverse=True))
        ),
        "vector": Scene(document).add(
            replace(
                leaf,
                clip=VectorClip(
                    VectorPath.rectangle(40, 30).map(lambda p: p + Vec2(20, 10)),
                    inverse=True,
                ),
            )
        ),
    }
    for name, scene in scenes.items():
        scene.compile().document.save(output / f"{name}.ass")
    renderer: set[str] = set()

    def render(name: str, background: str) -> bytes:
        completed = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "info",
                "-f",
                "lavfi",
                "-i",
                background,
                "-vf",
                f"format=rgb24,setparams=range=full,ass={name}.ass",
                "-frames:v",
                "1",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            ],
            cwd=output,
            capture_output=True,
            check=True,
        )
        renderer.update(
            line.partition("] ")[2]
            for line in completed.stderr.decode().splitlines()
            if "libass source:" in line or "Shaper:" in line
        )
        if len(completed.stdout) != 320 * 240 * 3:
            raise AssertionError("unexpected render dimensions")
        return completed.stdout

    errors: dict[str, dict[str, int]] = {}
    for name, source in {
        "black": "color=black:s=320x240:r=1",
        "white": "color=white:s=320x240:r=1",
        "pattern": "testsrc2=s=320x240:r=1",
    }.items():
        background = render("empty", source)
        reference = bytearray(render("unmasked", source))
        for y in range(10, 40):
            start, end = (y * 320 + 20) * 3, (y * 320 + 60) * 3
            reference[start:end] = background[start:end]
        errors[name] = {}
        for mask in ("rectangle", "vector"):
            actual = render(mask, source)
            error = max(abs(a - b) for a, b in zip(actual, reference, strict=True))
            errors[name][mask] = error
            if mask == "rectangle" and error:
                raise AssertionError("native inverse rectangle introduced paint seams")
    report = {
        "scope": "320x240, 8px paint bands, fixed integer inverse mask; not an arbitrary vector error bound",
        "reference": "unmasked RGB render with hole pixels replaced by the same background",
        "renderer": sorted(renderer),
        "max_rgb_error": errors,
        "notes": [
            "inverse rectangles use disjoint native clips and must be pixel-identical",
            "vector booleans use standard vector clip coverage, which differs from hard rectangular exclusion",
            "path topology, stroke seams and independently authored vector references are tested in test_path_boolean.py and test_group_masks.py",
        ],
    }
    (output / "boolean-masks-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output.resolve())


if __name__ == "__main__":
    main()
