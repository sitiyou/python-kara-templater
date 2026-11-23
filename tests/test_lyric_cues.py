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


def layout(right_to_left=False):
    doc = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    doc.records.append(
        Line(text=r"{\k100}AB|!ab{\k100}CD|!cd", start_time=1000, end_time=3000)
    )
    return doc, layout_document_lyrics(
        doc, len(doc.records) - 1, display=Lifetime(0, 4), right_to_left=right_to_left
    )


@pytest.mark.parametrize("right_to_left", [False, True])
def test_ruby_keeps_body_center_offset_during_multiple_reservations_and_releases(right_to_left):
    _, original = layout(right_to_left)
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
        == pytest.approx(-95 if right_to_left else 95)
    )


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
    presets = {"bars": CuePreset(factory=BarsCue())}
    from_input = bind_lyric_cues(imported, presets)
    from_code = bind_lyric_cues(
        original, presets, markers=(CueMarker("intro", "bars"),)
    )
    assert (
        Scene(Document.create()).add(from_input.group()).ass.compile().document.dumps()
        == Scene(Document.create()).add(from_code.group()).ass.compile().document.dumps()
    )
    scene = Scene(doc).add(from_input.group())
    scene.replace_source(len(doc.records) - 1)
    result = scene.ass.compile()
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
    from kara_templater import Color, ObjectGroup, PathObject

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
        visible = [n for n in group.children if isinstance(n, PathObject) and n.lifetime.contains(time)]
        bars = [n for n in visible if n.filled]
        outer = [n for n in visible if not n.filled]
        assert len(bars) == len(outer) == 3
        assert sum(n.state.outline == Color.hex("#FFCB86") for n in outer) == covered
        assert sum(n.state.fill == Color(255, 90, 111) for n in bars) == covered
        assert all(
            evaluator.at(n.id, time).opacity == pytest.approx(opacity) for n in bars
        )
    assert group.lifetime.end == 3
    assert all(not n.lifetime.contains(3) for n in group.children)


@pytest.mark.parametrize(
    ("transition", "opacity"),
    [(0, (1, 0, 0, 1)), (0.67, (0.8, 0.2, 0.2, 0.8)), (1, (0.866, 0.464, 0.464, 0.866))],
)
def test_volume_flash_softness_preserves_fill_time(transition, opacity):
    from kara_templater import ObjectGroup, VolumeCue

    doc, lyrics = layout()
    cue = VolumeCue(flashes=1, transition=transition)
    bound = bind_lyric_cues(
        lyrics, {"lead": CuePreset(factory=cue)}, markers=(CueMarker("intro", "lead"),)
    )
    (group,) = bound.inline[0].children
    assert isinstance(group, ObjectGroup)
    scene = Scene(doc).add(bound.group())
    evaluator = scene.evaluator()
    assert [evaluator.at(group.id, t).opacity for t in (0.1, 0.15, 0.35, 0.4)] == pytest.approx(opacity)
    assert evaluator.at(group.id, 0.5).opacity == 1


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
    assert Scene(doc).add(bound.group()).ass.compile().event_count > 0


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


def test_signal_waits_before_nonuniform_countdown_and_keeps_all_slots():
    from kara_templater import SignalCue

    doc, lyrics = layout()
    preset = CuePreset(factory=SignalCue(countdown=0.4, size=20, spacing=8), steps=(0, 0.25, 1))
    bound = bind_lyric_cues(lyrics, {"lamp": preset}, markers=(CueMarker("intro", "lamp"),))
    right, left = bound.inline[0].children
    assert right.state.position.x - left.state.position.x == 38
    assert bound.cues[0].content.width == 58
    assert right.lifetime.end == pytest.approx(0.7)
    assert left.lifetime.end == 1
    scene = Scene(doc).add(bound.group())
    assert scene.evaluator().at(right.id, 0.59).opacity == 1
    assert scene.evaluator().at(right.id, 0.6665).opacity == pytest.approx(0.5)
    assert scene.ass.compile().event_count > 0


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


@pytest.mark.parametrize(("align", "tops"), [
    ("top", [0, 0, 0]), ("center", [0, 12.5, 25]), ("bottom", [0, 25, 50]),
])
def test_volume_alignment_and_size_ratios(align, tops):
    from kara_templater import (
        CueContext,
        EventOrigin,
        ObjectGroup,
        SignalCue,
        SourceRef,
        VolumeCue,
    )

    context = CueContext("count", Lifetime(0, 2), (0, 1, 2),
                         EventOrigin((SourceRef("timed"),), "cue"), host_em=64)
    cue = VolumeCue(count=3, flashes=0, border=0, ratio=3, align=align,
                    size_ratio=0.75, column_width_ratio=1/3)
    content = cue(context)
    assert (content.width, content.height) == (75, 75)
    group, = content.objects
    assert isinstance(group, ObjectGroup)
    bars = [bar for bar in group.children if bar.lifetime.contains(1.9)]
    assert [bar.state.position for bar in bars] == [Vec2(i * 25, y) for i, y in enumerate(tops)]
    assert SignalCue(size_ratio=0.75)(context).height == 75
    assert SignalCue(size=12, size_ratio=0.75)(context).height == 12


def test_default_signals_follow_authored_font_sizes_and_explicit_sizes_win():
    from kara_templater import SignalCue, VolumeCue

    doc = Document.create(styles=(
        Style(name="Main", fontname="DejaVu Sans", fontsize=80),
        Style(name="Harmony", fontname="DejaVu Serif", fontsize=40),
    ))
    doc.records.append(Line(style="Main", text=r"{\k50}A{\rHarmony\k50}B", start_time=1000, end_time=2000))
    lyrics = layout_document_lyrics(doc, len(doc.records) - 1)
    cues = bind_lyric_cues(
        lyrics,
        {"lead": CuePreset(factory=VolumeCue()), "lamp": CuePreset(factory=SignalCue()),
         "fixed": CuePreset(factory=SignalCue(size=24))},
        markers=(CueMarker("a", "lead", 0), CueMarker("b", "lamp", 1), CueMarker("c", "fixed", 2)),
    )
    assert [cue.content.height for cue in cues.cues] == [40, 20, 24]


def test_cues_share_first_visible_role_colors_at_marker_font_size():
    from kara_templater import (
        Color,
        ObjectGroup,
        Paint,
        PaintPair,
        SignalCue,
        VolumeCue,
    )

    doc = Document.create(styles=(
        Style(name="Main", fontname="DejaVu Sans", fontsize=80),
        Style(name="Harmony", fontname="DejaVu Sans", fontsize=40),
    ))
    doc.styles["Harmony"].fields.update(PrimaryColour="&H0000FF", SecondaryColour="&H00FF00",
                                       OutlineColour="&HFF0000")
    doc.records.append(Line(style="Main", text=r"{\k20} {\rHarmony\k40}B{\rMain\k40}C",
                            start_time=1000, end_time=2000))
    layout = layout_document_lyrics(doc, len(doc.records) - 1)
    fixed = PaintPair(Paint(Color.hex("#112233")), Paint(Color.hex("#334455")))
    presets = {
        "bar": CuePreset(factory=VolumeCue(count=1)),
        "lamp": CuePreset(factory=SignalCue(edge_brightness=0), colors=fixed),
    }
    bound = bind_lyric_cues(layout, presets, markers=(
        CueMarker("bar", "bar", 2), CueMarker("lamp", "lamp", 2),
    ))
    bar, lamp = bound.cues
    assert bar.content.height == 40
    bar_group, lamp_group = bar.content.objects[0], lamp.content.objects[0]
    assert isinstance(bar_group, ObjectGroup) and isinstance(lamp_group, ObjectGroup)
    assert {(p.state.fill, p.state.outline) for p in bar_group.children} == {
        (Color.hex("#00FF00"), Color.hex("#0000FF")),
        (Color.hex("#FF0000"), Color.hex("#0000FF")),
    }
    assert lamp_group.children[0].state.fill == fixed.after.fill


def test_role_zoom_tracks_each_step_and_releases_completed_volume_column():
    from kara_templater import (
        CueContext,
        EventOrigin,
        ObjectGroup,
        SignalCue,
        SourceRef,
        VolumeCue,
    )

    context = CueContext("intro", Lifetime(0, 2), (0, 0.5, 2), EventOrigin((SourceRef("voice"),), "cue"),
                         zoom_pulse_curve_level=3)
    lamps = SignalCue(edge_brightness=0)(context).objects
    first, second = lamps
    assert isinstance(first, ObjectGroup) and isinstance(second, ObjectGroup)
    assert first.children[0].at(0.25).scale.x == pytest.approx(1.0875)
    assert second.children[0].at(0.25).scale.x == 1
    assert second.children[0].at(1.25).scale.x == pytest.approx(1.0875)
    (volume,) = VolumeCue(count=2, flashes=0)(context).objects
    assert isinstance(volume, ObjectGroup)
    bar = volume.children[0]
    assert bar.at(1).scale.x == pytest.approx(1.10)
    assert bar.at(1.15).scale.x == pytest.approx(1.0875)
    assert bar.at(1.3).scale.x == pytest.approx(1)


def test_role_paint_switches_both_volume_strokes_without_changing_column_slots():
    from kara_templater import (
        Color,
        CueContext,
        EventOrigin,
        Glow,
        ObjectGroup,
        Paint,
        PaintPair,
        PathObject,
        SignalCue,
        SourceRef,
        VolumeCue,
    )

    before = Paint(border=4, glow=Glow(Color.hex("#DD88FF"), border=8))
    after = Paint(border=2, glow=Glow(Color.hex("#1166FF"), border=12))
    context = CueContext("role", Lifetime(0, 4), (0, 2, 4),
                         EventOrigin((SourceRef("voice"),), "cue"),
                         colors=PaintPair(before, after), role_em=100)
    bars = VolumeCue(count=2, height=50, flashes=0)(context)
    group, = bars.objects
    assert isinstance(group, ObjectGroup)
    layers = [n for n in group.children if isinstance(n, PathObject) and "/column:1:" in n.id]
    old_ring, old_body, new_ring, new_body = layers
    # The second column's outer ink can cover the first one's body.
    column_zero = next(n for n in group.children if isinstance(n, PathObject) and "/column:0:" in n.id and n.filled)
    ordered = sorted(group.children, key=lambda n: n.layer)
    assert ordered.index(column_zero) < ordered.index(old_ring) < ordered.index(old_body)
    assert old_body.state.position == new_body.state.position
    assert old_ring.state.position == new_ring.state.position
    assert not old_ring.filled and not new_ring.filled
    assert (old_ring.state.outline, new_ring.state.outline) == (Color.hex("#DD88FF"), Color.hex("#1166FF"))
    assert (old_ring.state.border, old_body.state.border) == (4, 2)
    # The narrow column caps each pen independently to half the column width.
    assert (new_ring.state.border, new_body.state.border) == (4, 1)
    lamp = SignalCue(size=50, edge_brightness=0)(context).objects[0]
    assert isinstance(lamp, ObjectGroup)
    assert lamp.children[0].state.border == 6
    assert lamp.children[0].state.outline == new_ring.state.outline


def test_strokeless_signal_renders_a_soft_glow_outside_the_body():
    from dataclasses import replace

    from kara_templater import (
        Color,
        CueContext,
        EventOrigin,
        Glow,
        ObjectGroup,
        Paint,
        PaintPair,
        SignalCue,
        SourceRef,
        VisualState,
    )
    from kara_templater._raster import rasterize

    red, blue = Color(255, 0, 0), Color(0, 0, 255)
    palette = PaintPair(Paint(), Paint(fill=red, border=0, glow=Glow(blue, blur=6)))
    context = CueContext("cue", Lifetime(0, 2), (0, 2), EventOrigin((SourceRef("voice"),), "cue"),
                         colors=palette, role_font_size=40)
    lamp, = SignalCue(shape="square", size=40, border=0, edge_brightness=0)(context).objects
    assert isinstance(lamp, ObjectGroup)
    lamp = replace(lamp, state=VisualState(position=Vec2(16, 16)))
    scene = Scene(Document.create(width=80, height=80)).add(lamp)
    rgba = rasterize(scene.ass.compile().document.dumps(), 0, (80, 80)).rgba
    outer = (36 * 80 + 12) * 4
    center = (36 * 80 + 36) * 4
    # Six-pixel-wide pen convolved with a sigma-6 Gaussian, 3.5 px outside.
    assert rgba[outer + 2] > 0 and 77 <= rgba[outer + 3] <= 89
    assert tuple(rgba[center:center + 4]) == (255, 0, 0, 255)


def test_vertical_inline_cue_reserves_and_releases_height_for_body_and_ruby():
    doc, _ = layout()
    original = layout_document_lyrics(doc, len(doc.records) - 1, display=Lifetime(0, 4), vertical=True)
    bound = bind_lyric_cues(original, {"bars": CuePreset(factory=BarsCue(width=90, height=20), gap=7,
                                                       keep_space=False)}, markers=(CueMarker("intro", "bars"),))
    cue, = bound.cues
    assert cue.position.x + cue.content.width / 2 == original.body.characters[0].bounds.center
    for before, after in ((original.body, bound.lyrics.body), (original.ruby[0].layout, bound.lyrics.ruby[0].layout)):
        a, b = before.characters[0].object, after.characters[0].object
        assert b.at(0.5).position - a.at(0.5).position == Vec2(0, 27)
        assert b.at(1.5).position == a.at(1.5).position


@pytest.mark.parametrize("kind", ["circle", "square", "rounded", "star", "note8", "note16",
                                  "notepair", "bars", "volume", "text"])
def test_cue_render_is_independent_of_the_lyric_font(kind):
    from kara_templater import (
        CueContext,
        EventOrigin,
        ObjectGroup,
        SignalCue,
        SourceRef,
        TextObject,
        VolumeCue,
    )
    from kara_templater._raster import rasterize

    factory = {"bars": BarsCue(), "volume": VolumeCue(flashes=0), "text": TextCue()}.get(kind)
    if factory is None:
        factory = SignalCue(shape=kind)
    life = Lifetime(0, 3)
    frames = []
    heights = []
    for font, size, measured_em in (("DejaVu Sans", 48, 40), ("DejaVu Serif", 48, 45), ("DejaVu Sans", 96, 80)):
        host = TextObject(id="host", text="A", font=font, font_size=size, lifetime=life)
        content = factory(CueContext("cue", life, (0, 1, 2, 3), EventOrigin((SourceRef("lyric"),), "test"),
                                     host=host, host_height=measured_em, host_em=measured_em, role_font_size=size))
        heights.append(content.height)
        scene = Scene(Document.create(width=240, height=100)).add(
            ObjectGroup(id="row", lifetime=life, children=content.objects))
        frames.append(rasterize(scene.ass.compile().document.dumps(), 2250, (240, 100)).rgba)
    assert any(frames[0][3::4])
    assert frames[0] == frames[1]
    assert heights[2] == pytest.approx(2 * heights[0], abs=1)
