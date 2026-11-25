"""The delivery contract is FFmpeg alone, including a precise first/last frame."""

import shutil
import subprocess
from array import array
from dataclasses import replace
from math import radians, tan

import pytest

from kara_templater import (
    WHITE,
    Color,
    Contour,
    Document,
    DriftOut,
    Extrusion,
    Lifetime,
    Line,
    LineSegment,
    ObjectGroup,
    PathObject,
    ProgressCurve,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    SceneCompileError,
    StateFunction,
    Style,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
    ease_in,
)
from kara_templater._cli_preset import preset_scene
from kara_templater._raster import rasterize


def test_custom_shader_motion_indexes_only_reachable_tiles_for_each_window(tmp_path):
    from kara_templater import ShaderMotion
    from kara_templater.output.hook.export import _TILE

    width, height = 6 * _TILE, 4 * _TILE
    motion = ShaderMotion(
        lambda base, p: replace(base, position=base.position + Vec2(300 * p, 0)),
        frozenset({"position"}),
        "pos.x+=300.*p;",
    )
    scene = Scene(Document.create(width=width, height=height)).add(PathObject(
        id="moving", path=VectorPath.rectangle(10, 10), lifetime=Lifetime(0, 2),
        state=VisualState(position=Vec2(10, 20)),
    ).animate(motion, duration=2))
    directory = tmp_path / "resources"
    scene.export_resources(directory, fps=30)

    data = array("f")
    data.frombytes((directory / "KARADATA.bin").read_bytes())
    tracks = int(data[6])
    occupied = {}
    for tile, ref in enumerate(data[tracks:tracks + 24]):
        if ref < 0:
            continue
        index = int(ref)
        occupied[tile] = tuple(
            (int(data[index + 1 + 2 * key]), data[index + 2 + 2 * key] >= 0)
            for key in range(int(data[index]))
        )
    assert occupied[0][0] == (0, True)
    assert occupied[0][-1][1] is False
    assert occupied[4][-1][1] is True
    assert occupied[4][0] == (0, False)
    assert max(occupied) < 6


@pytest.mark.parametrize(
    ("size", "copies", "diagnostic"),
    [(640, 129, "per-pixel draw candidates"), (16, 1025, "tile (0, 0)")],
)
def test_hook_rejects_excessive_fragment_work_before_writing(tmp_path, size, copies, diagnostic):
    scene = Scene(Document.create(width=640, height=360))
    path = VectorPath.rectangle(size, size)
    for index in range(copies):
        scene.add(PathObject(id=f"layer:{index}", path=path, lifetime=Lifetime(2, 3)))

    hook = tmp_path / "scene.hook"
    hook.write_text("previous export")
    with pytest.raises(SceneCompileError, match="Hook GPU work budget exceeded at 2s") as standalone:
        scene.export(hook, fps=30, start=1, duration=2)
    assert diagnostic in str(standalone.value)
    assert hook.read_text() == "previous export"

    resources = tmp_path / "resources"
    with pytest.raises(SceneCompileError, match="Hook GPU work budget exceeded at 2s"):
        scene.export_resources(resources, fps=30, start=1, duration=2)
    assert not resources.exists()


def test_large_hook_record_and_curve_addresses_survive_float32_storage():
    from kara_templater.output.hook.export import _HookRecordTable

    table = _HookRecordTable()
    table.values = array("f", [0]) * (2**24 + 1)
    curve = table.add(0.0, 0.5, 1.0)
    references = table.add(curve, 4 + curve, -4 - curve)
    direct, samples, knots = table.values[references : references + 3]
    assert direct == samples - 4 == -4 - knots == curve
    assert list(table.values[curve : curve + 3]) == [0.0, 0.5, 1.0]
    assert table.add(0.0, 0.5, 1.0) == curve


def test_hook_keeps_fixed_border_under_inherited_scale_and_a_pulse(tmp_path, vulkan):
    scene = Scene(Document.create(width=128, height=96))
    for scaled, y in ((False, 12), (True, 56)):
        drawing = PathObject(
            id=f"outline-{y}",
            path=VectorPath.rectangle(16, 12),
            lifetime=Lifetime(0, 1),
            filled=False,
            scale_border=scaled,
            state=VisualState(border=3, outline=Color(255, 255, 255)),
        ).animate(ScalePulse(peak=2, peak_at=0.5), duration=1)
        scene.add(ObjectGroup(
            id=f"group-{y}", children=(drawing,), lifetime=Lifetime(0, 1),
            state=VisualState(position=Vec2(66, y), scale=Vec2(0.5, 1.5)),
        ))
    scene.export(tmp_path / "outline.hook", fps=2)
    frames = subprocess.check_output(
        [
            "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi",
            "-i", "color=black:s=128x96:r=2:d=1", "-vf",
            "libplacebo=custom_shader_path=outline.hook:format=rgb24",
            "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        ],
        cwd=tmp_path,
    )

    def pixel(frame, x, y):
        return frames[((frame * 96 + y) * 128 + x) * 3]

    for frame in range(2):
        assert pixel(frame, 63, 20) > 250
        assert pixel(frame, 62, 20) < 5
    assert pixel(0, 63, 64) < 5
    assert pixel(1, 63, 64) > 250


def _render_hook(scene, directory, *, fps=2, background="black", duration=1):
    scene.export(directory / "test.hook", fps=fps, duration=duration)
    return subprocess.check_output(
        [
            "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi",
            "-i", f"color={background}:s=160x120:r={fps}:d={duration}", "-vf",
            "libplacebo=custom_shader_path=test.hook:format=rgb24",
            "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        ],
        cwd=directory,
    )


@pytest.mark.parametrize("filled", [False, True])
def test_hook_blurred_fixed_border_is_continuous_near_unit_scale(tmp_path, vulkan, filled):
    scene = Scene(Document.create(width=160, height=120)).add(
        TextObject(
            id="blurred", text="A", font_size=52, filled=filled, lifetime=Lifetime(0, 1),
            state=VisualState(position=Vec2(55, 25), fill=Color(0, 0, 0), outline=WHITE,
                              border=6, blur=8),
        ).animate(ScalePulse(peak=1.001, peak_at=0.5), duration=1)
    )
    pixels = _render_hook(scene, tmp_path)[::3]
    first, second = pixels[:160 * 120], pixels[160 * 120:]
    assert max(first) > 50
    assert sum(10 < value < 40 for value in first) > 200
    assert max(abs(a - b) for a, b in zip(first, second, strict=True)) <= 5


def test_hook_fixed_outline_closes_drawing_contours(tmp_path, vulkan):
    contour = Contour(Vec2(), (LineSegment(Vec2(20, 0)), LineSegment(Vec2(20, 20))), closed=False)
    scene = Scene(Document.create(width=160, height=120)).add(
        PathObject(
            id="open-contour", path=VectorPath((contour,)), filled=False, lifetime=Lifetime(0, 1),
            state=VisualState(position=Vec2(42, 24), scale=Vec2(2, 2), outline=WHITE, border=3),
        )
    )
    pixels = _render_hook(scene, tmp_path)[::3]
    assert pixels[44 * 160 + 60] > 200
    assert pixels[44 * 160 + 55] < 5


def test_preset_preserves_face_and_shadow_alpha_through_highlight_and_fades(tmp_path, vulkan):
    document = Document.create(
        width=160, height=120,
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=0, shadow=18),),
    )
    document.styles["Default"].fields.update(
        PrimaryColour="&H800000FF", SecondaryColour="&HC00000FF", BackColour="&H80000000",
    )
    document.records.append(Line(text=r"{\k150}A", start_time=500, end_time=2000))
    scene = preset_scene(
        document, owner="test", before=None, after=None, pulse="none", fade_in=0.25,
        fade_out=0.5, preview=0.5, tail=0, styles=None,
    )
    hook = _render_hook(scene, tmp_path, fps=8, background="white", duration=2.5)
    rendered_ass = scene.ass.compile().document.dumps()
    frame_size = 160 * 120 * 3
    for frame, face_alpha, shadow_alpha in ((1, 32, 64), (2, 63, 127), (6, 127, 127), (18, 64, 64)):
        rgba = rasterize(rendered_ass, frame * 125, (160, 120)).rgba
        red, green, alpha = rgba[::4], rgba[1::4], rgba[3::4]
        assert max(a for r, g, a in zip(red, green, alpha, strict=True) if r > g) == pytest.approx(face_alpha, abs=2)
        assert max(a for r, a in zip(red, alpha, strict=True) if r == 0) == pytest.approx(shadow_alpha, abs=2)
        rgb = hook[frame * frame_size:(frame + 1) * frame_size]
        red, green = rgb[::3], rgb[1::3]
        assert max(r - g for r, g in zip(red, green, strict=True)) == pytest.approx(face_alpha, abs=3)
        assert max(255 - r for r, g in zip(red, green, strict=True) if r == g) == pytest.approx(shadow_alpha, abs=3)


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
    "rate", [
        ProgressCurve(((0, 0), (0.25, 0.77), (1, 1))).at,
        ProgressCurve.cubic_bezier(.17, .17, 0, 1).at,
        ease_in,
    ]
)
def test_parametric_motion_matches_the_scene_evaluator(
    tmp_path, vulkan, rate, monkeypatch
):
    from kara_templater.output.hook.draws import HookDrawResolver

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

    from kara_templater.output.hook import export as hook
    from kara_templater.output.hook.motion import DrawSpan

    def oracle(frames, leaf, fps, first, stop, *, visible=None):
        for index in range(first, stop):
            if leaf.start <= index / fps < leaf.end:
                draw = frames.draw_at(leaf, index / fps)
                if draw is not None:
                    yield DrawSpan(index, index + 1, draw)

    with monkeypatch.context() as reference:
        reference.setattr(hook, "iter_draw_spans", oracle)
        build(True).export(tmp_path / "sampled.hook", fps=20)

    def forbid_full_draw(*args):
        pytest.fail("ordinary motion unexpectedly sampled a full draw")

    monkeypatch.setattr(HookDrawResolver, "draw_at", forbid_full_draw)
    build(False).export(tmp_path / "parametric.hook", fps=20)
    expected, actual = render("sampled"), render("parametric")
    assert max(actual) > 200
    assert max(abs(x - y) for x, y in zip(actual, expected, strict=True)) <= 4


@pytest.mark.parametrize(("core", "gradient", "reverse"), [(None, False, False), (Color(255, 255, 0), False, False), (None, True, False), (None, True, True)])
def test_feather_mixes_ink_inside_glyph_coverage(tmp_path, vulkan, core, gradient, reverse):
    from kara_templater import ColorRamp, ColorStop, LinearGradient
    from kara_templater.lyrics.highlights import _FeatheredWipeClip

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
        id="highlight",
        material=None,
        state=replace(shape.state, fill=after),
        clip=(
            _FeatheredWipeClip(
                8 if reverse else -100,
                -100,
                100 if reverse else 24,
                100,
                space="local",
                width=16,
                before_fill=before,
                before_outline=before,
                before_gradient=base,
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
    from kara_templater.output.hook import draws

    scene = Scene(Document.create(width=64, height=32))
    box = PathObject(id="a", path=VectorPath.rectangle(12, 12), lifetime=Lifetime(0, 2))
    scene.add(box)
    reference = tmp_path / "reference.hook"
    scene.export(reference, start=0, duration=0.5, fps=30)
    original = draws._coverage
    calls = []

    def record(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(draws, "_coverage", record)
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


def test_group_rectangles_use_their_own_clock_and_cut_extrusion(tmp_path, vulkan):
    drawing = PathObject(
        id="face", path=VectorPath.rectangle(28, 34), lifetime=Lifetime(.5, 1.75),
        clock_start=.75,
        clip=RectangleClip(
            4, 0, 36, 40, space="local",
            deform=RectangleKeyframes(((-.25, (4, 0, 36, 40)), (.75, (12, 0, 40, 40)))),
        ),
        extrusion=Extrusion(Vec2(8, 0), Color(255, 0, 0)),
    )
    inner = ObjectGroup(
        id="row", children=(drawing,), lifetime=Lifetime(.25, 1.75),
        state=VisualState(position=Vec2(7, 5)), clip=RectangleClip(0, 12, 64, 32),
    )
    outer = ObjectGroup(
        id="viewport", children=(inner,), lifetime=Lifetime(.25, 1.75), clock_start=.5,
        clip=RectangleClip(
            8, 0, 24, 48, deform=RectangleKeyframes((
                (0, (8, 0, 24, 48)), (.5, (20, 0, 40, 48)),
                (.5, (20, 0, 20, 48)), (1, (20, 0, 56, 48)),
            )),
        ),
    )
    Scene(Document.create(width=64, height=48)).add(outer).export(
        tmp_path / "group.hook", fps=4, start=.5, duration=1.25,
    )
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi", "-i",
        "color=c=black:s=64x48:r=4", "-vf", "libplacebo=custom_shader_path=group.hook:format=rgb24",
        "-frames:v", "5", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ], cwd=tmp_path)

    def pixel(frame, x, y=20):
        offset = 3 * ((48 * frame + y) * 64 + x)
        return tuple(raw[offset:offset + 3])

    white, red, black = (255, 255, 255), (255, 0, 0), (0, 0, 0)
    assert pixel(0, 10) == pytest.approx(black, abs=3)
    assert pixel(0, 11) == pytest.approx(white, abs=3)
    assert pixel(0, 24) == pytest.approx(black, abs=3)
    assert pixel(1, 20) == pytest.approx(white, abs=3)
    assert pixel(1, 20, 11) == pytest.approx(black, abs=3)
    assert pixel(1, 20, 12) == pytest.approx(white, abs=3)
    assert pixel(1, 20, 32) == pytest.approx(black, abs=3)
    assert pixel(2, 21) == pytest.approx(black, abs=3)
    assert pixel(3, 37) == pytest.approx(red, abs=3)
    assert pixel(3, 38) == pytest.approx(black, abs=3)
    assert pixel(4, 40) == pytest.approx(red, abs=3)
    assert pixel(4, 49) == pytest.approx(black, abs=3)


@pytest.mark.parametrize("reverse,feather,vertical,outer_width,inherited", [
    (False, 0, False, 3, False), (True, 8, False, 3, False),
    (False, 0, True, 3, False), (False, 0, False, 6, False), (True, 8, False, 3, True),
])
def test_shader_wipe_matches_split_draws_in_playback(
    tmp_path, vulkan, monkeypatch, reverse, feather, vertical, outer_width, inherited,
):
    from kara_templater import (
        BLUE,
        RED,
        KaraokeEffects,
        Line,
        LyricGradient,
        SecondaryOutline,
        Style,
        Track,
        build_lyric_scene,
    )
    from kara_templater.output.hook import export as hook

    doc = Document.create(width=160, height=96, styles=(Style(fontname="DejaVu Sans", fontsize=24, outline=2),))
    doc.records.append(Line(text=r"{\k80}Q", start_time=400, end_time=1200))
    scene = build_lyric_scene(doc, tracks=(Track(id="vocal", vertical=vertical, effects=(KaraokeEffects(
        highlight="none", entry="none", exit="none", reverse_wipe=reverse, hook_feather=feather,
        base_material=LyricGradient((BLUE, RED)), after_outline=RED,
        secondary_outline=SecondaryOutline(RED, 3), after_secondary_outline=SecondaryOutline(BLUE, outer_width),
    ),)),))
    if inherited:
        scene = Scene(doc).add(ObjectGroup(
            id="viewport", children=tuple(node for node in scene.objects if isinstance(node, ObjectGroup)),
            lifetime=Lifetime(0, 2), clip=RectangleClip(0, 0, 83, 96),
        ))
    masks = []
    original = hook._draw_record

    def record(table, atlas, draw, image, *args):
        masks.append(image[4])
        return original(table, atlas, draw, image, *args)

    monkeypatch.setattr(hook, "_draw_record", record)

    def play(name):
        scene.export(tmp_path / name, fps=10, start=0.2, duration=1.3)
        return subprocess.check_output([
            "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi", "-i",
            "color=c=black:s=160x96:r=10", "-vf", f"libplacebo=custom_shader_path={name}:format=rgb24",
            "-frames:v", "13", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        ], cwd=tmp_path)

    fused = play("wipe.hook")
    fused_count = len(masks)
    masks.clear()
    monkeypatch.setattr(hook, "match_wipe", lambda *_: None)
    split = play("split.hook")
    if outer_width == 3:
        assert fused_count > 0 and len(masks) == 2 * fused_count
    else:
        # Only the face and primary outline share coverage.
        assert fused_count < len(masks) < 2 * fused_count
    assert any(fused)
    if inherited:
        assert all(not any(fused[row + 3 * 83:row + 3 * 160])
                   for row in range(0, len(fused), 3 * 160))
    assert fused[:160 * 96 * 3] != fused[-160 * 96 * 3:]
    assert fused == split


@pytest.mark.parametrize("reverse", [False, True])
def test_shader_color_bands_match_scanline_and_glow_strips(tmp_path, vulkan, monkeypatch, reverse):
    from kara_templater import (
        BLUE,
        RED,
        Glow,
        KaraokeEffects,
        LyricGradient,
        SecondaryOutline,
        Track,
        build_lyric_scene,
    )
    from kara_templater.output.hook import export as hook

    doc = Document.create(width=192, height=112, styles=(Style(fontname="DejaVu Sans", fontsize=30, outline=2),))
    doc.records.append(Line(text=r"{\k35}M{\k40}i", start_time=700, end_time=1600))
    scene = build_lyric_scene(doc, tracks=(Track(id="vocal", effects=(KaraokeEffects(
        entry="tilt_pop", exit="spin_flip", highlight="utopia_scanline", reverse_wipe=reverse,
        scanline_width=12, scanline_softness=5, sweep_angle=19,
        base_material=LyricGradient((BLUE, WHITE)), material=LyricGradient((RED, WHITE)),
        secondary_outline=SecondaryOutline(RED, 1),
        base_glow=Glow(BLUE, blur=4, border=4, opacity=0.6),
        glow=Glow(RED, blur=4, border=4, opacity=0.4),
    ),)),))

    band_opacity_modes = set()
    original_paint = hook._BandedSpan.paint

    def record_band(band, table, *args):
        offset = original_paint(band, table, *args)
        band_opacity_modes.add(table.values[offset + 2])
        return offset

    monkeypatch.setattr(hook._BandedSpan, "paint", record_band)

    def play(name):
        scene.export(tmp_path / name, fps=20, start=0.25, duration=2)
        return subprocess.check_output([
            "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi", "-i",
            "color=c=black:s=192x112:r=20", "-vf", f"libplacebo=custom_shader_path={name}:format=rgb24",
            "-frames:v", "40", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        ], cwd=tmp_path)

    packed = play("band.hook")
    monkeypatch.setattr(hook, "match_band", lambda *_: None)
    monkeypatch.setattr(hook, "visible_windows", lambda *args: ((0, args[-1]),))
    original = play("strips.hook")

    assert packed == original
    assert any(packed)
    assert band_opacity_modes == {0, 1}
    assert (tmp_path / "band.hook").stat().st_size < (tmp_path / "strips.hook").stat().st_size


@pytest.mark.parametrize(("angle", "reverse", "feather"), [(None, False, 4), (-28, True, 4), (28, False, 0)])
def test_slanted_wipe_projects_color_boundary_in_playback(tmp_path, vulkan, angle, reverse, feather):
    from kara_templater import (
        BLUE,
        RED,
        KaraokeEffects,
        Layout,
        Track,
        VectorGuide,
        build_lyric_scene,
    )

    width, height = 128, 112
    doc = Document.create(width=width, height=height, styles=(
        Style(fontname="DejaVu Sans", fontsize=64, italic=angle is None, outline=0, shadow=0),
    ))
    doc.records.append(Line(text=r"{\k100}/", end_time=1000))
    effect = KaraokeEffects(
        entry="none", exit="none", highlight="none", before_fill=BLUE, after_fill=RED,
        reverse_wipe=reverse, sweep_angle=angle, hook_feather=feather,
    )
    guide = VectorGuide(VectorPath.polygon(
        Vec2(0, 0), Vec2(0.65, 0), Vec2(0.65, -0.65), Vec2(0, -0.65),
    ), advance=0.65)
    scene = build_lyric_scene(doc, tracks=(
        Track(id="voice", layout=Layout(position=Vec2(22, 12)), effects=(effect,), guide_symbols={"/": guide}),
    ))
    hook = tmp_path / "sweep.hook"
    scene.export(hook, fps=4, duration=1)
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-init_hw_device", "vulkan=vk", "-f", "lavfi", "-i",
        "color=c=black:s=128x112:r=4", "-vf", f"libplacebo=custom_shader_path={hook}:format=rgb24",
        "-frames:v", "4", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ])
    frame = raw[2 * width * height * 3:3 * width * height * 3]
    boundaries = []
    for y in range(height):
        row = y * width * 3
        reds = [x for x in range(width) if frame[row + 3*x] > 180]
        blues = [x for x in range(width) if frame[row + 3*x + 2] > 180]
        if reds and blues:
            boundaries.append((y, min(reds) if reverse else max(reds)))
    assert len(boundaries) > 20
    y0, x0 = boundaries[4]
    y1, x1 = boundaries[-5]
    assert (x1 - x0) / (y1 - y0) == pytest.approx(-tan(radians(19 if angle is None else angle)), abs=0.08)
