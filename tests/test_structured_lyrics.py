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


def document():
    return Document.create(
        width=320,
        height=180,
        styles=(Style(fontname="DejaVu Sans", fontsize=30, shadow=0, outline=0),),
    )


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
    result = scene.compile()
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
    ).compile()
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
    assert scene.compile().event_count > 0
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


def test_flat_sweep_exports_ass_bands_and_preserves_hook_scene() -> None:
    from kara_templater import LyricHighlights, StatePatch

    source = structured()
    first = source.lyrics.units[0].segments[0]
    unit = replace(source.lyrics.units[0], segments=(first,))
    projection = replace(source.lyrics, units=(unit,))
    source = LyricSource.from_lyrics("ink", projection, display=source.display)
    recipe = LyricHighlights.from_singing(
        StatePatch(fill=RED), base_paint=StatePatch(fill=BLUE),
        hook_feather=12, ass_feather_bands=4, edge_duration=0,
    )
    scene = prepare_tracks(document(), inputs=(source,), tracks=(Track(id="ink", effects=(recipe,)),))
    original = scene.objects.copy()
    result = scene.compile(native_tweens=True)
    # The midpoint of each strip uses the same smoothstep as the shader.
    expected = {round(255 * (p*p*(3-2*p))) for p in (0.125, 0.375, 0.625, 0.875)}
    text = result.document.dumps()
    assert all(rf"\1c&H{255-red:02X}00{red:02X}&" in text for red in expected)
    assert all(a is b for a, b in zip(scene.objects, original, strict=True))
