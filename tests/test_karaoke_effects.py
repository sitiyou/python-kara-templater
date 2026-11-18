"""Catalog contracts: source timing, shared motion, front ownership and budgets."""

from dataclasses import replace
from typing import get_args

import pytest

from examples.karaoke_catalog import build
from kara_templater import (
    Color,
    Document,
    KaraokeDecoration,
    KaraokeEffects,
    KaraokeEntry,
    KaraokeExit,
    KaraokeSinging,
    Line,
    PathObject,
    RectangleClip,
    SceneBudget,
    Style,
    Track,
    prepare_tracks,
)
from kara_templater._gpu_scene import SceneFrames
from kara_templater._karaoke_motion import transition
from kara_templater.karaoke_effects import _walk
from kara_templater.lyric_line import LyricAnimationContext
from kara_templater.scene_animation import VisualState

CATALOG = [
    (field, name)
    for field, alias in (
        ("entry", KaraokeEntry),
        ("exit", KaraokeExit),
        ("singing", KaraokeSinging),
        ("decoration", KaraokeDecoration),
    )
    for name in get_args(alias.__value__)
]


@pytest.mark.parametrize("field,name", CATALOG)
def test_every_menu_choice_compiles_and_retains_source_timing(field, name):
    recipe = replace(
        KaraokeEffects(entry="none", exit="none", singing="none"), **{field: name}
    )
    scene = build(recipe=recipe)
    original = scene.lines[0].layout.lyrics
    assert [
        v
        for t in scene.lines[0].query("character")
        for s in t.singing
        for v in (s.start, s.end)
    ] == pytest.approx([1.4, 1.75, 1.75, 2.1, 2.1, 2.8, 2.8, 4.2])
    result = scene.compile(native_tweens=True, budget=SceneBudget(fps=24))
    assert result.event_count > 0
    assert scene.lines[0].layout.lyrics == original
    frames = SceneFrames(scene)
    assert frames.at(1.6)
    frames.at(0.5)
    frames.at(4.9)
    assert all(
        r.end_time >= r.start_time
        for r in result.document.records
        if isinstance(r, Line)
    )


def subject(text=r"{\k50}AB|ab{\k100}C", start=1000, end=2500, min_outline_gap=2, **options):
    doc = Document.create(
        width=640, height=360, styles=(Style(fontname="DejaVu Sans", fontsize=40),)
    )
    doc.records.append(Line(start_time=start, end_time=end, text=text))
    return prepare_tracks(
        doc, tracks=(Track(id="main", min_outline_gap=min_outline_gap, effects=(KaraokeEffects(**options),)),)
    )


def test_default_pulse_handles_zero_notes_and_caps_the_attack_on_held_notes():
    scene = subject(text=r"{\k0}A{\k20}B{\k100}C", end=2200)
    _, short, held = scene.lines[0].query("character")
    evaluator = scene.evaluator()
    for target, start, peak, end in ((short, 1.0, 1.05, 1.2), (held, 1.2, 1.3, 2.2)):
        scale = evaluator.at(target.node_id, start).scale.x
        assert evaluator.at(target.node_id, peak).scale.x == pytest.approx(1.15 * scale)
        assert evaluator.at(target.node_id, end).scale.x == pytest.approx(scale)


def test_zero_preview_and_ruby_have_no_overlapping_animations():
    scene = subject(start=0, end=1500, stroke_flash=True)
    assert scene.lines[0].lifetime.start == 0
    assert scene.lines[0].query("ruby")
    assert scene.compile(native_tweens=True).event_count > 0
    nodes = list(_walk(scene.lines[0]))
    assert all(isinstance(n, PathObject) for n in nodes if ":flash:" in n.id)
    assert not any(":flash:" in n.id for n in nodes if "/ruby" in n.id)


def test_entry_is_visible_before_motion_has_settled():
    scene = build(entry="tracking_in", singing="none", exit="none")
    line = scene.lines[0]
    target = line.query("character")[0]
    motion = transition(
        LyricAnimationContext(line, target, None, 0.6), "tracking_in", True, 7
    )
    early = motion.sample(VisualState(), 0.25)
    end = motion.sample(VisualState(), 1)
    assert early.opacity == 1 and early.position.x < -target.center.y
    assert end == VisualState()


def test_scanline_uses_one_unit_front_across_two_characters_and_ruby():
    scene = subject(entry="none", exit="none", singing="scanline")
    line = scene.lines[0]
    nodes = {n.id: n for n in _walk(line)}
    fronts = [
        nodes[next(a for a in t.aliases if ":front:" in a)]
        for t in line.query("character")[:2]
    ]
    positions = []
    for front in fronts:
        assert isinstance(front.clip, RectangleClip) and front.clip.deform is not None
        bounds = front.clip.deform.sample(1.25 - front.time_origin)
        assert bounds is not None
        positions.append(
            front.state.position.x + (bounds[0] + bounds[2]) / 2 * front.state.scale.x
        )
    first, second = line.layout.body.characters[:2]
    # The front skips only the extra clearance between these letters.
    assert first.ink_bounds and second.ink_bounds
    raw = subject(entry="none", exit="none", singing="scanline", min_outline_gap=None)
    a, b = raw.lines[0].layout.body.characters[:2]
    extra = second.bounds.left - first.bounds.left - (b.bounds.left - a.bounds.left)
    assert extra > 0
    assert positions[1] - positions[0] == pytest.approx(extra)
    clip = fronts[0].clip
    assert isinstance(clip, RectangleClip) and clip.deform is not None
    assert clip.deform.sample(0.5 - fronts[0].time_origin) is None


def test_zoom_uses_full_note_then_releases_without_stacking_repeats():
    scene = subject(
        text=r"{\k100}A{\kt100\k100}#",
        end=3000,
        entry="none",
        exit="none",
        singing="zoom_pulse",
    )
    target = scene.lines[0].query("character")[0]
    evaluator = scene.evaluator()
    base = evaluator.at(target.node_id, 0.9).scale.x
    assert evaluator.at(target.node_id, 1.99).scale.x == pytest.approx(
        base * 1.25, rel=1e-4
    )
    assert evaluator.at(target.node_id, 2.9).scale.x <= base * 1.25 + 1e-7
    assert evaluator.at(target.node_id, 3.30).scale.x == pytest.approx(base)
    assert scene.compile(native_tweens=True).event_count > 0


def test_budget_rejects_before_particle_construction(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("factory ran before budget check")

    monkeypatch.setattr("kara_templater.karaoke_effects.ornament", fail)
    with pytest.raises(ValueError, match="budget"):
        subject(decoration="petal", max_particles=1)


def test_seeded_outputs_and_source_immutability():
    a = build(decoration="petal", entry="assemble_in")
    b = build(decoration="petal", entry="assemble_in")
    first = a.compile(native_tweens=True, budget=SceneBudget(fps=12)).document.dumps()
    assert (
        first
        == b.compile(native_tweens=True, budget=SceneBudget(fps=12)).document.dumps()
    )
    # Seek in arbitrary order; particles cannot consume a mutable random stream.
    particle = next(n for n in _walk(a.lines[0]) if ":particle:" in n.id)
    evaluator = a.evaluator()
    moment = particle.lifetime.start + 0.1
    state = evaluator.at(particle.id, moment)
    evaluator.at(particle.id, particle.lifetime.end - 0.01)
    assert evaluator.at(particle.id, moment) == state


def test_invalid_parameters_and_zero_duration_disable_motion():
    for values in (
        {"entry": "typo"},
        {"stagger": 1},
        {"particle_size": 0},
        {"max_particles": True},
        {"scanline_width": float("nan")},
    ):
        with pytest.raises((ValueError, TypeError)):
            replace(KaraokeEffects(), **values)
    scene = build(
        recipe=KaraokeEffects(
            entry="wave_in",
            exit="glow_out",
            entry_duration=0,
            exit_duration=0,
            singing="none",
        )
    )
    assert not any(n.animations for n in _walk(scene.lines[0]))


def test_no_wipe_is_instant_including_zero_length_notes():
    scene = subject(
        text=r"{\k0}A{\k100}B",
        end=2000,
        entry="none",
        exit="none",
        singing="no_wipe",
        unsung=Color(100, 100, 100),
    )
    assert scene.compile(native_tweens=True).event_count > 0
    target = scene.lines[0].query("character")[0]
    nodes = {n.id: n for n in _walk(scene.lines[0])}
    before = nodes[target.node_id]
    assert before.state.fill == Color(100, 100, 100)
    after = nodes[target.aliases[0]]
    assert isinstance(after.clip, RectangleClip) and after.clip.deform is not None
    assert after.clip.deform.sample(1.01 - after.time_origin) is not None


def test_utopia_exit_follows_next_character_instead_of_waiting_for_line_end():
    scene = build(entry="none", exit="utopia", singing="none")
    first, last = (
        scene.lines[0].query("character")[0],
        scene.lines[0].query("character")[-1],
    )
    evaluator = scene.evaluator()
    assert evaluator.at(first.node_id, 2).opacity == 1
    assert 0 < evaluator.at(first.node_id, 2.3).opacity < 1
    assert evaluator.at(first.node_id, 2.75).opacity == 0
    assert evaluator.at(last.node_id, 2.75).opacity == 1


def test_gradient_and_glow_stay_composable_with_builtin_motion():
    from kara_templater import Glow, LyricGradient

    scene = build(
        recipe=KaraokeEffects(
            entry="glow_in",
            exit="stretch_out",
            singing="scanline",
            material=LyricGradient((Color(100, 220, 255), Color(255, 160, 205))),
            glow=Glow(Color(120, 180, 255), 2, 2, 0.3),
        )
    )
    frames = SceneFrames(scene)
    assert any(draw.gradient is not None for draw in frames.at(2.5))
    assert frames.at(0.5)


@pytest.mark.parametrize(
    "entry", ["tracking_in", "wave_in", "assemble_in", "spin_flip", "petal"]
)
def test_staggered_entries_hide_waiting_glyphs_and_restore_their_opacity(entry):
    scene = build(entry=entry, exit="none", singing="none")
    line = scene.lines[0]
    last = line.query("character")[-1]
    evaluator = scene.evaluator()
    assert evaluator.at(last.node_id, line.lifetime.start + 0.1).opacity == 0
    assert evaluator.at(
        last.node_id, line.lifetime.start + 0.7
    ).opacity == pytest.approx(1)
    assert all(
        evaluator.at(alias, line.lifetime.start + 0.1).opacity == 0
        for alias in last.aliases
    )


def test_ripple_rings_expand_from_one_shared_glyph_center():
    scene = subject(
        text=r"{\k100}A",
        end=2000,
        entry="none",
        exit="none",
        singing="none",
        decoration="ripple",
    )
    rings = [n for n in _walk(scene.lines[0]) if ":particle:" in n.id]
    assert len(rings) > 1
    assert len({n.state.position for n in rings}) == 1
    assert len({n.lifetime.start for n in rings}) == len(rings)


def test_compact_ass_uses_resolved_recipe_and_absolute_singing(tmp_path):
    scene = subject(
        text=r"{\kt40}{\kf20}A{\kf40}B",
        sung=Color(12, 34, 56),
        entry="none",
        exit="fade",
        exit_duration=0.27,
        singing="no_wipe",
    )
    path = tmp_path / "compact.ass"
    scene.export_compact_ass(path)
    rows = Document.load(path).lines
    assert all(row.start_time == 0 for row in rows)
    assert [row.text.split(r"\fad(0,270)}")[1] for row in rows] == [
        r"{\k140}{\k20}A", r"{\k160}{\k40}B",
    ]
    assert all(r"\1c&H38220C&" in row.text for row in rows)
    assert all(not row.comment for row in scene.document.lines)


def test_compact_ass_preserves_ruby_via_scene_compilation(tmp_path):
    scene = subject(entry="none", exit="none", singing="none")
    path = tmp_path / "ruby.ass"
    scene.export_compact_ass(path)
    expected = [
        row.serialize()
        for row in scene.compile(native_tweens=True).document.lines
        if not row.comment
    ]
    assert [row.serialize() for row in Document.load(path).lines] == expected


def test_fixed_clearance_uses_outer_hard_paint_for_body_and_readings():
    from kara_templater import Glow, LyricHighlights, StatePatch

    doc = Document.create(styles=(Style(fontname="DejaVu Sans", outline=1),))
    doc.records.append(Line(text=r"{\k100}AA|aa", start_time=1000, end_time=2000))
    rim = LyricHighlights.from_singing(
        StatePatch(border=6), base_glow=Glow(Color(255, 255, 255), border=20, blur=8)
    )
    tracks = (
        Track(id="ink", effects=(rim,), min_outline_gap=3),
        Track(id="face", reserved_border=6, min_outline_gap=3),
        Track(id="raw", min_outline_gap=None),
    )
    ink, face, raw = prepare_tracks(doc, tracks=tracks).lines
    for painted, aligned, original in (
        (ink.layout.body, face.layout.body, raw.layout.body),
        (ink.layout.ruby[0].layout, face.layout.ruby[0].layout, raw.layout.ruby[0].layout),
    ):
        a, b = painted.characters
        assert a.ink_bounds and b.ink_bounds
        assert b.ink_bounds.left - a.ink_bounds.right == pytest.approx(6 + 3 + 6)
        assert painted.bounds == aligned.bounds
        assert painted.bounds.width > original.bounds.width
        assert painted.singing == original.singing
        assert [c.bounds for c in painted.characters] == [c.bounds for c in aligned.characters]


def test_duotone_compact_wipes_both_inks_in_one_letter(tmp_path):
    from kara_templater._raster import rasterize

    recipe = KaraokeEffects.duotone()
    doc = Document.create(
        width=320,
        height=180,
        styles=(
            Style(fontname="DejaVu Sans", fontsize=64, bold=True, outline=5, shadow=0),
        ),
    )
    doc.records.append(Line(start_time=1000, end_time=3000, text=r"{\kt50\kf100}O"))
    scene = prepare_tracks(doc, tracks=(Track(id="main", effects=(recipe,)),))
    output = tmp_path / "duotone.ass"
    scene.export_compact_ass(output)
    script = output.read_text(encoding="utf-8-sig")

    def painted_pixels(time):
        rgba = rasterize(script, time, (320, 180)).rgba
        return {
            tuple(rgba[i : i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] == 255
        }

    before, middle, after = map(painted_pixels, (1450, 2000, 2550))
    for color in (recipe.unsung, recipe.unsung_outline):
        assert color is not None
        rgb = (color.red, color.green, color.blue)
        assert rgb in before and rgb in middle and rgb not in after
    for color in (recipe.sung, recipe.sung_outline):
        assert color is not None
        rgb = (color.red, color.green, color.blue)
        assert rgb not in before and rgb in middle and rgb in after
    # O has solid horizontal strokes across the front at its top and bottom.
    # A sharp clip yields only endpoint inks there; a wide wipe has interior inks.
    weights = [i / 16 for i in (3, 5, 7, 9, 11, 13)]
    assert recipe.unsung_outline and recipe.sung_outline
    for a, b in (
        (recipe.unsung, recipe.sung),
        (recipe.unsung_outline, recipe.sung_outline),
    ):
        midtones = set()
        for x in weights:
            w = x * x * (3 - 2 * x)
            midtones.add(
                tuple(
                    round(p + (q - p) * w)
                    for p, q in zip(
                        (a.red, a.green, a.blue), (b.red, b.green, b.blue), strict=True
                    )
                )
            )
        assert len(midtones & middle) >= 4


def test_compact_duotone_preserves_separately_timed_readings(tmp_path):
    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=80),))
    doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k30}A|x{\k70}#|y"))
    scene = prepare_tracks(
        doc, tracks=(Track(id="main", effects=(KaraokeEffects.duotone(),)),)
    )
    plan = scene.plans[0]
    (unit,) = plan.line.layout.lyrics.units
    [(body_start, body_end)] = [(s.start, s.end) for s in unit._body_singing()]
    assert (body_start, body_end) == (1, 2)
    output = tmp_path / "readings.ass"
    scene.export_compact_ass(output)
    rows = Document.load(output).lines
    origin = round(plan.line.lifetime.start * 100) * 10
    for text, size, start, end in (
        ("A", 80, 1000, 2000),
        ("x", 40, 1000, 1300),
        ("y", 40, 1300, 2000),
    ):
        parts = [r.text for r in rows if r.text.endswith(text)]
        assert parts and all(rf"\fs{size}" in p for p in parts)
        assert all(rf"\t({start - origin},{end - origin}," in p for p in parts)
