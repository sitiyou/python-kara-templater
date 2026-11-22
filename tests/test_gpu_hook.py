"""The delivery contract is FFmpeg alone, including a precise first/last frame."""

import shutil
import subprocess
from array import array
from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    Document,
    DriftOut,
    Lifetime,
    PathObject,
    ProgressCurve,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    StateFunction,
    Vec2,
    VectorPath,
    VisualState,
)


def test_large_hook_record_and_curve_addresses_survive_float32_storage():
    from kara_templater._gpu_hook import _Table

    table = _Table()
    table.values = array("f", [0]) * (2**24 + 1)
    curve = table.add(0.0, 0.5, 1.0)
    references = table.add(curve, 4 + curve, -4 - curve)
    direct, samples, knots = table.values[references : references + 3]
    assert direct == samples - 4 == -4 - knots == curve
    assert list(table.values[curve : curve + 3]) == [0.0, 0.5, 1.0]
    assert table.add(0.0, 0.5, 1.0) == curve


@pytest.fixture
def vulkan():
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    probe = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-init_hw_device",
            "vulkan=vk",
            "-f",
            "lavfi",
            "-i",
            "color=s=32x32",
            "-vf",
            "libplacebo",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    if probe.returncode:
        pytest.skip("FFmpeg/libplacebo with Vulkan unavailable")


def test_exported_hook_runs_on_its_frame_grid(tmp_path, vulkan):
    doc = Document.create(width=32, height=32)
    scene = Scene(doc).add(
        PathObject(
            id="rectangle",
            path=VectorPath.rectangle(12, 12),
            lifetime=Lifetime(1.1, 1.2),
            state=VisualState(position=Vec2(4, 4), fill=Color(255, 0, 0), border=0),
        )
    )
    hook = tmp_path / "test.hook"
    scene.export_hook(hook, start=1, duration=0.3, fps=10)
    frames = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-init_hw_device",
            "vulkan=vk",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:r=10:d=0.4",
            "-vf",
            "libplacebo=custom_shader_path=test.hook",
            "-c:v",
            "rawvideo",
            "-threads",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        cwd=tmp_path,
    )
    offset = (8 * 32 + 8) * 3
    assert len(frames) == 4 * 32 * 32 * 3
    assert [frames[offset + i * 32 * 32 * 3] > 200 for i in range(4)] == [
        False,
        True,
        False,
        False,
    ]
    assert frames[32 * 32 * 3 + offset + 1] < 30
    assert frames[32 * 32 * 3] < 30
    assert not doc.lines


@pytest.mark.parametrize("options", [{"fps": 0}, {"start": 0.007}, {"duration": 0}])
def test_invalid_export_preserves_existing_file(tmp_path, options):
    output = tmp_path / "song.hook"
    output.write_bytes(b"previous")
    scene = Scene(Document.create(width=32, height=32))
    with pytest.raises(ValueError):
        scene.export_hook(output, **options)
    assert output.read_bytes() == b"previous"


@pytest.mark.parametrize(
    "rate", [ProgressCurve(((0, 0), (0.25, 0.77), (1, 1))).at, lambda p: p**2]
)
def test_parametric_motion_matches_the_scene_evaluator(
    tmp_path, vulkan, rate, monkeypatch
):
    from kara_templater._gpu_scene import SceneFrames

    def build(sampled):
        shape = PathObject(
            id="shape",
            path=VectorPath.rectangle(28, 24),
            lifetime=Lifetime(0, 2),
            state=VisualState(position=Vec2(119, 3), fill=Color(240, 60, 40), border=2),
            clip=RectangleClip(
                0,
                0,
                28,
                24,
                space="local",
                deform=RectangleKeyframes(
                    (
                        (0, (0, 0, 3, 24)),
                        (0.5, (0, 0, 28, 24)),
                        (0.5, (0, 0, 18, 24)),
                        (1, (0, 0, 28, 24)),
                    )
                ),
            ),
        )
        for at, duration, motion in (
            (0, 0.7, ScalePulse(peak=1.4, peak_at=0.33, pivot=Vec2(8, 8), rate=rate)),
            (0.85, 0.9, DriftOut(offset=Vec2(-22, 3), scale=0.7, rate=rate)),
        ):
            shape = shape.animate(
                StateFunction(motion.sample, motion.channels) if sampled else motion,
                at=at,
                duration=duration,
            )
        return Scene(Document.create(width=160, height=32)).add(
            shape,
            replace(
                shape,
                id="second",
                layer=1,
                state=replace(shape.state, position=Vec2(8, 3)),
            ),
        )

    def render(name):
        return subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-init_hw_device",
                "vulkan=vk",
                "-f",
                "lavfi",
                "-i",
                "color=black:s=160x32:r=20:d=2",
                "-vf",
                f"libplacebo=dithering=none:custom_shader_path={name}.hook",
                "-pix_fmt",
                "rgb24",
                "-threads",
                "1",
                "-f",
                "rawvideo",
                "-",
            ],
            cwd=tmp_path,
        )

    build(True).export_hook(tmp_path / "sampled.hook", fps=20)

    def forbid_full_draw(*args):
        pytest.fail("ordinary motion unexpectedly sampled a full draw")

    monkeypatch.setattr(SceneFrames, "draw_at", forbid_full_draw)
    build(False).export_hook(tmp_path / "parametric.hook", fps=20)
    expected, actual = render("sampled"), render("parametric")
    assert max(actual) > 200
    assert max(abs(x - y) for x, y in zip(actual, expected, strict=True)) <= 4


@pytest.mark.parametrize(("core", "gradient", "reverse"), [(None, False, False), (Color(255, 255, 0), False, False), (None, True, False), (None, True, True)])
def test_feather_mixes_ink_inside_glyph_coverage(tmp_path, vulkan, core, gradient, reverse):
    from kara_templater import ColorRamp, ColorStop, LinearGradient
    from kara_templater.lyric_highlights import _FeatheredSingingClip

    before = Color(20, 30, 210)
    after = Color(220, 40, 20)
    base = LinearGradient(axis="y", space="local", fill=ColorRamp((
        ColorStop(0, before), ColorStop(18, Color(20, 230, 210)),
    ))) if gradient else None
    shape = PathObject(
        id="base",
        material=base,
        path=VectorPath.rectangle(32, 18),
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(8, 6), fill=before, border=0),
    )
    front = replace(
        shape,
        id="sung",
        material=None,
        state=replace(shape.state, fill=after),
        clip=(
            _FeatheredSingingClip(
                8 if reverse else -100,
                -100,
                100 if reverse else 24,
                100,
                space="local",
                width=16,
                unsung_fill=before,
                unsung_outline=before,
                unsung_gradient=base,
                front_color=core,
            )
        ),
    )
    scene = Scene(Document.create(width=48, height=32)).add(shape, front)
    scene.export_hook(tmp_path / "edge.hook", fps=10)
    data = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-init_hw_device",
            "vulkan=vk",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=48x32:r=10",
            "-vf",
            "libplacebo=custom_shader_path=edge.hook",
            "-frames:v",
            "1",
            "-threads",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        cwd=tmp_path,
    )

    def rgb(x, y):
        if reverse:
            x = 47 - x
        i = (48 * y + x) * 3
        return tuple(data[i : i + 3])

    red = [rgb(x, 15)[0] for x in (13, 20, 24, 28, 35)]
    if core is None:
        assert all(a > b + 8 for a, b in zip(red, red[1:], strict=False))
    else:
        assert rgb(27, 15)[1] > 200
        assert max(rgb(x, 15)[1] for x in (13, 35)) < 75
    if gradient:
        # Just inside the feather, the incoming ramp still varies with local y.
        assert rgb(30, 21)[1] > rgb(30, 8)[1] + 90
        assert abs(rgb(30, 21)[1] - rgb(36, 21)[1]) < 15
    assert max(rgb(24, 2)) < 10
