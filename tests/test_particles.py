from dataclasses import replace
from itertools import repeat

import pytest

from kara_templater import (
    AnimationClip,
    Contour,
    Document,
    Emission,
    EventOrigin,
    Lifetime,
    LineSegment,
    MoveAlong,
    ObjectGroup,
    ParticleContext,
    PathFunction,
    PathObject,
    Scene,
    SourceRef,
    StateFunction,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
    emit_particles,
    flatten,
)
from kara_templater.geometry import CubicSegment


def make_particle(context: ParticleContext) -> PathObject:
    return PathObject(
        id=context.id,
        lifetime=Lifetime(context.birth, context.birth + 1),
        path=VectorPath.rectangle(2, 2),
        state=VisualState(
            position=context.position
            + Vec2(context.uniform("x", -20, 20), context.uniform("y", -20, 20))
        ),
    )


def test_keyed_random_is_independent_of_order_and_unrelated_parameters():
    ctx = ParticleContext("snow/a", 1, 17, Vec2(), None)
    x = ctx.uniform("x")
    ctx.uniform("other")
    assert ctx.uniform("x") == x
    assert replace(ctx, seed=18).uniform("x") != x
    assert ctx.choose("shape", ("a", "b", "c")) in ("a", "b", "c")
    schedule = (Emission("a", 1), Emission("b", 2))
    first = emit_particles(schedule, make_particle, seed=17)
    second = emit_particles(reversed(schedule), make_particle, seed=17)
    assert {node.id: node.state for node in first} == {
        node.id: node.state for node in second
    }
    third = emit_particles((*schedule, Emission("c", 0)), make_particle, seed=17)
    assert third[:2] == first


def test_generation_budget_precedes_callbacks_and_detects_duplicate_ids():
    def fail(context: ParticleContext) -> PathObject:
        raise AssertionError("factory must not run")

    with pytest.raises(ValueError, match="budget"):
        emit_particles((Emission(str(i), i) for i in range(4)), fail, max_particles=3)
    with pytest.raises(ValueError, match="duplicate"):
        emit_particles(repeat(Emission("same", 0), 3), fail)
    with pytest.raises(ValueError, match="preserve id"):
        emit_particles(
            (Emission("a", 1),), lambda ctx: replace(make_particle(ctx), id="wrong")
        )


def test_capture_and_continuous_emitter_have_explicit_distinct_times():
    seen: list[ParticleContext] = []

    def build(ctx: ParticleContext) -> PathObject:
        seen.append(ctx)
        return make_particle(ctx)

    origin = EventOrigin((SourceRef("line", 0),), "emit")
    nodes = emit_particles(
        (Emission("a", 2),),
        build,
        emitter=lambda time: Vec2(time * 10, 0),
        origin=origin,
    )
    assert seen[0].position == Vec2(20, 0)
    assert seen[0].position_at(1) == Vec2(30, 0)
    assert nodes[0].origin == origin
    assert nodes[0].lifetime == Lifetime(2, 3)


def test_move_along_native_linear_and_curve_tangent():
    line = Contour(Vec2(), (LineSegment(Vec2(100, 0)),), False)
    motion = MoveAlong(line)
    assert motion.native_linear
    node = PathObject(
        id="p",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(2, 2),
        animations=(AnimationClip(0, 2, motion),),
    )
    result = Scene(Document.create()).add(node).ass.compile()
    assert result.event_count == 1
    assert result.objects[0].strategy == "native-move"
    assert node.at(1).position == Vec2(50, 0)
    curved = Contour(
        Vec2(), (CubicSegment(Vec2(0, 100), Vec2(100, 100), Vec2(100, 0)),), False
    )
    follow = MoveAlong(flatten(curved), orient=True)
    state = follow.sample(VisualState(position=Vec2(20, 30)), 0.5)
    assert state.position.x == pytest.approx(70)
    assert state.position.y == pytest.approx(105)
    assert state.rotation == pytest.approx(0, abs=0.001)
    assert not follow.native_linear


def test_echoes_sample_past_state_and_geometry_and_keep_independent_lives():
    base = VectorPath.rectangle(10, 10)
    node = PathObject(
        id="source",
        lifetime=Lifetime(1, 3),
        path=base,
        animations=(
            AnimationClip(0, 2, Tween(StatePatch(position=Vec2(100, 0), opacity=0.2))),
        ),
        deform=PathFunction(lambda p, t: p.map(lambda v: v * (1 + t)), max_points=4),
    )
    copies = echoes(node, count=2, spacing=0.1, opacity=0.5, decay=0.5)
    assert copies[0].lifetime == Lifetime(1.1, 3.1)
    assert copies[1].lifetime == Lifetime(1.2, 3.2)
    assert copies[0].at(2.1).position.x == pytest.approx(node.at(2).position.x)
    assert copies[0].at(2.1).opacity == pytest.approx(node.at(2).opacity * 0.5)
    assert copies[1].at(2.2).opacity == pytest.approx(node.at(2).opacity * 0.25)
    assert copies[0].path_at(2.1) == node.path_at(2)
    assert copies[1].layer == node.layer - 2
    assert copies[0].at(1.6).position.x == pytest.approx(node.at(1.5).position.x)


def test_echo_group_delays_parent_and_children_once():
    child = PathObject(
        id="child",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(2, 2),
        animations=(AnimationClip(0, 2, Tween(StatePatch(position=Vec2(20, 0)))),),
    )
    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 2),
        children=(child,),
        animations=(AnimationClip(0, 2, Tween(StatePatch(position=Vec2(100, 0)))),),
    )
    copy = echoes(group, count=1, spacing=0.5)[0]
    assert copy.at(1.5).position == group.at(1).position
    assert copy.children[0].at(1.5).position == child.at(1).position
    assert copy.children[0].id != child.id
    with pytest.raises(ValueError, match="before copying"):
        echoes(group, count=3, max_objects=5)


def test_split_geometry_has_local_moving_cells_and_preserves_sources():
    from kara_templater import path_bounds, split_path

    origin = EventOrigin((SourceRef("word"),), "pieces")
    node = PathObject(
        id="word",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(100, 60),
        origin=origin,
    )
    pieces = split_path(node, columns=2, rows=3)
    assert len(pieces) == 6
    assert all(p.origin is origin and p.clip is None for p in pieces)
    assert [path_bounds(p.path).width for p in pieces] == [50] * 6
    assert [path_bounds(p.path).height for p in pieces] == [20] * 6
    assert pieces[1].id == "word/cell:0:1"
    with pytest.raises(ValueError, match="before subdivision"):
        split_path(node, columns=100, rows=100)
    with pytest.raises(ValueError, match="static"):
        split_path(
            replace(node, deform=PathFunction(lambda p, t: p, max_points=4)),
            columns=2,
            rows=2,
        )


def test_curve_layout_preserves_grouped_annotation_and_local_animation():
    from kara_templater import PathItem, Polyline, TextObject, layout_path

    body = TextObject(
        id="body",
        lifetime=Lifetime(0, 2),
        text="A",
        state=VisualState(position=Vec2(10, 20)),
    )
    ruby = TextObject(
        id="ruby",
        lifetime=Lifetime(0, 2),
        text="a",
        state=VisualState(position=Vec2(10, 0)),
    )
    group = ObjectGroup(
        id="syllable",
        lifetime=Lifetime(0, 2),
        children=(body, ruby),
        animations=(AnimationClip(0, 2, Tween(StatePatch(scale=Vec2(2, 2)))),),
    )
    placed = layout_path((PathItem(group, 50),), Polyline((Vec2(), Vec2(100, 100))))
    wrapper = placed.children[0]
    assert wrapper.state.position == Vec2(50, 50)
    assert wrapper.state.rotation == pytest.approx(45)
    assert isinstance(wrapper, ObjectGroup)
    inner = wrapper.children[0]
    assert isinstance(inner, ObjectGroup)
    assert inner.children == group.children
    assert inner.at(1).scale == Vec2(1.5, 1.5)
    with pytest.raises(ValueError, match="budget"):
        layout_path(
            (PathItem(group, 50), PathItem(group, 50)),
            Polyline((Vec2(), Vec2(100, 0))),
            max_items=1,
        )


def test_closed_motion_includes_the_implicit_closing_edge():
    path = VectorPath.rectangle(100, 100).contours[0]
    assert path.point(1) == Vec2()
    assert path.point(0.875) == Vec2(0, 50)


def test_keyed_noise_animates_common_objects_without_seek_order_state():
    def factory(context: ParticleContext) -> PathObject:
        phase = context.uniform("phase")

        def jitter(state: VisualState, progress: float) -> VisualState:
            return replace(
                state,
                position=Vec2(context.uniform(f"x/{progress:.8f}"), phase),
            )

        return make_particle(context).animate(
            StateFunction(jitter, frozenset(("position",))), duration=1
        )

    schedule = (Emission("one", 0), Emission("two", 0))
    nodes = emit_particles(schedule, factory, seed=123)
    repeated = emit_particles(reversed(schedule), factory, seed=123)
    by_id = {node.id: node for node in repeated}
    different = emit_particles(schedule, factory, seed=124)
    first = nodes[0].at(0.1)
    for time in (0.7, 0.1, 0.5, 0.1):
        for node in nodes:
            assert node.at(time) == by_id[node.id].at(time)
            assert node.at(time).position.y == node.at(0).position.y
    assert nodes[0].at(0.1) == first
    assert nodes[0].at(0.7).position.x != first.position.x
    assert different[0].at(0.1).position != first.position
    assert nodes[1].at(0.1).position != first.position
