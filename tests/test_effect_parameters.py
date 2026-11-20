"""Relative recipe parameters bind to the same targets in every delivery path."""

from dataclasses import replace
from math import ceil

import pytest

from kara_templater import (
    BLUE,
    RED,
    Color,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    Glyph,
    KaraokeEffects,
    KaraokeTheme,
    Layout,
    Line,
    LyricRule,
    Note,
    ScalePulse,
    Style,
    TextCue,
    Track,
    prepare_tracks,
)
from kara_templater.lyric_highlights import _FeatheredSingingClip


@pytest.mark.parametrize(("ruby_size", "fixed"), [(36, False), (48, False), (48, True)])
def test_body_and_reading_share_resolved_export_widths(tmp_path, ruby_size, fixed):
    body = Style(fontname="DejaVu Sans", fontsize=72)
    doc = Document.create(
        styles=(body, replace(body, name="Default-furigana", fontsize=ruby_size))
    )
    doc.records.append(Line(text=r"{\k100}A|x", end_time=1000))
    effect = KaraokeEffects.duotone(feather=12) if fixed else KaraokeEffects.duotone()
    scene = prepare_tracks(
        doc, tracks=(Track(id="main", layout=Layout(), effects=(effect,)),)
    )
    (line,) = scene.lines
    expected = {"A": 12, "x": 12 if fixed else ruby_size / 6}

    def clips(node):
        if isinstance(node.clip, _FeatheredSingingClip):
            yield node.text, node.clip.width
        for child in getattr(node, "children", ()):
            yield from clips(child)

    assert dict(clips(line)) == expected
    path = tmp_path / "compact.ass"
    scene.export_compact_ass(path)
    assert all(
        sum(
            row.text.endswith(letter)
            for row in Document.load(path).lines
            if not row.comment
        )
        == 2 + ceil(width / 3)
        for letter, width in expected.items()
    )
    assert scene.compile(native_tweens=True).event_count > 0
    scene.export_hook(tmp_path / "song.hook", fps=20)
    assert "//!HOOK MAIN" in (tmp_path / "song.hook").read_text()


def test_interval_expressions_and_factory_read_the_same_source_note():
    doc = Document.create(styles=(Style(fontsize=72),))
    doc.records.append(Line(text=r"{\k20}A{\k100}#{\k0}B", end_time=1200))
    clocks = []

    def pulse(ctx):
        clocks.append(
            (ctx.resolve(Note.duration), ctx.duration, ctx.resolve(Glyph.font_size / 6))
        )
        return ScalePulse(peak=1.15)

    scene = prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                effects=(
                    LyricRule(
                        "character", "singing", pulse, duration=Note.duration / 2
                    ),
                    LyricRule(
                        "character",
                        "after_singing",
                        FadeIn(),
                        duration=0.1,
                        offset=(Note.duration / 4).clamp(0.06, 0.20),
                    ),
                ),
            ),
        ),
    )
    assert clocks == [(0.2, 0.1, 12), (1, 0.5, 12), (0, 0, 12)]
    identity = scene.lines[0].query("character")[0].id
    evaluator = scene.evaluator()
    assert evaluator.at(identity, 0.45).scale.x == pytest.approx(1.15)
    assert evaluator.at(identity, 0.05).scale.x == pytest.approx(1.15)
    assert evaluator.at(identity, 1.45).opacity == pytest.approx(0.5)
    assert len(clocks) == 3
    with pytest.raises(ValueError, match=r"LyricRule.duration requires Note.duration"):
        prepare_tracks(
            doc,
            tracks=(
                Track(
                    id="bad",
                    effects=(
                        LyricRule("line", "enter", FadeIn(), duration=Note.duration),
                    ),
                ),
            ),
        )


def test_theme_inheritance_reaches_cues_and_respects_effect_ink():
    doc = Document.create()
    marker = CueMarker("lead", "count").markup()
    doc.records.append(
        Line(text=marker + r"{\1c&H00FF00&\k100}A", start_time=2000, end_time=3000)
    )
    seen = []

    def cue(ctx):
        seen.append((ctx.colors.before.fill, ctx.colors.after.fill))
        return TextCue()(ctx)

    palette = KaraokeTheme(sung=RED, unsung=BLUE)
    ink = KaraokeEffects.duotone()
    harmony = Color(40, 200, 188)
    tracks = tuple(
        Track(
            id=name,
            theme=theme,
            effects=(effect,),
            cues={"count": CuePreset(factory=cue)},
        )
        for name, theme, effect in (
            ("main", KaraokeTheme(), ink),
            ("harmony", KaraokeTheme(sung=harmony), ink),
            ("accent", KaraokeTheme(sung=harmony), replace(ink, sung=BLUE)),
        )
    )
    scene = prepare_tracks(doc, tracks=tracks, theme=palette)
    assert seen == [(BLUE, RED), (BLUE, harmony), (BLUE, BLUE)]
    assert [
        line._karaoke_paint.sung for line in scene.lines if line._karaoke_paint
    ] == [RED, harmony, BLUE]
    assert ink.sung is None
    assert ink.with_theme(palette).particle_color == "follow_after"
    assert (
        ink.with_theme(palette).shine
        != ink.with_theme(KaraokeTheme(sung=harmony)).shine
    )


def test_canvas_and_animation_fields_resolve_at_their_own_stage():
    from kara_templater import Animation, Canvas

    doc = Document.create(width=640, height=360)
    doc.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    recipe = KaraokeEffects(
        singing="scanline",
        scanline_width=Canvas.height / 45,
        scanline_softness=Glyph.font_size / 8,
    )
    calls = []

    def pulse(ctx):
        calls.append(
            (
                ctx.resolve(Canvas.height),
                ctx.resolve(Animation.duration),
                ctx.resolve(Note.duration),
            )
        )
        return ScalePulse()

    scene = prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                effects=(
                    recipe,
                    LyricRule(
                        "character",
                        "singing",
                        pulse,
                        duration=0.2,
                        offset=Animation.duration / 2,
                    ),
                ),
            ),
        ),
    )
    assert calls == [(360, 0.2, 1)]
    (target,) = scene.lines[0].query("character")
    assert scene.evaluator().at(target.id, 1.2).scale.x == pytest.approx(1.1)
    with pytest.raises(
        ValueError, match=r"LyricRule.duration requires Animation.duration"
    ):
        prepare_tracks(
            doc,
            tracks=(
                Track(
                    id="cycle",
                    effects=(
                        LyricRule(
                            "character",
                            "singing",
                            ScalePulse(),
                            duration=Animation.duration,
                        ),
                    ),
                ),
            ),
        )
    with pytest.raises(ValueError, match="hook_feather must be nonnegative"):
        prepare_tracks(
            doc,
            tracks=(
                Track(
                    id="bad",
                    effects=(KaraokeEffects.duotone(feather=-1 * Glyph.font_size),),
                ),
            ),
        )


def test_explicit_transparent_cue_and_unthemed_lyric_keep_their_paints():
    from kara_templater import BarsCue, Paint, PaintPair

    doc = Document.create()
    doc.records.append(
        Line(
            text=CueMarker("lead", "count").markup() + r"{\1c&H00FF00&\k100}A",
            start_time=2000,
            end_time=3000,
        )
    )
    output = []

    def bars(ctx):
        content = BarsCue()(ctx)
        output.extend((node.state.fill, node.state.opacity) for node in content.objects)
        return content

    track = Track(
        id="main",
        cues={
            "count": CuePreset(
                factory=bars,
                colors=PaintPair(after=Paint(fill=BLUE, opacity=0)),
            )
        },
    )
    scene = prepare_tracks(doc, tracks=(track,), theme=KaraokeTheme(sung=RED))
    assert output == [(BLUE, 0)] * 3
    assert scene.lines[0].layout.body.characters[0].object.state.fill == Color(
        0, 255, 0
    )


def test_compiled_bands_match_absolute_width_for_each_resolved_style():
    from kara_templater import LyricHighlights, StatePatch

    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=72),))
    doc.records.append(Line(text=r"{\k100}A|x", end_time=1000))

    def band_events(width, glyph):
        ink = LyricHighlights.from_singing(
            StatePatch(fill=RED),
            base_paint=StatePatch(fill=BLUE),
            hook_feather=width,
            ass_feather_bands=4,
        )
        scene = prepare_tracks(doc, tracks=(Track(id="main", effects=(ink,)),))
        return [
            r.text
            for r in scene.compile(native_tweens=True).document.lines
            if not r.comment and r.text.endswith(glyph)
        ]

    for glyph, width in (("A", 12), ("x", 6)):
        assert band_events(Glyph.font_size / 6, glyph) == band_events(width, glyph)
        assert band_events(24, glyph) != band_events(width, glyph)
