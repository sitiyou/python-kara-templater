"""Measured crossing clocks bind ordinary clips and reserve layout occupancy."""

from dataclasses import replace

import pytest

from kara_templater import (
    HighlightArrival,
    HighlightPass,
    Jump,
    LyricRule,
    Scene,
    TimeSpan,
)
from kara_templater.timeline import Region
from tests.test_lyric_highlights import highlights, source


def test_measured_crossings_and_copy_clocks_use_shared_animations():
    doc, line = source()
    red = highlights(line)[0]
    anchor = HighlightArrival(highlights=(red,))
    targets = line.query("character")
    first, second = (anchor(line, target)[0] for target in targets)
    assert first.start == 1
    assert first.end == pytest.approx(second.start)
    assert second.end == 2
    assert 1 < second.start < 2
    bound = line.bind(LyricRule("character", anchor, Jump(), hold=False))
    evaluator = Scene(doc).add(bound).evaluator()
    middle = (second.start + second.end) / 2
    assert evaluator.at(targets[1].node_id, middle).position.y == pytest.approx(
        Scene(doc).add(line).evaluator().at(targets[1].node_id, middle).position.y - 12
    )
    clone = line.copy(id="copy", delay=3)
    shifted = anchor(clone, clone.query("character")[1])[0]
    assert shifted == TimeSpan(second.start + 3, second.end + 3)
    assert clone.query("character")[1].singing == targets[1].singing
    fixed = line.bind(LyricRule("character", anchor, Jump(), duration=0.2, hold=False))
    fixed_evaluator = Scene(doc).add(fixed).evaluator()
    plain = Scene(doc).add(line).evaluator()
    box = line.layout.body.bounds
    for target, character in zip(targets, line.layout.body.characters, strict=True):
        start = 1 + (character.bounds.left - box.left) / box.width
        assert fixed_evaluator.at(
            target.node_id, start + 0.1
        ).position.y == pytest.approx(
            plain.at(target.node_id, start + 0.1).position.y - 12
        )
        assert (
            fixed_evaluator.at(target.node_id, start + 0.25).position
            == plain.at(target.node_id, start + 0.25).position
        )


def test_named_first_each_and_repeat_rounds_are_independent_of_paint_priority():
    _, line = source()
    red, blue = highlights(line)
    blue = replace(blue, passes=(replace(red.passes[0], time=TimeSpan(0.5, 1.5)),))
    target = line.query("character")[0]
    anchor = HighlightArrival(highlights=(red, blue))
    assert anchor(line, target)[0].start == 0.5
    assert replace(anchor, selection="each")(line, target)[1].start == 1
    assert replace(anchor, names=frozenset(("red",)))(line, target)[0].start == 1
    repeated = replace(
        red,
        passes=(red.passes[0], replace(red.passes[0], time=TimeSpan(3, 4), round=1)),
    )
    anchor = replace(anchor, highlights=(repeated,))
    assert [s.start for s in anchor(line, target)] == [1, 3]
    assert len(replace(anchor, retrigger=False)(line, target)) == 1
    with pytest.raises(ValueError, match="unknown arrival"):
        replace(anchor, names=frozenset(("missing",)))(line, target)


def test_partition_pause_boundary_uses_enter_and_complete_ownership():
    _, line = source()
    red = highlights(line)[0]
    first, second = line.query("character")
    boundary = line.layout.body.characters[1].bounds.left
    whole = red.passes[0].region
    split = replace(
        red,
        passes=(
            HighlightPass(TimeSpan(1, 1.2), Region(whole.left, boundary)),
            HighlightPass(TimeSpan(1.8, 2), Region(boundary, whole.right)),
        ),
    )
    anchor = HighlightArrival(highlights=(split,))
    assert anchor(line, second)[0].start == 1.8
    assert replace(anchor, threshold="complete")(line, first)[0].start == 1.2
    partial = replace(
        red,
        passes=(
            replace(
                red.passes[0], region=Region(whole.left, boundary / 2 + whole.left / 2)
            ),
        ),
    )
    with pytest.raises(ValueError, match="incomplete character traversal"):
        replace(anchor, highlights=(partial,))(line, first)
    assert replace(anchor, highlights=(partial,), duration=0.2)(line, first) == (
        TimeSpan(1, 1.2),
    )


def test_nonlinear_arrival_requires_declared_inverse_and_checks_range():
    span = HighlightPass(TimeSpan(1, 3), Region(0, 100), rate=lambda t: t * t)
    with pytest.raises(ValueError, match="inverse_rate"):
        span.arrival(25)
    assert replace(span, inverse_rate=lambda p: p**0.5).arrival(25) == 2
    assert span.arrival(101) is None
    with pytest.raises(ValueError, match="0..1"):
        replace(span, inverse_rate=lambda p: 2).arrival(25)


def test_arrival_duration_is_reserved_before_layout_and_factory_runs_once():
    from kara_templater import Track, prepare_tracks

    doc, _ = source()
    calls = []

    def clock(line, target):
        calls.append(target.id)
        return HighlightArrival(
            highlights=highlights, names=frozenset(("red",)), duration=2
        )(line, target)

    scene = prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                preview=0,
                tail=0,
                effects=(LyricRule("character", clock, Jump(), hold=False),),
            ),
        ),
    )
    plan = scene.plans[0]
    assert len(calls) == 2
    assert plan.placement.display.end > 3
    assert plan.input.singing == TimeSpan(1, 2)
    for target in plan.line.query("character"):
        assert scene.evaluator().at(target.node_id, 2.5).opacity == 1


def test_ruby_crossings_map_reading_width_to_body_and_keep_cluster_boundaries():
    from kara_templater import Lifetime, LyricLine, layout_document_lyrics

    doc, _ = source()
    record = doc.lines[-1]
    record.text = r"{\k100}áB|reading"
    line = LyricLine.from_layout(
        layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 3))
    )
    anchor = HighlightArrival(highlights=lambda line: highlights(line)[:1])
    body = tuple(anchor(line, target)[0] for target in line.query("character"))
    ruby = tuple(anchor(line, target)[0] for target in line.query("ruby"))
    assert len(body) == 2  # Combining accent stays in its shaped cluster.
    assert len(ruby) == 7
    assert body[0].start == ruby[0].start == 1
    assert body[-1].end == pytest.approx(2)
    assert ruby[-1].end == pytest.approx(2)
    for before, after in zip(ruby, ruby[1:], strict=False):
        assert before.end == pytest.approx(after.start)


def test_nonlinear_pause_inverse_returns_first_crossing_at_plateau():
    def rate(progress: float) -> float:
        if progress <= 0.2:
            return progress
        if progress <= 0.6:
            return 0.2
        return 0.2 + 2 * (progress - 0.6)

    def inverse(progress: float) -> float:
        return progress if progress <= 0.2 else 0.6 + (progress - 0.2) / 2

    span = HighlightPass(
        TimeSpan(1, 2), Region(0, 100), rate=rate, inverse_rate=inverse
    )
    assert span.arrival(20) == pytest.approx(1.2)
    assert span.arrival(60) == pytest.approx(1.8)
    assert span.front(1.4) == pytest.approx(20)
    assert span.front(1.8) == pytest.approx(60)


def test_reverse_pass_owns_the_suffix_and_reaches_the_last_character_first():
    _, line = source()
    red = highlights(line)[0]
    span = replace(red.passes[0], reverse=True)
    reverse = replace(red, passes=(span,))
    assert reverse.regions(1.5) == (Region(span.region.center, span.region.right),)
    anchor = HighlightArrival(highlights=(reverse,))
    left, right = (anchor(line, target)[0] for target in line.query("character"))
    assert right.start == 1
    assert right.end == pytest.approx(left.start)
    assert left.end == 2
