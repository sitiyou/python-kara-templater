"""Lyric ownership and edits use the normal Scene coverage strategy."""

from dataclasses import replace

import pytest

from kara_templater import (
    PINK,
    Document,
    FadeOut,
    Highlight,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    Region,
    SceneBudget,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Tween,
    Vec2,
    prepare_tracks,
)

BUDGET = SceneBudget(fps=10, max_events=100_000, max_active=10_000)


def source():
    doc = Document.create(
        width=160,
        height=100,
        styles=(Style(fontname="DejaVu Sans", fontsize=20, shadow=0, outline=0),),
    )
    doc.records.append(Line(text=r"{\c&HFFFF00&\k20}AB", start_time=0, end_time=400))
    return doc


def paint(line: LyricLine) -> LyricLine:
    return LyricHighlights(
        highlights=tuple(
            Highlight(
                str(index),
                index,
                tuple(
                    HighlightPass(
                        TimeSpan(segment.singing.start, segment.singing.end),
                        Region(box.left, box.right),
                        round=round_id,
                    )
                    for round_id, segment in enumerate(unit.segments)
                ),
                StatePatch(fill=PINK),
            )
            for index, unit in enumerate(line.layout.lyrics.units)
            for box in (line.layout.body.range_bounds(unit.start, unit.end),)
        ),
        strategy="coverage",
    )(line)


def track(**changes):
    return replace(
        Track(
            id="lyrics",
            layout=Layout(position=Vec2(30, 40)),
            preview=0,
            tail=0,
            effects=(paint,),
        ),
        **changes,
    )


def test_preparation_defers_animation_callbacks_and_preserves_source():
    calls = []
    config = track(
        effects=(*((
            LyricRule(
                "syllable",
                "singing",
                Tween(
                    StatePatch(scale=Vec2(1.2, 1.2)),
                    rate=lambda t: calls.append(t) or t,
                ),
            ),
        )), paint,), 
    )
    doc = source()
    before = doc.dumps()
    scene = prepare_tracks(doc, tracks=(config,))
    assert not calls
    assert doc.dumps() == before
    assert scene.lines[0].coverage is not None
    assert scene.lines[0].coverage.partitions


def test_unselected_sources_are_preserved():
    document = source()
    unselected = prepare_tracks(
        document, tracks=(track(source=lambda source: False),)
    ).ass.compile(budget=BUDGET)
    assert unselected.event_count == 0
    assert any(
        not event.comment and event.text == document.lines[0].text
        for event in unselected.document.lines
    )


def test_sweep_hold_and_exit_extend_display_without_retiming_source():
    document = source()
    document.lines[0].start_time = 1000
    document.lines[0].end_time = 1200
    original = document.dumps()
    plain = prepare_tracks(document, tracks=(track(),))
    extended = prepare_tracks(
        document,
        tracks=(
            track(
                preview=0.2,
                effects=(*((LyricRule("line", "exit", FadeOut(), duration=0.2),)), paint,), 
            ),
        ),
    )
    assert (
        extended.lines[0].query("character")[0].singing
        == plain.lines[0].query("character")[0].singing
    )
    assert extended.plans[0].placement.display.end == pytest.approx(1.4)
    assert extended.plans[0].input.required.end == pytest.approx(1.4)
    assert document.dumps() == original


