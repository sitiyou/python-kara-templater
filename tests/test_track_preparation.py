"""Shared target preparation retains semantics before choosing an ASS backend."""

from dataclasses import replace

import pytest

from kara_templater import (
    CYAN,
    PINK,
    Animate,
    Body,
    DisplayWindow,
    KaraokeItem,
    KaraokeLine,
    LineMatch,
    On,
    Overlay,
    PaintStyle,
    Ruby,
    Segment,
    Style,
    Syllable,
    TextStyle,
    TextUnit,
    Track,
    layout_line,
)
from kara_templater._track_types import TrackContext
from kara_templater.behaviors import sample_hierarchy


def binding(*animations):
    item = KaraokeItem(
        "source",
        KaraokeLine((TextUnit("AB", (Segment(500, 1500, "ab"),)),)),
        "Default",
        DisplayWindow(0, 2000),
    )
    track = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=CYAN)),
        ruby=Ruby(),
        overlay=Overlay(style=PaintStyle(fill=PINK)),
        animations=animations,
    )
    bound = track.bind((item,))[item.id]
    style = Style(fontname="DejaVu Sans", fontsize=32, shadow=0)
    body, ruby = bound.prepare_styles(style, replace(style, name="ruby", fontsize=16))
    context = TrackContext(
        layout_line(item.source, style=body, ruby_style=ruby, resolution=(320, 240)),
        body,
        ruby,
        (320, 240),
    )
    return bound, item, context


def test_preparation_keeps_text_ruby_paints_clocks_and_sources():
    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    targets = prepared.lyrics.targets
    assert {target.kind for target in targets} == {"body", "ruby"}
    assert "".join(target.text for target in targets if target.kind == "body") == "AB"
    assert all(target.sources[0].item_id == "source" for target in targets)
    assert all(target.singing == item.source.units[0].segments for target in targets)
    assert all(target.paints.after.fill == PINK for target in targets)
    assert all(target.tracks for target in targets)
    assert prepared.lyrics.window == item.window
    assert prepared.context == context
    assert not prepared.properties
    assert not prepared.materials


def test_unlowered_native_scale_stays_editable_and_matches_native_binding():
    bound, item, context = binding(On(Syllable.Singing, Animate(scale=(1, 1.5))))
    editable = bound.prepare(item, context)
    native = bound.prepare(item, context, lower_native=True)
    assert all(not target.animations for target in editable.lyrics.targets)
    assert any(target.animations for target in native.lyrics.targets)
    assert editable.properties
    for motions in editable.properties.values():
        assert sample_hierarchy(motions, 1000)["scale"] == 1.25
    assert editable.lyrics.targets[0].sources == native.lyrics.targets[0].sources
    assert editable.lyrics.targets[0].box == native.lyrics.targets[0].box


def test_preparing_custom_animation_does_not_sample_callback():
    calls = []

    def rate(progress):
        calls.append(progress)
        return progress * progress

    bound, item, context = binding(
        On(Syllable.Singing, Animate(scale=(1, 2), rate=rate))
    )
    prepared = bound.prepare(item, context)
    assert not calls
    assert prepared.properties
    motions = next(iter(prepared.properties.values()))
    assert sample_hierarchy(motions, 1000)["scale"] == 1.25
    assert calls


def test_lowering_accepts_edited_targets_without_preparing_again():
    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    edited = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, text="Z") if target.kind == "body" else target
                for target in prepared.lyrics.targets
            ),
        ),
    )
    output = bound.lower(item, edited)
    assert any(layer.text == "Z" for layer in output.layers)
    assert not any(layer.text == "Z" for layer in bound.lower(item, prepared).layers)
    assert all(target.text != "Z" for target in prepared.lyrics.targets)


def test_scene_objects_preserve_unswept_static_pixels_and_provenance():
    from kara_templater import Document, Scene, compile_layers
    from kara_templater._raster import rasterize
    from kara_templater._track_scene import track_objects

    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, tracks=()) for target in prepared.lyrics.targets
            ),
        ),
    )
    group = track_objects(item.id, prepared)
    assert all(
        child.origin is not None and child.origin.sources for child in group.children
    )
    assert all(
        child.origin is not None and child.origin.effect == "Track"
        for child in group.children
    )
    document = Document.create(width=320, height=240)
    actual = Scene(document).add(group).compile().document.dumps()
    plan = bound.lower(item, prepared)
    reference = compile_layers(plan.layers)
    document = Document.create(
        width=320, height=240, styles=(context.style, context.ruby_style)
    )
    document.records.extend(reference.events)
    assert (
        rasterize(actual, 0, (320, 240)).rgba
        == rasterize(document.dumps(), 0, (320, 240)).rgba
    )


def test_scene_scale_uses_same_pivot_and_scales_border():
    from kara_templater._track_scene import track_objects

    bound, item, context = binding(On(Syllable.Singing, Animate(scale=(1, 1.5))))
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, tracks=()) for target in prepared.lyrics.targets
            ),
        ),
    )
    group = track_objects(item.id, prepared)
    for child, target in zip(group.children, prepared.lyrics.targets, strict=True):
        if target.id not in prepared.properties:
            assert child.at(1) == child.state
            continue
        values = sample_hierarchy(prepared.properties[target.id], 1000)
        x, y = values["pivot"]
        state = child.at(1)
        assert state.position.x == x + (target.box.center - x) * 1.25
        assert state.position.y == y + (target.box.middle - y) * 1.25
        assert state.border == target.paints.before.border * 1.25
        assert child.copy(id="copy", delay=3).at(4) == state


def test_scene_adapter_preserves_sweep_as_editable_clipped_text():
    from kara_templater import Document, Scene, TextObject
    from kara_templater._track_scene import track_objects

    bound, item, context = binding()
    group = track_objects(item.id, bound.prepare(item, context))
    assert any(isinstance(child, TextObject) for child in group.children)
    assert any(child.clip is not None for child in group.children)
    assert Scene(Document.create()).add(group).compile().event_count > 0


def test_scene_glow_and_dynamic_scale_match_native_at_sample_centers():
    from kara_templater import Document, Glow, Scene, compile_layers
    from kara_templater._raster import rasterize
    from kara_templater._track_scene import track_objects

    bound, item, context = binding(On(Syllable.Singing, Animate(scale=(1, 1.5))))

    def without_sweep(prepared):
        targets = []
        for target in prepared.lyrics.targets:
            paint = replace(target.paints.before, glow=Glow(PINK, 3, 4, 0.6))
            targets.append(
                replace(
                    target,
                    tracks=(),
                    paints=replace(target.paints, before=paint, after=paint),
                )
            )
        return replace(
            prepared, lyrics=replace(prepared.lyrics, targets=tuple(targets))
        )

    prepared = without_sweep(bound.prepare(item, context))
    group = track_objects(item.id, prepared)
    actual = Scene(Document.create(width=320, height=240)).add(group).compile().document
    native = without_sweep(bound.prepare(item, context, lower_native=True))
    reference = Document.create(
        width=320, height=240, styles=(context.style, context.ruby_style)
    )
    reference.records.extend(compile_layers(bound.lower(item, native).layers).events)
    for time in (0, 500, 1000, 1500):
        a = rasterize(actual.dumps(), time, (320, 240)).rgba
        b = rasterize(reference.dumps(), time + 10, (320, 240)).rgba
        assert a == b, time


def test_scene_geometry_animation_does_not_overwrite_unrelated_editable_color():
    from kara_templater import TextObject
    from kara_templater._track_scene import track_objects

    bound, item, context = binding(On(Syllable.Singing, Animate(scale=(1, 1.5))))
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, tracks=()) for target in prepared.lyrics.targets
            ),
        ),
    )
    child = track_objects(item.id, prepared).children[0]
    assert isinstance(child, TextObject)
    edited = replace(child, state=replace(child.state, fill=PINK))
    assert edited.at(1).fill == PINK
    assert edited.at(1).scale.x == 1.25


def test_scene_track_callback_waits_for_compiler_preflight():
    import pytest

    from kara_templater import Document, Scene, SceneBudget, SceneCompileError
    from kara_templater._track_scene import track_objects

    calls = []

    def rate(progress):
        calls.append(progress)
        return progress

    bound, item, context = binding(
        On(Syllable.Singing, Animate(scale=(1, 2), rate=rate))
    )
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, tracks=()) for target in prepared.lyrics.targets
            ),
        ),
    )
    group = track_objects(item.id, prepared)
    assert not calls
    with pytest.raises(SceneCompileError, match="budget"):
        Scene(Document.create()).add(group).compile(budget=SceneBudget(max_events=1))
    assert not calls


def test_scene_material_binding_retains_color_and_width_animation():
    from kara_templater import Color
    from kara_templater._track_scene import track_objects

    bound, item, context = binding(
        On(
            Syllable.Singing,
            Animate(
                fill=(CYAN, PINK),
                stroke_width=(2, 6),
                compose="override",
            ),
        )
    )
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(target, tracks=()) for target in prepared.lyrics.targets
            ),
        ),
    )
    child = track_objects(item.id, prepared).children[0]
    expected = Color(
        *(
            round((a + b) / 2)
            for a, b in zip(
                (CYAN.red, CYAN.green, CYAN.blue),
                (PINK.red, PINK.green, PINK.blue),
                strict=True,
            )
        )
    )
    assert child.at(1).fill == expected
    assert child.at(1).border == 4
    assert child.at(0).fill == CYAN
    assert child.at(1.5).fill == CYAN


@pytest.mark.parametrize("animated", [False, True])
def test_scene_sweep_matches_native_reference_at_selected_centers(animated):
    from kara_templater import Document, Scene, compile_layers
    from kara_templater._raster import rasterize
    from kara_templater._track_scene import track_objects

    bound, item, context = binding(
        *((On(Syllable.Singing, Animate(scale=(1, 1.5))),) if animated else ())
    )
    group = track_objects(item.id, bound.prepare(item, context))
    actual = Scene(Document.create(width=320, height=240)).add(group).compile().document
    reference = Document.create(
        width=320, height=240, styles=(context.style, context.ruby_style)
    )
    reference.records.extend(compile_layers(bound.build(item, context).layers).events)
    for time in (0, 500, 740, 1000, 1240, 1500, 1900):
        a = rasterize(actual.dumps(), time, (320, 240)).rgba
        b = rasterize(reference.dumps(), time + 10, (320, 240)).rgba
        assert a == b, time
