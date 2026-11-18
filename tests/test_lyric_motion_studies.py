"""Reusable motion recipes own geometry; lyric rules own clocks and selection."""

from dataclasses import replace

import pytest

from examples.lyric_studies import EFFECTS, build
from kara_templater import (
    CurveIn,
    Document,
    FadeOut,
    Lifetime,
    Line,
    LyricAnimationContext,
    LyricEcho,
    LyricLine,
    LyricRule,
    ObjectGroup,
    ScalePulse,
    ScatterOut,
    Scene,
    Style,
    Timeline,
    Track,
    Vec2,
    VisualState,
    layout_document_lyrics,
    prepare_tracks,
)
from kara_templater._raster import rasterize


def subject():
    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    doc.records.append(Line(text=r"{\k100}ABC", start_time=1000, end_time=2000))
    layout = layout_document_lyrics(
        doc, len(doc.records) - 1, id="line", display=Lifetime(0, 3)
    )
    return doc, LyricLine.from_layout(layout)


def test_stagger_respects_explicit_order_and_last_exit_boundary():
    doc, line = subject()
    targets = tuple(reversed(line.query("character")))
    bound = line.bind(LyricRule(targets, "exit", FadeOut(), duration=0.3, stagger=0.1))
    evaluator = Scene(doc).add(bound).evaluator()
    for target, start in zip(targets, (2.5, 2.6, 2.7), strict=True):
        assert evaluator.at(target.node_id, start).opacity == 1
        assert evaluator.at(target.node_id, start + 0.15).opacity == pytest.approx(0.5)
        assert evaluator.at(target.node_id, start + 0.3).opacity == 0
    with pytest.raises(ValueError, match="stagger"):
        LyricRule("character", "exit", FadeOut(), duration=0.3, stagger=-0.1)


def test_stagger_reserves_whole_exit_and_does_not_change_source_clocks():
    doc, original = subject()
    scene = prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                tail=0,
                effects=(
                    LyricRule(
                        "character", "exit", FadeOut(), duration=0.3, stagger=0.1
                    ),
                ),
            ),
        ),
    )
    line = scene.plans[0].line
    assert line.lifetime.end == pytest.approx(2.5)
    assert [t.singing for t in line.query("character")] == [
        t.singing for t in original.query("character")
    ]


def test_curve_entrance_preserves_pivot_and_reaches_original_pose():
    base = VisualState(
        position=Vec2(10, 20), scale=Vec2(2, 3), rotation=35, opacity=0.4
    )
    pivot = Vec2(4, 5)
    animation = CurveIn(pivot=pivot)
    midpoint = animation.sample(base, 0.5)
    expected = base.transform.apply(pivot) + Vec2(0, -12)
    actual = midpoint.transform.apply(pivot)
    assert (actual.x, actual.y) == pytest.approx((expected.x, expected.y))
    assert midpoint.opacity == pytest.approx(0.2)
    assert midpoint.rotation == 29
    assert animation.sample(base, 1) == base


def test_scatter_is_seeded_target_specific_and_relative_to_incoming_state():
    doc, line = subject()
    targets = line.query("character")
    effect = ScatterOut(seed=42)
    bound = line.bind(LyricRule("character", "after_singing", effect, duration=0.5))
    evaluator = Scene(doc).add(bound).evaluator()
    for target in targets:
        animation = effect(LyricAnimationContext(line, target, None, 0.5))
        base = VisualState(opacity=0.3)
        assert animation.sample(base, 0.5) == effect(LyricAnimationContext(line, target, None, 0.5)).sample(base, 0.5)
        assert animation.sample(base, 0.5).opacity == pytest.approx(0.15)
        end = max(span.end for span in target.singing)
        before = evaluator.at(target.node_id, end).transform.apply(target.center)
        after = evaluator.at(target.node_id, end + 0.5).transform.apply(target.center)
        assert abs(after.x - before.x) <= 24
        assert -36 * 1.3 <= after.y - before.y <= -36 * 0.7
    assert effect(LyricAnimationContext(line, targets[0], None, 0.5)).sample(VisualState(), 1) != effect(LyricAnimationContext(line, targets[1], None, 0.5)).sample(VisualState(), 1)


def test_echo_accepts_shared_animation_sequence_and_pre_onset_delay():
    doc, line = subject()
    sequence = (
        Timeline().play(CurveIn(), duration=0.2).play(FadeOut(), duration=0.4).animation
    )
    effect = LyricEcho(
        count=1, offset=Vec2(), delay=-0.2, duration=0.6, animation=sequence
    )
    decorated = effect(line)

    def children(group):
        for child in group.children:
            if isinstance(child, ObjectGroup):
                yield from children(child)
            else:
                yield child

    copies = [node for node in children(decorated) if "/echo:" in node.id]
    assert len(copies) == 3
    evaluator = Scene(doc).add(decorated).evaluator()
    for target, copy in zip(line.query("character"), copies, strict=True):
        start = target.singing[0].start - 0.2
        assert copy.lifetime.start == pytest.approx(start)
        assert evaluator.at(copy.id, start + 0.2).opacity == pytest.approx(0.35)
        assert evaluator.at(copy.id, start + 0.4).opacity == pytest.approx(0.175)
    assert decorated.query("character") == line.query("character")
    assert isinstance(sequence.clips[0].animation, CurveIn)
    assert sequence.clips[0].animation.pivot is None
    with pytest.raises(ValueError, match="Scene zero"):
        replace(effect, delay=-2)(line)


def test_singing_stagger_is_explicit_shift_not_a_new_duration():
    _, line = subject()
    bindings = line._resolve(
        (LyricRule("character", "singing", ScalePulse(), stagger=0.1),)
    )
    for index, binding in enumerate(bindings):
        assert binding.offset == pytest.approx(index * 0.1)
        assert binding.duration == pytest.approx(
            binding.target.singing[0].end - binding.target.singing[0].start
        )


@pytest.mark.parametrize("effect", EFFECTS)
@pytest.mark.parametrize("japanese", (False, True))
def test_studies_keep_common_source_timing_and_independent_harmony(effect, japanese):
    scene = build(effect, japanese=japanese)
    assert [plan.track_id for plan in scene.plans] == ["main", "harmony"]
    main, harmony = (plan.line for plan in scene.plans)
    spans = main.query("syllable")
    assert [(t.singing[0].start, t.singing[-1].end) for t in spans] == [
        (1, 1.25),
        (1.25, 1.5),
        (1.5, 2.5),
        (2.5, 4.5),
    ]
    assert harmony.query("line")[0].singing[0].start == 2.5
    assert bool(main.query("ruby")) == japanese
    result = scene.compile(native_tweens=True)
    assert result.event_count > 0
    assert result.peak_active < 300


def test_particle_writing_reveals_hidden_text_while_sparkles_keep_unsung_text():
    writing = build("writing").compile(native_tweens=True).document.dumps()
    sparkles = build("sparkles").compile(native_tweens=True).document.dumps()
    assert not any(rasterize(writing, 900, (640, 360)).rgba[3::4])
    assert any(rasterize(sparkles, 900, (640, 360)).rgba[3::4])
    assert any(rasterize(writing, 2200, (640, 360)).rgba[3::4])


def test_echo_study_rises_continuously_while_original_baseline_stays_put():
    scene = build("echo")
    line = scene.plans[0].line

    def copies(group):
        for child in group.children:
            if isinstance(child, ObjectGroup):
                yield from copies(child)
            elif "/echo:" in child.id:
                yield child

    echo = next(copies(line))
    target = line.query("character")[0]
    evaluator = scene.evaluator()
    start = echo.lifetime.start
    initial = evaluator.at(echo.id, start)
    middle = evaluator.at(echo.id, start + 0.3)
    assert middle.position.y == pytest.approx(initial.position.y - 27)
    assert middle.scale == initial.scale
    assert (
        evaluator.at(target.node_id, start).position
        == evaluator.at(target.node_id, start + 0.3).position
    )
