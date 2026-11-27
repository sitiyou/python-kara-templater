"""A replacement inherits the source fragment's measured sweep clock."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    WHITE,
    Document,
    KaraokeEffects,
    Lifetime,
    Line,
    LyricLine,
    ObjectGroup,
    Scene,
    Style,
    TimeSpan,
    Vec2,
    VisualState,
    layout_document_lyrics,
    layout_document_text,
    layout_lyrics,
)
from tests.test_gpu_hook import _render_hook
from tests.test_gpu_hook import vulkan as vulkan


def _paused_sweep():
    doc = Document.create(width=160, height=120, styles=(
        Style(fontname="DejaVu Sans Mono", fontsize=38, outline=0, shadow=0),
    ))
    doc.records.append(Line(text=r"{\k40}WW|one{\k60}#|two", start_time=1000, end_time=2400))
    index = len(doc.records) - 1
    lyrics = doc.lyrics_at(index)
    unit, = lyrics.units
    first, second = unit.segments
    second = replace(second, timing=replace(second.timing, start=1.8, end=2.4))
    lyrics = replace(lyrics, units=(replace(unit, segments=(first, second)),))
    line = LyricLine.from_layout(layout_lyrics(doc, lyrics, id="source", display=Lifetime(0, 3)))
    return doc, line


@pytest.mark.parametrize("reverse", [False, True])
def test_replacement_hook_keeps_progress_through_an_inaudible_gap(tmp_path, vulkan, reverse):
    doc, line = _paused_sweep()
    effects = KaraokeEffects(
        before_fill=BLUE, after_fill=RED, highlight="scanline", reverse_wipe=reverse,
        scanline_color=WHITE, scanline_width=5, scanline_softness=1,
    )
    sweep = effects.sweep(line, 0, 2)
    assert sweep.interval == TimeSpan(1, 2.4)

    doc.records.append(Line(text="MMMM", start_time=0, end_time=3000))
    incoming_layout = layout_document_text(doc, len(doc.records) - 1)
    scene = Scene(doc).add(
        ObjectGroup(
            id="original", lifetime=Lifetime(0, 1.5),
            state=VisualState(position=Vec2(26, 25)),
            children=sweep.paint(line.layout.body.characters),
        ),
        ObjectGroup(
            id="replacement", lifetime=Lifetime(1.5, 3),
            state=VisualState(position=Vec2(26, 25), scale=Vec2(1, 0.75)),
            children=tuple(
                replace(glyph, lifetime=Lifetime(1.5, 3))
                for glyph in sweep.paint(incoming_layout.characters)
            ),
        ),
    )
    frames = _render_hook(scene, tmp_path, fps=10, duration=3)
    frame_size = 160 * 120 * 3

    def frame(index):
        return frames[index * frame_size : (index + 1) * frame_size]

    def colors(index, left, right):
        data = frame(index)
        red = blue = 0
        for y in range(25, 65):
            for x in range(left, right):
                offset = (y * 160 + x) * 3
                r, _, b = data[offset : offset + 3]
                red += r > 150 and b < 50
                blue += b > 150 and r < 50
        return red, blue

    assert frame(15) == frame(17)
    assert frame(17) != frame(21)
    high, low = (0, 1) if not reverse else (1, 0)
    left, right = colors(17, 29, 60), colors(17, 70, 100)
    assert left[high] > 50 and left[low] == 0
    assert right[low] > 50 and right[high] == 0
    red, blue = colors(24, 26, 105)
    assert red > 150 and blue == 0


def test_fragment_clocks_share_measured_boundaries_with_the_source():
    _, line = _paused_sweep()
    effects = KaraokeEffects()
    assert effects.sweep(line, 0, 1).interval == TimeSpan(1, 1.4)
    assert effects.sweep(line, 1, 2).interval == TimeSpan(1.8, 2.4)
    shifted = line.copy(id="delayed", delay=3)
    assert effects.sweep(shifted, 1, 2).interval == TimeSpan(4.8, 5.4)
    assert replace(effects, highlight="no_wipe").sweep(line, 0, 2).interval == TimeSpan(1, 1)


def test_repeated_source_note_resets_replacement_at_the_next_attack():
    _, line = _paused_sweep()
    layout = line.layout
    unit, = layout.lyrics.units
    lyrics = replace(layout.lyrics, units=(replace(unit, repeat=True),))
    line = LyricLine.from_layout(replace(layout, lyrics=lyrics))
    sweep = KaraokeEffects().sweep(line, 0, 2)
    assert sweep._points == ((1, 0), (1.4, 1), (1.8, 1), (1.8, 0), (2.4, 1))


def test_replacement_range_must_stay_within_one_shaped_lyric_unit():
    doc = Document.create()
    doc.records.append(Line(text=r"{\k40}á{\k40}B", start_time=1000, end_time=1800))
    line = LyricLine.from_layout(layout_document_lyrics(doc, len(doc.records) - 1))
    with pytest.raises(ValueError, match="shaped clusters"):
        KaraokeEffects().sweep(line, 1, 2)
    with pytest.raises(ValueError, match="one lyric unit"):
        KaraokeEffects().sweep(line, 0, 3)
