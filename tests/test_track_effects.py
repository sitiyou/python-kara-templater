"""One effect recipe shares preparation, layout reservation and final aliases."""

import pytest

from kara_templater import (
    CYAN,
    Document,
    DriftOut,
    Line,
    LyricAnimationContext,
    LyricEcho,
    LyricHighlights,
    LyricRule,
    ScalePulse,
    StatePatch,
    Track,
    build_lyric_scene,
)


def test_mixed_effects_resolve_once_and_bind_after_decoration():
    document = Document.create(width=640, height=360)
    document.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    original = document.dumps()
    calls = []

    def pulse(timing: LyricAnimationContext):
        calls.append("timing")
        return ScalePulse(peak=1.1)

    def paint(line):
        calls.append("paint")
        return LyricHighlights.from_timing(StatePatch(fill=CYAN))(line)

    def echo(line):
        calls.append("echo")
        assert line.query("character")[0].aliases
        return LyricEcho(count=1, duration=1.9)(line)

    scene = build_lyric_scene(document, tracks=(Track(id="main", effects=(
        paint,
        LyricRule("character", "timing", pulse),
        echo,
        LyricRule("character", "after_timing", DriftOut(), offset=0.14, duration=0.56),
    )),))
    assert calls == ["timing", "paint", "echo"]
    assert scene.plans[0].layout_request.required_display.end == pytest.approx(2.9)
    target = scene.lines[0].query("character")[0]
    evaluator = scene.evaluator()
    peak = evaluator.at(target.node_id, 1.5)
    for alias in target.aliases:
        assert evaluator.at(alias, 1.5).transform == peak.transform
        assert evaluator.at(alias, 2.42).opacity == pytest.approx(0.5)
    assert document.dumps() == original
    assert calls == ["timing", "paint", "echo"]


@pytest.mark.parametrize("decorate_first", [False, True])
def test_custom_schedule_reserves_exit_and_binds_final_materials(decorate_first):
    document = Document.create(width=640, height=360)
    document.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    original = document.dumps()
    calls = []

    def motion(timing: LyricAnimationContext):
        calls.append(timing.target.id)
        return DriftOut()

    def custom(line):
        return line.schedule(LyricRule(
            "character", "after_timing", motion, offset=0.14, duration=0.56,
        ))

    paint = LyricHighlights.from_timing(StatePatch(fill=CYAN))
    effects = (paint, custom) if decorate_first else (custom, paint)
    scene = build_lyric_scene(document, tracks=(Track(id="main", effects=effects, tail=0),))
    target = scene.lines[0].query("character")[0]
    assert calls == [target.id]
    assert scene.plans[0].layout_request.required_display.end == pytest.approx(2.7)
    assert scene.lines[0].lifetime.end == pytest.approx(2.7)
    assert target.aliases
    evaluator = scene.evaluator()
    for name in (target.node_id, *target.aliases):
        assert evaluator.at(name, 2.14).opacity == pytest.approx(1)
        assert evaluator.at(name, 2.42).opacity == pytest.approx(0.5)
    assert document.dumps() == original
    assert calls == [target.id]


def test_scheduled_copy_shifts_visual_clocks_once():
    from kara_templater import Lifetime, LyricLine, layout_lyrics

    document = Document.create(width=640, height=360)
    document.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    line = LyricLine.from_layout(layout_lyrics(document, document.lyrics_at(-1), id="row", display=Lifetime(1, 2)))
    line = line.schedule(LyricRule(
        "character", "after_timing", DriftOut(), duration=0.5,
    ))
    copied = line.copy(id="copy", delay=0.3)
    assert copied._scheduled[0].at == pytest.approx(2.3)
    assert copied._scheduled[0].target == copied.query("character")[0]
    assert line._scheduled[0].at == pytest.approx(2)


def test_custom_display_anchors_use_final_reserved_window():
    from kara_templater import FadeIn, FadeOut, Layout

    document = Document.create(width=640, height=360)
    document.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    allocations = []

    class Inspect(Layout):
        def allocate(self, lines, context):
            allocations.append(lines)
            return super().allocate(lines, context)

    def custom(line):
        return line.schedule(
            LyricRule("line", "enter", FadeIn(), duration=0.8),
            LyricRule("line", "exit", FadeOut(), duration=0.2),
        )

    scene = build_lyric_scene(document, tracks=(Track(
        id="main", layout=Inspect(), preview=0, tail=0,
        effects=(custom, LyricEcho(count=1, duration=2)),
    ),))
    assert len(allocations) == 1
    line = scene.lines[0]
    assert line.lifetime.start == pytest.approx(0.2)
    assert line.lifetime.end == pytest.approx(3)
    evaluator = scene.evaluator()
    assert evaluator.at(line.id, 0.6).opacity == pytest.approx(0.5)
    assert evaluator.at(line.id, 2.9).opacity == pytest.approx(0.5)
    assert not line._scheduled


def test_earlier_local_clip_keeps_clock_and_renders():
    from dataclasses import replace

    from kara_templater import (
        AnimationClip,
        AnimationSequence,
        FadeIn,
        Lifetime,
        PathObject,
        Timeline,
        VectorPath,
    )
    node = PathObject(
        id="dot", lifetime=Lifetime(0.2, 2), clock_start=1,
        path=VectorPath.rectangle(12, 12),
        animations=(AnimationClip(-0.8, 0.8, FadeIn()),),
    )
    assert node.time_origin == 1
    with pytest.raises(ValueError, match="absolute time zero"):
        replace(node, animations=(AnimationClip(-1.1, 0.5, FadeIn()),))
    with pytest.raises(ValueError, match="nonnegative"):
        Timeline().play(FadeIn(), at=-0.1, duration=1)
    with pytest.raises(ValueError, match="nonnegative"):
        AnimationSequence((AnimationClip(-0.1, 0.5, FadeIn()),), duration=1)


def test_custom_schedule_keeps_repeated_timing_and_zero_notes():
    document = Document.create(width=640, height=360)
    document.records.append(Line(
        start_time=1000, end_time=2000, text=r"{\k25}A{\k25}{\k25}#{\k0}B",
    ))

    def custom(line):
        return line.schedule(
            LyricRule("character", "timing", ScalePulse(peak=1.1)),
            LyricRule("character", "after_timing", DriftOut(), duration=0.5),
        )

    scene = build_lyric_scene(document, tracks=(Track(id="main", effects=(custom,)),))
    target = scene.lines[0].query("character")[0]
    evaluator = scene.evaluator()
    assert evaluator.at(target.node_id, 1.125).scale.x == pytest.approx(1.1)
    assert evaluator.at(target.node_id, 1.625).scale.x == pytest.approx(1.1)
    assert evaluator.at(target.node_id, 1.5).opacity == 1
    assert evaluator.at(target.node_id, 2).opacity == pytest.approx(0.5)
    assert scene.plans[0].layout_request.required_display.end == pytest.approx(2.25)
