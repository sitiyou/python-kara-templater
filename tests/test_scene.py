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
    with pytest.raises(SceneCompileError, match="frame sampling"):
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


def test_custom_copy_translation():
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


def test_native_tween_spans_the_long_final_hold():
    node = TextObject(
        id="brief",
        text="brief",
        lifetime=Lifetime(0, 60),
        animations=(AnimationClip(1, 0.5, Tween(StatePatch(opacity=0.5))),),
    )
    result = Scene(document()).add(node).compile(budget=SceneBudget(max_events=100))
    assert result.estimated_events < 100
    assert result.objects[0].sample_interval is None
    assert any(
        line.start_time == 0 and line.end_time == 60000
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
    with pytest.raises(SceneCompileError, match="frame sampling"):
        Scene(document()).add(node).compile(budget=SceneBudget(max_events=100))


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
