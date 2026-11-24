"""Typed lyric projections enter the same pipeline without an ASS round trip."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    WHITE,
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    KaraokeEffects,
    KaraokeRows,
    Layout,
    Lifetime,
    Line,
    LyricRule,
    LyricSource,
    Style,
    TextAppearance,
    TextRun,
    Track,
    prepare_tracks,
)
from kara_templater.document_lyrics import (
    DocumentLyrics,
    LyricMapping,
    LyricSegment,
    LyricUnit,
    RubyText,
)
from kara_templater.document_text import DocumentText, SingingSpan
from kara_templater.scene_lyrics import layout_lyrics


def structured():
    appearance = TextAppearance(
        "Default", RED, WHITE, BLUE, BLUE, frozenset(("primary",))
    )
    body = DocumentText(None, (), (TextRun("A|#", 0, 3, appearance),), (), (), ())
    reading = replace(body, runs=(TextRun("ei", 0, 2, appearance),))
    ruby = RubyText(reading, (LyricMapping(0, 2, 0, 2),))
    segments = tuple(
        LyricSegment(SingingSpan(0, 3, start, end, "k"), 0, 3, ruby)
        for start, end in ((1.0003, 1.4456), (2.0007, 2.2234))
    )
    lyrics = DocumentLyrics(
        body, body, (LyricMapping(0, 3, 0, 3),), (LyricUnit(0, 3, segments),)
    )
    return LyricSource.from_lyrics(
        "structured:verse", lyrics, display=Lifetime(0.5, 2.5)
    )


@pytest.mark.parametrize("gap", [0, 0.02, 0.1])
def test_one_reading_holds_body_progress_across_a_rest(gap):
    (unit,) = structured().lyrics.units
    first, second = unit.segments
    second = replace(second, singing=replace(second.singing, start=first.singing.end + gap))
    unit = replace(unit, segments=(first, second))
    assert unit._body_parts() == ((first.singing, 0, 0.5), (second.singing, 0.5, 1))
    assert replace(unit, repeat=True)._body_parts() == ((first.singing, 0, 1), (second.singing, 0, 1))


def document():
    return Document.create(
        width=320,
        height=180,
        styles=(Style(fontname="DejaVu Sans", fontsize=30, shadow=0, outline=0),),
    )


@pytest.mark.parametrize("layout", [None, Layout(rows=2, alignment="alternating")])
def test_chapter_restarts_rotation_without_a_cue(layout):
    doc = document()
    for start in (6000, 8000, 10000, 12000, 14000):
        doc.records.append(Line(start_time=start, end_time=start + 500, text=r"{\k50}A"))
    inputs = tuple(
        LyricSource.from_lyrics(str(i), plan.source.lyrics, display=plan.source.display,
                                chapter="verse" if i < 3 else "chorus")
        for i, plan in enumerate(prepare_tracks(doc, tracks=(Track(id="base"),)).plans)
    )
    def rows(allocator):
        scene = prepare_tracks(document(), inputs=inputs, tracks=(Track(id="main", layout=allocator),))
        return [plan.placement.row for plan in scene.plans]
    assert rows(layout) == [0, 1, 0, 0, 1]
    assert rows(replace(layout or KaraokeRows(), reset_on_lead=False)) == [0, 1, 0, 1, 0]


def test_structured_literal_text_repeats_ruby_and_precision_survive_without_records():
    source = structured()
    doc = document()
    original = doc.dumps()
    scene = prepare_tracks(
        doc,
        inputs=(source,),
        tracks=(
            Track(
                id="main",
                effects=(LyricRule("line", "enter", FadeIn(), duration=0.1),),
            ),
        ),
    )
    line = scene.lines[0]
    assert line.layout.body.record_index is None
    assert line.layout.body.source.text == "A|#"
    assert len(line.query("segment")) == 2
    assert line.query("segment")[0].singing[0].start == 1.0003
    assert line.query("segment")[1].singing[0].end == 2.2234
    assert len(line.layout.ruby) == 2
    assert all(
        character.object.state.fill == RED for character in line.layout.body.characters
    )
    assert not scene.replace_records
    assert doc.dumps() == original
    result = scene.ass.compile()
    assert not any(
        record.effect.startswith("kara:source") for record in result.document.lines
    )
    for report in result.objects:
        assert report.origin is not None
        assert all(ref.item_id == source.id for ref in report.origin.sources)
    regenerated = prepare_tracks(
        result.document,
        inputs=(source,),
        tracks=(
            Track(
                id="main",
                effects=(LyricRule("line", "enter", FadeIn(), duration=0.1),),
            ),
        ),
    ).ass.compile()
    assert regenerated.document.dumps() == result.document.dumps()


def test_same_structured_source_has_independent_views_and_only_ass_sources_are_replaced():
    source = structured()
    doc = document()
    doc.records.append(
        Line(start_time=3000, end_time=4000, text=r"{\k100}ASS", actor="parsed")
    )
    index = len(doc.records) - 1
    scene = prepare_tracks(
        doc,
        inputs=(source,),
        tracks=(
            Track(id="main"),
            Track(id="copy", source=lambda item: item.record_index is None),
        ),
    )
    assert [plan.source.id for plan in scene.plans].count(source.id) == 2
    assert len({line.id for line in scene.lines}) == 3
    assert scene.replace_records == {index}
    assert scene.plans[-1].source.record_index is None
    assert scene.ass.compile().event_count > 0
    with pytest.raises(ValueError, match="duplicate lyric source"):
        prepare_tracks(doc, inputs=(source, source), tracks=(Track(id="main"),))
    with pytest.raises(ValueError, match="without ASS record ownership"):
        prepare_tracks(doc, inputs=(replace(source, record_index=index),), tracks=())


def test_structured_cue_uses_same_measurement_and_occupancy():
    source = structured()
    projection = source.lyrics
    body = replace(projection.body, cues=(CueMarker("lead", "bars"),))
    projection = replace(projection, body=body)
    source = LyricSource.from_lyrics(source.id, projection, display=source.display)
    scene = prepare_tracks(
        document(),
        inputs=(source,),
        tracks=(
            Track(
                id="main",
                layout=Layout(rows=3),
                cues={"bars": CuePreset(factory=BarsCue())},
            ),
        ),
    )
    assert scene.plans[0].input.lead
    assert len(scene.lines[0].query("cue")) == 1
    assert scene.plans[0].placement.display.start <= scene.lines[0].lifetime.start


def test_projection_measurement_does_not_dereference_provenance_indices():
    source = structured()
    lyrics = replace(
        source.lyrics, source=replace(source.lyrics.source, record_index=999)
    )
    measured = layout_lyrics(document(), lyrics, id="external", display=source.display)
    assert measured.body.record_index == 999
    assert measured.body.source.text == "A|#"


def test_invalid_projection_ranges_fail_before_measurement():
    source = structured()
    lyrics = source.lyrics
    malformed = replace(lyrics, units=(replace(lyrics.units[0], start=1),))
    with pytest.raises(ValueError, match="contiguous body"):
        layout_lyrics(document(), malformed, id="invalid", display=source.display)
    body = replace(lyrics.body, runs=(replace(lyrics.body.runs[0], end=4),))
    with pytest.raises(ValueError, match="contiguous decoded"):
        layout_lyrics(
            document(), replace(lyrics, body=body), id="invalid", display=source.display
        )


def test_feathered_wipe_requires_hook(tmp_path) -> None:
    from kara_templater import LyricHighlights, SceneCompileError, StatePatch

    source = structured()
    first = source.lyrics.units[0].segments[0]
    unit = replace(source.lyrics.units[0], segments=(first,))
    projection = replace(source.lyrics, units=(unit,))
    source = LyricSource.from_lyrics("ink", projection, display=source.display)
    recipe = LyricHighlights.from_singing(
        StatePatch(fill=RED), base_paint=StatePatch(fill=BLUE),
        hook_feather=12, edge_duration=0,
    )
    scene = prepare_tracks(document(), inputs=(source,), tracks=(Track(id="ink", effects=(recipe,)),))
    original = scene.objects.copy()
    with pytest.raises(SceneCompileError, match="feathered wipes"):
        scene.ass.compile()
    scene.export(tmp_path / "sweep.hook", fps=24)
    assert all(a is b for a, b in zip(scene.objects, original, strict=True))


@pytest.mark.parametrize(("singing", "exit_effect", "exit_duration"), (
    ("zoom_pulse", "fade", 0.3),
    ("utopia", "utopia", 0.45),
))
def test_strict_preview_keeps_absolute_indices_and_neighbor_placement(
    singing, exit_effect, exit_duration,
):
    doc = document()
    for i in range(32):
        start = 1000 + i * 1500
        doc.records.append(Line(start_time=start, end_time=start + 700, text=r"{\k70}A|a" if i % 3 else r"{\k70}W"))
    inputs = tuple(
        LyricSource.from_lyrics(str(i), plan.source.lyrics, display=plan.source.display, chapter=str(i // 7))
        for i, plan in enumerate(prepare_tracks(doc, tracks=(Track(id="base"),)).plans)
    )
    track = Track(id="indexed", layout=Layout(rows=3), effects=(
        KaraokeEffects(singing=singing, exit=exit_effect, exit_duration=exit_duration),
    ))
    def build(window):
        return prepare_tracks(document(), inputs=inputs, tracks=(track,), preview_interval=window)
    whole = build(None)
    for start in (40.5, 9.5, 22.0, 60.0):
        subset = build((start, start + 2))
        expected = [p for p in whole.plans if p.placement.display.start < start + 2
                    and p.placement.display.end > start]
        assert [(p.line.track_index, p.placement) for p in subset.plans] == [
            (p.line.track_index, p.placement) for p in expected]
