"""Scene geometry → coverage materials, without the Track frontend."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    WHITE,
    AnimationClip,
    Document,
    Glow,
    Lifetime,
    ObjectGroup,
    PathObject,
    RasterSettings,
    RectangleClip,
    Scene,
    SceneBudget,
    StateFunction,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import RasterCanvas, rasterize
from kara_templater._scene_coverage import SceneCoverageSampler

RESOLUTION = (120, 90)
LIFETIME = Lifetime(0, 1)
DEFAULT_POSITION = Vec2(25, 30)


def root(*children, opacity=1):
    return ObjectGroup(
        id="root",
        lifetime=LIFETIME,
        children=children,
        state=VisualState(opacity=opacity),
    )


def rectangle(identity="shape", *, position=DEFAULT_POSITION, color=BLUE, opacity=1):
    return PathObject(
        id=identity,
        lifetime=LIFETIME,
        path=VectorPath.rectangle(40, 25),
        state=VisualState(
            position=position, fill=color, outline=RED, border=2, opacity=opacity
        ),
    )


def sampler(group, **kwargs):
    return SceneCoverageSampler(
        group,
        resolution=RESOLUTION,
        glows=kwargs.pop("glows", {}),
        settings=kwargs.pop("settings", RasterSettings()),
        budget=kwargs.pop("budget", SceneBudget()),
        **kwargs,
    )


def canvas_frame(frame):
    canvas = RasterCanvas(*RESOLUTION)
    if frame is not None:
        x, y, image = frame
        canvas.over_frame(image, x, y)
    return canvas.finish()


def native(*nodes, time=500, opacity=1):
    scene = Scene(Document.create(width=RESOLUTION[0], height=RESOLUTION[1])).add(
        *nodes
    )
    return rasterize(
        scene.compile().document.dumps(), time, RESOLUTION, opacity=opacity
    )


@pytest.mark.parametrize("text", [False, True])
def test_fill_stroke_component_matches_native_before_root_alpha(text):
    node = rectangle()
    if text:
        node = TextObject(
            id="shape",
            text="A",
            font_size=40,
            alignment=7,
            lifetime=LIFETIME,
            state=node.state,
        )
    sampled = canvas_frame(sampler(root(node, opacity=0.5)).frame(0.5))
    assert sampled.rgba == native(node, opacity=0.5).rgba


def test_nested_groups_apply_opacity_after_child_composition():
    first = replace(
        rectangle("first", color=RED),
        state=VisualState(position=Vec2(25, 30), fill=RED),
    )
    second = replace(
        rectangle("second", color=BLUE),
        state=VisualState(position=Vec2(40, 35), fill=BLUE),
    )
    child = ObjectGroup(
        id="child",
        lifetime=LIFETIME,
        children=(first, second),
        state=VisualState(opacity=0.5),
    )
    actual = canvas_frame(sampler(root(child, opacity=0.5)).frame(0.5))
    offset = (40 * RESOLUTION[0] + 50) * 4
    assert actual.rgba[offset : offset + 4] == bytes(
        (BLUE.red, BLUE.green, BLUE.blue, 64)
    )
    assert actual != native(root(child, opacity=0.5))


def test_explicit_glow_is_composed_before_component_opacity():
    node = replace(
        rectangle(), state=VisualState(position=Vec2(25, 30), fill=WHITE, opacity=0.5)
    )
    actual = canvas_frame(
        sampler(root(node), glows={node.id: Glow(RED, blur=2, border=3)}).frame(0.5)
    )
    halo = replace(
        node,
        id="halo",
        state=replace(node.state, fill=RED, outline=RED, border=3, blur=2, opacity=1),
    )
    ink = replace(node, id="ink", layer=1, state=replace(node.state, opacity=1))
    expected = native(halo, ink, opacity=0.5)
    # The coverage/core and native glyph kernels have independent 8-bit stages.
    for background in (0, 255):

        def over(data, background=background):
            return tuple(
                round(
                    data[i + c] * data[i + 3] / 255
                    + background * (1 - data[i + 3] / 255)
                )
                for i in range(0, len(data), 4)
                for c in range(3)
            )

        assert (
            max(
                abs(a - b)
                for a, b in zip(over(actual.rgba), over(expected.rgba), strict=True)
            )
            <= 2
        )


def test_motion_masks_seek_and_copy_keep_scene_geometry():
    node = replace(
        rectangle(),
        clip=RectangleClip(30, 25, 70, 60),
        animations=(AnimationClip(0, 1, Tween(StatePatch(position=Vec2(35, 30)))),),
    )
    group = root(node)
    sample = sampler(group)
    delayed = sampler(group.copy(id="later", delay=2))
    for time in (0.91, 0.11, 0.51, 0.31):
        actual = canvas_frame(sample.frame(time))
        assert actual.rgba == native(group, time=round(time * 1000)).rgba
        assert canvas_frame(delayed.frame(time + 2)) == actual
    assert sample.frame(1) is None


def test_budget_preflight_precedes_callbacks_and_errors_have_identity():
    calls = []

    def callback(state, progress):
        calls.append(progress)
        return state

    node = replace(
        rectangle(),
        animations=(
            AnimationClip(0, 1, StateFunction(callback, frozenset(("position",)))),
        ),
    )
    with pytest.raises(ValueError, match="geometry event budget"):
        sampler(root(node), budget=SceneBudget(max_events=1))
    assert not calls
    with pytest.raises(ValueError, match="glow blur"):
        sampler(root(node), glows={node.id: Glow(RED, blur=101)})
    assert not calls
    invalid = replace(node, state=replace(node.state, blur=1))
    with pytest.raises(ValueError, match="shape:.*explicit glow"):
        sampler(root(invalid)).frame(0.5)


@pytest.mark.parametrize("axis", ["x", "y"])
def test_color_fields_use_scene_coordinates_before_coverage_composition(axis):
    from kara_templater import SoftSweep

    field = SoftSweep(
        left=25,
        right=65,
        start=0,
        duration=1,
        fill=(RED, BLUE),
        outline=(BLUE, RED),
        axis=axis,
        width=12,
    )
    node = replace(rectangle(), material=field)
    sample = sampler(root(node))
    for time in (0.11, 0.51, 0.91):
        actual = canvas_frame(sample.frame(time)).rgba
        expected = native(node, time=round(time * 1000)).rgba
        assert actual[3::4] == expected[3::4]
        # Coverage painting has an extra 8-bit premultiply/unpremultiply stage.
        # Compare displayed color, not unstable straight RGB at tiny alpha.
        for background in (0, 255):

            def over(data, background=background):
                return tuple(
                    round(
                        data[i + c] * data[i + 3] / 255
                        + background * (1 - data[i + 3] / 255)
                    )
                    for i in range(0, len(data), 4)
                    for c in range(3)
                )

            assert (
                max(
                    abs(a - b)
                    for a, b in zip(over(actual), over(expected), strict=True)
                )
                <= 1
            )


def test_glow_field_spreads_across_the_front_before_fill_occlusion():
    from kara_templater import Color, SoftSweep

    red, blue = Color(255, 0, 0), Color(0, 0, 255)
    field = SoftSweep(left=25, right=65, start=0, duration=1, fill=(red, blue), width=0)
    node = replace(rectangle(), state=VisualState(position=Vec2(25, 30), fill=WHITE))
    sample = sampler(
        root(node), glows={node.id: Glow(red, blur=4)}, glow_materials={node.id: field}
    )
    image = canvas_frame(sample.frame(0.5))
    # Above the fill, both sides of the hard material front receive the blur.
    for x in (44, 45):
        offset = (27 * RESOLUTION[0] + x) * 4
        assert image.rgba[offset] > 0
        assert image.rgba[offset + 2] > 0
        assert image.rgba[offset + 3] > 0
    offset = (40 * RESOLUTION[0] + 45) * 4
    assert image.rgba[offset : offset + 4] == bytes((255, 255, 255, 255))


def test_hidden_path_deformation_does_not_fall_back_to_original_geometry():
    from kara_templater import PathFunction

    node = replace(
        rectangle(),
        deform=PathFunction(
            lambda path, time: None if time >= 0.5 else path,
            max_points=4,
            breakpoints=(0.5,),
        ),
    )
    sample = sampler(root(node), glows={node.id: Glow(RED, blur=2)})
    assert sample.frame(0.75) is None
    assert sample.frame(0.25) is not None
    assert sample.frame(0.75) is None


def test_scene_material_sample_survives_standard_ass_encoding():
    from kara_templater import DisplayWindow, SoftSweep
    from kara_templater._raster import encode_frame

    sweep = SoftSweep(left=25, right=65, start=0, duration=1, fill=(RED, BLUE), width=8)
    node = replace(rectangle(), material=sweep)
    source = sampler(
        root(node, opacity=0.65),
        glows={node.id: Glow(RED, blur=2)},
        glow_materials={node.id: sweep},
    )
    sampled = source.frame(0.51)
    assert sampled is not None
    x, y, frame = sampled
    document = Document.create(width=RESOLUTION[0], height=RESOLUTION[1])
    document.records.extend(
        encode_frame(
            frame, DisplayWindow(500, 520), position=(x, y), resolution=RESOLUTION
        )
    )
    assert rasterize(document.dumps(), 510, RESOLUTION) == canvas_frame(sampled)


def test_component_combines_colored_fragments_before_scope_alpha():
    from kara_templater import Color

    red, blue = Color(255, 0, 0), Color(0, 0, 255)
    first = replace(
        rectangle("first", color=red, opacity=0.25),
        state=VisualState(position=DEFAULT_POSITION, fill=red, opacity=0.25),
    )
    second = replace(
        rectangle("second", color=blue, opacity=0.75),
        state=VisualState(position=DEFAULT_POSITION, fill=blue, opacity=0.75),
    )
    group = root(first, second, opacity=0.5)
    actual = canvas_frame(sampler(group, components=(group.id,)).frame(0.5))
    offset = (40 * RESOLUTION[0] + 40) * 4
    assert actual.rgba[offset : offset + 4] == bytes((64, 0, 191, 64))
    assert actual != canvas_frame(sampler(group).frame(0.5))


def test_complementary_fragments_share_one_glow_before_blur():
    full = replace(
        rectangle(), state=VisualState(position=DEFAULT_POSITION, fill=WHITE)
    )
    left = replace(full, id="left", clip=RectangleClip(0, 0, 45, 90))
    right = replace(full, id="right", clip=RectangleClip(45, 0, 120, 90))
    glow = Glow(RED, blur=4)
    actual = canvas_frame(
        sampler(
            root(left, right), components=("root",), glows={"left": glow, "right": glow}
        ).frame(0.5)
    )
    expected = canvas_frame(sampler(root(full), glows={"shape": glow}).frame(0.5))
    assert actual.rgba == expected.rgba
    assert actual != canvas_frame(
        sampler(root(left, right), glows={"left": glow, "right": glow}).frame(0.5)
    )


def test_component_containers_preserve_exposure_and_opacity_weights():
    node = rectangle()
    wrapper = ObjectGroup(
        id="exposure",
        lifetime=Lifetime(0.2, 0.8),
        children=(node,),
        state=VisualState(opacity=0.5),
    )
    group = root(wrapper, opacity=0.5)
    sample = sampler(group, components=("root",))
    assert sample.frame(0.1) is None
    assert sample.frame(0.9) is None
    assert canvas_frame(sample.frame(0.5)) == native(node, opacity=0.25)
    copied = group.copy(id="copy", delay=2)
    assert canvas_frame(
        sampler(copied, components=("copy",)).frame(2.5)
    ) == canvas_frame(sample.frame(0.5))


def test_component_selection_and_leaf_errors_are_diagnosed_before_rendering():
    calls = []

    def callback(state, progress):
        calls.append(progress)
        return state

    node = replace(
        rectangle(),
        animations=(
            AnimationClip(0, 1, StateFunction(callback, frozenset(("position",)))),
        ),
    )
    inner = ObjectGroup(id="inner", lifetime=LIFETIME, children=(node,))
    group = root(inner)
    for selected, message in (
        (("shape",), "object groups"),
        (("root", "inner"), "cannot nest"),
    ):
        with pytest.raises(ValueError, match=message):
            sampler(group, components=selected)
        assert not calls
    invalid = replace(node, state=replace(node.state, shadow=Vec2(1, 1)))
    with pytest.raises(ValueError, match="shape:.*native blur/shadow"):
        sampler(root(invalid), components=("root",)).frame(0.5)


def test_sibling_components_keep_identity_and_layer_order_when_alphas_match():
    from kara_templater import Color

    red, blue = Color(255, 0, 0), Color(0, 0, 255)
    first = replace(
        rectangle("first"), state=VisualState(position=DEFAULT_POSITION, fill=red)
    )
    second = replace(
        rectangle("second"), state=VisualState(position=DEFAULT_POSITION, fill=blue)
    )
    lower = ObjectGroup(
        id="lower",
        lifetime=LIFETIME,
        children=(first,),
        layer=1,
        state=VisualState(opacity=0.5),
    )
    upper = ObjectGroup(
        id="upper",
        lifetime=LIFETIME,
        children=(second,),
        layer=2,
        state=VisualState(opacity=0.5),
    )
    image = canvas_frame(
        sampler(root(upper, lower, opacity=0.5), components=("lower", "upper")).frame(
            0.5
        )
    )
    offset = (40 * RESOLUTION[0] + 40) * 4
    assert image.rgba[offset : offset + 4] == bytes((85, 0, 170, 96))


def test_dynamic_glow_uses_world_state_and_the_leaf_birth_clock():
    from kara_templater.coverage_animation import GlowFunction

    node = replace(
        rectangle(),
        animations=(AnimationClip(0, 1, Tween(StatePatch(scale=Vec2(1.2, 1.2)))),),
    )
    group = replace(root(node), state=VisualState(scale=Vec2(1.1, 1.1)))

    def animate(state, time):
        return Glow(
            RED if time < 0.5 else BLUE,
            blur=(1 + time) * state.scale.x,
            border=time * state.scale.x,
            opacity=1 - time / 2,
        )

    animation = GlowFunction(animate, max_blur=3, max_border=2, breakpoints=(0.5,))
    dynamic = sampler(group, glows={node.id: animation})
    copied = group.copy(id="later", delay=2)
    delayed = sampler(copied, glows={copied.children[0].id: animation})
    for time in (0.9, 0.1, 0.5, 0.3):
        scale = (1 + 0.2 * time) * 1.1
        expected = Glow(
            RED if time < 0.5 else BLUE,
            blur=(1 + time) * scale,
            border=time * scale,
            opacity=1 - time / 2,
        )
        actual = canvas_frame(dynamic.frame(time))
        assert actual == canvas_frame(
            sampler(group, glows={node.id: expected}).frame(time)
        )
        assert actual == canvas_frame(delayed.frame(time + 2))


def test_dynamic_glow_can_hide_without_removing_fill_or_stroke():
    from kara_templater.coverage_animation import GlowFunction

    node = rectangle()
    animation = GlowFunction(
        lambda state, time: None if time >= 0.5 else Glow(RED, blur=2),
        max_blur=2,
        max_border=0,
        breakpoints=(0.5,),
    )
    dynamic = sampler(root(node), glows={node.id: animation})
    bare = canvas_frame(sampler(root(node)).frame(0.75))
    assert canvas_frame(dynamic.frame(0.75)) == bare
    assert canvas_frame(dynamic.frame(0.25)) != bare
    assert canvas_frame(dynamic.frame(0.75)) == bare


def test_glow_declaration_preflight_and_runtime_bounds_preserve_source():
    from kara_templater import EventOrigin, SourceRef
    from kara_templater.coverage_animation import GlowFunction
    from kara_templater.scene_output import SceneCompileError

    calls = []

    def animate(state, time):
        calls.append(time)
        return Glow(RED, blur=3, border=2)

    origin = EventOrigin((SourceRef("line"),), "test")
    node = replace(rectangle(), origin=origin)
    animation = GlowFunction(animate, max_blur=10, max_border=2)
    with pytest.raises(ValueError, match="pixel"):
        sampler(
            root(node),
            glows={node.id: animation},
            settings=RasterSettings(max_pixels=120 * 90),
        )
    assert not calls
    with pytest.raises(ValueError, match="pixel"):
        sampler(root(node), glows={node.id: replace(animation, max_border=10_000)})
    assert not calls
    with pytest.raises(ValueError, match="breakpoint outside"):
        sampler(root(node), glows={node.id: replace(animation, breakpoints=(2,))})
    assert not calls
    for bounded in (replace(animation, max_blur=2), replace(animation, max_border=1)):
        with pytest.raises(SceneCompileError, match="shape:.*declared") as caught:
            sampler(root(node), glows={node.id: bounded}).frame(0.5)
        assert caught.value.origin == origin


@pytest.mark.parametrize(
    "blur,border,points",
    [(101, 0, ()), (-1, 0, ()), (1, -1, ()), (float("nan"), 0, ()), (1, 0, (-1,))],
)
def test_invalid_glow_function_declarations(blur, border, points):
    from kara_templater.coverage_animation import GlowFunction

    with pytest.raises(ValueError):
        GlowFunction(
            lambda state, time: None,
            max_blur=blur,
            max_border=border,
            breakpoints=points,
        )


def scoped_shapes():
    from kara_templater import Color

    return tuple(
        replace(
            rectangle(identity),
            state=VisualState(position=DEFAULT_POSITION, fill=color, opacity=opacity),
        )
        for identity, color, opacity in (
            ("red", Color(255, 0, 0), 0.5),
            ("blue", Color(0, 0, 255), 0.25),
        )
    )


def center_pixel(sample, time=0.5):
    image = canvas_frame(sample.frame(time))
    offset = (40 * RESOLUTION[0] + 40) * 4
    return image.rgba[offset : offset + 4]


@pytest.mark.parametrize(
    "red_weight,blue_weight,expected",
    [(0.5, 0.5, (153, 0, 102, 80)), (0.75, 0.1, (235, 0, 20, 78))],
)
def test_root_scope_weights_do_not_reveal_occluded_sibling_material(
    red_weight, blue_weight, expected
):
    from kara_templater.coverage_animation import ScopeOpacity

    group = root(*scoped_shapes())
    sample = sampler(
        group,
        scope_opacities={
            "red": (ScopeOpacity("root", lambda time: red_weight),),
            "blue": (ScopeOpacity("root", lambda time: blue_weight),),
        },
    )
    assert center_pixel(sample) == bytes(expected)
    # Applying each root factor directly to the leaf's opacity has different
    # occlusion: the foreground would reveal too much of its sibling.
    individually = tuple(
        replace(node, state=replace(node.state, opacity=node.state.opacity * factor))
        for node, factor in zip(scoped_shapes(), (red_weight, blue_weight), strict=True)
    )
    assert center_pixel(sampler(root(*individually))) != bytes(expected)


def test_two_ancestor_scopes_close_in_order_with_different_target_weights():
    from kara_templater.coverage_animation import ScopeOpacity

    unit = ObjectGroup(id="unit", lifetime=LIFETIME, children=scoped_shapes())
    sample = sampler(
        root(unit),
        scope_opacities={
            "red": (
                ScopeOpacity("unit", lambda time: 0.5),
                ScopeOpacity("root", lambda time: 0.5),
            ),
            "blue": (
                ScopeOpacity("unit", lambda time: 0.25),
                ScopeOpacity("root", lambda time: 1),
            ),
        },
    )
    assert center_pixel(sample) == bytes((153, 0, 102, 40))


def test_component_retains_root_weights_after_its_intrinsic_plane_closes():
    from kara_templater.coverage_animation import ScopeOpacity

    red, blue = scoped_shapes()
    red = replace(red, state=replace(red.state, opacity=0.25))
    blue = replace(blue, state=replace(blue.state, opacity=0.75))
    word = ObjectGroup(id="word", lifetime=LIFETIME, children=(red, blue))
    sample = sampler(
        root(word),
        components=("word",),
        scope_opacities={
            "red": (ScopeOpacity("root", lambda time: 0.5),),
            "blue": (ScopeOpacity("root", lambda time: 0.25),),
        },
    )
    assert center_pixel(sample) == bytes((102, 0, 153, 40))


def test_scope_callback_uses_owner_clock_and_empty_rules_preserve_fast_path():
    from kara_templater.coverage_animation import ScopeOpacity

    node = rectangle()
    group = ObjectGroup(id="owner", lifetime=Lifetime(0.2, 0.8), children=(node,))
    rule = ScopeOpacity("owner", lambda time: time, breakpoints=(0.3,))
    original = sampler(group, scope_opacities={node.id: (rule,)})
    copied = group.copy(id="later", delay=2)
    delayed = sampler(
        copied, scope_opacities={copied.children[0].id: (replace(rule, owner="later"),)}
    )
    for time in (0.7, 0.3, 0.5):
        assert canvas_frame(original.frame(time)) == canvas_frame(
            delayed.frame(time + 2)
        )
    assert center_pixel(original, 0.5)[3] == 77
    assert canvas_frame(
        sampler(root(node), scope_opacities={node.id: ()}).frame(0.5)
    ) == canvas_frame(sampler(root(node)).frame(0.5))


def test_scope_preflight_and_runtime_errors_keep_leaf_identity():
    from kara_templater import EventOrigin, SourceRef
    from kara_templater.coverage_animation import ScopeOpacity
    from kara_templater.scene_output import SceneCompileError

    calls = []

    def value(time):
        calls.append(time)
        return 2

    origin = EventOrigin((SourceRef("lyric"),), "test")
    node = replace(rectangle(), origin=origin)
    rule = ScopeOpacity("root", value)
    for rules, message in (
        ((replace(rule, owner="other"),), "ancestor"),
        ((rule, rule), "duplicate"),
        ((replace(rule, breakpoints=(2,)),), "breakpoints"),
    ):
        with pytest.raises(ValueError, match=message):
            sampler(root(node), scope_opacities={node.id: rules})
        assert not calls
    with pytest.raises(ValueError, match="plane pixel budget"):
        sampler(
            root(node),
            scope_opacities={node.id: (rule,)},
            settings=RasterSettings(max_pixels=120 * 90 * 2),
        )
    assert not calls
    with pytest.raises(SceneCompileError, match="shape:.*0..1") as caught:
        sampler(root(node), scope_opacities={node.id: (rule,)}).frame(0.5)
    assert caught.value.origin == origin


def test_fractional_material_partition_shares_one_pixel_without_hard_clip():
    from kara_templater import Color
    from kara_templater.coverage_animation import CoveragePartition
    from kara_templater.timeline import Region

    before = replace(
        rectangle("before"),
        state=VisualState(
            position=DEFAULT_POSITION, fill=Color(255, 0, 0), opacity=0.4
        ),
    )
    after = replace(
        rectangle("after"),
        state=VisualState(
            position=DEFAULT_POSITION, fill=Color(0, 0, 255), opacity=0.8
        ),
    )
    partition = CoveragePartition(
        lambda state, time: (Region(45.25, 120),), max_regions=1
    )
    sample = sampler(
        root(before, after),
        components=("root",),
        partitions={"before": replace(partition, inside=False), "after": partition},
    )
    image = canvas_frame(sample.frame(0.5))
    offset = (40 * RESOLUTION[0] + 45) * 4
    # Pixel [45, 46): 1/4 red at alpha .4, 3/4 blue at alpha .8.
    assert image.rgba[offset : offset + 4] == bytes((37, 0, 218, 179))


def test_partition_declared_budget_precedes_callbacks_and_bounds_are_enforced():
    from kara_templater.coverage_animation import CoveragePartition
    from kara_templater.timeline import Region

    calls = []

    def regions(state, time):
        calls.append(time)
        return (Region(20, 30), Region(40, 50))

    node = rectangle()
    partition = CoveragePartition(regions, max_regions=1)
    with pytest.raises(ValueError, match="partition band budget"):
        sampler(
            root(node),
            partitions={node.id: partition},
            settings=RasterSettings(max_images=2),
        )
    assert not calls
    with pytest.raises(ValueError, match="shape:.*region bound"):
        sampler(root(node), partitions={node.id: partition}).frame(0.5)


@pytest.mark.parametrize("inverse", [False, True])
@pytest.mark.parametrize("vector", [False, True])
@pytest.mark.parametrize("axis", ["x", "y"])
def test_overscan_keeps_screen_mask_and_material_coordinates(inverse, vector, axis):
    from kara_templater import SoftSweep, VectorClip

    field = SoftSweep(
        left=-20 if axis == "x" else 20,
        right=20 if axis == "x" else 65,
        start=0,
        duration=1,
        fill=(RED, BLUE),
        width=10,
        axis=axis,
    )
    clip = RectangleClip(-10, 20, 15, 65, inverse=inverse)
    if vector:
        clip = VectorClip(
            VectorPath.rectangle(25, 45).map(lambda point: point + Vec2(-10, 20)),
            inverse=inverse,
        )
    node = replace(
        rectangle(),
        state=VisualState(position=Vec2(-20, 30), fill=WHITE),
        clip=clip,
        material=field,
    )
    # An invisible halo still has a real kernel/overscan. Its absence must not
    # shift either the geometry mask or the field's world-coordinate partition.
    actual = canvas_frame(
        sampler(root(node), glows={node.id: Glow(RED, blur=8, opacity=0)}).frame(0.51)
    )
    expected = canvas_frame(sampler(root(node)).frame(0.51))
    assert actual == expected
    # Independent ordinary ASS mask: colored clip strips have extra AA seams,
    # so use the unsplit silhouette to check coverage itself.
    assert (
        actual.rgba[3::4] == native(replace(node, material=None), time=510).rgba[3::4]
    )


def test_overscan_resolves_local_mask_before_affine_canvas_translation():
    node = replace(
        rectangle(),
        state=VisualState(position=Vec2(-10, 30), fill=WHITE),
        clip=RectangleClip(0, 0, 15, 25, space="local"),
    )
    group = replace(
        root(node),
        state=VisualState(scale=Vec2(1.2, 0.8), rotation=10, skew=Vec2(0.15, 0)),
    )
    expected = canvas_frame(sampler(group).frame(0.5))
    actual = canvas_frame(
        sampler(group, glows={node.id: Glow(RED, blur=8, opacity=0)}).frame(0.5)
    )
    assert any(expected.rgba[3::4])
    assert actual == expected
