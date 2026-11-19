from dataclasses import replace

import pytest

from kara_templater import Document, Line, Record, Style
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from kara_templater.geometry import Contour, CubicSegment, Vec2, VectorPath
from kara_templater.scene import (
    Lifetime,
    NativeEvent,
    ObjectGroup,
    PathObject,
    Scene,
    TextObject,
)
from kara_templater.scene_animation import (
    AnimationClip,
    StateFunction,
    StatePatch,
    Timeline,
    Tween,
    VisualState,
)
from kara_templater.scene_output import SceneBudget, SceneCompileError


def document() -> Document:
    return Document(
        [
            "[Script Info]",
            "PlayResX: 640",
            "PlayResY: 360",
            "[V4+ Styles]",
            "Format: " + STYLE_FORMAT,
            Style(),
            "[Events]",
            "Format: " + EVENT_FORMAT,
            Line(text="source", start_time=0, end_time=3000),
            "[Fonts]",
            "fontname: keep",
            "encoded",
        ],
        Record(res_x=640, res_y=360),
    )


def text(**kwargs):
    return TextObject(id="text", lifetime=Lifetime(0, 3), text="hello", **kwargs)


def test_scene_preserves_document_and_reordered_custom_columns():
    doc = document()
    doc.records[7] = "Format: Start, End, Text"
    doc.records[8] = Line(
        text="source",
        start_time=0,
        end_time=3000,
        fields={"Start": "", "End": "", "Text": ""},
    )
    before = doc.dumps()
    scene = Scene(doc).add(text())
    scene.replace_source(8)
    result = scene.compile()
    assert doc.dumps() == before
    assert result.document.lines[0].comment
    assert result.document.dumps().endswith("[Fonts]\nfontname: keep\nencoded\n")
    assert Document.parse(result.document.dumps()).dumps() == result.document.dumps()
    assert result.event_count == 1
    assert result.peak_active == 1


def test_repeat_compile_is_stable_and_removes_only_own_events():
    first = Scene(document()).add(text()).compile()
    second = Scene(first.document).add(text()).compile()
    assert second.document.dumps() == first.document.dumps()
    other = Scene(first.document, owner="another").add(text()).compile()
    assert len(other.document.lines) == 3


def test_native_move_avoids_sampling_and_has_relative_time():
    node = replace(
        text(),
        lifetime=Lifetime(2, 5),
        animations=(AnimationClip(0.5, 1, Tween(StatePatch(position=Vec2(100, 50)))),),
    )
    result = Scene(document()).add(node).compile()
    assert result.event_count == 1
    assert result.objects[0].strategy == "native-move"
    assert (
        r"\move(0,0,100,50,500,1500)"
        in result.document.lines[-1].text
    )


def test_group_transforms_once_and_intersects_lifetimes():
    node = text(state=VisualState(position=Vec2(10, 0)))
    inner = ObjectGroup(
        id="inner",
        lifetime=Lifetime(1, 3),
        state=VisualState(position=Vec2(5, 0)),
        children=(node,),
    )
    outer = ObjectGroup(
        id="outer",
        lifetime=Lifetime(0, 2),
        state=VisualState(
            position=Vec2(100, 50), scale=Vec2(2, 2), rotation=90, opacity=0.5
        ),
        children=(inner,),
    )
    event = Scene(document()).add(outer).compile().document.lines[-1]
    assert (event.start_time, event.end_time) == (1000, 2000)
    assert r"\pos(100,80)" in event.text
    assert r"\frz-90" in event.text
    assert r"\fscx200" in event.text
    assert r"\alpha&H80&" in event.text


def test_identity_and_affine_combination_report():
    with pytest.raises(SceneCompileError, match="duplicate object"):
        Scene(document()).add(text(), text()).compile()
    group = ObjectGroup(
        id="g",
        lifetime=Lifetime(0, 3),
        state=VisualState(scale=Vec2(2, 1)),
        children=(text(state=VisualState(rotation=45)),),
    )
    result = Scene(document()).add(group).compile()
    assert result.objects[0].strategy == "native-static-affine-path"
    assert (result.objects[0].peak_path_points or 0) > 0


def test_timeline_takeover_release_and_random_access():
    timeline = Timeline().play(Tween(StatePatch(position=Vec2(20, 0))), duration=1)
    timeline.play(Tween(StatePatch(position=Vec2(40, 0))), duration=1, hold=False)
    node = text(animations=timeline.clips)
    assert node.at(1.5).position == Vec2(30, 0)
    assert node.at(2.5).position == Vec2(20, 0)
    assert node.at(0.5).position == Vec2(10, 0)
    assert node.at(1.5).position == Vec2(30, 0)


def test_parallel_channels_conflicts_and_declared_writes():
    timeline = Timeline().play(
        Tween(StatePatch(opacity=0)),
        Tween(StatePatch(position=Vec2(10, 0))),
        duration=1,
    )
    node = text(animations=timeline.clips)
    assert node.at(0.5).opacity == 0.5
    assert node.at(0.5).position == Vec2(5, 0)
    with pytest.raises(ValueError, match="overlapping animation"):
        timeline.play(Tween(StatePatch(opacity=0.2)), duration=1, at=0.5)
    function = StateFunction(
        lambda state, t: replace(state, opacity=0.1, rotation=t * 90),
        frozenset(("rotation",)),
    )
    node = text(animations=(AnimationClip(0, 1, function),))
    assert node.at(0.5).rotation == 45
    assert node.at(0.5).opacity == 1


def test_budget_preflight_never_invokes_callback():
    def fail(state: VisualState, progress: float) -> VisualState:
        raise AssertionError("must fail preflight before callbacks")

    node = text(animations=(AnimationClip(0, 3, StateFunction(fail)),))
    with pytest.raises(SceneCompileError, match="estimated event budget"):
        Scene(document()).add(node).compile(budget=SceneBudget(max_events=10))


def test_actual_byte_peak_path_and_quantization_budgets():
    with pytest.raises(SceneCompileError, match="byte budget"):
        Scene(document()).add(text()).compile(budget=SceneBudget(max_bytes=50))
    with pytest.raises(SceneCompileError, match="peak active"):
        Scene(document()).add(text()).compile(budget=SceneBudget(max_active=1))
    path = PathObject(
        id="p", lifetime=Lifetime(0, 1), path=VectorPath.rectangle(50, 50)
    )
    with pytest.raises(SceneCompileError, match="path complexity"):
        Scene(document()).add(path).compile(budget=SceneBudget(max_path_points=3))
    with pytest.raises(SceneCompileError, match="centisecond"):
        Scene(document()).add(replace(text(), lifetime=Lifetime(0, 0.001))).compile()


def test_sampler_merges_constant_states_and_preserves_boundaries():
    node = text(
        animations=(AnimationClip(0.507, 0.123, StateFunction(lambda state, _: state)),)
    )
    result = Scene(document()).add(node).compile()
    assert result.event_count == 1
    assert result.objects[0].strategy == "sampled"
    assert result.objects[0].sample_interval == 0.02


def test_native_event_copies_caller_object():
    event = Line(text=r"{\pos(4,5)}hello", end_time=1000)
    node = NativeEvent("legacy", event)
    result = Scene(document()).add(node).compile()
    assert result.document.lines[-1].text == event.text
    assert event.effect == ""
    assert event.fields == {}


def test_path_cubic_and_contour_winding():
    curve = Contour(
        Vec2(), (CubicSegment(Vec2(0, 10), Vec2(10, 10), Vec2(10, 0)),), False
    )
    assert curve.point(0.5) == Vec2(5, 7.5)
    path = VectorPath((curve,))
    assert path.point_count == 4
    assert path.map(lambda p: p + Vec2(2, 3)).contours[0].point(0.5) == Vec2(7, 10.5)
    assert "b 0.0000 10.0000 10.0000 10.0000 10.0000 0.0000" in path.drawing()


def test_native_effect_and_metadata_survive_recompile():
    event = Line(text="hello", end_time=1000, effect="Banner;30;0;0", actor="singer")
    node = NativeEvent("legacy", event)
    first = Scene(document()).add(node).compile()
    assert first.document.lines[-1].effect == event.effect
    assert first.document.lines[-1].actor == "singer"
    assert first.event_count == 1
    second = Scene(Document.parse(first.document.dumps())).add(node).compile()
    assert second.document.dumps() == first.document.dumps()


def test_copy_translates_entire_animation_and_group_children():
    original = text(
        animations=(AnimationClip(0, 1, Tween(StatePatch(position=Vec2(50, 0)))),)
    )
    copied = original.copy(id="copy", offset=Vec2(100, 0), delay=1)
    assert copied.at(1.5).position == Vec2(125, 0)
    assert copied.at(3).position == Vec2(150, 0)
    group = ObjectGroup(id="group", lifetime=Lifetime(0, 3), children=(original,))
    duplicate = group.copy(id="group2", delay=3)
    assert duplicate.children[0].id == "group2/text"
    assert duplicate.children[0].lifetime == Lifetime(3, 6)
    Scene(document()).add(group, duplicate).compile()


def test_custom_copy_translation_and_actual_sample_interval():
    node = text(
        animations=(
            AnimationClip(
                0,
                3,
                StateFunction(
                    lambda state, p: replace(state, position=Vec2(30 * p, 0)),
                    frozenset(("position",)),
                ),
            ),
        )
    )
    copied = node.copy(id="copy", offset=Vec2(100, 0))
    assert copied.at(1.5).position == Vec2(115, 0)
    result = Scene(document()).add(node).compile(budget=SceneBudget(fps=60))
    assert result.objects[0].sample_interval == 0.02


def test_reordered_without_effect_column_recompiles_without_duplication():
    doc = document()
    doc.records[7] = "Format: Start, End, Text"
    doc.records[8] = Line(
        text="source",
        start_time=0,
        end_time=3000,
        fields={"Start": "", "End": "", "Text": ""},
    )
    first = Scene(doc).add(text()).compile()
    second = Scene(Document.parse(first.document.dumps())).add(text()).compile()
    assert second.document.dumps() == first.document.dumps()


def test_sampling_budget_uses_only_known_changing_intervals():
    node = TextObject(
        id="brief",
        text="brief",
        lifetime=Lifetime(0, 60),
        animations=(AnimationClip(1, 0.5, Tween(StatePatch(opacity=0.5))),),
    )
    result = Scene(document()).add(node).compile(budget=SceneBudget(max_events=100))
    assert result.estimated_events < 100
    assert result.objects[0].sample_interval == 0.02
    assert any(
        line.start_time == 1500 and line.end_time == 60000
        for line in result.document.lines
        if not line.comment
    )


def test_unknown_geometry_callbacks_still_budget_the_full_lifetime():
    from kara_templater import PathFunction

    node = PathObject(
        id="unbounded-time",
        lifetime=Lifetime(0, 60),
        path=VectorPath.rectangle(10, 10),
        deform=PathFunction(lambda path, time: path, max_points=5, breakpoints=(1, 2)),
    )
    with pytest.raises(SceneCompileError, match="estimated event budget"):
        Scene(document()).add(node).compile(budget=SceneBudget(max_events=100))


def test_identity_organization_group_preserves_native_move_and_paint_budget():
    from dataclasses import replace

    from kara_templater import (
        CYAN,
        PINK,
        AnimationClip,
        ColorRamp,
        ColorStop,
        Document,
        Lifetime,
        LinearGradient,
        ObjectGroup,
        Scene,
        SceneBudget,
        StatePatch,
        TextObject,
        Tween,
        Vec2,
    )

    node = TextObject(
        id="text",
        text="MOVE",
        lifetime=Lifetime(0, 5),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(0, CYAN), ColorStop(640, PINK)))
        ),
        animations=(AnimationClip(0, 5, Tween(StatePatch(position=Vec2(100, 0)))),),
    )
    budget = SceneBudget(max_events=1000)
    direct = Scene(Document.create()).add(node).compile(budget=budget)
    parent = ObjectGroup(id="organization", lifetime=Lifetime(0, 5), children=(node,))
    grouped = Scene(Document.create()).add(parent).compile(budget=budget)
    assert grouped.estimated_events == direct.estimated_events
    assert grouped.event_count == direct.event_count
    assert [line.text for line in grouped.document.lines if not line.comment] == [
        line.text for line in direct.document.lines if not line.comment
    ]
    # A moving parent still needs joint evaluation and cannot use this shortcut.
    moving = replace(
        parent,
        animations=(AnimationClip(0, 5, Tween(StatePatch(position=Vec2(0, 20)))),),
    )
    with pytest.raises(SceneCompileError, match="budget"):
        Scene(Document.create()).add(moving).compile(budget=budget)


def test_identity_group_that_crops_birth_does_not_restart_native_move_clock():
    node = TextObject(
        id="move",
        text="MOVE",
        lifetime=Lifetime(0, 5),
        animations=(AnimationClip(0, 5, Tween(StatePatch(position=Vec2(100, 0)))),),
    )
    group = ObjectGroup(id="late", lifetime=Lifetime(1, 4), children=(node,))
    result = Scene(Document.create()).add(group).compile()
    assert result.objects[0].strategy == "sampled"
    first = next(line for line in result.document.lines if not line.comment)
    assert first.start_time == 1000
    assert r"\pos(20.2,0)" in first.text


def test_song_offset_copy_keeps_half_grid_boundaries_and_alpha_identical():
    node = TextObject(
        id="original",
        text="A",
        lifetime=Lifetime(0.025, 1.025),
        state=VisualState(opacity=0),
        animations=(AnimationClip(0.04, 0.5, Tween(StatePatch(opacity=1))),),
    )
    scene = Scene(Document.create()).add(node, node.copy(id="later", delay=72))
    result = scene.compile()
    early = [
        (line.start_time, line.end_time, line.text)
        for line in result.document.lines
        if not line.comment and line.start_time < 72000
    ]
    late = [
        (line.start_time - 72000, line.end_time - 72000, line.text)
        for line in result.document.lines
        if not line.comment and line.start_time >= 72000
    ]
    assert early == late
    for time in (0.025, 0.065, 0.315, 0.565, 0.995):
        assert node.at(time) == node.copy(id="copy", delay=144).at(time + 144)


def test_sampled_callback_failure_preserves_origin_time_and_original_cause():
    from kara_templater import EventOrigin, SourceRef

    origin = EventOrigin((SourceRef("line", 1, 2),), "custom", ("echo",))
    failure = RuntimeError("broken property")
    calls = []

    def fail(state, progress):
        calls.append(progress)
        raise failure

    node = text(
        origin=origin,
        animations=(AnimationClip(0, 3, StateFunction(fail)),),
    )
    scene = Scene(document()).add(node)
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=SceneBudget(max_events=1))
    assert not calls
    with pytest.raises(SceneCompileError, match="sample at 0.010000s") as caught:
        scene.compile()
    assert caught.value.object_id == node.id
    assert caught.value.origin == origin
    cause: BaseException = caught.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert cause is failure
    assert calls == [pytest.approx(0.01 / 3)]


def test_event_merging_keeps_sampling_callbacks_and_visibility_gaps():
    calls = []

    def constant(state, progress):
        calls.append(progress)
        return replace(state, opacity=0.5)

    node = replace(
        text(),
        lifetime=Lifetime(0, 0.12),
        animations=(AnimationClip(0, 0.12, StateFunction(constant)),),
    )
    result = Scene(Document.create()).add(node).compile()
    assert calls == pytest.approx(
        [t / 0.12 for t in (0.01, 0.03, 0.05, 0.07, 0.09, 0.11)]
    )
    assert result.event_count == 1
    events = [e for e in result.document.lines if not e.comment]
    assert [(e.start_time, e.end_time) for e in events] == [(0, 120)]

    def interrupted(state, progress):
        return replace(state, opacity=0 if 1 / 3 <= progress < 2 / 3 else 0.5)

    changed = replace(
        node,
        animations=(
            AnimationClip(
                0, 0.12, StateFunction(interrupted), breakpoints=(0.04, 0.08)
            ),
        ),
    )
    output = Scene(Document.create()).add(changed).compile()
    visible = [
        event
        for event in output.document.lines
        if not event.comment and r"\alpha&HFF&" not in event.text
    ]
    assert [(e.start_time, e.end_time) for e in visible] == [(0, 40), (80, 120)]
    assert (
        output.document.dumps()
        == Scene(Document.create()).add(changed).compile().document.dumps()
    )


def test_sub_alpha_precision_changes_merge_only_after_all_samples_are_evaluated():
    calls = []

    def nearly_constant(state, progress):
        value = 0.5 + progress * 1e-10
        calls.append(value)
        return replace(state, opacity=value)

    node = replace(
        text(),
        lifetime=Lifetime(0, 0.12),
        animations=(AnimationClip(0, 0.12, StateFunction(nearly_constant)),),
    )
    result = Scene(Document.create()).add(node).compile()
    assert len(calls) == len(set(calls)) == 6
    # Distinct float states have identical serialized ASS alpha; merging is exact
    # at the output representation, without skipping callback samples.
    assert result.event_count == 1


def test_invalid_state_callback_reports_target_and_sample_time():
    invalid = StateFunction(lambda state, p: None)  # ty: ignore[invalid-argument-type]
    scene = Scene(Document.create()).add(
        text(animations=(AnimationClip(0, 3, invalid),))
    )
    with pytest.raises(
        SceneCompileError, match="sample at 0.010000s.*must return VisualState"
    ) as caught:
        scene.compile()
    assert caught.value.object_id == "text"


def test_native_empty_negative_intervals_and_budget():
    scene = Scene(Document.create()).add(
        NativeEvent("empty", Line(start_time=0, end_time=0, text="empty")),
        NativeEvent("negative", Line(start_time=-100, end_time=100, text="prelude")),
    )
    result = scene.compile()
    assert result.event_count == 2
    assert any(line.start_time == -100 for line in result.document.lines)
    assert all(
        line.start_time >= 0 for line in Document.parse(result.document.dumps()).lines
    )
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=SceneBudget(max_events=1))


def test_native_event_with_missing_effect_column():
    plain = Document.parse(
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style().serialize()
        + "\n[Events]\nFormat: Start, End, Text\nDialogue: 0:00:00.00,0:00:01.00,kept\n"
    )
    compiled = (
        Scene(plain)
        .add(NativeEvent("native", Line(text="added", end_time=1000)))
        .compile()
    )
    assert len(Document.parse(compiled.document.dumps()).lines) == 3
