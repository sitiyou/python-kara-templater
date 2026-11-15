from copy import deepcopy
from dataclasses import replace

import pytest
from track_helpers import compile_tracks

from examples._lyrics import document
from kara_templater import (
    BLUE,
    CYAN,
    GREEN,
    RED,
    UNSET,
    WHITE,
    Animate,
    Animation,
    AnimationContext,
    AnimationTarget,
    Blur,
    Body,
    Display,
    DisplayWindow,
    DoubleLine,
    Envelope,
    FadeInAnimation,
    FadeOutAnimation,
    KaraokeItem,
    KaraokeLine,
    LineMatch,
    On,
    Overlay,
    Paint,
    PaintStyle,
    Parallel,
    Ruby,
    RubySpan,
    Segment,
    Sequence,
    SingingPulseAnimation,
    SingleLine,
    StyleSheet,
    Sweep,
    Syllable,
    TextSpan,
    TextStyle,
    TextUnit,
    Track,
    compile_layers,
    layout_line,
    on,
    rule,
)
from kara_templater._track_types import TrackContext
from kara_templater.behaviors import bind_property


def item(
    *, identity="one", start=1000, end=2000, window=(0, 3000), text="AB", ruby="a"
):
    return KaraokeItem(
        identity,
        KaraokeLine((TextUnit(text, (Segment(start, end, ruby),)),)),
        "Default",
        DisplayWindow(*window),
    )


def build(track, source=None):
    source = item() if source is None else source
    doc = document(fontname="DejaVu Sans", text="AB")
    bound = track.bind((source,))[source.id]
    style = doc.styles["Default"]
    style, ruby_style = bound.prepare_styles(
        style, replace(style, name="ruby", fontsize=24)
    )
    context = TrackContext(
        layout_line(
            source.source, style=style, ruby_style=ruby_style, resolution=(640, 480)
        ),
        style,
        ruby_style,
        (640, 480),
    )
    return bound.build(source, context)


def test_direct_configuration_and_partial_overlay_geometry():
    shared = PaintStyle(fill=BLUE, blur=Blur(color=CYAN))
    track = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(fill=WHITE, stroke_width=5, blur=Blur(radius=10, width=10))
        ),
        ruby=Ruby(style=TextStyle(stroke_width=3, blur=Blur(radius=6, width=6))),
        overlay=Overlay(style=shared),
    )
    plan = build(track)
    for role, border, width, radius in (("ruby", 3, 6, 6), ("Default", 5, 10, 10)):
        sung = [
            layer.paint
            for layer in plan.layers
            if layer.style.name == role and layer.paint.fill == BLUE
        ]
        assert sung
        assert all(
            p.border == border and p.glow.border == width and p.glow.blur == radius
            for p in sung
        )
        assert all(p.glow.color == CYAN for p in sung)
    assert isinstance(shared.blur, Blur)
    assert shared.blur.width is UNSET


def test_overlay_role_override_disable_and_target_validation():
    track = Track(
        source=LineMatch(),
        ruby=Ruby(),
        overlay=Overlay(style=PaintStyle(fill=BLUE), ruby=PaintStyle(fill=RED)),
    )
    plan = build(track)
    assert any(
        layer.style.name == "ruby" and layer.paint.fill == RED for layer in plan.layers
    )
    track.overlay = Overlay(style=PaintStyle(fill=BLUE), ruby=None)
    plan = build(track)
    assert all(
        layer.paint.fill != BLUE for layer in plan.layers if layer.style.name == "ruby"
    )
    with pytest.raises(ValueError, match="no Ruby"):
        Track(source=LineMatch(), overlay=Overlay(targets=(Ruby,)))
    with pytest.raises(TypeError, match="TextStyle"):
        Overlay(style=TextStyle(font_size=100))


def test_ordinary_subclasses_explicit_parameters_and_reuse():
    class Accent(Animation):
        def __init__(self, *, peak: float = 1.2) -> None:
            super().__init__()
            self.peak = peak

        @on(Syllable.Singing)
        def pulse(self, event: Syllable.Singing) -> Animate:
            return Animate(event.target, scale=Envelope(peak=self.peak, release=240))

    class Lead(Track):
        def __init__(self, *, source, peak=1.2):
            super().__init__(
                source=source,
                body=Body(style=TextStyle(fill=RED)),
                animations=(Accent(peak=peak),),
            )

    animation = Accent(peak=1.3)
    track = Track(source=LineMatch(), animations=(animation,))
    first, second = track.bind((item(),))["one"], track.bind((item(),))["one"]
    assert first.config is not second.config
    assert first.config.animations[0] is not animation
    assert first.rules == second.rules
    assert build(Lead(source=LineMatch())).layers
    with pytest.raises(TypeError):
        Accent(unknown=1)  # ty: ignore[unknown-argument]


def test_envelope_release_and_separate_lambda_rates():
    animation = SingingPulseAnimation(
        peak=1.2, attack=100, release=200, rise=lambda p: p * p, fall=lambda p: p * p
    )
    source = item()
    (rule,) = animation.bind(AnimationContext(source))
    motion = bind_property(rule, source.source.units[0].segments, source.window, (0, 0))
    assert motion is not None
    assert rule.during == (1000, 2200)
    assert motion.at(1050) == pytest.approx(1.05)
    assert motion.at(1500) == pytest.approx(1.2)
    assert motion.at(2100) == pytest.approx(1.15)
    assert motion.at(2200) == 1


@pytest.mark.parametrize(
    "duration,attack,release",
    [(0, 0, 0), (0, 80, 160), (30, 80, 160), (30, 0, 0), (100, 80, 0)],
)
def test_short_and_zero_length_envelopes(duration, attack, release):
    source = item(start=1000, end=1000 + duration)
    animation = SingingPulseAnimation(attack=attack, release=release)
    track = Track(source=LineMatch(), animations=(animation,))
    assert build(track, source).layers


def test_extension_is_used_for_row_occupancy_without_changing_event_clock():
    a = item(window=(1000, 2000))
    b = item(identity="two", start=2000, end=2500, window=(2000, 3000))
    track = Track(
        source=LineMatch(),
        layout=SingleLine(),
        animations=(SingingPulseAnimation(extend_display=True),),
    )
    with pytest.raises(ValueError, match="occupied"):
        track.bind((a, b))
    track.layout = DoubleLine()
    bound = track.bind((a, b))
    assert bound["one"].window.end_ms == 2160
    assert (bound["one"].row, bound["two"].row) == (0, 1)
    assert a.window.end_ms == 2000


def test_display_animation_reaches_ruby_without_syllable_follow_and_only_once():
    plan = build(
        Track(
            source=LineMatch(),
            ruby=Ruby(follow="none"),
            overlay=Overlay(style=PaintStyle(fill=BLUE)),
            animations=(FadeInAnimation(duration=200), FadeOutAnimation(duration=200)),
        )
    )
    assert plan.layers
    for layer in plan.layers:
        assert len(layer.opacity_animations) == 2


def test_multiple_animations_conflict_instead_of_last_writer_wins():
    track = Track(
        source=LineMatch(),
        animations=(SingingPulseAnimation(), SingingPulseAnimation(peak=1.3)),
    )
    with pytest.raises(ValueError, match="conflict"):
        build(track)


def test_sequence_and_parallel_share_the_animation_compiler():
    source = item()
    sequence = On(
        Display.Start,
        Sequence(
            Animate(opacity=(0, 1), duration=200),
            Animate(offset_y=(0, 10), duration=300),
        ),
    )
    assert [r.during for r in sequence.bind(AnimationContext(source))] == [
        (0, 200),
        (200, 500),
    ]
    parallel = On(
        Display.Start,
        Parallel(
            Animate(opacity=(0, 1), duration=200),
            Animate(offset_y=(0, 10), duration=300),
        ),
    )
    assert [r.during for r in parallel.bind(AnimationContext(source))] == [
        (0, 200),
        (0, 300),
    ]


@pytest.mark.parametrize("parsed", [False, True])
def test_three_colors_from_code_on_parsed_and_constructed_documents(parsed, tmp_path):
    doc = document(fontname="DejaVu Sans", text="ABCABC")
    if parsed:
        path = tmp_path / "input.ass"
        doc.save(path)
        doc = type(doc).load(path)
    original = deepcopy(doc)
    track = Track(
        source=LineMatch(),
        body=Body(
            spans=tuple(
                TextSpan(i, i + 1, overlay=PaintStyle(fill=(RED, GREEN, BLUE)[i % 3]))
                for i in range(6)
            )
        ),
        overlay=Overlay(),
    )
    result = compile_tracks(doc, tracks=(track,))
    final = [
        line
        for line, _ in result.event_origins
        if line.start_time <= 3500 < line.end_time
    ]
    assert len(final) == 6
    for index, line in enumerate(final):
        color = (RED, GREEN, BLUE)[index % 3]
        assert rf"\1c&H{color.blue:02X}{color.green:02X}{color.red:02X}&" in line.text
    assert [r.text for r in doc.lines] == [r.text for r in original.lines]


def test_unmatched_sources_preserved_and_restored_on_rerender():
    doc = document(fontname="DejaVu Sans", text="AB")
    result = compile_tracks(doc, tracks=(Track(source=LineMatch()),), owner="track")
    again = compile_tracks(result.document, tracks=(), owner="track")
    assert again.event_count == 0
    lines = list(again.document.lines)
    assert len(lines) == 1 and not lines[0].comment
    assert lines[0].effect == ""


def test_dispatch_rejects_multiple_matches_and_mixed_entry_points():
    doc = document(fontname="DejaVu Sans", text="AB")
    with pytest.raises(ValueError, match="multiple Tracks"):
        compile_tracks(
            doc, tracks=(Track(source=LineMatch()), Track(source=LineMatch()))
        )
    with pytest.raises(TypeError, match="tracks"):
        compile_tracks(doc)


def test_explicit_items_and_repeated_render_are_isolated():
    doc = document(fontname="DejaVu Sans", text="AB")
    track = Track(
        source=LineMatch(style="Default"), body=Body(style=TextStyle(fill=RED))
    )
    first = compile_tracks(doc, items=(item(),), tracks=(track,))
    second = compile_tracks(doc, items=(item(),), tracks=(track,))
    assert [line.text for line, _ in first.event_origins] == [
        line.text for line, _ in second.event_origins
    ]
    assert any(
        not line.comment and line.text == r"{\k300}AB" for line in first.document.lines
    )


def test_layout_moves_body_and_ruby_together_and_default_preserves_input():
    basic = build(Track(source=LineMatch(), ruby=Ruby()))
    moved = build(
        Track(source=LineMatch(), ruby=Ruby(), layout=SingleLine(position=(20, 30)))
    )
    shifts = {
        (round(b.box.left - a.box.left, 5), round(b.box.top - a.box.top, 5))
        for a, b in zip(basic.layers, moved.layers, strict=True)
    }
    # libass rounds character placement to an eighth-pixel grid during shaping.
    assert max(dx for dx, _ in shifts) - min(dx for dx, _ in shifts) <= 0.125
    assert len({dy for _, dy in shifts}) == 1
    assert shifts != {(0, 0)}


def test_immutable_style_replace_and_nested_inheritance():
    common = PaintStyle(fill=BLUE, blur=Blur(radius=10, width=4))
    variant = replace(common, fill=RED)
    assert common.fill == BLUE
    paint = variant.resolve(PaintStyle(blur=Blur(opacity=0.5)).resolve(Paint()))
    assert paint.glow is not None
    assert paint.glow.opacity == 0.5
    assert paint.glow.blur == 10


def test_ruby_sweep_uses_own_segment_clock():
    source = replace(
        item(),
        source=KaraokeLine(
            (TextUnit("AB", (Segment(1000, 1400, "a"), Segment(1600, 2000, "b"))),)
        ),
    )
    plan = build(
        Track(
            source=LineMatch(),
            ruby=Ruby(),
            overlay=Overlay(style=PaintStyle(fill=BLUE)),
        ),
        source,
    )
    assert all(
        "ruby:" in track
        for layer in plan.layers
        if layer.style.name == "ruby"
        for track in layer.origin.track_ids
    )


def test_no_public_padding_workaround_in_overlay():
    from kara_templater import EdgeSweep

    with pytest.raises(ValueError, match="compensation"):
        Overlay(reveal=Sweep(edges=EdgeSweep(lead_ms=24)))


def test_match_inversion():
    source = item()
    assert LineMatch(style="Default")(source)
    assert not (~LineMatch(style="Default"))(source)
    assert (~~LineMatch(text="AB"))(source)


def test_handler_filter_and_subclass_override():
    class Filtered(Animation):
        @on(Syllable.Singing, where=LineMatch(style="Other"))
        def accent(self, event: Syllable.Singing) -> Animate:
            return Animate(scale=(1, 2))

    class Replaced(Filtered):
        @on(Syllable.Singing)
        def accent(self, event: Syllable.Singing) -> Animate:
            return Animate(scale=(1, 1.1))

    context = AnimationContext(item())
    assert Filtered().bind(context) == ()
    assert len(Replaced().bind(context)) == 1


def test_display_keyframes_do_not_retime_when_another_animation_extends_output():
    from kara_templater import Keyframe, Keyframes, display

    source = item(window=(0, 2000))
    fade = On(
        Display.Start,
        Animate(
            duration=2000,
            opacity=Keyframes(Keyframe(display.start, 0), Keyframe(display.end, 1)),
        ),
    )
    track = Track(
        source=LineMatch(),
        animations=(fade, SingingPulseAnimation(extend_display=True)),
    )
    bound = track.bind((source,))[source.id]
    assert bound.window.end_ms == 2160
    rule = bound.rules[0]
    motion = bind_property(rule, source.source.units[0].segments, bound.window, (0, 0))
    assert motion is not None
    assert motion.at(1000) == 0.5
    assert build(track, source).layers


def test_nested_composites_propagate_offset_and_include_release():
    action = Sequence(
        Animate(opacity=(0, 1), duration=100),
        Parallel(
            Sequence(
                Animate(offset_y=(0, 10), duration=50),
                Animate(offset_x=(0, 10), duration=150),
            ),
            Animate(scale=Envelope(peak=1.1, attack=10, release=240), duration=60),
        ),
        Animate(opacity=(1, 0), duration=80),
    )
    rules = On(Display.Start, action).bind(AnimationContext(item()))
    assert [(r.property, r.during) for r in rules] == [
        ("opacity", (0, 100)),
        ("offset_y", (100, 150)),
        ("offset_x", (150, 300)),
        ("scale", (100, 400)),
        ("opacity", (400, 480)),
    ]
    assert build(
        Track(source=LineMatch(), animations=(On(Display.Start, action),))
    ).layers


@pytest.mark.parametrize("composite", [Sequence, Parallel])
def test_empty_composites_are_not_silent_noops(composite):
    with pytest.raises(ValueError, match="at least one"):
        composite()


def test_target_capabilities_fail_before_silent_animation_drop():
    source = item(ruby="")
    for target, message in (
        (AnimationTarget("one", (3,)), "missing syllable"),
        (AnimationTarget("one", (0,), "segment", ((0, 4),)), "missing segment"),
        (AnimationTarget("one", (0,), "ruby"), "missing ruby"),
    ):
        with pytest.raises(ValueError, match=message):
            On(Display.Start, Animate(target, scale=(1, 2), duration=100)).bind(
                AnimationContext(source)
            )
    with pytest.raises(ValueError, match="outside selected"):
        AnimationTarget("one", (0,), segments=((1, 0),))
    with pytest.raises(ValueError, match="duplicate"):
        AnimationTarget("one", (0, 0))


def test_ruby_ranges_share_clock_and_original_transform_center():
    source = item(ruby="ABC")
    track = Track(
        source=LineMatch(),
        overlay=Overlay(),
        ruby=Ruby(
            spans=tuple(
                RubySpan(0, 0, start=i, end=i + 1, overlay=PaintStyle(fill=color))
                for i, color in enumerate((RED, GREEN, BLUE))
            )
        ),
        animations=(
            On(
                Display.Start,
                Animate(AnimationTarget("one", (0,), "ruby"), scale=1.2, duration=3000),
            ),
        ),
    )
    plan = build(track, source)
    ruby_layers = [layer for layer in plan.layers if layer.style.name == "ruby"]
    assert {layer.text for layer in ruby_layers} == {"A", "B", "C"}
    pivots = {
        animation.pivot for layer in ruby_layers for animation in layer.animations
    }
    assert len(pivots) == 1
    events = compile_layers(plan.layers).events
    final = [
        event
        for event in events
        if event.style == "ruby" and event.start_time <= 2500 < event.end_time
    ]
    assert len(final) == 3
    for char, color in zip("ABC", (RED, GREEN, BLUE), strict=True):
        event = next(event for event in final if event.text.endswith(char))
        assert rf"\1c&H{color.blue:02X}{color.green:02X}{color.red:02X}&" in event.text
    # All glyph masks traverse the same reading box during the original interval.
    assert {
        layer.clips[0].start_ms
        for layer in ruby_layers
        if layer.clips and 1000 <= layer.clips[0].start_ms < 2000
    } == {1000}


@pytest.mark.parametrize(
    "span,message",
    [
        (RubySpan(3, 0), "missing syllable"),
        (RubySpan(0, 3), "missing reading"),
        (RubySpan(0, 0, start=1, end=4), "reading length"),
    ],
)
def test_ruby_range_references_are_validated(span, message):
    with pytest.raises(ValueError, match=message):
        build(Track(source=LineMatch(), ruby=Ruby(spans=(span,))), item(ruby="abc"))


def test_ruby_range_cannot_cut_combining_cluster():
    from kara_templater import LayoutCapabilityError

    with pytest.raises(LayoutCapabilityError):
        build(
            Track(source=LineMatch(), ruby=Ruby(spans=(RubySpan(0, 0, end=1),))),
            item(ruby="a\u0301"),
        )


def test_stylesheet_and_explicit_range_overrides_share_a_cascade():
    track = Track(
        source=LineMatch(),
        overlay=Overlay(style=PaintStyle(fill=CYAN)),
        body=Body(
            spans=(
                TextSpan(0, 1, classes=("accent",), overlay=PaintStyle(fill=GREEN)),
                TextSpan(0, 1, style=PaintStyle(stroke=RED)),
            )
        ),
        ruby=Ruby(spans=(RubySpan(0, 0, classes=("reading",)),)),
        styles=StyleSheet(
            rule("lyrics", fill=WHITE),
            rule("body[style=Default]", stroke=BLUE),
            rule("body:sung", fill=RED),
            rule(".accent:sung", fill=BLUE),
            rule("ruby[segment=0]:sung", fill=GREEN),
        ),
    )
    plan = build(track)
    final = [
        event
        for event in compile_layers(plan.layers).events
        if event.start_time <= 2500 < event.end_time
    ]
    assert any(
        event.style == "Default"
        and event.text.endswith("A")
        and r"\1c&H00FF00&" in event.text
        for event in final
    )
    assert any(
        event.style == "Default"
        and event.text.endswith("B")
        and r"\1c&H0000FF&" in event.text
        for event in final
    )
    assert any(
        event.style == "ruby" and r"\1c&H00FF00&" in event.text for event in final
    )
    assert track.body.parent is None
    assert all(
        layer.paint.fill == WHITE
        for layer in plan.layers
        if layer.clips and layer.clips[0].end_ms <= 1000
    )


def test_font_cascade_is_resolved_before_layout_and_ranges_cannot_relayout():
    track = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(font_size=40)),
        styles=StyleSheet(rule("lyrics", font_size=24), rule("body", font_size=30)),
    )
    assert all(layer.style.fontsize == 40 for layer in build(track).layers)
    track = Track(
        source=LineMatch(),
        body=Body(spans=(TextSpan(0, 1, classes=("large",)),)),
        styles=StyleSheet(rule(".large", font_size=100)),
    )
    with pytest.raises(ValueError, match="cannot change layout"):
        build(track)
    with pytest.raises(TypeError, match="geometry"):
        TextSpan(0, 1, style=TextStyle(font_size=100))


def test_ruby_target_requires_a_visible_ruby_component():
    animation = On(
        Display.Start,
        Animate(AnimationTarget("one", (0,), "ruby"), scale=1.2, duration=100),
    )
    with pytest.raises(ValueError, match="no visible Ruby"):
        build(Track(source=LineMatch(), animations=(animation,)))
    ruby = Ruby()
    ruby.hide()
    with pytest.raises(ValueError, match="no visible Ruby"):
        build(Track(source=LineMatch(), ruby=ruby, animations=(animation,)))
