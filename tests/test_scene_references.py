from dataclasses import replace

import pytest

from kara_templater import (
    AnimationClip,
    Document,
    FollowObject,
    Lifetime,
    ObjectGroup,
    ReferenceFunction,
    Scene,
    SceneCompileError,
    SceneReferenceError,
    StateFunction,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
)


def text(id, **kwargs):
    return TextObject(id=id, text=id, lifetime=Lifetime(0, 3), **kwargs)


def target():
    return text(
        "target",
        animations=(AnimationClip(0, 2, Tween(StatePatch(position=Vec2(200, 0)))),),
    )


def test_world_reference_is_independent_of_order_parent_and_seek_history():
    parent = ObjectGroup(
        id="parent",
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(30, 20)),
        children=(target(),),
    )
    follower = text(
        "follower", reference=FollowObject("target", offset=Vec2(5, 10), delay=0.5)
    )
    other = ObjectGroup(
        id="other",
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(1000, 1000)),
        children=(follower,),
    )
    scene = Scene(Document.create()).add(other, parent)
    evaluator = scene.evaluator()
    for t in (2, 0, 1, 0.5, 2):
        assert evaluator.at("follower", t).position == Vec2(
            30 + 100 * max(0, t - 0.5) + 5, 30
        )
    assert evaluator.at("follower", 1).opacity == 1


def test_missing_and_cyclic_references_fail_before_callbacks():
    def forbidden(state, progress):
        pytest.fail("graph validation must precede callbacks")

    a = text(
        "a",
        reference=FollowObject("b"),
        animations=(
            AnimationClip(0, 1, StateFunction(forbidden, frozenset(("opacity",)))),
        ),
    )
    with pytest.raises(SceneCompileError, match="missing visual dependency"):
        Scene(Document.create()).add(a).compile()
    b = text("b", reference=FollowObject("a", delay=1))
    with pytest.raises(SceneCompileError, match="dependency cycle"):
        Scene(Document.create()).add(a, b).compile()
    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 3),
        reference=FollowObject("child"),
        children=(text("child"),),
    )
    with pytest.raises(SceneCompileError, match="dependency cycle"):
        Scene(Document.create()).add(group).compile()


def test_custom_reference_declares_inputs_channels_and_breakpoints():
    def middle(base, time, lookup):
        a, b = lookup("a", time), lookup("b", time)
        return replace(base, position=a.position.lerp(b.position, 0.5))

    reference = ReferenceFunction(
        middle, ("a", "b"), frozenset(("position",)), (0.337,)
    )
    scene = Scene(Document.create()).add(
        text("a"),
        text("b", state=VisualState(position=Vec2(100, 100))),
        text("middle", reference=reference),
    )
    assert scene.evaluator().at("middle", 0.7).position == Vec2(50, 50)
    assert 0.337 in scene.evaluator().breakpoints("middle")
    bad = replace(reference, dependencies=("a",))
    with pytest.raises(SceneReferenceError, match="undeclared dependency"):
        Scene(Document.create()).add(
            text("a"), text("middle", reference=bad)
        ).evaluator().at("middle", 1)
    bad_channel = ReferenceFunction(
        lambda base, t, get: replace(base, opacity=0.2),
        ("a",),
        frozenset(("position",)),
    )
    with pytest.raises(SceneReferenceError, match="undeclared channel"):
        Scene(Document.create()).add(
            text("a"), text("bad", reference=bad_channel)
        ).evaluator().at("bad", 1)


def test_selected_channels_cannot_conflict_with_local_animation():
    with pytest.raises(ValueError, match="same channel"):
        text(
            "f",
            reference=FollowObject("t"),
            animations=(AnimationClip(0, 1, Tween(StatePatch(position=Vec2(10, 10)))),),
        )


def test_external_reference_copy_preserves_past_state_and_offset():
    follower = text(
        "f", reference=FollowObject("target", offset=Vec2(10, 0), delay=0.2)
    )
    copied = follower.copy(id="copy", delay=1, offset=Vec2(20, 0))
    evaluator = Scene(Document.create()).add(target(), follower, copied).evaluator()
    assert evaluator.at("copy", 2).position == evaluator.at("f", 1).position + Vec2(
        20, 0
    )


@pytest.mark.parametrize("new_id", ["group", "copy"])
def test_nested_group_copy_retargets_internal_history_exactly_once(new_id):
    inside = ObjectGroup(
        id="inside",
        lifetime=Lifetime(0, 3),
        children=(target(), text("f", reference=FollowObject("target", delay=0.2))),
    )
    original = ObjectGroup(id="group", lifetime=Lifetime(0, 3), children=(inside,))
    copied = original.copy(id=new_id, delay=1)
    inner = copied.children[0]
    assert isinstance(inner, ObjectGroup)
    follower = inner.children[1]
    assert isinstance(follower.reference, FollowObject)
    assert follower.reference.target == inner.children[0].id
    assert follower.reference.delay == pytest.approx(0.2)
    before = Scene(Document.create()).add(original).evaluator().at("f", 1)
    after = Scene(Document.create()).add(copied).evaluator().at(follower.id, 2)
    assert after == before


def test_delayed_target_discontinuities_reach_output_grid():
    jump = StateFunction(
        lambda state, p: replace(state, position=Vec2(100, 0)), frozenset(("position",))
    )
    leader = text("target", animations=(AnimationClip(0.337, 0.01, jump),))
    scene = Scene(Document.create()).add(
        leader, text("follow", reference=FollowObject("target", delay=0.2))
    )
    assert 0.537 in scene.evaluator().breakpoints("follow")


def test_custom_reference_copy_and_internal_retarget_preserve_clock():
    def follow(base, time, get):
        return replace(base, position=base.position + get("target", time).position)

    follower = text(
        "f",
        state=VisualState(position=Vec2(10, 0)),
        reference=ReferenceFunction(follow, ("target",), frozenset(("position",))),
    )
    copied = follower.copy(id="copied", delay=1, offset=Vec2(20, 0))
    evaluator = Scene(Document.create()).add(target(), follower, copied).evaluator()
    assert evaluator.at("copied", 2).position == evaluator.at("f", 1).position + Vec2(
        20, 0
    )
    group = ObjectGroup(
        id="group", lifetime=Lifetime(0, 3), children=(target(), follower)
    )
    duplicate = group.copy(id="other", delay=1)
    after = Scene(Document.create()).add(duplicate).evaluator().at("other/f", 2)
    assert after == Scene(Document.create()).add(group).evaluator().at("f", 1)


def test_echoes_preserve_reference_history_and_dim_referenced_opacity():
    from kara_templater import echoes

    follower = text(
        "f",
        reference=FollowObject("target", channels=frozenset(("position", "opacity"))),
    )
    ghost = echoes(follower, count=1, spacing=0.2, opacity=0.4)[0]
    evaluator = Scene(Document.create()).add(target(), follower, ghost).evaluator()
    assert evaluator.at(ghost.id, 1.2).position == evaluator.at("f", 1).position
    assert evaluator.at(ghost.id, 1.2).opacity == 0.4


def test_repeated_reference_lookup_shares_one_state_within_a_seek():
    calls = []

    def motion(base, progress):
        calls.append(progress)
        return replace(base, position=Vec2(7, 3))

    def double_lookup(base, time, lookup):
        first = lookup("source", time)
        assert lookup("source", time) is first
        return replace(base, position=first.position)

    scene = Scene(Document.create()).add(
        text("source", animations=(AnimationClip(0, 3, StateFunction(motion)),)),
        text(
            "copy",
            reference=ReferenceFunction(
                double_lookup, ("source",), frozenset(("position",))
            ),
        ),
    )
    evaluator = scene.evaluator()
    assert not calls
    assert evaluator.at("copy", 0.3).position == Vec2(7, 3)
    assert calls == [pytest.approx(0.1)]
