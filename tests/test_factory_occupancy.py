"""Visual factories reserve authored time before a single layout allocation."""

from dataclasses import replace

import pytest

from kara_templater import (
    RED,
    Coverage,
    Document,
    GlowFunction,
    Highlight,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    Region,
    SceneBudget,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Tween,
    prepare_tracks,
)


@pytest.mark.parametrize("effect", ("clip", "coverage", "glow"))
@pytest.mark.parametrize("preview", (0, 1))
def test_authored_visual_time_reaches_allocator_before_factory_output_is_clipped(
    effect,
    preview,
):
    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),)
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    original = source.dumps()
    allocations = []
    factories = []

    class Inspect(Layout):
        def allocate(self, lines, context):
            allocations.extend(lines)
            return super().allocate(lines, context)

    def factory(line):
        factories.append(line.id)
        if effect == "glow":
            glow = GlowFunction.from_animation(
                Tween(StatePatch(blur=4)), start=1 - line.lifetime.start, duration=1.4
            )
            return replace(
                line,
                coverage=Coverage(glows={line.query("character")[0].node_id: glow}),
            )
        box = line.layout.body.bounds
        return LyricHighlights(
            highlights=(
                Highlight(
                    "late",
                    0,
                    (HighlightPass(TimeSpan(1, 2.4), Region(box.left, box.right)),),
                    StatePatch(fill=RED),
                ),
            ),
            strategy=effect,
        )(line)

    scene = prepare_tracks(
        source,
        tracks=(
            Track(
                id="main", preview=preview, tail=0, layout=Inspect(), effects=(factory,)
            ),
        ),
    )
    assert len(factories) == 1
    assert len(allocations) == 1
    assert allocations[0].required.end == pytest.approx(2.4)
    assert scene.lines[0].lifetime.end == pytest.approx(2.4)
    assert source.dumps() == original


def test_factory_tail_participates_in_capacity_and_preview_trim_keeps_clock():
    from kara_templater import VisualState

    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),)
    )
    source.records.extend(
        (
            Line(text=r"{\k100}A", start_time=1000, end_time=2000),
            Line(text=r"{\k100}B", start_time=2500, end_time=3500),
        )
    )
    calls = []

    def factory(line):
        calls.append(line.id)
        target = line.query("character")[0]
        glow = GlowFunction.from_animation(
            Tween(StatePatch(blur=4)),
            start=target.singing[0].start - line.time_origin,
            duration=1.2,
        )
        return replace(line, coverage=Coverage(glows={target.node_id: glow}))

    config = Track(id="main", preview=1, tail=0, layout=Layout(rows=1), effects=(factory,))
    scene = prepare_tracks(source, tracks=(config,))
    assert len(calls) == 2 and len(set(calls)) == 2
    second = scene.lines[1]
    assert second.lifetime.start == pytest.approx(2.2)
    assert second.time_origin == 1.5
    assert second.lifetime.end == pytest.approx(3.7)
    assert second.coverage is not None
    glow = next(iter(second.coverage.glows.values()))
    assert isinstance(glow, GlowFunction)
    sampled = glow.sample(VisualState(), 3.1 - second.time_origin)
    assert sampled is not None and sampled.blur == pytest.approx(2)
    source.records[-1] = Line(text=r"{\k100}B", start_time=2100, end_time=3100)
    original = source.dumps()
    with pytest.raises(ValueError, match="occupied"):
        prepare_tracks(source, tracks=(config,))
    assert source.dumps() == original


def test_attached_decoration_reserves_visible_tail_but_external_visual_does_not():
    from kara_templater import (
        Lifetime,
        ObjectGroup,
        PathObject,
        Scene,
        Vec2,
        VectorPath,
        VisualState,
    )

    source = Document.create(
        width=96,
        height=64,
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),),
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    original = source.dumps()
    allocations = []
    calls = []

    class Inspect(Layout):
        def allocate(self, lines, context):
            allocations.extend(lines)
            return super().allocate(lines, context)

    def factory(line):
        calls.append(line.id)
        spark = PathObject(
            id=f"{line.id}/spark",
            lifetime=Lifetime(1.5, 4),
            path=VectorPath.rectangle(5, 5),
            state=VisualState(fill=RED),
        )
        # This fixed group deliberately clips the longer-lived child.
        attached = ObjectGroup(
            id=f"{line.id}/decoration",
            lifetime=Lifetime(1.5, 2.4),
            children=(spark,),
        )
        external = ObjectGroup(
            id=f"{line.id}/external",
            lifetime=Lifetime(1.5, 5),
            children=(spark.copy(id=f"{line.id}/external/spark"),),
            state=VisualState(position=Vec2(10, 10)),
        )
        return replace(
            line,
            children=(*line.children, attached),
            independent=(external,),
        )

    scene = prepare_tracks(
        source,
        tracks=(
            Track(id="main", preview=0, tail=0, layout=Inspect(), effects=(factory,)),
        ),
    )
    assert len(calls) == len(allocations) == 1
    assert allocations[0].required == TimeSpan(1, 2.4)
    line = scene.lines[0]
    assert line.lifetime == Lifetime(1, 2.4)
    attached = line.children[-1]
    assert attached.lifetime == Lifetime(1.5, 2.4)
    assert isinstance(attached, ObjectGroup)
    assert attached.children[0].lifetime == Lifetime(1.5, 4)
    assert line.independent[0].lifetime == Lifetime(1.5, 5)
    from kara_templater._raster import rasterize

    attached_only = Scene(source, replace_records={len(source.records) - 1}).add(line)
    output = attached_only.ass.compile(budget=SceneBudget(fps=10)).document.dumps()
    assert any(rasterize(output, 2300, (96, 64)).rgba[3::4])
    assert not any(rasterize(output, 2500, (96, 64)).rgba[3::4])
    scene.ass.compile(budget=SceneBudget(fps=10, max_events=100_000))
    assert len(calls) == 1
    assert source.dumps() == original


def test_factory_declared_bounds_reach_allocator_without_remeasuring_text():
    from kara_templater import Box

    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),)
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    declared = Box(-40, -20, 160, 80)
    measurements = []
    allocations = []

    def factory(line):
        measurements.append(line.layout.body)
        return replace(line, layout=replace(line.layout, bounds=declared))

    class Inspect(Layout):
        def allocate(self, lines, context):
            allocations.extend(lines)
            return super().allocate(lines, context)

    scene = prepare_tracks(
        source, tracks=(Track(id="main", effects=(factory,), layout=Inspect()),)
    )
    assert len(measurements) == len(allocations) == 1
    assert allocations[0].bounds == declared
    assert scene.lines[0].layout.bounds == declared
    assert scene.lines[0].layout.body.bounds == measurements[0].bounds


def test_factory_early_decoration_extends_visibility_without_restarting_animation():
    from kara_templater import Lifetime, PathObject, Vec2, VectorPath, VisualState

    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),)
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    allocations = []
    calls = []

    class Inspect(Layout):
        def allocate(self, lines, context):
            allocations.extend(lines)
            return super().allocate(lines, context)

    def factory(line):
        calls.append(line.id)
        line = line.animate(Tween(StatePatch(position=Vec2(10, 0))), duration=1)
        ornament = PathObject(
            id=f"{line.id}/early",
            lifetime=Lifetime(0.5, 1),
            path=VectorPath.rectangle(5, 5),
            state=VisualState(fill=RED),
        )
        return replace(line, children=(*line.children, ornament))

    scene = prepare_tracks(
        source,
        tracks=(
            Track(id="main", preview=0, tail=0, layout=Inspect(), effects=(factory,)),
        ),
    )
    line = scene.lines[0]
    assert len(calls) == len(allocations) == 1
    assert allocations[0].required == TimeSpan(0.5, 2)
    assert line.lifetime == Lifetime(0.5, 2)
    assert line.time_origin == 1
    assert line.at(0.75).position == line.state.position
    assert line.at(1.5).position == line.state.position * 0.5 + Vec2(5, 0)
    assert line.layout.body.singing[0].start == 1


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_early_highlight_matches_explicit_preview_without_moving_existing_animation(
    strategy,
):
    from kara_templater import FadeIn, Lifetime

    source = Document.create(
        width=96,
        height=64,
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),),
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    original = source.dumps()
    calls = []

    def factory(line):
        calls.append(line.id)
        line = line.animate(FadeIn(), at=1 - line.time_origin, duration=0.5)
        box = line.layout.body.bounds
        return LyricHighlights(
            highlights=(
                Highlight(
                    "early",
                    0,
                    (HighlightPass(TimeSpan(0.5, 1.5), Region(box.left, box.right)),),
                    StatePatch(fill=RED),
                ),
            ),
            strategy=strategy,
        )(line)

    scenes = tuple(
        prepare_tracks(
            source,
            tracks=(
                Track(
                    id="main",
                    preview=preview,
                    tail=0,
                    effects=(factory,),
                ),
            ),
        )
        for preview in (0, 0.5)
    )
    assert len(calls) == 2
    assert scenes[0].lines[0].time_origin == 1
    assert scenes[1].lines[0].time_origin == 0.5
    for scene in scenes:
        assert scene.lines[0].lifetime == Lifetime(0.5, 2)
        assert scene.lines[0].required_display == (TimeSpan(0.5, 1.5),)
    assert source.dumps() == original


def test_signed_glow_requirement_reserves_early_window_before_sampling():
    from kara_templater import Glow, Lifetime

    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),)
    )
    source.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    samples = []
    allocations = []

    class Inspect(Layout):
        def allocate(self, lines, context):
            assert samples == []
            allocations.extend(lines)
            return super().allocate(lines, context)

    def glow(state, time):
        samples.append(time)
        return Glow(RED, blur=1)

    def factory(line):
        return replace(
            line,
            coverage=Coverage(
                glows={
                    line.query("character")[0].node_id: GlowFunction(
                        glow,
                        max_blur=1,
                        max_border=0,
                        breakpoints=(-0.5, 0.5),
                        required_interval=TimeSpan(-0.5, 0.5),
                    ),
                }
            ),
        )

    scene = prepare_tracks(
        source,
        tracks=(
            Track(
                id="main",
                preview=0,
                tail=0,
                layout=Inspect(),
                effects=(factory,),
            ),
        ),
    )
    assert allocations[0].required == TimeSpan(0.5, 2)
    assert scene.lines[0].lifetime == Lifetime(0.5, 2)
    assert scene.lines[0].time_origin == 1


@pytest.mark.parametrize(
    ("tail", "duration", "stagger", "expected", "minimum"),
    [
        (None, 0, 0, 1.0, 0.2),
        (None, 0.42, 0, 1.0, 0.62),
        (None, 0.9, 0, 1.1, 1.1),
        (None, 0.5, 0.25, 1.2, 1.2),
        (0, 0.42, 0, 0.42, 0.42),
    ],
)
def test_exit_span_and_hold_include_stagger_and_parallel_rules(tail, duration, stagger, expected, minimum):
    from kara_templater import FadeOut, LyricRule

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.append(Line(text=r"{\k100}ABC", start_time=1000, end_time=2000))
    rules = (
        LyricRule("character", "exit", FadeOut(), duration=duration, stagger=stagger),
        LyricRule("line", "exit", FadeOut(), duration=duration / 2),
    ) if duration else ()
    plan, = prepare_tracks(doc, tracks=(Track(id="main", tail=tail, effects=rules),)).plans
    assert plan.input.required.end == pytest.approx(2 if tail is None else 2 + minimum)
    assert plan.placement.display.end == pytest.approx(2 + expected)


def test_row_handoff_keeps_the_hold_until_preview_is_exhausted():
    from kara_templater import KaraokeEffects

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.extend((
        Line(text=r"{\k100}A", start_time=1000, end_time=2000),
        Line(text=r"{\k100}B", start_time=2700, end_time=3700),
    ))
    fade = KaraokeEffects(entry="none", exit="fade", singing="none", exit_duration=0.42)
    track = Track(id="main", layout=Layout(rows=1), effects=(fade,))
    first, second = prepare_tracks(doc, tracks=(track,)).plans
    assert first.placement.display.end == pytest.approx(second.input.required.start)
    assert second.placement.display.start >= first.placement.display.end


@pytest.mark.parametrize("layout_type", ["rotating", "paged"])
@pytest.mark.parametrize(("gap_ms", "tail", "lead"), [
    (2700, 1, 1.7), (2000, 1, 1), (1200, .63, .57), (990, .42, .57),
    (500, .5 * .42 / .99, .5 * .57 / .99), (0, 0, 0),
])
def test_dense_row_handoff_retimes_animations_without_moving_notes(layout_type, gap_ms, tail, lead):
    from kara_templater import FadeIn, FadeOut, KaraokeRows, LyricRule

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.extend((
        Line(text=r"{\k100}AB", start_time=2000, end_time=3000),
        Line(text=r"{\k100}CD", start_time=3000 + gap_ms, end_time=4000 + gap_ms),
    ))
    layout = Layout(rows=1) if layout_type == "rotating" else KaraokeRows(
        rows=1, lane_gap=0, fill_section=False,
    )
    track = Track(id="main", layout=layout, preview=1.7, effects=(
        LyricRule("line", "enter", FadeIn(), duration=.57),
        LyricRule("character", "exit", FadeOut(), duration=.32, stagger=.10),
    ))
    scene = prepare_tracks(doc, tracks=(track,))
    old, new = scene.plans
    assert old.placement.display.end == pytest.approx(3 + tail)
    assert new.placement.display.start == pytest.approx(3 + gap_ms / 1000 - lead)
    assert old.placement.display.end <= new.placement.display.start + 1e-9
    assert old.input.singing.end == 3
    assert new.input.singing.start == pytest.approx(3 + gap_ms / 1000)
    assert [clip.duration for clip in new.line.animations] == pytest.approx([min(.57, lead)] if lead else [])
    evaluator = scene.evaluator()
    for index, target in enumerate(old.line.query("character")):
        if not tail:
            assert evaluator.at(target.node_id, 2.99).opacity == 1
            continue
        scale = min(1, tail / .42)
        midpoint = old.placement.display.end - (.26 - index * .10) * scale
        assert evaluator.at(target.node_id, midpoint).opacity == pytest.approx(.5)


@pytest.mark.parametrize("exit_kind", ["fade", "char_fade", "utopia", "dissolve_out"])
@pytest.mark.parametrize("gap_ms", [0, 500])
def test_catalog_decorations_follow_dense_handoffs(exit_kind, gap_ms):
    from kara_templater import KaraokeEffects

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    for start in (2000, 3000 + gap_ms):
        doc.records.append(Line(text=r"{\k50}A{\k50}B", start_time=start, end_time=start + 1000))
    recipe = KaraokeEffects(entry="fade", exit=exit_kind, singing="zoom_pulse",
                            decoration="twinkle_classic", entry_duration=.57, exit_duration=.42)
    old, new = prepare_tracks(doc, tracks=(Track(id="main", layout=Layout(rows=1), effects=(recipe,)),)).plans
    outgoing = old.input.exit
    assert outgoing > 0
    boundary = 3 + gap_ms / 1000 * outgoing / (.57 + outgoing)
    assert old.placement.display.end == pytest.approx(boundary)
    assert new.placement.display.start == pytest.approx(boundary)


def test_inline_countdown_keeps_its_clock_when_the_previous_line_cannot_yield():
    from kara_templater import BarsCue, CueMarker, CuePreset

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.extend((
        Line(text=r"{\k100}A", start_time=2000, end_time=3000),
        Line(text=CueMarker("countdown", "bars").markup() + r"{\k100}B", start_time=3500, end_time=4500),
    ))
    track = Track(id="main", layout=Layout(rows=1), cues={"bars": CuePreset(factory=BarsCue(), lead=1, duration=1)})
    with pytest.raises(ValueError, match="countdown"):
        prepare_tracks(doc, tracks=(track,))


@pytest.mark.parametrize("paged", [True, False])
def test_two_rows_share_only_the_reused_lane_budget(paged):
    from kara_templater import FadeIn, FadeOut, KaraokeRows, LyricRule

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    for start, end, text in [(2000, 3000, "A"), (3000, 3500, "B"), (3500, 4500, "C")]:
        doc.records.append(Line(text=rf"{{\k{(end - start) // 10}}}{text}", start_time=start, end_time=end))
    layout = KaraokeRows(rows=2) if paged else Layout(rows=2, alignment="alternating")
    effects = (LyricRule("line", "enter", FadeIn(), duration=.57),
               LyricRule("line", "exit", FadeOut(), duration=.42))
    plans = prepare_tracks(doc, tracks=(Track(id="main", layout=layout, effects=effects),)).plans
    a, b, c = plans
    assert [p.placement.row for p in plans] == [0, 1, 0]
    assert a.placement.display.end == c.placement.display.start == pytest.approx(3 + .5 * .42 / .99)
    assert b.input.singing == TimeSpan(3, 3.5)
    assert b.placement.display.start <= 3 and b.placement.display.end >= 3.5
