"""Visual effects retain source clocks, hierarchy and finite native output."""

from dataclasses import replace

import pytest

from kara_templater import (
    RED,
    Box,
    Document,
    Layout,
    Lifetime,
    Line,
    LyricEcho,
    LyricHighlights,
    LyricLine,
    ObjectGroup,
    Scene,
    StatePatch,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
    layout_document_lyrics,
    lyric_effects,
)


def subject(text=r"{\k50}A|a", end=1500):
    doc = Document.create(width=320, height=180, styles=(
        Style(fontname="DejaVu Sans", fontsize=32),
    ))
    doc.records.append(Line(text=text, start_time=1000, end_time=end))
    layout = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, end / 1000))
    return doc, LyricLine.from_layout(layout)


def objects(node):
    yield node
    if isinstance(node, ObjectGroup):
        for child in node.children:
            yield from objects(child)


def test_onset_copies_have_independent_fades_and_exact_offsets():
    doc, line = subject()
    target = line.query("character")[0]
    echo = LyricEcho(count=2, spacing=0.1, duration=0.8, opacity=0.4, decay=0.5)
    decorated = echo(line)
    copies = [node for node in objects(decorated) if "/echo:" in node.id]
    assert [node.lifetime.start for node in copies] == pytest.approx([1, 1.1])
    assert [node.lifetime.end for node in copies] == pytest.approx([1.8, 1.9])
    assert decorated.lifetime.end == pytest.approx(1.9)
    evaluator = Scene(doc).add(decorated).evaluator()
    original = evaluator.at(target.node_id, 1.4)
    for index, (node, opacity) in enumerate(zip(copies, (0.2, 0.125), strict=True)):
        state = evaluator.at(node.id, 1.4)
        assert state.position == original.position + Vec2(0, -8 * (index + 1))
        assert state.opacity == pytest.approx(opacity)
    assert decorated.query("character") == line.query("character")
    assert decorated.layout.lyrics == line.layout.lyrics
    assert line.lifetime.end == 1.5
    compiled = Scene(doc).add(decorated).ass.compile(native_tweens=True)
    echo_reports = [r for r in compiled.objects if "/echo:" in r.id]
    assert len(echo_reports) == 2
    assert all(r.events == 1 for r in echo_reports)


def test_repeats_and_delayed_copies_retain_original_timing_clocks():
    doc, line = subject(r"{\k25}A{\kt50\k25}#", end=2000)
    delayed = line.copy(id="delayed", delay=0.3)
    decorated = LyricEcho(count=1)(delayed)
    copies = [node for node in objects(decorated) if "/echo:" in node.id]
    assert [node.lifetime.start for node in copies] == [1.3, 1.8]
    assert decorated.query("character")[0].timing == line.query("character")[0].timing
    assert Scene(doc).add(decorated).ass.compile(native_tweens=True).event_count > 0
    with pytest.raises(ValueError, match="budget exceeded before copying"):
        LyricEcho(count=3, max_copies=5)(delayed)
    with pytest.raises(ValueError, match="duplicate lyric echo"):
        LyricEcho(count=1)(decorated)


def test_composed_highlight_and_echo_reserve_track_tail_without_manual_timing():
    doc, _ = subject()
    style = lyric_effects(
        LyricHighlights.from_timing(StatePatch(fill=RED)),
        LyricEcho(count=3, spacing=0.1, duration=1, paint=StatePatch(fill=RED)),
    )
    scene = build_lyric_scene(doc, tracks=(Track(
        id="main", preview=0, tail=0, region=Box(20, 40, 280, 120),
        layout=Layout(), effects=(style,),
    ),))
    line = scene.lines[0]
    assert line.lifetime.end >= 2.2
    copies = [node for node in objects(line) if "/echo:" in node.id]
    assert len(copies) == 3
    assert all(node.clip is None and node.material is None for node in copies)
    assert all(node.state.fill == RED for node in copies)
    result = scene.ass.compile(native_tweens=True)
    assert sum(r.events for r in result.objects if "/echo:" in r.id) == 3


def test_factory_composition_and_empty_schedule_contracts():
    _, line = subject(r"{\k0}A")
    assert not any("/echo:" in node.id for node in objects(LyricEcho()(line)))
    assert lyric_effects()(line) is line
    with pytest.raises(ValueError, match="preserve line identity"):
        lyric_effects(lambda item: replace(item, id="wrong"))(line)
