"""Complete Document → lyric allocation → common Scene compilation contracts."""

from dataclasses import dataclass, field, replace

import pytest

from kara_templater import (
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    FadeOut,
    Jump,
    Layout,
    Line,
    LyricAnimationContext,
    LyricRule,
    Scene,
    Style,
    TextCue,
    Track,
    Vec2,
    prepare_tracks,
)


def document():
    doc = Document.create(
        width=640,
        height=360,
        styles=(
            Style(name="Main", fontname="DejaVu Sans", fontsize=32, shadow=0),
            Style(name="Harmony", fontname="DejaVu Sans", fontsize=24, shadow=0),
        ),
    )
    for start, end, style in (
        (1000, 2000, "Main"),
        (2000, 3000, "Main"),
        (2500, 3500, "Main"),
        (1000, 3000, "Harmony"),
    ):
        doc.records.append(
            Line(
                start_time=start,
                end_time=end,
                style=style,
                text=rf"{{\k{(end - start) // 20}}}AB|ab{{\k{(end - start) // 20}}}CD|cd",
            )
        )
    return doc


def main(**changes):
    return replace(
        Track(
            id="main",
            source=lambda source: source.style == "Main",
            layout=Layout(rows=2, position=Vec2(50, 200), gap=70),
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("line", "exit", FadeOut(), duration=0.2),
                LyricRule("syllable", "singing", Jump()),
            ),
        ),
        **changes,
    )


def test_two_tracks_share_only_scene_and_keep_singing_source():
    doc = document()
    original = doc.dumps()
    harmony = Track(
        id="harmony",
        source=lambda source: source.style == "Harmony",
        layout=Layout(position=Vec2(80, 20)),
    )
    scene = prepare_tracks(doc, tracks=(main(), harmony))
    assert isinstance(scene, Scene)
    assert [p.placement.row for p in scene.plans] == [0, 1, 0, 0]
    assert [p.placement.display.start for p in scene.plans] == pytest.approx(
        [0, 0.2, 2.2, 0]
    )
    assert scene.plans[2].source.lyrics.units[0].segments[0].singing.start == 2.5
    assert scene.plans[3].line.state.position.y < scene.plans[0].line.state.position.y
    result = scene.compile()
    assert result.event_count > 1
    assert all(isinstance(obj, type(scene.lines[0])) for obj in scene.objects)
    assert len(scene.replace_records) == 4
    assert doc.dumps() == original
    assert len([line for line in result.document.lines if line.comment]) == 4
    assert (
        prepare_tracks(doc, tracks=(main(layout=Layout(rows=3)),))
        .plans[2]
        .placement.row
        == 2
    )


def test_default_track_alternates_bottom_rows_and_scales_margins():
    scene = prepare_tracks(
        document(), tracks=(Track(id="main", source=lambda s: s.style == "Main"),)
    )
    upper, lower, again = scene.plans
    assert [p.placement.row for p in scene.plans] == [0, 1, 0]
    a, b = upper.input.bounds, lower.input.bounds
    left = upper.placement.position.x + a.left
    right = 640 - (lower.placement.position.x + b.right)
    assert left == pytest.approx(right)
    assert left > 50 / 3
    assert lower.placement.position.y + b.top + b.height == pytest.approx(340)
    assert lower.placement.position.y + b.top - (
        upper.placement.position.y + a.top + a.height
    ) == pytest.approx(15)
    assert again.placement.position.x + again.input.bounds.center == pytest.approx(320)


def test_source_can_have_multiple_views_but_is_replaced_only_once_and_regenerates():
    doc = document()
    track = main(source=lambda source: source.style == "Harmony", effects=(*(()),))
    scene = prepare_tracks(
        doc,
        tracks=(track, replace(track, id="copy", layout=Layout(position=Vec2(80, 20)))),
    )
    assert len(scene.lines) == 2
    assert scene.lines[0].id != scene.lines[1].id
    assert scene.lines[0].origin is not None
    assert scene.lines[1].origin is not None
    assert scene.lines[0].origin.sources == scene.lines[1].origin.sources
    assert len(scene.replace_records) == 1
    output = scene.compile()
    again = prepare_tracks(
        output.document,
        tracks=(track, replace(track, id="copy", layout=Layout(position=Vec2(80, 20)))),
    )
    assert again.compile().document.dumps() == output.document.dumps()


def test_inline_cue_is_reserved_independent_cue_keeps_own_lifetime_and_position():
    doc = document()
    record = next(line for line in doc.lines if line.style == "Main")
    record.text = (
        CueMarker("inline", "bars").markup()
        + CueMarker("separate", "text", placement="independent").markup()
        + record.text
    )
    presets = {
        "bars": CuePreset(factory=BarsCue(width=35, height=20), lead=0.8, duration=0.8),
        "text": CuePreset(
            factory=TextCue(labels=("3", "2", "1"), font_size=20),
            lead=1,
            duration=1,
            position=Vec2(500, 30),
        ),
    }
    scene = prepare_tracks(doc, tracks=(main(cues=presets, preview=0),))
    first = scene.plans[0]
    assert first.input.reserved is not None
    assert first.input.reserved.start == pytest.approx(0.2)
    assert first.placement.display.start == pytest.approx(0.2)
    assert len(first.line.query("cue")) == 2
    assert len(first.line.independent) == 1
    separate = first.line.independent[0]
    assert separate.state.position == Vec2(500, 30)
    assert separate.lifetime.start == 0
    assert separate in scene.objects
    assert first.line.lifetime.start > separate.lifetime.start
    assert scene.compile().event_count > 1


def test_semantic_copy_retargets_nodes_and_preserves_source_singing():
    scene = prepare_tracks(document(), tracks=(main(effects=(*(()),)),))
    original = scene.lines[0]
    clone = original.copy(id="copy", delay=5, offset=Vec2(10, 0))
    assert clone.targets[0].singing == original.targets[0].singing
    assert clone.targets[0].node_id == "copy"
    bound = clone.bind(LyricRule("syllable", "singing", Jump()))
    evaluator = Scene(document()).add(bound).evaluator()
    target = clone.query("character")[0]
    baseline = Scene(document()).add(clone).evaluator().at(target.node_id, 6.25)
    assert evaluator.at(target.node_id, 6.25).position == baseline.position + Vec2(
        0, -12
    )
    assert clone.origin == original.origin


def test_custom_allocator_is_called_once_with_complete_input_and_validated():
    calls = []

    class Custom(Layout):
        def allocate(self, lines, context):
            calls.append((lines, context))
            # An arbitrary overlapping free layout is permitted by the engine.
            return tuple(
                replace(p, row=None, position=Vec2(100, 100))
                for p in super().allocate(lines, context)
            )

    scene = prepare_tracks(document(), tracks=(main(layout=Custom(rows=3)),))
    assert len(calls) == 1
    assert len(calls[0][0]) == 3
    assert all(plan.placement.row is None for plan in scene.plans)

    class Broken(Layout):
        def allocate(self, lines, context):
            return ()

    with pytest.raises(ValueError, match="missing placements"):
        prepare_tracks(document(), tracks=(main(layout=Broken()),))


def test_allocator_mutable_configuration_is_isolated_between_preparations():
    @dataclass(frozen=True)
    class Remembering(Layout):
        history: list[str] = field(default_factory=list)

        def allocate(self, lines, context):
            self.history.extend(line.id for line in lines)
            return tuple(
                replace(placement, position=Vec2(len(self.history), 40))
                for placement in super().allocate(lines, context)
            )

    allocator = Remembering(rows=3)
    configuration = main(layout=allocator)
    source = document()
    original = source.dumps()
    first = prepare_tracks(source, tracks=(configuration,))
    second = prepare_tracks(source, tracks=(configuration,))
    assert allocator.history == []
    assert all(plan.placement.position == Vec2(3, 40) for plan in first.plans)
    assert [plan.placement for plan in first.plans] == [
        plan.placement for plan in second.plans
    ]
    assert first.lines[0] is not second.lines[0]
    assert source.dumps() == original
    assert first.compile().document.dumps() == second.compile().document.dumps()


def test_removing_all_tracks_restores_sources_without_losing_unrelated_events():
    source = document()
    output = prepare_tracks(source, tracks=(main(),)).compile().document
    restored = prepare_tracks(output, tracks=()).compile().document
    assert [line.serialize() for line in restored.lines if not line.comment] == [
        line.serialize() for line in source.lines if not line.comment
    ]


def test_unselected_animated_ass_is_retained_without_projection():
    doc = document()
    unrelated = Line(
        style="Harmony",
        start_time=1000,
        end_time=2000,
        text=r"{\move(0,0,50,50)\k100}native",
    )
    doc.records.append(unrelated)
    result = prepare_tracks(doc, tracks=(main(),)).compile()
    assert any(
        event.text == unrelated.text and not event.comment
        for event in result.document.lines
    )


def test_singing_rule_extent_participates_in_layout_before_binding():
    rules = (LyricRule("line", "singing", Jump(), duration=2),)
    with pytest.raises(
        ValueError, match="required singing/animation intervals overlap"
    ):
        prepare_tracks(document(), tracks=(main(effects=(*(rules),)),))
    scene = prepare_tracks(
        document(), tracks=(main(effects=(*(rules),), layout=Layout(rows=3)),)
    )
    assert scene.lines[0].animations[0].duration == 2
    assert scene.plans[0].placement.display.end >= 3


def test_explicit_cross_track_measurements_are_available_to_override():
    doc = document()
    main_scene = prepare_tracks(doc, tracks=(main(),))
    references = tuple(plan.input for plan in main_scene.plans)
    inspected = []

    class Coordinated(Layout):
        def allocate(self, lines, context):
            inspected.extend(context.other_lines)
            return super().allocate(lines, context)

    harmony = Track(
        id="harmony",
        source=lambda source: source.style == "Harmony",
        layout=Coordinated(),
        references=references,
    )
    prepare_tracks(doc, tracks=(harmony,))
    assert tuple(inspected) == references


def test_inline_cue_factory_runs_once_and_copy_keeps_independent_anchors():
    from kara_templater import CueContent, CueContext, Lifetime, LyricLine, ObjectGroup

    calls = []

    def factory(context: CueContext) -> CueContent:
        calls.append(context)
        return BarsCue(width=30, height=20)(context)

    doc = document()
    record = next(line for line in doc.lines if line.style == "Main")
    record.text = CueMarker("lead", "bars").markup() + record.text
    scene = prepare_tracks(
        doc, tracks=(main(cues={"bars": CuePreset(factory=factory)}),)
    )
    assert len(calls) == 1
    first = scene.lines[0]
    standalone = ObjectGroup(id="separate", lifetime=Lifetime(0, 1), children=())
    line = LyricLine.from_layout(first.layout, independent=(standalone,))
    copied = line.copy(id="copy", delay=2).bind(
        LyricRule("cue", "enter", FadeIn(), duration=0.2)
    )
    assert copied.independent[0].lifetime == Lifetime(2, 3)
    assert copied.independent[0].at(2.1).opacity == pytest.approx(0.5)
    assert copied.query("cue")[0].node_id == copied.independent[0].id


def test_zero_duration_singing_is_not_replaced_with_the_display_interval():
    doc = document()
    record = next(line for line in doc.lines if line.style == "Main")
    record.text = r"{\k0}Zero"
    scene = prepare_tracks(doc, tracks=(main(effects=(*(()),)),))
    first = scene.plans[0]
    assert first.input.singing.start == first.input.singing.end == 1
    assert first.line.query("syllable")[0].singing[0].start == 1
    assert first.line.query("syllable")[0].singing[0].end == 1
    assert first.placement.display.start < first.placement.display.end


def test_cross_track_singing_anchor_is_explicit_and_participates_in_occupancy():
    doc = document()
    harmony = prepare_tracks(
        doc,
        tracks=(
            Track(
                id="harmony",
                source=lambda source: source.style == "Harmony",
            ),
        ),
    )
    anchor = harmony.lines[0].query("line")[0]
    rule = LyricRule("line", anchor, Jump(), hold=False)
    scene = prepare_tracks(
        doc, tracks=(main(layout=Layout(rows=3), effects=(*((rule,)),)),)
    )
    for plan in scene.plans:
        assert plan.placement.display.start <= 1
        assert plan.placement.display.end >= 3
        assert plan.line.at(2).position == plan.line.state.position + Vec2(0, -12)
    assert scene.plans[2].input.singing.start == 2.5
    assert scene.plans[2].line.query("line")[0].singing[0].start == 2.5
    # The anchor is source data, so the referenced visual need not be in this Scene.
    assert all(plan.track_id == "main" for plan in scene.plans)


def test_custom_allocator_bypasses_builtin_capacity_and_preserves_positions():
    from kara_templater import LayoutContext, LayoutLine, Placement

    class FreeLayout(Layout):
        def allocate(
            self, lines: tuple[LayoutLine, ...], context: LayoutContext
        ) -> tuple[Placement, ...]:
            return tuple(
                Placement(item.id, Vec2(25 + index * 120, 80), item.display)
                for index, item in enumerate(lines)
            )

    doc = document()
    with pytest.raises(ValueError, match="occupied"):
        prepare_tracks(doc, tracks=(main(layout=Layout(rows=1)),))
    scene = prepare_tracks(doc, tracks=(main(layout=FreeLayout(rows=1)),))
    assert [plan.placement.position for plan in scene.plans] == [
        Vec2(25, 80),
        Vec2(145, 80),
        Vec2(265, 80),
    ]
    assert all(plan.placement.row is None for plan in scene.plans)
    assert all(plan.placement.display == plan.input.display for plan in scene.plans)


def test_prepared_lyrics_remain_editable_and_share_native_tween_compilation():
    from kara_templater import PINK, ObjectGroup, StatePatch, TextObject, Tween

    source = document()
    original = source.dumps()
    calls: list[str] = []

    def factory(line):
        calls.append(line.id)
        return line

    config = main(
        source=lambda source: source.style == "Harmony",
        effects=(*((
            LyricRule(
                "character",
                "singing",
                Tween(StatePatch(scale=Vec2(1.5, 1.5), border=3)),
            ),
        )), factory,),
        
    )
    scene = prepare_tracks(source, tracks=(config,))
    line = scene.lines[0]
    group = line.children[0]
    assert isinstance(group, ObjectGroup)
    child = group.children[0]
    assert isinstance(child, TextObject)
    assert child.origin is not None and child.origin.sources
    edited = replace(child, text="Z", state=replace(child.state, fill=PINK))
    scene.objects[0] = replace(
        line,
        children=(
            replace(group, children=(edited, *group.children[1:])),
            *line.children[1:],
        ),
    )
    state = scene.evaluator().at(edited.id, 1.5)
    assert state.fill == PINK
    assert state.scale == Vec2(1.25, 1.25)
    assert state.border == 2.5
    native = scene.compile(native_tweens=True)
    sampled = scene.compile()
    assert any(
        r"\t(" in event.text and event.text.endswith("Z")
        for event in native.document.lines
        if not event.comment
    )
    assert any(
        event.text.endswith("Z")
        for event in sampled.document.lines
        if not event.comment
    )
    assert calls == [line.id]
    assert child.text == "A" and child.state.fill != PINK
    assert (
        line.query("character")[0].singing
        == scene.lines[0].query("character")[0].singing
    )
    assert source.dumps() == original


def test_layout_translation_moves_body_and_ruby_without_mutating_source():
    source = Document.create(
        width=320,
        height=180,
        styles=(Style(fontname="DejaVu Sans", fontsize=24, outline=0, shadow=0),),
    )
    source.records.append(Line(text=r"{\k100}AB|ab", start_time=1000, end_time=2000))
    original = source.dumps()
    config = Track(id="lyrics", preview=0, tail=0, layout=Layout(position=Vec2(30, 40)))
    baseline = prepare_tracks(source, tracks=(config,))
    shifted = prepare_tracks(
        source, tracks=(replace(config, layout=Layout(position=Vec2(50, 70))),)
    )
    before = baseline.evaluator()
    after = shifted.evaluator()
    for target in baseline.lines[0].query("character", "ruby"):
        assert after.at(target.node_id, 1.5).position == before.at(
            target.node_id, 1.5
        ).position + Vec2(20, 30)
    from kara_templater._raster import rasterize

    a = rasterize(baseline.compile().document.dumps(), 1500, (320, 180)).rgba
    b = rasterize(shifted.compile().document.dumps(), 1500, (320, 180)).rgba
    assert any(a[3::4])
    for y in range(150):
        assert (
            b[((y + 30) * 320 + 20) * 4 : ((y + 30) * 320 + 320) * 4]
            == a[(y * 320) * 4 : (y * 320 + 300) * 4]
        )
    assert source.dumps() == original


def test_display_keyframe_factory_keeps_original_window_when_other_rule_extends_it():
    from kara_templater import StateKeyframe, StatePatch, Timeline, TimeSpan

    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(Line(text=r"{\kt100\k100}A", start_time=0, end_time=2000))
    original = source.dumps()
    durations = []

    def keyframes(timing: LyricAnimationContext):
        duration = timing.line.lifetime.end - timing.line.lifetime.start
        durations.append(duration)
        return (
            Timeline()
            .keyframes(StateKeyframe(duration, StatePatch(opacity=0)))
            .animation
        )

    def original_display(line, target):
        return (TimeSpan(line.lifetime.start, line.lifetime.end),)

    # An animation spanning the source display window uses that explicit clock.
    # "enter" instead reserves a pre-singing entrance, which is a different rule.
    rule = LyricRule("line", original_display, keyframes)
    config = Track(id="lyrics", preview=0, tail=0, effects=(rule,))
    baseline = prepare_tracks(source, tracks=(config,))
    extended = prepare_tracks(
        source,
        tracks=(
            replace(
                config,
                effects=(
                    rule,
                    LyricRule("character", "singing", Jump(), duration=1.2),
                ),
            ),
        ),
    )
    assert durations == [2, 2]
    assert baseline.lines[0].lifetime.end == 2
    assert extended.lines[0].lifetime.end == pytest.approx(2.2)
    for time, opacity in ((1, 0.5), (0.5, 0.75), (2, 0), (2.1, 0)):
        assert baseline.lines[0].at(time).opacity == pytest.approx(opacity)
        assert extended.lines[0].at(time).opacity == pytest.approx(opacity)
    extended.compile()
    assert durations == [2, 2]
    assert source.dumps() == original


def test_track_style_overrides_are_measured_before_allocation_and_leave_source_intact():
    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, outline=0, shadow=0),)
    )
    source.records.append(Line(text=r"{\k100}AB|ab", start_time=1000, end_time=2000))
    original = source.dumps()
    sizes = []

    class InspectLayout(Layout):
        def allocate(self, lines, context):
            sizes.append(lines[0].bounds)
            return super().allocate(lines, context)

    config = Track(id="lyrics", layout=InspectLayout(), preview=0, tail=0)
    small = prepare_tracks(source, tracks=(config,))
    larger_style = replace(source.styles["Default"], fontsize=40)
    large = prepare_tracks(source, tracks=(replace(config, styles=(larger_style,)),))
    assert sizes[1].width > sizes[0].width
    assert sizes[1].height > sizes[0].height
    assert [c.object.font_size for c in small.lines[0].layout.body.characters] == [
        24,
        24,
    ]
    assert [c.object.font_size for c in large.lines[0].layout.body.characters] == [
        40,
        40,
    ]
    assert all(
        c.object.font_size == 20
        for c in large.lines[0].layout.ruby[0].layout.characters
    )
    assert source.dumps() == original
    assert larger_style.fontsize == 40
