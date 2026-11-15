"""Track preparation, mixed scenes and ownership across both output entrances."""

from dataclasses import replace

import pytest

from kara_templater import (
    CYAN,
    PINK,
    Animate,
    Body,
    Document,
    Lifetime,
    Line,
    LineMatch,
    NativeEvent,
    On,
    OutputSettings,
    Overlay,
    PaintStyle,
    RasterSettings,
    SceneBudget,
    SceneCompileError,
    Style,
    Syllable,
    TextObject,
    TextStyle,
    Track,
    Vec2,
    VisualState,
    prepare_karaoke,
    render_karaoke,
)
from kara_templater._raster import rasterize


def source():
    doc = Document.create(
        width=320,
        height=240,
        styles=(Style(fontname="DejaVu Sans", fontsize=20, align=5, shadow=0),),
    )
    doc.records.append(Line(text=r"{\k20}AB", start_time=0, end_time=400))
    return doc


def track(**kwargs):
    return Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=CYAN)),
        overlay=Overlay(style=PaintStyle(fill=PINK)),
        **kwargs,
    )


@pytest.mark.parametrize("raster", [False, True])
def test_prepared_tracks_preserve_native_and_raster_playback(raster):
    doc = source()
    before = doc.dumps()
    settings = OutputSettings(
        resolution=(320, 240),
        raster=RasterSettings() if raster else None,
    )
    prepared = prepare_karaoke(doc, tracks=(track(),), settings=settings)
    assert doc.dumps() == before
    assert prepared.scene.objects
    assert all(isinstance(node, NativeEvent) for node in prepared.scene.objects)
    assert all(node.origin is not None for node in prepared.scene.objects)
    old = render_karaoke(doc, tracks=(track(),), settings=settings)
    new = prepared.scene.compile()
    assert new.event_count == old.event_count
    assert prepared.layer_count == old.layer_count
    assert prepared.diagnostics == old.diagnostics
    for time in (0, 100, 200, 390):
        assert (
            rasterize(new.document.dumps(), time, (320, 240)).rgba
            == rasterize(old.document.dumps(), time, (320, 240)).rgba
        )
    # Shared output must keep unknown sections, and must not mutate prepared events.
    prepared.scene.document.records.extend(("[Fonts]", "fontname: retained"))
    snapshot = prepared.scene.document.dumps()
    assert "fontname: retained" in prepared.scene.compile().document.dumps()
    assert prepared.scene.document.dumps() == snapshot


def test_mixed_output_regenerates_without_stale_provenance_or_other_owner_loss():
    scene = prepare_karaoke(source(), tracks=(track(),), owner="song").scene
    scene.add(
        TextObject(
            id="caption",
            text="caption",
            lifetime=Lifetime(0, 0.4),
            state=VisualState(position=Vec2(20, 20)),
        )
    )
    output = scene.compile().document
    other = Line(text="other owner", effect="karaoke:v1:other:0", end_time=400)
    output.records.append(other)
    repeat = prepare_karaoke(output, tracks=(track(),), owner="song").scene.compile()
    assert not any(line.text.endswith("caption") for line in repeat.document.lines)
    assert any(line.effect == other.effect for line in repeat.document.lines)
    # Switching back to the historical entrance also consumes scene provenance pairs.
    old = render_karaoke(output, tracks=(track(),), owner="song")
    assert not any(
        line.text == "kara native event follows" for line in old.document.lines
    )
    assert not any(
        line.effect.startswith("kara:scene:v1:karaoke%3Asong:")
        for line in old.document.lines
    )
    assert old.event_count == repeat.event_count
    restored = prepare_karaoke(repeat.document, tracks=(), owner="song").scene.compile()
    assert any(
        not line.comment and line.text == r"{\k20}AB"
        for line in restored.document.lines
    )


def test_preparation_evaluates_callbacks_once_and_scene_adds_combined_budgets():
    calls = []

    def rate(progress):
        calls.append(progress)
        return progress

    config = track(
        animations=(On(Syllable.Singing, Animate(scale=(1, 1.2), rate=rate)),)
    )
    estimates = []
    prepared = prepare_karaoke(source(), tracks=(config,), on_estimate=estimates.append)
    assert calls and len(estimates) == 1
    count = len(calls)
    scene = prepared.scene
    output = scene.compile()
    assert count == len(calls)
    assert output.document.dumps() == scene.compile().document.dumps()
    assert count == len(calls)
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=SceneBudget(max_events=1))
    with pytest.raises(SceneCompileError, match="byte budget"):
        scene.compile(budget=SceneBudget(max_bytes=100))
    scene.add(TextObject(id="extra", text="X", lifetime=Lifetime(0, 0.4)))
    with pytest.raises(SceneCompileError, match="peak active"):
        scene.compile(budget=SceneBudget(max_active=1))
    assert count == len(calls)


def test_scene_generated_karaoke_text_is_not_imported_as_a_new_source():
    doc = source()
    doc.records.append(
        Line(
            text=r"{\k20}not a source",
            effect="kara:scene:v1:other:object",
            end_time=400,
        )
    )
    result = prepare_karaoke(doc, tracks=(track(),))
    expected = prepare_karaoke(source(), tracks=(track(),))
    assert len(result.scene.objects) == len(expected.scene.objects)
    assert any(
        line.text == r"{\k20}not a source" for line in result.scene.document.lines
    )


def test_corrupt_owned_native_marker_is_diagnosed_before_track_callbacks():
    prepared = prepare_karaoke(source(), tracks=(track(),))
    output = prepared.scene.compile().document
    marker = next(
        line for line in output.lines if line.text == "kara native event follows"
    )
    index = output.records.index(marker)
    output.records[index + 1] = replace(marker)
    with pytest.raises(SceneCompileError, match="damaged native-event provenance"):
        prepare_karaoke(output, tracks=(track(),))


def test_editable_tracks_document_input_ownership_and_repeat_generation():
    from kara_templater import ObjectGroup, prepare_track_scene

    document = source()
    original = document.dumps()
    prepared = prepare_track_scene(document, tracks=(track(),), owner="editable")
    assert document.dumps() == original
    assert prepared.scene.objects
    assert all(isinstance(node, ObjectGroup) for node in prepared.scene.objects)
    first = prepared.scene.compile()
    parsed = prepare_track_scene(
        Document.parse(original), tracks=(track(),), owner="editable"
    )
    assert parsed.scene.compile().document.dumps() == first.document.dumps()
    repeated = prepare_track_scene(first.document, tracks=(track(),), owner="editable")
    assert repeated.scene.compile().document.dumps() == first.document.dumps()
    # Both frontends consume the same source ownership and remove stale output.
    legacy = prepare_karaoke(first.document, tracks=(track(),), owner="editable")
    switched_back = prepare_track_scene(
        legacy.scene.compile().document, tracks=(track(),), owner="editable"
    )
    assert switched_back.scene.compile().document.dumps() == first.document.dumps()


def test_editable_tracks_callbacks_wait_for_scene_budget_and_are_seekable():
    from kara_templater import prepare_track_scene

    calls = []

    def rate(progress):
        calls.append(progress)
        return progress * progress

    configured = track(
        animations=(On(Syllable.Singing, Animate(scale=(1, 1.2), rate=rate)),)
    )
    prepared = prepare_track_scene(source(), tracks=(configured,))
    assert not calls
    with pytest.raises(SceneCompileError, match="budget"):
        prepared.scene.compile(budget=SceneBudget(max_events=1))
    assert not calls
    first = prepared.scene.compile().document.dumps()
    assert calls
    assert prepared.scene.compile().document.dumps() == first
    with pytest.raises(ValueError, match="object budget|layers|regions"):
        prepare_track_scene(source(), tracks=(configured,), max_objects=1)


def test_editable_track_groups_can_be_transformed_and_keep_diagnostics():
    from kara_templater import Blur, ObjectGroup, prepare_track_scene

    configured = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=CYAN)),
        overlay=Overlay(
            style=PaintStyle(fill=PINK, blur=Blur(color=PINK, radius=3, width=4))
        ),
    )
    prepared = prepare_track_scene(source(), tracks=(configured,))
    assert any("hard-clips" in message for message in prepared.diagnostics)
    assert any("per drawing layer" in message for message in prepared.diagnostics)
    group = prepared.scene.objects[0]
    assert isinstance(group, ObjectGroup)
    prepared.scene.objects[0] = replace(group, state=VisualState(position=Vec2(0, -20)))
    assert prepared.scene.compile().event_count > 0
    assert all(
        node.origin is not None
        for node in group.children
        if isinstance(node, TextObject)
    )


def test_editable_trackgroup_allocates_rows_and_restores_unselected_sources():
    from kara_templater import DoubleLine, ObjectGroup, TrackGroup, prepare_track_scene

    document = source()
    document.records.append(
        Line(text=r"{\k20}CD", start_time=0, end_time=400, actor="second")
    )
    grouped = TrackGroup(
        Track(source=LineMatch()), layout=DoubleLine(position=(60, 80), gap=50)
    )
    prepared = prepare_track_scene(document, tracks=(grouped,))
    assert len(prepared.scene.objects) == 2
    groups = prepared.scene.objects
    assert all(isinstance(group, ObjectGroup) for group in groups)
    first, second = groups
    assert isinstance(first, ObjectGroup) and isinstance(second, ObjectGroup)
    assert second.layer > first.layer
    body1 = next(child for child in first.children if isinstance(child, TextObject))
    body2 = next(child for child in second.children if isinstance(child, TextObject))
    assert body2.state.position.y - body1.state.position.y == 50
    output = prepared.scene.compile().document
    restored = prepare_track_scene(output, tracks=()).scene.compile().document
    assert {line.text for line in restored.lines if not line.comment} == {
        r"{\k20}AB",
        r"{\k20}CD",
    }
