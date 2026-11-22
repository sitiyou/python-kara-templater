"""Named highlight policies retain ownership, alpha and shared animation binding."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    Document,
    Highlight,
    HighlightPass,
    Jump,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    Scene,
    SceneBudget,
    StatePatch,
    Style,
    Vec2,
    layout_document_lyrics,
)
from kara_templater._raster import rasterize
from kara_templater.lyric_highlights import _owners
from kara_templater.scene_animation import TimeSpan
from kara_templater.timeline import Region, union_regions

BUDGET = SceneBudget(fps=10, max_events=40_000, max_active=10_000)


def source():
    doc = Document.create(
        width=96,
        height=64,
        styles=(Style(fontname="DejaVu Sans", fontsize=24, shadow=0, outline=0),),
    )
    doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}AB"))
    layout = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 3))
    return doc, LyricLine.from_layout(layout)


def highlights(line):
    box = line.layout.body.bounds
    span = HighlightPass(TimeSpan(1, 2), Region(box.left, box.right))
    return (
        Highlight("red", 0, (span,), StatePatch(fill=RED, opacity=0.5)),
        Highlight(
            "blue",
            0,
            (replace(span, time=TimeSpan(1.2, 1.8)),),
            StatePatch(fill=BLUE, opacity=0.5),
            priority=10,
            end="hide",
        ),
    )


def test_priority_layer_and_union_have_distinct_overlap_contracts():
    _, line = source()
    red, blue = highlights(line)
    priority = _owners((red, blue), 1.5, "priority")
    layered = _owners((red, blue), 1.5, "layer")
    assert _owners((blue, red), 1.5, "priority") == priority
    assert _owners((blue, red), 1.5, "layer") == layered
    assert priority[0][1] == ("blue",)
    assert layered[0][1] == ("red", "blue")
    assert _owners((red, blue), 1.9, "priority")[0][1] == ("red",)
    with pytest.raises(ValueError, match="identical appearance"):
        _owners((red, blue), 1.5, "union")
    same = replace(blue, paint=red.paint)
    assert _owners((red, same), 1.5, "union")[0][1] == ("red",)
    with pytest.raises(ValueError, match="equal-priority"):
        _owners((red, replace(blue, priority=0)), 1.5, "priority")
    with pytest.raises(ValueError, match="distinct priorities"):
        _owners((red, replace(blue, priority=0)), 1.5, "layer")


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_highlighted_line_uses_common_scene_and_target_aliases_follow_animation(
    strategy,
):
    doc, line = source()
    decorated = LyricHighlights(
        highlights=highlights, mode="priority", strategy=strategy
    )(line)
    target = decorated.query("character")[0]
    assert len(target.aliases) >= 2
    assert len(set(target.aliases)) == len(target.aliases)
    animated = decorated.bind(LyricRule("character", "singing", Jump()))
    scene = Scene(doc).add(animated)
    evaluator = scene.evaluator()
    for identity in target.aliases:
        assert (
            evaluator.at(identity, 1.5).position
            == evaluator.at(target.node_id, 1.5).position
        )
    result = scene.compile(budget=BUDGET)
    assert result.event_count > 0
    assert all(report.strategy != "native-event" for report in result.objects)
    assert (result.objects[0].strategy == "coverage") == (strategy == "coverage")
    assert any(rasterize(result.document.dumps(), 1500, (96, 64)).rgba)
    copied = animated.copy(id="copy", delay=3)
    copied_target = copied.query("character")[0]
    assert all(identity.startswith("copy/") for identity in copied_target.aliases)
    assert copied.query("line", "character") == copied.query("line")
    assert Scene(doc).add(copied).compile(budget=BUDGET).event_count > 0


def test_disjoint_regions_and_repeat_reset_keep_explicit_round_clocks():
    first = HighlightPass(TimeSpan(1, 2), Region(0, 10))
    repeat = HighlightPass(TimeSpan(3, 4), Region(0, 10), round=1)
    highlight = Highlight(
        "word", 0, (first, repeat), StatePatch(fill=RED), repeat="reset"
    )
    assert highlight.regions(2.5) == (Region(0, 10),)
    assert highlight.regions(3.5) == (Region(0, 5),)
    disjoint = replace(
        highlight, passes=(first, replace(repeat, region=Region(20, 30))), repeat="hold"
    )
    assert disjoint.regions(3.5) == (Region(0, 10), Region(20, 25))
    with pytest.raises(ValueError, match="separate visual components"):
        LyricHighlights(highlights=(highlight,), mode="layer", strategy="coverage")


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_reverse_pass_renders_sung_ink_to_the_right_of_waiting_ink(strategy):
    doc, line = source()
    red = highlights(line)[0]
    red = replace(red, passes=(replace(red.passes[0], reverse=True),))
    painted = LyricHighlights(
        highlights=(red,), base_paint=StatePatch(fill=BLUE), strategy=strategy
    )(line)
    scene = Scene(doc, replace_records={len(doc.records) - 1}).add(painted)
    script = scene.compile(budget=BUDGET).document.dumps()
    frame = rasterize(script, 1500, (96, 64)).rgba
    pixels = [frame[i:i + 4] for i in range(0, len(frame), 4)]
    sung = [i % 96 for i, (r, _, b, a) in enumerate(pixels) if a > 80 and r > b]
    waiting = [i % 96 for i, (r, _, b, a) in enumerate(pixels) if a > 80 and b > r]
    assert max(waiting) <= min(sung)


def test_zero_duration_highlight_is_complete_at_its_start():
    span = HighlightPass(TimeSpan(1, 1), Region(10, 30))
    assert span.front(0.99) == 10
    assert span.front(1) == span.front(2) == 30
    assert span.arrival(10) == span.arrival(30) == 1
    highlight = Highlight("instant", 0, (span,), StatePatch(fill=RED))
    assert highlight.regions(0.99) == ()
    assert highlight.regions(1) == (Region(10, 30),)


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_rendered_priority_has_one_alpha_contribution(strategy):
    doc, line = source()
    original = doc.dumps()
    red, blue = highlights(line)
    whole = red.passes[0].region
    span = HighlightPass(TimeSpan(1, 1.1), whole)
    red = replace(red, passes=(span,))
    blue = replace(blue, passes=(span,), end="hold")

    def pixels(mode, chosen, method):
        decorated = LyricHighlights(
            highlights=chosen, mode=mode, strategy=method
        )(line)
        scene = Scene(doc, replace_records={len(doc.records) - 1}).add(decorated)
        result = scene.compile(budget=BUDGET)
        assert all(
            origin is not None and origin.sources for _, origin in result.event_origins
        )
        assert scene.compile(budget=BUDGET).document.dumps() == result.document.dumps()
        frame = rasterize(result.document.dumps(), 1500, (96, 64))
        return tuple(tuple(frame.rgba[i : i + 4]) for i in range(0, len(frame.rgba), 4))

    priority = pixels("priority", (red, blue), strategy)
    union = pixels("union", (red, replace(blue, paint=red.paint)), strategy)
    layered = pixels("layer", (red, blue), "clip")
    index = max(range(len(priority)), key=lambda i: priority[i][3])
    # Fully covered glyph interiors: one half-opacity contribution versus two.
    assert priority[index][:3] == (0, 0, 255)
    assert 126 <= priority[index][3] <= 129
    assert union[index][:3] == (255, 0, 0)
    assert 126 <= union[index][3] <= 129
    # Blue(.5) over red(.5): alpha .75, unpremultiplied RGB (1/3, 0, 2/3).
    assert layered[index] == pytest.approx((85, 0, 170, 191), abs=2)
    assert doc.dumps() == original


def test_sweep_cannot_silently_repaint_only_one_highlight_contribution():
    from kara_templater import LyricSweep

    _, line = source()
    decorated = LyricHighlights(highlights=highlights, mode="priority")(line)
    with pytest.raises(ValueError, match="compose existing material/highlight"):
        LyricSweep(fill=RED)(decorated)


def test_clip_glow_is_separate_layers_with_shared_character_motion():
    from kara_templater import Glow, GlowFunction

    doc, line = source()
    red = replace(
        highlights(line)[0],
        paint=StatePatch(fill=RED),
        glow=Glow(BLUE, blur=2, border=1),
    )
    decorated = LyricHighlights(
        highlights=(red,), glow=Glow(BLUE, blur=2, border=1)
    )(line)
    target = decorated.query("character")[0]
    assert any(identity.endswith("/glow") for identity in target.aliases)
    assert any("/highlight:red" in identity for identity in target.aliases)
    animated = decorated.bind(LyricRule("character", "singing", Jump()))
    scene = Scene(doc, replace_records={len(doc.records) - 1}).add(animated)
    evaluator = scene.evaluator()
    for identity in target.aliases:
        assert (
            evaluator.at(identity, 1.5).position
            == evaluator.at(target.node_id, 1.5).position
        )
    result = scene.compile(budget=BUDGET)
    assert all(report.strategy != "coverage" for report in result.objects)
    assert {record.layer for record in result.document.lines if not record.comment} == {
        -1,
        0,
    }
    frame = rasterize(result.document.dumps(), 1500, (96, 64))
    assert any(
        frame.rgba[i + 2] > frame.rgba[i] and frame.rgba[i + 3]
        for i in range(0, len(frame.rgba), 4)
    )
    with pytest.raises(ValueError, match="dynamic glow"):
        LyricHighlights(
            highlights=(red,),
            glow=GlowFunction(lambda state, time: Glow(), max_blur=0, max_border=0),
        )(line)


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_glow_factories_resolve_once_per_target_and_validate_dynamic_strategy(strategy):
    from kara_templater import Glow, GlowFunction

    doc, line = source()
    calls = []

    def choose(line, target):
        calls.append(target.id)
        return Glow(BLUE, border=1, blur=1)

    red = replace(highlights(line)[0], glow=choose)
    decorated = LyricHighlights(
        highlights=(red,), glow=choose, strategy=strategy
    )(line)
    expected = [target.id for target in line.query("character") for _ in range(2)]
    assert calls == expected
    scene = Scene(doc).add(decorated)
    scene.compile(budget=BUDGET)
    assert calls == expected

    def dynamic(line, target):
        return GlowFunction(lambda state, time: Glow(), max_blur=0, max_border=0)

    with pytest.raises(ValueError, match="dynamic glow"):
        LyricHighlights(highlights=(replace(red, glow=dynamic),))(line)


def test_explicit_target_selected_before_painting_uses_current_aliases():
    doc, line = source()
    selected = line.query("character")[0]
    decorated = LyricHighlights(highlights=highlights)(line)
    current = decorated.query("character")[0]
    assert current.aliases
    animated = decorated.bind(LyricRule(selected, "singing", Jump()))
    evaluator = Scene(doc).add(animated).evaluator()
    baseline = Scene(doc).add(decorated).evaluator()
    for identity in (current.node_id, *current.aliases):
        assert evaluator.at(identity, 1.5).position == baseline.at(
            identity, 1.5
        ).position + Vec2(0, -12)


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
def test_delayed_highlight_copy_reserves_and_renders_the_same_interval(strategy):
    doc, line = source()
    original = doc.dumps()
    box = line.layout.body.bounds
    effect = LyricHighlights(
        highlights=(
            Highlight(
                "tail",
                0,
                (HighlightPass(TimeSpan(1, 3.5), Region(box.left, box.right)),),
                StatePatch(fill=RED),
            ),
        ),
        strategy=strategy,
    )
    before = effect(line).copy(id="copy", delay=2)
    after = effect(line.copy(id="copy", delay=2))
    assert before.required_display == after.required_display == (TimeSpan(3, 5.5),)
    assert before.lifetime == after.lifetime == Lifetime(2, 5.5)
    assert before.layout.lyrics == after.layout.lyrics == line.layout.lyrics

    outputs = tuple(
        Scene(doc, replace_records={len(doc.records) - 1})
        .add(visual)
        .compile(budget=BUDGET)
        .document.dumps()
        for visual in (before, after)
    )
    for time in (3050, 4250, 5350):
        first = rasterize(outputs[0], time, (96, 64)).rgba
        second = rasterize(outputs[1], time, (96, 64)).rgba
        assert any(first[3::4])
        assert first == second
    assert doc.dumps() == original


def test_fractional_crossing_clip_clocks_preserve_alpha_through_scale_and_fade():
    from tools.validate_clip_seams import subjects

    partitioned, reference = subjects(scale=True, fade=True, strategy="clip")
    budget = SceneBudget(fps=100, max_events=100_000)
    outputs = tuple(
        scene.compile(budget=budget).document.dumps()
        for scene in (partitioned, reference)
    )
    for time in (1010, 1220, 1230, 1500, 1800, 1810, 1990):
        actual = rasterize(outputs[0], time, (160, 120)).rgba
        expected = rasterize(outputs[1], time, (160, 120)).rgba
        assert any(actual[3::4])
        assert actual == expected


def test_fractional_coverage_partition_matches_unsplit_alpha_exactly():
    from tools.validate_clip_seams import subjects

    scenes = subjects(scale=True, fade=True, strategy="coverage")
    budget = SceneBudget(
        fps=25, max_events=500_000, max_active=100_000, max_bytes=128 * 1024 * 1024
    )
    outputs = tuple(scene.compile(budget=budget).document.dumps() for scene in scenes)
    for ms in (1120, 1520):
        expected = rasterize(outputs[1], ms, (160, 120)).rgba
        assert any(expected[3::4])
        assert rasterize(outputs[0], ms, (160, 120)).rgba == expected


def test_independent_highlights_keep_pauses_priority_exit_and_disjoint_regions():
    def paused(progress: float) -> float:
        if progress < 0.25:
            return 2 * progress
        if progress <= 0.75:
            return 0.5
        return 0.5 + 2 * (progress - 0.75)

    first = Highlight(
        "red",
        0,
        (
            HighlightPass(TimeSpan(0.1, 0.3), Region(0, 40), rate=paused),
            HighlightPass(TimeSpan(0.5, 0.6), Region(60, 100)),
        ),
        StatePatch(fill=RED),
    )
    second = Highlight(
        "blue",
        0,
        (HighlightPass(TimeSpan(0.2, 0.45), Region(20, 80)),),
        StatePatch(fill=BLUE),
        priority=1,
        end="hide",
    )
    expected = {
        0.15: ("red", None, None, None, None),
        0.25: ("red", "blue", None, None, None),
        0.35: ("red", "blue", "blue", None, None),
        0.45: ("red", "red", None, None, None),
        0.55: ("red", "red", None, "red", None),
        0.65: ("red", "red", None, "red", "red"),
    }
    for time, owners in expected.items():
        resolved = _owners((first, second), time, "priority")
        actual = tuple(
            next(
                (
                    names[0]
                    for region, names in resolved
                    if region.left <= x < region.right
                ),
                None,
            )
            for x in (10, 30, 50, 70, 90)
        )
        assert actual == owners


@pytest.mark.parametrize("strategy", ("clip", "coverage"))
@pytest.mark.parametrize("crop", (False, True))
def test_adjacent_passes_match_whole_sweep_at_handoff_and_after_window_crop(
    strategy, crop
):
    from kara_templater import Glow

    doc, line = source()
    box = line.layout.body.bounds
    middle = box.center
    glow = Glow(RED, blur=2, opacity=0.5)
    common = Highlight(
        "whole",
        0,
        (HighlightPass(TimeSpan(1, 2), Region(box.left, box.right)),),
        StatePatch(fill=RED, opacity=0.5),
        glow=glow,
    )
    pieces = (
        replace(
            common,
            id="left",
            passes=(HighlightPass(TimeSpan(1, 1.5), Region(box.left, middle)),),
        ),
        replace(
            common,
            id="right",
            passes=(HighlightPass(TimeSpan(1.5, 2), Region(middle, box.right)),),
        ),
    )
    outputs = []
    for selected in (pieces, (common,)):
        visual = LyricHighlights(
            highlights=selected, strategy=strategy, glow=glow
        )(line)
        if crop:
            visual = visual.with_display(Lifetime(1.25, 2.25))
        outputs.append(
            Scene(doc, replace_records={len(doc.records) - 1})
            .add(visual)
            .compile(budget=SceneBudget(fps=20, max_events=100_000))
            .document.dumps()
        )
    for time in (1300, 1490, 1500, 1510, 1990, 2000):
        assert (
            rasterize(outputs[0], time, (96, 64)).rgba
            == rasterize(outputs[1], time, (96, 64)).rgba
        )


def test_fill_and_halo_keep_independent_alpha_and_character_origins():
    from kara_templater import Glow

    doc, line = source()
    box = line.layout.body.bounds
    line = replace(line, state=replace(line.state, opacity=0.6))
    decorated = LyricHighlights(
        highlights=(
            Highlight(
                "full",
                0,
                (HighlightPass(TimeSpan(0, 0), Region(box.left, box.right)),),
                StatePatch(fill=RED),
                glow=Glow(RED, blur=2, opacity=0.25),
            ),
        ),
        strategy="clip",
    )(line)
    result = Scene(doc).add(decorated).compile()
    events = [event for event, _ in result.event_origins]
    assert len(events) == 4  # two character fills and their two halos
    halos = [event for event in events if event.effect.endswith("%2Fglow")]
    fills = [event for event in events if event not in halos]
    assert len(halos) == len(fills) == 2
    assert all(r"\alpha&HD9&" in event.text for event in halos)
    assert all(r"\alpha&H66&" in event.text for event in fills)
    origins = [character.object.origin for character in line.layout.body.characters]
    assert all(
        origin is not None and origin in origins for _, origin in result.event_origins
    )
    assert max(event.layer for event in halos) < min(event.layer for event in fills)


def test_union_merges_overlap_without_filling_unpainted_gaps():
    first = Highlight(
        "first",
        0,
        (HighlightPass(TimeSpan(1, 2), Region(0, 100)),),
        StatePatch(fill=RED),
    )
    second = replace(
        first, id="second", passes=(HighlightPass(TimeSpan(1, 2), Region(50, 150)),)
    )
    for time, expected in (
        (1.25, (Region(0, 25), Region(50, 75))),
        (2, (Region(0, 150),)),
    ):
        regions = _owners((first, second), time, "union")
        assert union_regions(tuple(region for region, _ in regions)) == expected
        assert all(len(owners) == 1 for _, owners in regions)


@pytest.mark.parametrize(
    "mode,strategy",
    (
        ("priority", "clip"),
        ("priority", "coverage"),
        ("union", "clip"),
        ("union", "coverage"),
        ("layer", "clip"),
    ),
)
def test_equal_priority_different_unit_paints_remain_independent(mode, strategy):
    doc, _ = source()
    doc.records[-1] = Line(start_time=1000, end_time=2000, text=r"{\k50}A{\k50}B")
    line = LyricLine.from_layout(
        layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 3))
    )
    chosen = tuple(
        Highlight(
            str(index),
            index,
            (HighlightPass(TimeSpan(1, 1), Region(box.left, box.right)),),
            StatePatch(fill=color),
        )
        for index, (unit, color) in enumerate(
            zip(line.layout.lyrics.units, (RED, BLUE), strict=True)
        )
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )
    frames = []
    for order in (chosen, chosen[::-1]):
        decorated = LyricHighlights(
            highlights=order, mode=mode, strategy=strategy
        )(line)
        result = (
            Scene(doc, replace_records={len(doc.records) - 1})
            .add(decorated)
            .compile(budget=BUDGET)
        )
        frames.append(rasterize(result.document.dumps(), 1500, (96, 64)).rgba)
    assert frames[0] == frames[1]
    opaque_colors = {
        tuple(frames[0][i : i + 3])
        for i in range(0, len(frames[0]), 4)
        if frames[0][i + 3] == 255
    }
    assert {(255, 0, 0), (0, 0, 255)} <= opaque_colors
