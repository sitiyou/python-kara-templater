from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    Document,
    Layout,
    Line,
    Style,
    Track,
    paint_pair_from_style,
    prepare_tracks,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def document(*lines):
    return Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style(fontname="DejaVu Sans", fontsize=32).serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
        + "\n".join(line.serialize() for line in lines)
    )


def lyric(text=r"{\k20}A{\k30}B", **kwargs):
    return Line(text=text, start_time=1000, end_time=2000, **kwargs)


def test_auto_render_preserves_sources_and_can_reimport_saved_output():
    source = document(
        lyric(effect="original:effect"),
        Line(text="plain subtitle", start_time=0, end_time=3000),
        lyric(comment=True, effect="notes"),
    )
    original = source.dumps()
    tracks = (Track(id="main"),)
    result = prepare_tracks(source, tracks=tracks, owner="a:b%").ass.compile()
    assert source.dumps() == original
    restored_scene = prepare_tracks(
        Document.parse(result.document.dumps()), tracks=tracks, owner="a:b%"
    )
    assert len(restored_scene.plans) == 1
    plan = restored_scene.plans[0]
    assert plan.source.effect == "original:effect"
    assert plan.source.record_index is not None
    saved = result.document.records[plan.source.record_index]
    assert isinstance(saved, Line) and saved.comment
    assert saved.text == source.lines[0].text
    again = restored_scene.ass.compile()
    assert again.document.dumps() == result.document.dumps()
    assert any(
        line.text == "plain subtitle" and not line.comment
        for line in again.document.lines
    )
    assert any(line.effect == "notes" and line.comment for line in again.document.lines)
    restored = (
        prepare_tracks(again.document, tracks=(), owner="a:b%").ass.compile().document
    )
    assert any(
        line.text == source.lines[0].text
        and line.effect == "original:effect"
        and not line.comment
        for line in restored.lines
    )


def test_identical_sources_get_distinct_stable_ids():
    source = document(lyric(), lyric())
    tracks = (Track(id="main", layout=Layout(rows=2)),)
    scene = prepare_tracks(source, tracks=tracks)
    ids = tuple(plan.source.id for plan in scene.plans)
    assert len(set(ids)) == 2
    result = scene.ass.compile()
    again = prepare_tracks(Document.parse(result.document.dumps()), tracks=tracks)
    assert tuple(plan.source.id for plan in again.plans) == ids
    assert len(again.replace_records) == 2
    assert again.ass.compile().document.dumps() == result.document.dumps()


def test_style_palette_decodes_bgr_and_secondary_before_primary():
    style = Style(
        fields={
            "PrimaryColour": "&H00112233",
            "SecondaryColour": "&H00445566",
            "OutlineColour": "&H00010203",
        }
    )
    pair = paint_pair_from_style(style)
    assert pair.after.fill == Color(0x33, 0x22, 0x11)
    assert pair.before.fill == Color(0x66, 0x55, 0x44)
    assert pair.after.outline == Color(3, 2, 1)
    with pytest.raises(ValueError, match="invalid PrimaryColour"):
        paint_pair_from_style(replace(style, fields={"PrimaryColour": "nonsense"}))


def test_common_preparation_error_identifies_actual_record_and_preserves_input():
    source = document(lyric(), lyric(r"{\k20\blur4}B"))
    original = source.dumps()
    index = next(
        i
        for i, record in enumerate(source.records)
        if isinstance(record, Line) and "blur" in record.text
    )
    with pytest.raises(
        ValueError, match=rf"record {index}, text offset 0: unsupported override"
    ):
        prepare_tracks(source, tracks=(Track(id="main", layout=Layout(rows=2)),))
    assert source.dumps() == original


@pytest.mark.parametrize("suffix", ("missing-separator", ":original"))
def test_invalid_owned_source_marker_reports_its_record(suffix):
    source = document(lyric(comment=True, effect="karaoke:source:v1:default:" + suffix))
    index = len(source.records) - 1
    with pytest.raises(ValueError, match=rf"record {index}: damaged lyric source marker"):
        prepare_tracks(source, tracks=(Track(id="main", source=lambda _: True),), owner="default")
