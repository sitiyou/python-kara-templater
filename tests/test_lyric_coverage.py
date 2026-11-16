"""Lyric ownership and edits use the normal Scene coverage strategy."""

from dataclasses import replace

import pytest
from PIL import Image, ImageChops

from kara_templater import (
    PINK,
    Coverage,
    Document,
    FadeOut,
    Glow,
    GlowFunction,
    Highlight,
    HighlightPass,
    Layout,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    ObjectGroup,
    PathObject,
    RasterSettings,
    Region,
    SceneBudget,
    SceneCompileError,
    StateFunction,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    prepare_tracks,
)
from kara_templater._raster import rasterize

BUDGET = SceneBudget(fps=10, max_events=100_000, max_active=10_000)


def source():
    doc = Document.create(
        width=160,
        height=100,
        styles=(Style(fontname="DejaVu Sans", fontsize=20, shadow=0, outline=0),),
    )
    doc.records.append(Line(text=r"{\c&HFFFF00&\k20}AB", start_time=0, end_time=400))
    return doc


def paint(line: LyricLine) -> LyricLine:
    return LyricHighlights(
        highlights=tuple(
            Highlight(
                str(index),
                index,
                tuple(
                    HighlightPass(
                        TimeSpan(segment.singing.start, segment.singing.end),
                        Region(box.left, box.right),
                        round=round_id,
                    )
                    for round_id, segment in enumerate(unit.segments)
                ),
                StatePatch(fill=PINK),
            )
            for index, unit in enumerate(line.layout.lyrics.units)
            for box in (line.layout.body.range_bounds(unit.start, unit.end),)
        ),
        strategy="coverage",
    ).apply(line)


def track(**changes):
    return replace(
        Track(
            id="lyrics",
            layout=Layout(position=Vec2(30, 40)),
            preview=0,
            tail=0,
            factory=paint,
        ),
        **changes,
    )


def test_preparation_defers_animation_callbacks_and_preserves_source():
    calls = []
    config = track(
        animations=(
            LyricRule(
                "syllable",
                "singing",
                Tween(
                    StatePatch(scale=Vec2(1.2, 1.2)),
                    rate=lambda t: calls.append(t) or t,
                ),
            ),
        )
    )
    doc = source()
    before = doc.dumps()
    scene = prepare_tracks(doc, tracks=(config,))
    assert not calls
    assert doc.dumps() == before
    assert scene.lines[0].coverage is not None
    assert scene.lines[0].coverage.partitions
    result = scene.compile(budget=BUDGET)
    assert calls and result.event_count
    assert doc.dumps() == before
    assert any(
        record.comment and r"\k20" in record.text for record in result.document.lines
    )


def test_selection_restore_and_other_owners_survive_coverage_regeneration():
    doc = source()
    doc.records.append(Line(text=r"{\k20}CD", start_time=0, end_time=400))
    selected = track(source=lambda item: item.text == "AB")
    first = (
        prepare_tracks(doc, tracks=(selected,), owner="one")
        .compile(budget=BUDGET)
        .document
    )
    again = (
        prepare_tracks(first, tracks=(selected,), owner="one")
        .compile(budget=BUDGET)
        .document
    )
    assert first.dumps() == again.dumps()
    assert any(not line.comment and line.text == r"{\k20}CD" for line in first.lines)
    second = (
        prepare_tracks(
            first, tracks=(track(source=lambda item: item.text == "CD"),), owner="two"
        )
        .compile(budget=BUDGET)
        .document
    )
    restored = (
        prepare_tracks(second, tracks=(), owner="one").compile(budget=BUDGET).document
    )
    assert any(not line.comment and r"\k20}AB" in line.text for line in restored.lines)
    assert any(line.effect.startswith("kara:scene:v1:two:") for line in restored.lines)
    assert not any(
        line.effect.startswith("kara:scene:v1:one:") for line in restored.lines
    )


def test_translation_and_custom_decoration_reach_actual_ass():
    scene = prepare_tracks(source(), tracks=(track(),))
    before = scene.compile(budget=BUDGET)
    line = scene.lines[0]
    scene.objects[0] = line.copy(id=line.id, offset=Vec2(8, 4))
    after = scene.compile(budget=BUDGET)
    original = rasterize(before.document.dumps(), 350, (160, 100))
    actual = rasterize(after.document.dumps(), 350, (160, 100))
    for y in range(96):
        assert (
            actual.rgba[((y + 4) * 160 + 8) * 4 : ((y + 4) * 160 + 160) * 4]
            == original.rgba[(y * 160) * 4 : (y * 160 + 152) * 4]
        )
    decoration = PathObject(
        id="accent",
        lifetime=Lifetime(0, 0.4),
        path=VectorPath.rectangle(10, 5),
        state=VisualState(position=Vec2(5, 5), fill=PINK),
    )
    scene.add(decoration)
    picture = rasterize(scene.compile(budget=BUDGET).document.dumps(), 350, (160, 100))
    offset = (7 * 160 + 7) * 4
    assert picture.rgba[offset : offset + 4] == bytes(
        (PINK.red, PINK.green, PINK.blue, 255)
    )


def test_glow_only_animation_boundaries_and_runtime_bounds():
    def factory(line):
        line = paint(line)
        assert line.coverage is not None
        glow = GlowFunction(
            lambda state, t: Glow(PINK, blur=2 + 2 * min(t / 0.03, 1)),
            max_blur=4,
            max_border=0,
            breakpoints=(0.03,),
        )
        glows = {
            identity: glow
            for target in line.query("character")
            for identity in (target.node_id, *target.aliases)
        }
        return replace(line, coverage=replace(line.coverage, glows=glows))

    scene = prepare_tracks(source(), tracks=(track(factory=factory),))
    result = scene.compile(budget=BUDGET)
    assert result.objects[0].sample_times[:2] == pytest.approx((0.015, 0.065))
    line = scene.lines[0]
    assert line.coverage is not None
    invalid = {
        name: replace(value, max_blur=1) for name, value in line.coverage.glows.items()
    }
    scene.objects[0] = replace(line, coverage=replace(line.coverage, glows=invalid))
    with pytest.raises(SceneCompileError, match="bounds"):
        scene.compile(budget=BUDGET)
    with pytest.raises(SceneCompileError, match="budget"):
        prepare_tracks(source(), tracks=(track(),)).compile(
            budget=replace(BUDGET, max_events=1)
        )


def test_nested_lyric_and_parent_opacity_have_one_contribution_per_material():
    scene = prepare_tracks(source(), tracks=(track(),))
    line = scene.lines[0]
    syllable = line.children[0]
    assert isinstance(syllable, ObjectGroup)
    line = replace(
        line,
        state=replace(line.state, opacity=0.7),
        children=(replace(syllable, state=replace(syllable.state, opacity=0.3)),),
    )
    scene.objects[0] = line
    frame = rasterize(scene.compile(budget=BUDGET).document.dumps(), 350, (160, 100))
    # Fully sung interior: .7 line alpha times .3 syllable alpha, regardless of
    # before/after fragments. Assert independent arithmetic, not a second renderer.
    offset = max(range(0, len(frame.rgba), 4), key=lambda i: frame.rgba[i + 3])
    assert tuple(frame.rgba[offset : offset + 3]) == (PINK.red, PINK.green, PINK.blue)
    assert frame.rgba[offset + 3] == pytest.approx(255 * 0.7 * 0.3, abs=1)
    assert line.coverage is not None and isinstance(line.coverage, Coverage)


def test_frame_preflight_rejects_before_animation_callbacks_without_mutating_input():
    calls: list[float] = []

    def limited(line: LyricLine) -> LyricLine:
        decorated = paint(line)
        assert decorated.coverage is not None
        return replace(
            decorated,
            coverage=replace(decorated.coverage, settings=RasterSettings(max_frames=1)),
        )

    configured = track(
        factory=limited,
        animations=(
            LyricRule(
                "character",
                "singing",
                Tween(
                    StatePatch(scale=Vec2(1.2, 1.2)),
                    rate=lambda p: calls.append(p) or p,
                ),
            ),
        ),
    )
    document = source()
    original = document.dumps()
    scene = prepare_tracks(document, tracks=(configured,))
    assert not calls
    with pytest.raises(SceneCompileError, match="frame budget"):
        scene.compile(budget=BUDGET)
    assert not calls
    assert document.dumps() == original


def test_coverage_character_budget_reports_the_group_and_keeps_source():
    document = source()
    original = document.dumps()
    scene = prepare_tracks(document, tracks=(track(),))
    line = scene.lines[0]
    assert line.coverage is not None
    scene.objects[0] = replace(
        line,
        coverage=replace(line.coverage, settings=RasterSettings(max_output_chars=1)),
    )
    with pytest.raises(SceneCompileError, match="coverage output budget") as error:
        scene.compile(budget=BUDGET)
    assert error.value.object_id == line.id
    assert document.dumps() == original


def test_empty_drawings_and_unselected_sources_do_not_generate_pixels():
    document = source()
    document.lines[0].text = r"{\k20}   "
    empty = prepare_tracks(document, tracks=(track(),)).compile(budget=BUDGET)
    assert empty.event_count == 0
    assert not any(rasterize(empty.document.dumps(), 100, (160, 100)).rgba)
    unselected = prepare_tracks(
        document, tracks=(track(source=lambda source: False),)
    ).compile(budget=BUDGET)
    assert unselected.event_count == 0
    assert any(
        not event.comment and event.text == r"{\k20}   "
        for event in unselected.document.lines
    )


def test_scene_byte_budget_covers_all_coverage_lines_and_keeps_sources():
    document = source()
    original = document.dumps()
    scene = prepare_tracks(document, tracks=(track(),))
    one = scene.compile(budget=BUDGET)
    scene.add(scene.lines[0].copy(id="second", delay=1))
    two = scene.compile(budget=BUDGET)
    one_bytes = len(one.document.dumps().encode("utf-8"))
    two_bytes = len(two.document.dumps().encode("utf-8"))
    assert two_bytes > one_bytes
    with pytest.raises(SceneCompileError, match="byte budget"):
        scene.compile(budget=replace(BUDGET, max_bytes=(one_bytes + two_bytes) // 2))
    assert document.dumps() == original


def test_color_error_budget_reduces_events_with_bounded_composited_error():
    scene = prepare_tracks(source(), tracks=(track(),))
    line = scene.lines[0]
    assert line.coverage is not None
    glows = {
        identity: Glow(PINK, blur=4, border=2, opacity=0.7)
        for target in line.query("character")
        for identity in (target.node_id, *target.aliases)
    }
    line = replace(line, coverage=replace(line.coverage, glows=glows))
    scene.objects[0] = line
    exact = scene.compile(budget=BUDGET)
    assert line.coverage is not None
    scene.objects[0] = replace(
        line,
        coverage=replace(line.coverage, settings=RasterSettings(max_channel_error=4)),
    )
    reduced = scene.compile(budget=BUDGET)
    assert reduced.objects[0].max_channel_error == 4
    assert reduced.event_count < exact.event_count
    for time in (0, 100, 200, 350):
        before = Image.frombytes(
            "RGBA", (160, 100), rasterize(exact.document.dumps(), time, (160, 100)).rgba
        )
        after = Image.frombytes(
            "RGBA",
            (160, 100),
            rasterize(reduced.document.dumps(), time, (160, 100)).rgba,
        )
        for color in ("black", "white", "gray"):
            background = Image.new("RGBA", (160, 100), color)
            left = Image.alpha_composite(background, before).convert("RGB")
            right = Image.alpha_composite(background, after).convert("RGB")
            assert max(ImageChops.difference(left, right).tobytes()) <= 4


def test_line_opacity_composes_body_and_ruby_once_and_releases_at_boundary():
    document = source()
    document.lines[0].text = r"{\k20}A|a"
    scene = prepare_tracks(document, tracks=(track(),))
    line = scene.lines[0]
    assert line.query("ruby")
    full = scene.compile(budget=BUDGET).document.dumps()
    scene.objects[0] = line.animate(
        StateFunction(
            lambda state, p: replace(state, opacity=0.5), frozenset(("opacity",))
        ),
        duration=0.08,
        hold=False,
    )
    half = scene.compile(budget=BUDGET).document.dumps()
    # Both samples fall before the sweep reaches this one-letter lyric's end.
    # Compare the same sample center by splitting the reference at 80 ms too.
    scene.objects[0] = line.animate(
        StateFunction(lambda state, p: state, frozenset(("opacity",))),
        duration=0.08,
        hold=False,
    )
    aligned = scene.compile(budget=BUDGET).document.dumps()
    a = rasterize(aligned, 40, (160, 100)).rgba
    b = rasterize(half, 40, (160, 100)).rgba
    assert any(a[3::4])
    for index in range(0, len(a), 4):
        assert b[index + 3] == pytest.approx(a[index + 3] / 2, abs=1)
        if b[index + 3]:
            assert b[index : index + 3] == a[index : index + 3]
    assert rasterize(half, 80, (160, 100)) == rasterize(aligned, 80, (160, 100))
    assert rasterize(half, 350, (160, 100)) == rasterize(full, 350, (160, 100))


def test_sweep_hold_and_exit_extend_display_without_retiming_source():
    document = source()
    document.lines[0].start_time = 1000
    document.lines[0].end_time = 1200
    original = document.dumps()
    plain = prepare_tracks(document, tracks=(track(preview=0.2, tail=0.2),))
    result = plain.compile(budget=BUDGET)
    script = result.document.dumps()

    def frame(ms):
        return rasterize(script, ms, (160, 100))

    assert frame(800) == frame(950)
    assert frame(1250) == frame(1350)
    assert frame(1050) != frame(1250)
    assert any(
        event.start_time == 800 and event.end_time >= 1000
        for event, _ in result.event_origins
    )
    assert all(
        origin is not None and origin.sources for _, origin in result.event_origins
    )
    extended = prepare_tracks(
        document,
        tracks=(
            track(
                preview=0.2,
                animations=(LyricRule("line", "exit", FadeOut(), duration=0.2),),
            ),
        ),
    )
    assert (
        extended.lines[0].query("character")[0].singing
        == plain.lines[0].query("character")[0].singing
    )
    assert extended.plans[0].placement.display.end == pytest.approx(1.4)
    assert extended.plans[0].input.required.end == pytest.approx(1.4)
    output = extended.compile(budget=BUDGET)
    faded = rasterize(output.document.dumps(), 1250, (160, 100)).rgba
    full = frame(1350).rgba
    # The 1250ms midpoint is one quarter through the authored 200ms exit.
    for index in range(3, len(full), 4):
        assert faded[index] == pytest.approx(full[index] * 0.75, abs=1)
    assert max(event.end_time for event, _ in output.event_origins) == 1400
    assert document.dumps() == original


def test_dynamic_glow_width_radius_and_none_match_static_materials():
    scene = prepare_tracks(source(), tracks=(track(),))
    line = scene.lines[0]
    assert line.coverage is not None
    appearances = (Glow(PINK, blur=2, border=1), Glow(PINK, blur=6, border=4), None)
    identities = tuple(
        identity
        for target in line.query("character")
        for identity in (target.node_id, *target.aliases)
    )
    dynamic = GlowFunction(
        lambda state, t: appearances[0 if t < 0.1 else 1 if t < 0.2 else 2],
        max_blur=6,
        max_border=4,
        breakpoints=(0.1, 0.2),
    )
    scene.objects[0] = replace(
        line, coverage=replace(line.coverage, glows=dict.fromkeys(identities, dynamic))
    )
    result = scene.compile(budget=BUDGET)
    for time, appearance in zip((50, 150, 350), appearances, strict=True):
        scene.objects[0] = replace(
            line,
            coverage=replace(
                line.coverage,
                glows={}
                if appearance is None
                else dict.fromkeys(identities, appearance),
            ),
        )
        expected = scene.compile(budget=BUDGET)
        actual = rasterize(result.document.dumps(), time, (160, 100))
        assert any(actual.rgba[3::4])
        assert actual == rasterize(expected.document.dumps(), time, (160, 100))


def test_partial_glow_overrides_keep_role_geometry_and_reusable_defaults():
    from kara_templater import BLUE, CYAN, WHITE, Scene

    doc = Document.create(
        width=160,
        height=100,
        styles=(Style(fontname="DejaVu Sans", fontsize=20, shadow=0, outline=0),),
    )
    doc.records.append(Line(text=r"{\k20}AB|ab", start_time=0, end_time=400))
    line = prepare_tracks(doc, tracks=(track(factory=None),)).lines[0]
    body = Glow(WHITE, blur=10, border=10, opacity=0.5)
    ruby = Glow(WHITE, blur=6, border=6, opacity=0.5)
    bases = {"character": body, "ruby": ruby}
    targets = line.query("character", "ruby")
    overridden = {
        target.node_id: replace(bases[target.role], color=CYAN)
        for target in targets
    }
    explicit = {
        target.node_id: Glow(
            CYAN,
            blur=6 if target.role == "ruby" else 10,
            border=6 if target.role == "ruby" else 10,
            opacity=0.5,
        )
        for target in targets
    }
    # Material recoloring is independent of the coverage glow configuration.
    from kara_templater import LyricSweep

    painted = LyricSweep(fill=BLUE, width=0).apply(line)
    actual = Scene(doc).add(replace(painted, coverage=Coverage(glows=overridden)))
    reference = Scene(doc).add(replace(painted, coverage=Coverage(glows=explicit)))
    output = actual.compile(budget=BUDGET).document.dumps()
    expected = reference.compile(budget=BUDGET).document.dumps()
    for time in (100, 300):
        pixels = rasterize(output, time, (160, 100)).rgba
        assert any(pixels[3::4])
        assert pixels == rasterize(expected, time, (160, 100)).rgba
    assert body == Glow(WHITE, blur=10, border=10, opacity=0.5)
    assert ruby == Glow(WHITE, blur=6, border=6, opacity=0.5)
    assert line.coverage is None
