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


@pytest.mark.parametrize("kind", ["char_fade", "char_drip", "spin_flip"])
def test_single_character_exit_finishes_at_display_end(kind):
    scene = subject(text=r"{\k50}H", start=1000, end=1500,
                    entry="none", exit=kind, singing="none", exit_duration=0.6)
    line, = scene.lines
    glyph, = line.query("character")
    state = scene.evaluator().at(glyph.node_id, line.lifetime.end - 0.20)
    assert state.opacity > 0


@pytest.mark.parametrize("kind", ["char_fade", "char_drip", "spin_flip"])
def test_ruby_uses_its_hosts_transition_slot(kind):
    scene = subject(text=r"{\k20}A{\k20}B|bc{\k20}C{\k20}D", start=1500, end=2300,
                    entry=kind, exit=kind, entry_duration=0.6, exit_duration=0.6, singing="none")
    line, = scene.lines
    host = line.query("character")[1]
    ruby = line.query("ruby")
    evaluator = scene.evaluator()
    times = (line.lifetime.start + 0.05, line.lifetime.start + 0.2,
             line.lifetime.end - 0.30, line.lifetime.end - 0.15)
    for time in times:
        opacity = evaluator.at(host.node_id, time).opacity
        assert [evaluator.at(r.node_id, time).opacity for r in ruby] == pytest.approx([opacity] * 2)


@pytest.mark.parametrize("kind", ["tracking_in", "wave_in"])
def test_readings_enter_with_the_hosts_translation_and_reveal(kind):
    scene = subject(text=r"{\k20}i{\k20}W|bc{\k20}！{\k20}D", start=1500, end=2300,
                    entry=kind, exit="none", entry_duration=0.6, singing="none")
    line, = scene.lines
    host = line.query("character")[1]
    evaluator = scene.evaluator()
    rest = line.lifetime.start + 0.8
    def displacement(node_id, dt):
        state = evaluator.at(node_id, line.lifetime.start + dt)
        delta = state.position - evaluator.at(node_id, rest).position
        return delta.x, delta.y, state.opacity

    for dt in (0.08, 0.15, 0.25):
        expected = displacement(host.node_id, dt)
        for target in line.query("ruby"):
            assert displacement(target.node_id, dt) == pytest.approx(expected)


@pytest.mark.parametrize(("entry", "exit"), [("petal", "snow"), ("assemble_in", "dissolve_out")])
def test_particle_transitions_reveal_the_reading_with_its_host(entry, exit):
    scene = subject(text=r"{\k20}i{\k20}W|bc{\k20}！", start=1500, end=2100,
                    entry=entry, exit=exit, entry_duration=0.6, exit_duration=0.6, singing="none")
    line, = scene.lines
    host = line.query("character")[1]
    evaluator = scene.evaluator()
    for time in (line.lifetime.start + 0.1, line.lifetime.start + 0.35, line.lifetime.end - 0.32):
        expected = evaluator.at(host.node_id, time).opacity
        for target in line.query("ruby"):
            assert evaluator.at(target.node_id, time).opacity == pytest.approx(expected)


@pytest.mark.parametrize(("entry", "exit", "during_entry"), [
    ("stretch_in", "none", True), ("none", "stretch_out", False),
    ("glow_in", "none", True), ("none", "converge_out", False),
])
def test_reading_resizes_as_one_annotation(entry, exit, during_entry):
    scene = subject(text=r"{\k20}i{\k20}W|bc{\k20}！", start=1500, end=2100,
                    entry=entry, exit=exit, entry_duration=0.6, exit_duration=0.6, singing="none")
    line, = scene.lines
    left, right = line.query("ruby")
    host = line.query("character")[1]
    evaluator = scene.evaluator()
    rest = 1.8
    time = line.lifetime.start + (0.12 if entry == "glow_in" else 0.25) if during_entry else line.lifetime.end - 0.25

    def centers_distance(at):
        a, b = (evaluator.at(t.node_id, at).transform.apply(t.center) for t in (left, right))
        return b.x - a.x

    ratio = evaluator.at(host.node_id, time).scale.x / evaluator.at(host.node_id, rest).scale.x
    assert abs(ratio - 1) > 0.02
    assert centers_distance(time) == pytest.approx(centers_distance(rest) * ratio)
    assert not any(":halo:" in name or ":echo:" in name
                   for t in (left, right) for name in t.aliases)


def test_utopia_shared_reading_leaves_after_following_main_glyph_and_skips_spaces():
    scene = subject(text=r"{\k50}AB|ab{\k20} {\k50}C{\k50}D", start=1500, end=3200,
                    entry="none", exit="utopia", singing="none")
    line, = scene.lines
    evaluator = scene.evaluator()
    for target in (*line.query("character")[:2], *line.query("ruby")):
        assert evaluator.at(target.node_id, 2.65).opacity == pytest.approx(1)
        assert evaluator.at(target.node_id, 3.0).opacity == pytest.approx(0.6)


def test_character_fade_composites_the_waiting_and_sung_colors():
    from kara_templater._raster import rasterize

    scene = subject(text=r"{\k50}H", start=1000, end=1500, entry="none",
                    exit="char_fade", exit_duration=0.6, singing="none",
                    unsung=Color(0, 0, 255), sung=Color(255, 0, 0),
                    unsung_outline=Color(0, 0, 0), sung_outline=Color(0, 0, 0))
    script = scene.compile(native_tweens=True).document.dumps()
    end = round(1000 * scene.lines[0].lifetime.end)

    def two_inks(ms):
        rgba = rasterize(script, ms, (640, 360)).rgba
        return any(rgba[i] > 80 and rgba[i + 2] > 20 and rgba[i + 3] > 80
                   for i in range(0, len(rgba), 4))

    assert not two_inks(end - 300)
    assert two_inks(end - 125)


def test_stroke_flash_uses_the_body_onset_and_stationary_outline():
    scene = subject(text=r"{\k0}A{\k25}空|そ{\k25}#|ら", start=1500, end=2000,
                    entry="none", exit="none", singing="utopia", stroke_flash=True)
    line, = scene.lines
    flashes = [n for n in _walk(line) if ":flash:" in n.id]
    assert len(flashes) == 2
    assert all((n.lifetime.start, n.lifetime.end) == pytest.approx((1.5, 1.74)) for n in flashes)
    evaluator = scene.evaluator()
    for n in flashes:
        assert evaluator.at(n.id, 1.60).scale == evaluator.at(n.id, 1.51).scale
    assert scene.compile(native_tweens=True).event_count


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
    scene = subject(entry="none", exit="none", singing="scanline", ruby_scanline="both")
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
    raw = subject(entry="none", exit="none", singing="scanline", ruby_scanline="both", min_outline_gap=None)
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
        base * 1.2475
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
    second = scene.lines[0].query("character")[1]
    mask = nodes[second.aliases[0]].clip
    assert isinstance(mask, RectangleClip) and mask.deform is not None
    assert mask.deform.sample(1.99 - after.time_origin) is None
    assert mask.deform.sample(2.00 - after.time_origin) is not None


def test_utopia_exit_follows_next_character_instead_of_waiting_for_line_end():
    scene = build(entry="none", exit="utopia", singing="none")
    first, last = (
        scene.lines[0].query("character")[0],
        scene.lines[0].query("character")[-1],
    )
    evaluator = scene.evaluator()
    assert evaluator.at(first.node_id, 2).opacity == 1
    assert 0 < evaluator.at(first.node_id, 2.3).opacity < 1
    assert evaluator.at(first.node_id, 2.70).opacity == pytest.approx(0.2)
    assert evaluator.at(first.node_id, 2.85).opacity == pytest.approx(0)
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
        r"{\k160}{\k0}A", r"{\k200}{\k0}B",
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
        ("A", 80, 1000, 1300),
        ("A", 80, 1300, 2000),
        ("x", 40, 1000, 1300),
        ("y", 40, 1300, 2000),
    ):
        parts = [r.text for r in rows if r.text.endswith(text)]
        assert parts and all(rf"\fs{size}" in p for p in parts)
        assert all(rf"\t({start - origin},{end - origin}," in p for p in parts)


@pytest.mark.parametrize("gradient", [False, True])
def test_scanline_retains_the_glyph_outline_and_inward_feather(gradient):
    from kara_templater import LyricGradient
    from kara_templater._raster import rasterize

    def script(singing):
        return subject(
            text=r"{\k50}H{\k50}Q", entry="none", exit="none", singing=singing,
            scanline_width=16, scanline_softness=6, scanline_color=Color(16, 100, 232),
            material=LyricGradient((Color(244, 20, 70), Color(120, 70, 255))) if gradient else None,
        ).compile(native_tweens=True).document.dumps()

    ordinary, softened = script("none"), script("scanline")
    for ms in (1050, 1300, 1500, 1750, 1950):
        plain, front = (
            rasterize(ass, ms, (640, 360)).rgba for ass in (ordinary, softened)
        )
        assert plain != front
        assert plain[3::4] == front[3::4]


@pytest.mark.parametrize("level,mid_attack,mid_release", [(1, 1.125, 1.125), (3, 1.21875, 1.21875)])
def test_zoom_curve_matches_studio_on_both_sides_of_peak(level, mid_attack, mid_release):
    scene = subject(text=r"{\k100}A", entry="none", exit="none",
                    singing="zoom_pulse", zoom_pulse_curve_level=level)
    target = scene.lines[0].query("character")[0]
    evaluator = scene.evaluator()
    baseline = evaluator.at(target.node_id, 1).scale.x
    for time, factor in ((1.5, mid_attack), (2, 1.25), (2.15, mid_release), (2.3, 1)):
        assert evaluator.at(target.node_id, time).scale.x == pytest.approx(baseline * factor)


@pytest.mark.parametrize("softness", [0, 4])
def test_scanline_colors_the_visible_second_outline(softness):
    from kara_templater import Glow
    from kara_templater._raster import rasterize

    rim = Color(182, 50, 86)

    def render(singing):
        glow = Glow(rim, border=7)
        scene = subject(text=r"{\k100}Q", singing=singing, entry="none", exit="none",
                        base_glow=glow, glow=glow, scanline_width=16, scanline_softness=softness,
                        scanline_color=Color(0, 255, 255))
        return rasterize(scene.compile(native_tweens=True).document.dumps(), 1500, (640, 360)).rgba

    plain, band = render("none"), render("scanline")
    outer = [i for i in range(0, len(plain), 4) if plain[i:i + 4] == bytes((182, 50, 86, 255))]
    assert any(band[i:i + 4] == bytes((0, 255, 255, 255)) for i in outer)
    assert any(band[i:i + 4] == plain[i:i + 4] for i in outer)
    if softness:
        assert plain[3::4] == band[3::4]
        assert any(50 < band[i + 1] < 255 for i in outer)


def test_role_scanline_reuses_a_singers_gradient_on_fill_and_border():
    from kara_templater import LinearGradient, LyricGradient

    sky = LyricGradient((Color(15, 100, 212), Color(230, 249, 255)), step=4)
    scene = subject(text=r"{\k60}H", singing="scanline", entry="none", exit="none",
                    scanline_mode="role", scanline_material=sky, scanline_width=8, scanline_softness=2)
    fronts = [n for n in _walk(scene.lines[0]) if ":front:" in n.id]
    brushes = [n.material for n in fronts if isinstance(n.material, LinearGradient)]
    assert len(brushes) == len(fronts) and all(g.outline for g in brushes)
    assert any(g.fill == g.outline for g in brushes)  # solid core
    assert any(g.fill != g.outline for g in brushes)  # softened edges
    document = scene.compile(native_tweens=True).document
    assert any(r"\clip(" in row.text for row in document.lines if not row.comment)
    assert any(d.gradient is not None for d in SceneFrames(scene).at(1.3))


def test_stretch_has_sharp_core_and_five_fading_white_halos():
    from kara_templater import TextObject

    scene = subject(
        text=r"{\k100}A",
        entry="stretch_in",
        entry_duration=0.6,
        singing="none",
        exit="none",
    )
    line = scene.lines[0]
    (target,) = line.query("character")
    halos = [n for n in _walk(line) if ":halo:" in n.id]
    assert len(halos) == 5
    assert all(isinstance(node, TextObject) and node.scale_border for node in halos)
    t = line.lifetime.start + 0.1
    evaluator = scene.evaluator()
    core = evaluator.at(target.node_id, t)
    assert core.blur == 0
    assert core.scale.x > core.scale.y
    states = [evaluator.at(node.id, t) for node in halos]
    assert all(
        state.scale.x == pytest.approx(core.scale.x)
        and state.outline == Color(255, 255, 255)
        for state in states
    )
    assert all(
        a.border < b.border and a.opacity > b.opacity
        for a, b in zip(states, states[1:], strict=False)
    )


def test_line_sparkle_burst_and_petal_exit_respect_the_text_window():
    options = {"entry_duration": 0.6, "exit_duration": 0.6, "singing": "none"}
    reference = subject(entry="fade", exit="fade", **options).lines[0]
    line = subject(entry="sparkle", exit="petal", **options).lines[0]
    assert line.lifetime == reference.lifetime
    stars = [n for n in line.children if isinstance(n, PathObject)]
    assert len(stars) == 14
    assert (
        max(n.lifetime.end for n in _walk(line) if ":particle:" in n.id)
        <= line.lifetime.end
    )


def test_slide_follows_allocated_lane_and_stars_start_at_their_sweep_position():
    doc = Document.create(
        width=640, height=360, styles=(Style(fontname="DejaVu Sans"),)
    )
    for start in (2000, 3200):
        doc.records.append(
            Line(start_time=start, end_time=start + 800, text=r"{\k80}AB")
        )
    effect = KaraokeEffects(
        entry="slide_in", exit="none", singing="none", decoration="twinkle"
    )
    scene = prepare_tracks(doc, tracks=(Track(id="main", effects=(effect,)),))
    for index, line in enumerate(scene.lines):
        assert line.track_index == index
        start_x = scene.evaluator().at(line.id, line.lifetime.start).position.x
        assert (
            (start_x < line.state.position.x)
            if index == 0
            else (start_x > line.state.position.x)
        )
        target = line.query("character")[0]
        assert target.em_size == pytest.approx(
            line.layout.body.characters[0].object.font_size * 2048 / 2384
        )
        stars = [
            node
            for node in _walk(line)
            if node.id.startswith(target.node_id + "/") and ":particle:" in node.id
        ]
        assert len(stars) == 7
        assert min(node.lifetime.start for node in stars) >= target.singing[0].start
        assert (
            max(node.lifetime.start for node in stars) > target.singing[0].start + 0.13
        )


@pytest.mark.parametrize("mode", ["brighten", "follow_after", "follow_before"])
def test_scanline_lifts_gradient_stops_on_the_selected_side(mode):
    from kara_templater import LinearGradient, LyricGradient

    calls = []

    def paint(line, target):
        calls.append(target.id)
        return LyricGradient((Color(100, 0, 0), Color(0, 40, 0)), step=4)(line, target)

    scene = subject(
        text=r"{\k100}H",
        entry="none",
        exit="none",
        singing="scanline",
        material=paint,
        scanline_mode=mode,
        scanline_width=4,
        scanline_softness=2,
        scanline_brightness=0.5,
    )
    assert len(calls) == 1
    ramps = [
        node.material.fill
        for node in _walk(scene.lines[0])
        if ":front:" in node.id and isinstance(node.material, LinearGradient)
    ]
    # The first strip is on the sung side. The outer two strips have the
    # same 5/32 weight, but the unsung background is white.
    assert ramps[0] is not None
    expected = {
        "brighten": [Color(112, 0, 0), Color(0, 57, 0)],
        "follow_after": [Color(112, 0, 0), Color(0, 57, 0)],
        "follow_before": [Color(124, 40, 40), Color(40, 74, 40)],
    }
    assert [s.color for s in ramps[0].stops] == expected[mode]
    if mode == "follow_after":
        assert ramps[-1] is not None
        assert [s.color for s in ramps[-1].stops] == [Color(243, 215, 215), Color(215, 238, 215)]
    assert scene.compile(native_tweens=True).event_count > 0


def test_dense_scanline_palettes_remain_exportable_to_gpu():
    from kara_templater import ColorRamp, ColorStop, LinearGradient

    def gradient(offset):
        return LinearGradient(space="local", axis="y", fill=ColorRamp(tuple(
            ColorStop(i * 4 + offset, Color(25 * i, 100, 255)) for i in range(9)
        )))

    scene = subject(
        text=r"{\k100}M", entry="none", exit="none", singing="scanline",
        base_material=gradient(0), material=gradient(2), scanline_mode="follow_after",
    )
    assert any(draw.gradient is not None for draw in SceneFrames(scene).at(1.5))


@pytest.mark.parametrize("mode", ["utopia", "zoom_pulse"])
def test_shared_reading_pulses_follow_each_kana_and_host_character(mode):
    scene = subject(text=r"{\k50}空空|まま", start=1000, end=1500,
                    entry="none", exit="none", singing=mode)
    evaluator = scene.evaluator()
    for role in ("character", "ruby"):
        first, second = scene.lines[0].query(role)
        scale = evaluator.at(second.node_id, 0.99).scale.x
        assert evaluator.at(first.node_id, 1.06).scale.x > scale
        assert evaluator.at(second.node_id, 1.06).scale.x == pytest.approx(scale)
        assert evaluator.at(second.node_id, 1.31).scale.x > scale


def test_multicharacter_reading_divides_its_wipe_by_shaped_cluster():
    from kara_templater import RectangleKeyframes

    scene = subject(text=r"{\k50}空|iがま", start=1000, end=1500,
                    entry="none", exit="none", singing="none")
    line, = scene.lines
    nodes = {n.id: n for n in _walk(line)}
    glyphs = line.layout.ruby[0].layout.characters
    assert [g.object.text for g in glyphs] == ["i", "が", "ま"]
    for target, start, end in zip(line.query("ruby"), (1, 1.166, 1.333),
                                  (1.166, 1.333, 1.5), strict=True):
        authored, = target.singing
        assert (authored.start, authored.end) == (1, 1.5)
        node = nodes[target.node_id]
        assert isinstance(node.clip, RectangleClip) and isinstance(node.clip.deform, RectangleKeyframes)
        knots = [round(t + node.time_origin, 6) for t in node.clip.deform.breakpoints]
        assert knots[1:-1] == [start, end]


def test_timed_readings_own_the_front_and_optional_body_sweeps_once():
    def fronts(mode):
        scene = subject(text=r"{\k25}空|そ{\k25}#|ら", start=1000, end=1500,
                        entry="none", exit="none", singing="scanline", ruby_scanline=mode)
        line = scene.lines[0]
        nodes = {n.id: n for n in _walk(line)}

        def bounds(target, ms):
            result = []
            for name in target.aliases:
                if ":front:" not in name:
                    continue
                node = nodes[name]
                assert isinstance(node.clip, RectangleClip) and node.clip.deform
                box = node.clip.deform.sample(ms / 1000 - node.time_origin)
                if box:
                    result.append(box)
            return result

        body, = line.query("character")
        assert all(bounds(r, ms) for r, ms in zip(line.query("ruby"), (1150, 1400), strict=True))
        return [bounds(body, ms) for ms in (1150, 1350)]

    assert fronts("reading") == [[], []]
    early, late = fronts("both")
    assert early and late and max(b[2] for b in early) < max(b[2] for b in late)


@pytest.mark.parametrize("mode", ["none", "scanline"])
def test_unequal_readings_reach_the_same_body_midpoint_in_exported_ass(tmp_path, mode):
    from kara_templater._raster import rasterize

    def frame(text, ms):
        scene = subject(text=text, start=1000, end=1500, entry="none", exit="none",
                        singing=mode, ruby_scanline="both", sung_outline=Color(30, 40, 50),
                        scanline_color=Color(0, 255, 255), scanline_width=16, scanline_softness=4)
        path = tmp_path / "lyric.ass"
        scene.export_compact_ass(path)
        return rasterize(path.read_text(encoding="utf-8-sig"), ms, (640, 360)).rgba

    short = frame(r"{\k10}空|そ{\k40}#|ら", 1100)
    equal = frame(r"{\k25}空|そ{\k25}#|ら", 1250)
    if mode == "none":
        assert short == equal
    else:
        def center(image):
            columns = [i // 4 % 640 for i in range(0, len(image), 4)
                       if image[i:i + 4] == bytes((0, 255, 255, 255))]
            return sum(columns) / len(columns)

        assert center(short) == pytest.approx(center(equal), abs=1)
    assert short != frame(r"{\k10}空|そ{\k40}#|ら", 1250)


@pytest.mark.parametrize(("text", "jump_ms"), [
    (r"{\k0}W|a{\k50}#|a", 1000),
    (r"{\k25}W|a{\k0}#|a{\k0}#|a{\k25}#|a", 1250),
    (r"{\k50}W|a{\k0}#|a", 1500),
])
def test_zero_length_reading_colors_its_share_at_the_checkpoint(tmp_path, text, jump_ms):
    from kara_templater._raster import rasterize

    doc = Document.create(width=640, height=360, styles=(Style(fontname="DejaVu Sans", fontsize=50),))
    doc.records.append(Line(start_time=1000, end_time=1500, text=text))
    recipe = KaraokeEffects(entry="none", exit="none", singing="none", sung=Color(255, 0, 0),
                            unsung=Color(255, 255, 255), sung_outline=Color(0, 0, 0))
    scene = prepare_tracks(doc, tracks=(Track(id="main", preview=0, tail=1, effects=(recipe,)),))
    compact = tmp_path / "lyric.ass"
    scene.export_compact_ass(compact)
    scripts = scene.compile(native_tweens=True).document.dumps(), compact.read_text(encoding="utf-8-sig")

    def red_pixels(script, ms):
        rgba = rasterize(script, ms, (640, 360)).rgba
        return sum(rgba[i:i + 4] == b"\xff\x00\x00\xff" for i in range(0, len(rgba), 4))

    for ms in (jump_ms - 10, jump_ms, jump_ms + 10):
        assert red_pixels(scripts[0], ms) == red_pixels(scripts[1], ms)
    assert red_pixels(scripts[0], jump_ms) - red_pixels(scripts[0], jump_ms - 10) > 100


def test_scanline_handoff_uses_endpoint_after_instant_final_reading():
    from kara_templater._raster import rasterize

    def handoff(first, last):
        scene = subject(text=rf"{{\k{first}}}空|そ{{\k{last}}}#|ら{{\k50}}を",
                        start=1500, end=2500, entry="none", exit="none", singing="scanline",
                        scanline_width=16, scanline_softness=3, scanline_color=Color(0, 255, 255))
        rgba = rasterize(scene.compile(native_tweens=True).document.dumps(), 2000, (640, 360)).rgba
        return [i for i in range(0, len(rgba), 4) if rgba[i:i + 4] == b"\x00\xff\xff\xff"]

    ordinary = handoff(25, 25)
    assert ordinary and handoff(50, 0) == ordinary


@pytest.mark.parametrize(("mode", "ticks", "expected"), [
    ("none", 0, (False, True, True)),
    ("no_wipe", 10, (False, False, True)),
])
def test_ruby_color_switch_at_the_annotation_boundary(tmp_path, mode, ticks, expected):
    from kara_templater._raster import rasterize

    scene = subject(text=rf"{{\k{ticks}}}空|そ{{\k{50-ticks}}}#|ら",
                    start=1000, end=1500, entry="none", exit="none", singing=mode,
                    sung=Color(255, 0, 0), unsung=Color(255, 255, 255), sung_outline=Color(0, 0, 0))
    path = tmp_path / "ruby.ass"
    scene.export_compact_ass(path)
    def ruby_has_red(script, ms):
        rgba = rasterize(script, ms, (640, 360)).rgba
        top = next(i // 640 for i, a in enumerate(rgba[3::4]) if a > 128)
        ruby = rgba[4 * 640 * top:4 * 640 * (top + 10)]
        return any(ruby[i] > 180 and ruby[i + 1] < 60 and ruby[i + 3] > 128
                   for i in range(0, len(ruby), 4))

    times = (1000, 1200 if ticks else 1010, 1500)
    for script in (scene.compile(native_tweens=True).document.dumps(), path.read_text(encoding="utf-8-sig")):
        assert tuple(ruby_has_red(script, ms) for ms in times) == expected


def test_empty_timed_reading_hides_scanline_during_rest():
    from kara_templater._raster import rasterize

    scene = subject(
        text=r"{\k10}空|そ{\k20}#|{\k20}#|ら{\k10}#|", start=1500, end=2100,
        entry="none", exit="none", singing="scanline", scanline_width=24,
        scanline_color=Color(0, 255, 255),
    )
    script = scene.compile(native_tweens=True).document.dumps()

    def visible(ms):
        rgba = rasterize(script, ms, (640, 360)).rgba
        return any(rgba[i:i + 4] == bytes((0, 255, 255, 255)) for i in range(0, len(rgba), 4))

    assert all(visible(ms) for ms in (1510, 1600, 1800, 1990, 2000))
    assert all(not visible(ms) for ms in (1500, 1610, 1790, 2010, 2090))


def test_body_scanline_holds_release_frame_and_resumes_after_a_pause():
    from kara_templater._raster import rasterize

    scene = subject(text=r"{\k40}H{\kt80\k40}Q", start=1500, end=2700,
                    entry="none", exit="none", singing="scanline", scanline_width=24,
                    scanline_color=Color(0, 255, 255), min_outline_gap=None)
    script = scene.compile(native_tweens=True).document.dumps()

    def cyan_columns(ms):
        rgba = rasterize(script, ms, (640, 360)).rgba
        return {i // 4 % 640 for i in range(0, len(rgba), 4)
                if rgba[i:i + 4] == bytes((0, 255, 255, 255))}

    assert not cyan_columns(1500)
    assert cyan_columns(1510)
    release = cyan_columns(1900)
    assert release and release == cyan_columns(2300)
    assert not cyan_columns(1910) and not cyan_columns(2290)
    assert max(cyan_columns(2350)) > max(release)
    assert not cyan_columns(2700)


def test_scanline_crosses_syllable_boundary_on_both_glyphs():
    scene = subject(
        text=r"{\k50}H{\k50}H",
        start=1000,
        end=2000,
        min_outline_gap=None,
        entry="none",
        exit="none",
        singing="scanline",
        scanline_width=24,
        scanline_softness=0,
    )
    line = scene.lines[0]
    nodes = {node.id: node for node in _walk(line)}
    for target, glyph in zip(
        line.query("character"), line.layout.body.characters, strict=True
    ):
        fronts = [nodes[name] for name in target.aliases if ":front:" in name]
        assert glyph.ink_bounds
        for t in (1.49, 1.51):
            masks = [
                node.clip.deform.sample(t - node.time_origin)
                for node in fronts
                if isinstance(node.clip, RectangleClip) and node.clip.deform
            ]
            active = [bounds for bounds in masks if bounds]
            assert len(active) == 1
            left, _, right, _ = active[0]
            assert glyph.bounds.left + left < glyph.ink_bounds.right
            assert glyph.bounds.left + right > glyph.ink_bounds.left


def test_second_row_particles_follow_synchronized_entry_and_extended_exit():
    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    for t in (2000, 4200, 6500, 8800):
        doc.records.append(Line(text=r"{\k100}A", start_time=t, end_time=t+1000))
    effect = KaraokeEffects(entry="sparkle", exit="glow_out", singing="scanline")
    scene = prepare_tracks(doc, tracks=(Track(id="main", effects=(effect,)),))
    line = scene.lines[1]
    assert line.lifetime.start == pytest.approx(0.2)
    stars = [n for n in line.children if ":particle:" in n.id]
    assert stars and max(n.lifetime.start for n in stars) < 0.6
    echoes = [n for n in _walk(line) if ":echo:glow_out:" in n.id]
    assert echoes and all(n.lifetime.start == pytest.approx(line.lifetime.end-0.3) for n in echoes)


def test_glow_echoes_stretch_with_the_core_and_scale_their_spacing():
    scene = subject(text=r"{\k100}A", entry="glow_in", entry_duration=0.6,
                    singing="none", exit="none")
    line = scene.lines[0]
    glyph, = line.query("character")
    echoes = [n for n in _walk(line) if ":echo:glow_in:" in n.id]
    left = next(n for n in echoes if n.id.endswith(":-1"))
    right = next(n for n in echoes if n.id.endswith(":1"))
    time = left.lifetime.start
    a, b = left.at(time), right.at(time)
    assert a.scale.x == pytest.approx(1.6)
    assert glyph.em_size is not None
    assert b.position.x - a.position.x == pytest.approx(2 * 0.12 * glyph.em_size * 1.6)


def test_scanline_front_reaches_outgoing_stroke_before_entering_next_letter():
    scene = subject(text=r"{\k50}M{\k50}i", end=2000, singing="scanline",
                    entry="none", exit="none", scanline_width=32, scanline_softness=0)
    line, = scene.lines
    body = line.layout.body
    first, second = body.characters
    prior = body._sweep_bounds(first.start, first.end, first)
    upcoming = body._sweep_bounds(second.start, second.end, second)
    nodes = {n.id: n for n in _walk(line)}
    target = line.query("character")[1]
    fronts = [nodes[a] for a in target.aliases if ":front:" in a]
    for t, expected in ((1.5, prior.right), (1.52, upcoming.left + 0.04 * upcoming.width)):
        centers = [
            second.object.state.position.x + (mask[0] + mask[2]) / 2 * node.state.scale.x
            for node in fronts
            if isinstance(node.clip, RectangleClip) and node.clip.deform
            and (mask := node.clip.deform.sample(t - node.time_origin))
        ]
        assert centers == pytest.approx([expected])
