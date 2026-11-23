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
    ease_in,
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
    scene.export(hook, start=1, duration=0.3, fps=10)
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
        scene.export(output, **options)
    assert output.read_bytes() == b"previous"


@pytest.mark.parametrize(
    "rate", [ProgressCurve(((0, 0), (0.25, 0.77), (1, 1))).at, ease_in]
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

    from kara_templater import _gpu_hook
    from kara_templater._hook_motion import Span

    def oracle(frames, leaf, fps, first, stop):
        for index in range(first, stop):
            if leaf.start <= index / fps < leaf.end:
                draw = frames.draw_at(leaf, index / fps)
                if draw is not None:
                    yield Span(index, index + 1, draw)

    with monkeypatch.context() as reference:
        reference.setattr(_gpu_hook, "spans", oracle)
        build(True).export(tmp_path / "sampled.hook", fps=20)

    def forbid_full_draw(*args):
        pytest.fail("ordinary motion unexpectedly sampled a full draw")

    monkeypatch.setattr(SceneFrames, "draw_at", forbid_full_draw)
    build(False).export(tmp_path / "parametric.hook", fps=20)
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
    scene.export(tmp_path / "edge.hook", fps=10)
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


def test_contour_stroke_changes_width_around_both_sides_of_path(tmp_path, vulkan):
    from kara_templater import ShaderMotion
    from kara_templater._contour_stroke import contour_stroke

    path = VectorPath.rectangle(16, 16)
    node = PathObject(
        id="flash",
        path=path,
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(8, 8), outline=Color(255, 255, 255)),
        filled=False,
        shader_paint=contour_stroke(path, 4),
    ).animate(
        ShaderMotion(
            lambda base, p: replace(base, border=4 * (1 - p)),
            frozenset({"border"}),
            "pen=4.*(1.-p);",
        ),
        duration=1,
    )
    Scene(Document.create(width=32, height=32)).add(node).export(
        tmp_path / "stroke.hook", fps=4
    )
    pixels = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-init_hw_device",
            "vulkan=vk",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=32x32:r=4:d=1",
            "-vf",
            "libplacebo=dithering=none:custom_shader_path=stroke.hook",
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

    def red(frame, x):
        return pixels[(frame * 32 * 32 + 16 * 32 + x) * 3]

    for x in (5, 10):
        assert red(0, x) > 240
        assert red(3, x) < 12
    assert red(3, 7) > 240
    assert red(0, 16) < 12


def test_binary_preview_resources_match_standalone_hook(tmp_path):
    import hashlib
    import json

    scene = Scene(Document.create(width=32, height=32)).add(
        PathObject(id="box", path=VectorPath.rectangle(12, 12), lifetime=Lifetime(0, 2))
    )
    hook, directory = tmp_path / "test.hook", tmp_path / "resources"
    scene.export(hook, start=0.5, duration=1, fps=30)
    scene.export_resources(directory, start=0.5, duration=1, fps=30)
    mask, commands, shader = hook.read_text().split("\n\n", 2)
    metadata = json.loads((directory / "textures.json").read_text())
    assert metadata["clock"] == [30, 15, 30]
    for block, name in ((mask, "KARAMASK"), (commands, "KARADATA")):
        payload = (directory / (name + ".bin")).read_bytes()
        assert payload == bytes.fromhex(block.splitlines()[-1])
        assert metadata["hashes"][name] == hashlib.sha256(payload).hexdigest()
        assert metadata[name] == list(map(int, block.splitlines()[1].split()[1:]))
    assert (
        shader.split("//!BIND KARADATA\n")[1] == (directory / "scene.frag").read_text()
    )


def test_prepared_hook_reuses_masks_across_seeks_and_snapshots_scene(
    tmp_path, monkeypatch
):
    from kara_templater import _gpu_scene

    scene = Scene(Document.create(width=64, height=32))
    box = PathObject(id="a", path=VectorPath.rectangle(12, 12), lifetime=Lifetime(0, 2))
    scene.add(box)
    reference = tmp_path / "reference.hook"
    scene.export(reference, start=0, duration=0.5, fps=30)
    original = _gpu_scene._coverage
    calls = []

    def record(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(_gpu_scene, "_coverage", record)
    prepared = scene.prepare_hook()
    scene.add(replace(box, id="b", state=VisualState(position=Vec2(32, 0))))
    prepared.export(tmp_path / "later.hook", start=1, duration=0.5, fps=60)
    prepared.export(tmp_path / "earlier.hook", start=0, duration=0.5, fps=30)
    assert calls == [1]
    assert (tmp_path / "earlier.hook").read_bytes() == reference.read_bytes()


def test_python_only_animation_reports_object_and_preserves_hook(tmp_path):
    from kara_templater import SceneCompileError

    scene = Scene(Document.create(width=32, height=32)).add(
        PathObject(
            id="moving-petal",
            path=VectorPath.rectangle(5, 3),
            lifetime=Lifetime(0, 1),
        ).animate(
            StateFunction(lambda base, p: base, frozenset({"position"})), duration=1
        )
    )
    output = tmp_path / "existing.hook"
    output.write_bytes(b"previous export")
    with pytest.raises(SceneCompileError, match="StateFunction") as error:
        scene.export(output)
    assert error.value.object_id == "moving-petal"
    assert "0s" in str(error.value)
    assert output.read_bytes() == b"previous export"


def test_shader_motion_can_color_the_fill_and_outline_independently(tmp_path, vulkan):
    from kara_templater import ShaderMotion

    node = PathObject(
        id="box",
        path=VectorPath.rectangle(16, 16),
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(8, 8), border=3),
    ).animate(
        ShaderMotion(
            lambda base, p: replace(
                base,
                fill=Color(round(255 * p), 0, 0),
                outline=Color(0, round(255 * (1 - p)), 0),
            ),
            frozenset({"fill", "outline"}),
            "fill=vec3(p,0.,0.); outline=vec3(0.,1.-p,0.);",
        ),
        duration=1,
    )
    Scene(Document.create(width=32, height=32)).add(node).export(
        tmp_path / "color.hook", fps=2
    )
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-init_hw_device",
            "vulkan=vk",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=32x32:r=2:d=1",
            "-vf",
            "libplacebo=dithering=none:custom_shader_path=color.hook",
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

    def sample(frame, x):
        index = (frame * 32 * 32 + 16 * 32 + x) * 3
        return tuple(raw[index : index + 3])

    assert sample(0, 16) == pytest.approx((0, 0, 0), abs=3)
    assert sample(0, 6) == pytest.approx((0, 255, 0), abs=3)
    assert sample(1, 16) == pytest.approx((128, 0, 0), abs=3)
    assert sample(1, 6) == pytest.approx((0, 128, 0), abs=3)
