"""Verify that invalid scene extension contracts are rejected by the pinned ty."""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


CASES = (
    'from kara_templater import Document, prepare_track_coverage\nprepare_track_coverage(Document.create(), tracks=("invalid",), max_glow_blur=2, max_glow_border=3)\n',
    'from kara_templater import GlowFunction\nGlowFunction(lambda state, time: "bad", max_blur=2, max_border=3)\n',
    'from kara_templater import ScopeOpacity\nScopeOpacity("root", lambda time: "bad")\n',
    'from kara_templater import CoveragePartition\nCoveragePartition(lambda state, time: "bad", max_regions=1)\n',
    'from kara_templater import compile_coverage, Document\ncompile_coverage(Document.create(), "bad")\n',
    'from kara_templater import rasterize_group\nrasterize_group("invalid", resolution=(320, 180))\n',
    'from kara_templater import Document, prepare_track_scene\nprepare_track_scene(Document.create(), tracks=("invalid",))\n',
    'from kara_templater import RectangleFunction\nRectangleFunction(lambda time: "invalid")\n',
    'from kara_templater import VectorPath, path_boolean\np = VectorPath.rectangle(10, 10)\npath_boolean(p, p, "subtract")\n',
    'from kara_templater import Affine2D\nAffine2D().apply((1, 2))\n',
    'from kara_templater import Document, prepare_karaoke\nprepare_karaoke(Document.create(), tracks=("invalid",))\n',
    'from kara_templater import ReferenceFunction\nReferenceFunction(lambda state, time, lookup: "bad", ("target",), frozenset(("position",)))\n',

    'from kara_templater import RectangleClip\nRectangleClip(0, 0, 10, 10, space="canvas")\n',

    'from kara_templater import Document, bind_lyric_cues\nbind_lyric_cues(Document.create(), {})\n',

    'from kara_templater import Engine\nEngine(video_size="640x480")\n',
    'from kara_templater import apply_templates\napply_templates("input.ass")\n',

    'from kara_templater import SoftSweep\nSoftSweep(left=0, right=100, start=0, duration=1, rate=lambda t: "bad")\n',
    'from kara_templater import LinearGradient\nLinearGradient(axis="diagonal")\n',
    "from kara_templater import emit_particles\nemit_particles((), lambda context: 42)\n",
    'from kara_templater import MoveAlong\nMoveAlong("not a path")\n',
    'from kara_templater import StateFunction\nStateFunction(lambda state, progress: "not a state")\n',
    "from kara_templater import PathFunction\nPathFunction(lambda path, time: 42, max_points=100)\n",
    'from kara_templater import CuePreset\nCuePreset(factory=lambda context: "not cue content")\n',
    'from kara_templater import StatePatch\nStatePatch(position="not a vector")\n',
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="kara-type-negatives-") as directory:
        for index, code in enumerate(CASES):
            source = Path(directory) / f"invalid_{index}.py"
            source.write_text(code)
            result = subprocess.run(
                [
                    "ty",
                    "check",
                    "--project",
                    str(ROOT),
                    str(source),
                    "--output-format",
                    "concise",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            diagnostics = result.stdout + result.stderr
            if (
                result.returncode != 1
                or "invalid-argument-type" not in diagnostics
                or "import-not-found" in diagnostics
            ):
                raise AssertionError(
                    f"negative typing case {index} was not rejected for an argument contract:\n{diagnostics}"
                )
    print(f"{len(CASES)} invalid public extension contracts correctly rejected")


if __name__ == "__main__":
    main()
