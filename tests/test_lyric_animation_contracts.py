"""Material animation diagnostics and clocks use the common object contracts."""

from dataclasses import replace

import pytest
from test_lyric_line import subject

from kara_templater import (
    BLUE,
    RED,
    Color,
    LyricRule,
    Scene,
    SceneBudget,
    SceneCompileError,
    SceneReferenceError,
    StateFunction,
    StatePatch,
    Timeline,
    Tween,
    VisualState,
)


def test_lyric_material_conflicts_are_explicit_in_both_declaration_orders():
    _, line = subject()
    first = LyricRule("character", "singing", Tween(StatePatch(fill=RED)))
    second = LyricRule("character", "singing", Tween(StatePatch(fill=BLUE)))
    for rules in ((first, second), (second, first)):
        with pytest.raises(ValueError, match="overlapping"):
            line.bind(*rules)
    assert not line.children[0].animations


def test_material_sequence_returns_to_base_and_keeps_its_source_clock():
    document, line = subject()
    sequence = (
        Timeline()
        .play(Tween(StatePatch(border=10)), duration=0.1)
        .wait(0.4)
        .play(Tween(StatePatch(border=2)), duration=0.2)
        .animation
    )
    animated = line.bind(LyricRule("character", "singing", sequence, hold=False))
    evaluator = Scene(document).add(animated).evaluator()
    target = line.query("character")[0]
    # The sequence starts at source singing, independent of the display's birth.
    for time, border in ((1.6, 6), (1.05, 6), (1.3, 10), (1.8, 2)):
        assert evaluator.at(target.node_id, time).border == pytest.approx(border)
    assert sequence.duration == pytest.approx(0.7)


def test_material_callbacks_wait_for_budget_preflight():
    document, line = subject()
    calls: list[float] = []

    def color(base: VisualState, progress: float) -> VisualState:
        calls.append(progress)
        return replace(base, fill=RED)

    animated = line.bind(
        LyricRule("character", "singing", StateFunction(color, frozenset(("fill",))))
    )
    scene = Scene(document).add(animated)
    assert not calls
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=SceneBudget(max_events=1))
    assert not calls
    assert scene.compile().event_count
    assert calls


def test_bad_material_callback_reports_its_contract_at_evaluation():
    document, line = subject()
    bad = StateFunction(lambda base, p: 3, frozenset(("fill",)))  # ty: ignore[invalid-argument-type]
    animated = line.bind(LyricRule("character", "singing", bad))
    with pytest.raises(SceneReferenceError, match="return VisualState"):
        Scene(document).add(animated).evaluator().at(
            line.query("character")[0].node_id, 1.25
        )
    with pytest.raises(SceneCompileError, match="return VisualState"):
        Scene(document).add(animated).compile()
    with pytest.raises(TypeError, match="Color"):
        VisualState(fill=3)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="Vec2"):
        VisualState(position=3)  # ty: ignore[invalid-argument-type]
    assert (
        Color(128, 0, 128)
        == Tween(StatePatch(fill=BLUE)).sample(VisualState(fill=RED), 0.5).fill
    )


@pytest.mark.parametrize("preview", (0, 0.6))
def test_material_keyframes_keep_singing_clock_when_exit_extends_display(
    preview: float,
):
    from kara_templater import (
        Document,
        FadeOut,
        Layout,
        Line,
        StateKeyframe,
        Style,
        TimeSpan,
        Track,
        prepare_tracks,
    )

    document = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    document.records.extend(
        (
            Line(text=r"{\k100}A", start_time=1000, end_time=2000),
            Line(text=r"{\k100}B", start_time=2000, end_time=3000),
        )
    )
    original = document.dumps()
    sequence = (
        Timeline()
        .keyframes(
            StateKeyframe(0.5, StatePatch(fill=RED, border=4)),
            StateKeyframe(1, StatePatch(fill=BLUE, border=6)),
        )
        .animation
    )
    material = LyricRule("character", "singing", sequence)
    config = Track(
        id="main",
        layout=Layout(rows=2),
        preview=preview,
        tail=0,
        animations=(material,),
    )
    plain = prepare_tracks(document, tracks=(config,))
    extended = prepare_tracks(
        document,
        tracks=(
            replace(
                config,
                animations=(
                    material,
                    LyricRule("line", "exit", FadeOut(), duration=0.2),
                ),
            ),
        ),
    )
    assert plain.plans[0].placement.display.end == 2
    assert extended.plans[0].placement.display.end == pytest.approx(2.2)
    assert extended.plans[0].input.required.end == pytest.approx(2.2)
    assert extended.plans[0].input.singing == TimeSpan(1, 2)
    assert [plan.placement.row for plan in extended.plans] == [0, 1]
    target = extended.lines[0].query("character")[0]
    assert [(span.start, span.end) for span in target.singing] == [(1, 2)]
    evaluator = extended.evaluator()
    baseline = plain.evaluator()
    for time, color, border in ((2.1, BLUE, 6), (1.5, RED, 4), (2, BLUE, 6)):
        actual = evaluator.at(target.node_id, time)
        assert actual.fill == color
        assert actual.border == border
        if time <= 2:
            assert actual.fill == baseline.at(target.node_id, time).fill
            assert actual.border == baseline.at(target.node_id, time).border
    assert evaluator.at(target.node_id, 2.1).opacity == pytest.approx(0.5)
    # With no extra exit, one row can hand off at 2s. Required exit occupies it.
    prepare_tracks(document, tracks=(replace(config, layout=Layout(rows=1)),))
    with pytest.raises(ValueError, match="occupied"):
        prepare_tracks(
            document,
            tracks=(
                replace(
                    config,
                    layout=Layout(rows=1),
                    animations=(
                        material,
                        LyricRule("line", "exit", FadeOut(), duration=0.2),
                    ),
                ),
            ),
        )
    assert extended.compile().event_count > 0
    assert document.dumps() == original
