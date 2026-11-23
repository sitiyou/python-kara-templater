"""Verify that invalid scene extension contracts are rejected by the pinned ty."""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


CASES = (
    "from kara_templater import KaraokeEffects, Note\nKaraokeEffects.duotone(feather=Note.duration)\n",
    'from kara_templater import FadeOut, Glyph, LyricRule\nLyricRule("line", "exit", FadeOut(), duration=Glyph.font_size)\n',
    'from kara_templater import KaraokeEffects\nKaraokeEffects(entry="scatter_out")\n',
    'from kara_templater import KaraokeEffects\nKaraokeEffects(singing="fade")\n',
    'from kara_templater import KaraokeEffects\nKaraokeEffects(decoration="glitter")\n',
    'from kara_templater import Track\nTrack(id="main", effects=(lambda line: "bad",))\n',
    'from kara_templater import TrailPath, Polyline, Vec2\nTrailPath(Polyline((Vec2(), Vec2(1, 1))), rate=lambda p: "bad")\n',
    'from kara_templater import LyricEcho\nLyricEcho(animation="invalid")\n',
    'from kara_templater import LyricHighlights, StatePatch\nLyricHighlights.from_singing(StatePatch(), base_paint="invalid")\n',
    'from kara_templater import LyricParticles\nLyricParticles(factory=lambda context: "bad")\n',
    'from kara_templater import LyricEcho\nLyricEcho(target="line")\n',
    'from kara_templater import lyric_effects\nlyric_effects(lambda line: "bad")\n',
    'from kara_templater import LyricGradient\nLyricGradient(("red", "blue"))\n',
    'from kara_templater import LyricHighlights, StatePatch\nLyricHighlights.from_singing(StatePatch(), material=lambda line, target: "bad")\n',
    'from kara_templater import Transform\nTransform(offset=lambda p: "wrong")\n',
    'from kara_templater import Transform\nTransform(scale=lambda p: None)\n',
    'from kara_templater import ScalePulse\nScalePulse(peak_at="late")\n',
    'from kara_templater import SceneBudget\nSceneBudget(clip_error_px="small")\n',
    'from kara_templater import RectangleKeyframes\nRectangleKeyframes(((0, "invalid"),))\n',
    'from kara_templater import GlowFunction\nGlowFunction(lambda state, time: None, max_blur=0, max_border=0, required_interval="invalid")\n',
    'from kara_templater import LyricLine\ndef bad(line: LyricLine) -> None:\n    LyricLine(id=line.id, lifetime=line.lifetime, layout=line.layout, targets=line.targets, required_display=("invalid",))\n',
    'from kara_templater import LyricLine\ndef bad(line: LyricLine) -> None:\n    line.query("typo")\n',
    'from kara_templater import LyricRule, Jump\nLyricRule(("ruby",), "singing", Jump())\n',
    'from kara_templater import Document, Scene\nScene(Document.create()).compile(on_estimate="invalid")\n',
    'from kara_templater import Document, compile_scene, Scene\ndef wrong(value: str) -> None: pass\ncompile_scene(Scene(Document.create()), on_estimate=wrong)\n',
    'from kara_templater import GlowFunction\nGlowFunction.from_animation("invalid", duration=1)\n',
    'from kara_templater import Track\nTrack(id="main", source=lambda source: "invalid")\n',
    'from kara_templater import Layout\nLayout(rows="two")\n',
    'from kara_templater import LyricRule\nLyricRule("line", "enter", lambda timing: "invalid", duration=1)\n',
    "from kara_templater import LyricHighlights\nLyricHighlights(highlights=(), glow=lambda line, target: 42)\n",
    'from kara_templater import Jump\nfrom kara_templater.lyric_line import LyricRule\nLyricRule("character", lambda line, target: "wrong", Jump())\n',
    'from kara_templater import GlowFunction\nGlowFunction(lambda state, time: "bad", max_blur=2, max_border=3)\n',
    'from kara_templater import ScopeOpacity\nScopeOpacity("root", lambda time: "bad")\n',
    'from kara_templater import CoveragePartition\nCoveragePartition(lambda state, time: "bad", max_regions=1)\n',
    'from kara_templater import Coverage\nCoverage(partitions={"bad": "wrong"})\n',
    'from kara_templater import Document, prepare_tracks\nprepare_tracks(Document.create(), tracks=("invalid",))\n',
    'from kara_templater import RectangleFunction\nRectangleFunction(lambda time: "invalid")\n',
    'from kara_templater import VectorPath, path_boolean\np = VectorPath.rectangle(10, 10)\npath_boolean(p, p, "subtract")\n',
    "from kara_templater import Affine2D\nAffine2D().apply((1, 2))\n",
    "from kara_templater import Document, prepare_tracks\nprepare_tracks(Document.create(), tracks=(), owner=123)\n",
    'from kara_templater import ReferenceFunction\nReferenceFunction(lambda state, time, lookup: "bad", ("target",), frozenset(("position",)))\n',
    'from kara_templater import RectangleClip\nRectangleClip(0, 0, 10, 10, space="canvas")\n',
    "from kara_templater import Document, bind_lyric_cues\nbind_lyric_cues(Document.create(), {})\n",
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
