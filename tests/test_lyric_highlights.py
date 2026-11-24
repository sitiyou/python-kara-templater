"""Named highlight policies retain ownership, alpha and shared animation binding."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    AssBudget,
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
    StatePatch,
    Style,
    Vec2,
    layout_document_lyrics,
)
from kara_templater.geometry import Region, union_regions
from kara_templater.lyrics.highlights import _resolve_region_owners
from kara_templater.scene_animation import TimeSpan

BUDGET = AssBudget(max_events=40_000, max_active=10_000)


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
    priority = _resolve_region_owners((red, blue), 1.5, "priority")
    layered = _resolve_region_owners((red, blue), 1.5, "layer")
    assert _resolve_region_owners((blue, red), 1.5, "priority") == priority
    assert _resolve_region_owners((blue, red), 1.5, "layer") == layered
    assert priority[0][1] == ("blue",)
    assert layered[0][1] == ("red", "blue")
    assert _resolve_region_owners((red, blue), 1.9, "priority")[0][1] == ("red",)
    with pytest.raises(ValueError, match="identical appearance"):
        _resolve_region_owners((red, blue), 1.5, "union")
    same = replace(blue, paint=red.paint)
    assert _resolve_region_owners((red, same), 1.5, "union")[0][1] == ("red",)
    with pytest.raises(ValueError, match="equal-priority"):
        _resolve_region_owners((red, replace(blue, priority=0)), 1.5, "priority")
    with pytest.raises(ValueError, match="distinct priorities"):
        _resolve_region_owners((red, replace(blue, priority=0)), 1.5, "layer")


def test_highlighted_line_uses_common_scene_and_target_aliases_follow_animation(
):
    doc, line = source()
    decorated = LyricHighlights(
        highlights=highlights, mode="priority"
    )(line)
    target = decorated.query("character")[0]
    assert len(target.aliases) >= 2
    assert len(set(target.aliases)) == len(target.aliases)
    animated = decorated.bind(LyricRule("character", "timing", Jump()))
    scene = Scene(doc).add(animated)
    evaluator = scene.evaluator()
    for identity in target.aliases:
        assert (
            evaluator.at(identity, 1.5).position
            == evaluator.at(target.node_id, 1.5).position
        )
    copied = animated.copy(id="copy", delay=3)
    copied_target = copied.query("character")[0]
    assert all(identity.startswith("copy/") for identity in copied_target.aliases)
    assert copied.query("line", "character") == copied.query("line")


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


def test_zero_duration_highlight_is_complete_at_its_start():
    span = HighlightPass(TimeSpan(1, 1), Region(10, 30))
    assert span.front(0.99) == 10
    assert span.front(1) == span.front(2) == 30
    assert span.arrival(10) == span.arrival(30) == 1
    highlight = Highlight("instant", 0, (span,), StatePatch(fill=RED))
    assert highlight.regions(0.99) == ()
    assert highlight.regions(1) == (Region(10, 30),)


def test_clip_glow_is_separate_layers_with_shared_character_motion():
    from kara_templater import Glow

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
    animated = decorated.bind(LyricRule("character", "timing", Jump()))
    scene = Scene(doc, replace_records={len(doc.records) - 1}).add(animated)
    evaluator = scene.evaluator()
    for identity in target.aliases:
        assert (
            evaluator.at(identity, 1.5).position
            == evaluator.at(target.node_id, 1.5).position
        )


def test_glow_factories_resolve_once_per_target():
    from kara_templater import Glow

    doc, line = source()
    calls = []

    def choose(line, target):
        calls.append(target.id)
        return Glow(BLUE, border=1, blur=1)

    red = replace(highlights(line)[0], glow=choose)
    LyricHighlights(
        highlights=(red,), glow=choose
    )(line)
    expected = [target.id for target in line.query("character") for _ in range(2)]
    assert calls == expected



def test_explicit_target_selected_before_painting_uses_current_aliases():
    doc, line = source()
    selected = line.query("character")[0]
    decorated = LyricHighlights(highlights=highlights)(line)
    current = decorated.query("character")[0]
    assert current.aliases
    animated = decorated.bind(LyricRule(selected, "timing", Jump()))
    evaluator = Scene(doc).add(animated).evaluator()
    baseline = Scene(doc).add(decorated).evaluator()
    for identity in (current.node_id, *current.aliases):
        assert evaluator.at(identity, 1.5).position == baseline.at(
            identity, 1.5
        ).position + Vec2(0, -12)


def test_delayed_highlight_copy_reserves_and_renders_the_same_interval():
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
    )
    before = effect(line).copy(id="copy", delay=2)
    after = effect(line.copy(id="copy", delay=2))
    assert before.required_display == after.required_display == (TimeSpan(3, 5.5),)
    assert before.lifetime == after.lifetime == Lifetime(2, 5.5)
    assert before.layout.lyrics == after.layout.lyrics == line.layout.lyrics

    assert doc.dumps() == original


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
        resolved = _resolve_region_owners((first, second), time, "priority")
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
        regions = _resolve_region_owners((first, second), time, "union")
        assert union_regions(tuple(region for region, _ in regions)) == expected
        assert all(len(owners) == 1 for _, owners in regions)
