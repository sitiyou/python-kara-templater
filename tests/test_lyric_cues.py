import pytest

from kara_templater import (
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    Scene,
    Style,
    TextCue,
    Vec2,
    bind_lyric_cues,
    layout_document_lyrics,
)


def layout():
    doc = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    doc.records.append(
        Line(text=r"{\k100}AB|!ab{\k100}CD|!cd", start_time=1000, end_time=3000)
    )
    return doc, layout_document_lyrics(
        doc, len(doc.records) - 1, display=Lifetime(0, 4)
    )


def test_ruby_keeps_body_center_offset_during_multiple_reservations_and_releases():
    _, original = layout()
    presets = {
        "lead": CuePreset(factory=BarsCue(width=60), gap=10, keep_space=False),
        "middle": CuePreset(
            factory=BarsCue(width=40), gap=10, keep_space=False, trigger=2
        ),
    }
    markers = (
        CueMarker("a", "lead", 0),
        CueMarker("b", "middle", 1),
        CueMarker("c", "lead", 2),
    )
    bound = bind_lyric_cues(original, presets, markers=markers)
    assert bound.lyrics.body.singing == original.body.singing
    times = (0, 0.9, 1, 1.005, 1.5, 2, 2.005, 3.9)
    for ruby, before in zip(bound.lyrics.ruby, original.ruby, strict=True):
        assert ruby.layout.singing == before.layout.singing
        unit = original.lyrics.units[ruby.unit_index]
        baseline = original.body.range_bounds(unit.start, unit.end).center
        for time in reversed(times):
            body_delta = (
                bound.lyrics.body.range_bounds(unit.start, unit.end, time=time).center
                - baseline
            )
            for actual, expected in zip(
                ruby.layout.characters, before.layout.characters, strict=True
            ):
                assert actual.object.at(time).position.x - expected.object.at(
                    time
                ).position.x == pytest.approx(body_delta)
                assert (
                    actual.object.at(time).position.y
                    == expected.object.at(time).position.y
                )
                assert actual.object.origin == expected.object.origin
                assert actual.object.lifetime == expected.object.lifetime
    assert (
        bound.lyrics.ruby[0].layout.characters[0].object.state.position.x
        - original.ruby[0].layout.characters[0].object.state.position.x
        == 95
    )
    scene = Scene(Document.create()).add(bound.group())
    assert scene.compile().document.dumps() == scene.compile().document.dumps()


def test_independent_cue_does_not_move_body_or_ruby_and_no_inline_group_works():
    _, original = layout()
    bound = bind_lyric_cues(
        original,
        {"numbers": CuePreset(factory=TextCue(), position=Vec2(20, 30))},
        markers=(CueMarker("counter", "numbers", 0, "independent"),),
    )
    assert bound.lyrics.body.characters == original.body.characters
    assert bound.lyrics.ruby == original.ruby
    assert bound.group().lifetime == original.body.lifetime
    assert len(bound.group().children) == len(original.group().children)
    assert bound.independent[0].state.position == Vec2(20, 30)


def test_input_marker_and_projected_python_marker_are_equivalent():
    doc, original = layout()
    event = doc.lines[0]
    event.text = CueMarker("intro", "bars").markup() + event.text
    imported = layout_document_lyrics(
        doc, len(doc.records) - 1, display=original.body.lifetime
    )
    presets = {"bars": CuePreset(factory=BarsCue(), keep_space=False)}
    from_input = bind_lyric_cues(imported, presets)
    from_code = bind_lyric_cues(
        original, presets, markers=(CueMarker("intro", "bars"),)
    )
    assert (
        Scene(Document.create()).add(from_input.group()).compile().document.dumps()
        == Scene(Document.create()).add(from_code.group()).compile().document.dumps()
    )
    scene = Scene(doc).add(from_input.group())
    scene.replace_source(len(doc.records) - 1)
    result = scene.compile()
    assert all(
        "kara:v1 cue" not in line.text
        for line in result.document.lines
        if not line.comment
    )


def test_releasing_cue_before_lyric_birth_is_shared_and_group_preserves_cue_lifetime():
    doc, original = layout()
    original = layout_document_lyrics(doc, len(doc.records) - 1)
    bound = bind_lyric_cues(
        original,
        {"bars": CuePreset(factory=BarsCue(), keep_space=False)},
        markers=(CueMarker("intro", "bars"),),
    )
    assert bound.group().lifetime == Lifetime(0, 3)
    assert bound.lyrics.body.lifetime == Lifetime(1, 3)
    for ruby, before in zip(bound.lyrics.ruby, original.ruby, strict=True):
        assert (
            ruby.layout.characters[0].object.at(1).position
            == before.layout.characters[0].object.at(1).position
        )


def test_volume_flashes_as_a_group_then_fills_and_clears_at_onset():
    from examples.karaoke_signals import build
    from kara_templater import Color, ObjectGroup

    scene = build()
    cue = next(n for n in scene.plans[0].line.children if "/cue:" in n.id)
    assert isinstance(cue, ObjectGroup)
    (group,) = cue.children
    assert isinstance(group, ObjectGroup)
    evaluator = scene.evaluator()
    for time, covered, opacity in (
        (2.9, 3, 1),
        (2.3, 1, 1),
        (0.38, 0, 0),
        (0.75, 0, 1),
    ):
        bars = [n for n in group.children if n.lifetime.contains(time)]
        assert len(bars) == 3
        assert sum(n.state.fill == Color(255, 90, 111) for n in bars) == covered
        assert all(
            evaluator.at(n.id, time).opacity == pytest.approx(opacity) for n in bars
        )
    assert group.lifetime.end == 3
    assert all(not n.lifetime.contains(3) for n in group.children)


@pytest.mark.parametrize(
    "shape", ("circle", "square", "rounded", "star", "note8", "note16", "notepair")
)
def test_signal_shapes_compile_on_nonuniform_steps(shape):
    from kara_templater import SignalCue

    doc, lyrics = layout()
    bound = bind_lyric_cues(
        lyrics,
        {"signal": CuePreset(factory=SignalCue(shape=shape), steps=(0, 0.25, 1))},
        markers=(CueMarker("intro", "signal"),),
    )
    right, left = bound.inline[0].children
    assert right.state.position.x > left.state.position.x
    assert (right.lifetime.end, left.lifetime.end) == (0.25, 1)
    assert Scene(doc).add(bound.group()).compile().event_count > 0


def test_signal_countdown_toward_lyric_preserves_step_times():
    from kara_templater import SignalCue

    _, lyrics = layout()
    preset = CuePreset(factory=SignalCue(direction="left_to_right"), steps=(0, 0.25, 1))
    bound = bind_lyric_cues(
        lyrics, {"signal": preset}, markers=(CueMarker("intro", "signal"),)
    )
    left, right = bound.inline[0].children
    assert left.state.position.x < right.state.position.x
    assert (left.lifetime.end, right.lifetime.end) == (0.25, 1)


def test_empty_leading_k_advances_cue_trigger_without_a_dummy_syllable():
    from kara_templater import VolumeCue

    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.append(Line(text=r"{\k500}{\kf100}Leave", start_time=0, end_time=6000))
    lyrics = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 6))
    bound = bind_lyric_cues(
        lyrics,
        {"lead": CuePreset(factory=VolumeCue(), lead=4, duration=4)},
        markers=(CueMarker("one", "lead"),),
    )
    assert bound.inline[0].lifetime == Lifetime(1, 5)


def test_auto_sized_signals_use_font_at_marker_and_explicit_sizes_win():
    from kara_templater import SignalCue, VolumeCue

    doc = Document.create(styles=(
        Style(name="Main", fontname="DejaVu Sans", fontsize=80),
        Style(name="Harmony", fontname="DejaVu Sans", fontsize=40),
    ))
    doc.records.append(Line(style="Main", text=r"{\k50}A{\rHarmony\k50}B", start_time=1000, end_time=2000))
    lyrics = layout_document_lyrics(doc, len(doc.records) - 1)
    cues = bind_lyric_cues(
        lyrics,
        {"lead": CuePreset(factory=VolumeCue()), "lamp": CuePreset(factory=SignalCue()),
         "fixed": CuePreset(factory=SignalCue(size=24))},
        markers=(CueMarker("a", "lead", 0), CueMarker("b", "lamp", 1), CueMarker("c", "fixed", 2)),
    )
    assert [cue.content.height for cue in cues.cues] == [34, 17, 24]
