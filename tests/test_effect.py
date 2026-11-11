import pytest

from examples.alternating_colors import AlternatingColors, document
from kara_templater import (
    BLUE,
    GREEN,
    INHERIT,
    RED,
    UNSET,
    WHITE,
    Body,
    Color,
    DisplayWindow,
    Document,
    Effect,
    KaraokeItem,
    KaraokeLine,
    LayoutCapabilityError,
    Line,
    Lyrics,
    Segment,
    StyleSheet,
    TextUnit,
    render_karaoke,
    rule,
)
from kara_templater.effect import Component
from kara_templater.stylesheet import Selector


def test_cascade_specificity_state_partial_overrides_and_inheritance():
    node = Body(id="main", classes="accent")
    Lyrics(node)
    node.attributes["style"] = "Lead Voice"
    sheet = StyleSheet(
        rule("body", fill=WHITE, stroke_width=3),
        rule("lyrics body.accent:sung", fill=RED),
        rule('#main[style="Lead Voice"]', stroke=BLUE),
        rule("body", fill=GREEN),
        rule(".accent:sung", fill=BLUE),
    )
    base = {"fill": WHITE, "opacity": 0.5}
    assert sheet.resolve(node, base)["fill"] == GREEN
    sung = sheet.resolve(node, base, sung=True)
    assert sung == {"fill": RED, "opacity": 0.5, "stroke_width": 3, "stroke": BLUE}
    node.style.fill = BLUE
    assert sheet.resolve(node, base, sung=True)["fill"] == BLUE
    node.style.sung.fill = INHERIT
    assert sheet.resolve(node, base, sung=True)["fill"] == WHITE
    node.style.sung.fill = UNSET
    node.style.fill = UNSET
    assert sheet.resolve(node, base, sung=True)["fill"] == RED


@pytest.mark.parametrize(
    "selector",
    ["", "body > ruby", "body:hover", "body, ruby", ".", "body[foo]", "body*"],
)
def test_invalid_selectors_fail(selector):
    with pytest.raises(ValueError):
        Selector.parse(selector)


@pytest.mark.parametrize("value", ["red", "#fff", "#ffffgg", None, 42])
def test_color_validation_at_declaration_boundary(value):
    with pytest.raises((TypeError, ValueError)):
        rule("body", fill=value)
    with pytest.raises((TypeError, ValueError)):
        Body(fill=value)


def test_colors_share_existing_color_type():
    assert RED == Color.hex("#ff0000")
    assert GREEN == Color.hex("#00ff00")
    assert BLUE == Color.hex("#0000ff")
    assert rule("body", fill=RED) == rule("body", fill="#ff0000")


@pytest.mark.parametrize("last", ["direct", "sweep", "unset", "inherit"])
def test_sweep_colors_are_actual_component_style_overrides(last):
    from test_effect_halo import build

    from kara_templater import Ruby

    class Styled(Effect):
        styles = StyleSheet(rule("body:sung", fill=GREEN))

        def compose(self):
            yield Lyrics(Body(), Ruby())

        def configure(self):
            if last == "sweep":
                self.body.style.sung.fill = BLUE
            self.text.sweep(fill=RED)
            if last == "direct":
                self.body.style.sung.fill = BLUE
                self.ruby.style.sung.fill = GREEN
            elif last == "unset":
                self.body.style.sung.fill = UNSET
                self.ruby.style.sung.fill = UNSET
            elif last == "inherit":
                self.ruby.style.sung.fill = INHERIT

    plan, _, _ = build(Styled(), segments=(Segment(1000, 2000, "a"),))
    expected_body, expected_ruby = {
        "direct": (BLUE, GREEN),
        "sweep": (RED, RED),
        "unset": (GREEN, GREEN),
        "inherit": (RED, RED),
    }[last]
    from kara_templater import compile_layers

    final = [
        e
        for e in compile_layers(plan.layers).events
        if e.start_time <= 2500 < e.end_time
    ]
    assert {e.style for e in final} == {"Default", "ruby"}
    for event in final:
        expected = expected_ruby if event.style == "ruby" else expected_body
        tag = rf"\1c&H{expected.blue:02X}{expected.green:02X}{expected.red:02X}&"
        assert tag in event.text


def test_sweep_unset_removes_an_existing_override():
    class Styled(Effect):
        styles = StyleSheet(rule("body:sung", fill=GREEN))

        def compose(self):
            yield Lyrics(Body())

        def configure(self):
            self.body.style.sung.fill = RED
            self.text.sweep(fill=UNSET)

    from test_effect_halo import build

    plan, _, _ = build(Styled(), segments=(Segment(1000, 2000, "a"),))
    from kara_templater import compile_layers

    final = [
        e
        for e in compile_layers(plan.layers).events
        if e.start_time <= 2500 < e.end_time
    ]
    assert final and all(r"\1c&H00FF00&" in e.text for e in final)


def events(result):
    return [
        (e.start_time, e.end_time, e.layer, e.style, e.text)
        for e, _ in result.event_origins
    ]


class LatinAlternating(AlternatingColors):
    def configure(self):
        if self.source.source.units[0].text == "ABCABC":
            for index in range(6):
                self.body.text_range(index, index + 1).add_class(
                    ("red", "green", "blue")[index % 3]
                )
        self.text.sweep()


class DirectAlternating(LatinAlternating):
    def configure(self):
        if self.source.source.units[0].text == "ABCABC":
            for index in range(6):
                self.body.text_range(index, index + 1).style.sung.fill = (
                    RED,
                    GREEN,
                    BLUE,
                )[index % 3]
        self.text.sweep()


def test_three_input_paths_and_direct_overrides_are_equivalent():
    source = document(fontname="DejaVu Sans", text="ABCABC")
    parsed = Document.parse(source.dumps())
    explicit = KaraokeItem(
        "explicit",
        KaraokeLine((TextUnit("ABCABC", (Segment(0, 3000),)),)),
        "Default",
        DisplayWindow(0, 4000),
    )
    results = [
        render_karaoke(source, effect=LatinAlternating),
        render_karaoke(parsed, effect=LatinAlternating()),
        render_karaoke(source, (explicit,), effect=LatinAlternating),
        render_karaoke(source, effect=DirectAlternating),
    ]
    assert all(events(result) == events(results[0]) for result in results)
    final = [
        e for e, _ in results[0].event_origins if e.start_time <= 3500 < e.end_time
    ]
    assert len(final) == 6
    assert [
        next(
            c
            for c in (r"\1c&H0000FF&", r"\1c&H00FF00&", r"\1c&HFF0000&")
            if c in e.text
        )
        for e in final
    ] == [r"\1c&H0000FF&", r"\1c&H00FF00&", r"\1c&HFF0000&"] * 2
    assert source.lines[0].text == r"{\k300}ABCABC"
    assert not source.lines[0].comment


@pytest.mark.parametrize("effect", [LatinAlternating, DirectAlternating])
@pytest.mark.parametrize("parsed", [False, True])
def test_cross_line_isolation_and_original_segment_mapping(effect, parsed):
    source = document(fontname="DejaVu Sans", text="ABCABC")
    source.records.append(Line(text=r"{\k300}DEFDEF", start_time=4000, end_time=8000))
    if parsed:
        source = Document.parse(source.dumps())
    original = source.dumps()
    result = render_karaoke(source, effect=effect())
    assert source.dumps() == original
    final = [e for e, _ in result.event_origins if e.start_time <= 7500 < e.end_time]
    assert len(final) == 6
    assert all(r"\1c&HFFFFFF&" in e.text for e in final)
    assert all(
        ref.segment_index == 0
        for _, origin in result.event_origins
        for ref in origin.sources
    )


def test_configuration_precedes_layout_and_emits_font_size():
    class Larger(Effect):
        def compose(self):
            yield Lyrics(Body(font_size=72))

    result = render_karaoke(document(fontname="DejaVu Sans", text="ABC"), effect=Larger)
    assert all(r"\fs72" in event.text for event, _ in result.event_origins)
    assert result.document.styles["Default"].fontsize == 56

    class InheritedSize(Effect):
        def compose(self):
            yield Lyrics(Body(), font_size=72)

    inherited = render_karaoke(
        document(fontname="DejaVu Sans", text="ABC"), effect=InheritedSize
    )
    assert events(inherited) == events(result)


def test_cluster_split_is_rejected_without_retiming():
    class Split(Effect):
        def compose(self):
            yield Lyrics(Body())

        def configure(self):
            self.body.text_range(0, 1).style.fill = RED

    with pytest.raises(LayoutCapabilityError, match="cluster"):
        render_karaoke(document(fontname="DejaVu Sans", text="a\u0301"), effect=Split)


def test_query_errors_and_component_instance_isolation():
    shared = Lyrics(Body(id="body"))

    class Shared(Effect):
        def compose(self):
            yield shared

        def configure(self):
            assert not self.body.classes
            self.query_one("#body").add_class("configured")
            assert self.query(".absent") == ()
            with pytest.raises(ValueError, match="found 0"):
                self.query_one("#absent")

    source = document(fontname="DejaVu Sans", text="ABC")
    render_karaoke(source, effect=Shared)
    render_karaoke(source, effect=Shared)
    assert not shared.children[0].classes
    with pytest.raises(ValueError, match="duplicate component id"):

        class Duplicate(Effect):
            def compose(self):
                yield Lyrics(Body(id="same"), Component(id="same"))

        render_karaoke(source, effect=Duplicate)


def test_source_ass_styles_are_the_base_and_explicit_styles_override():
    class SourceColors(Effect):
        def compose(self):
            yield Lyrics(Body())

        def configure(self):
            self.text.sweep()

    source = document(fontname="DejaVu Sans", text="ABC")
    source.styles["Default"].fields = {
        "PrimaryColour": "&H00FF0000",
        "SecondaryColour": "&H0000FF00",
    }
    result = render_karaoke(source, effect=SourceColors)
    final = [e for e, _ in result.event_origins if e.start_time <= 3500 < e.end_time]
    assert final and all(r"\1c&HFF0000&" in e.text for e in final)
    initial = [e for e, _ in result.event_origins if e.start_time == 0]
    assert any(r"\1c&H00FF00&" in e.text for e in initial)


def test_ruby_inherits_body_colors_with_independent_geometry():
    from kara_templater import Ruby

    class RubyEffect(Effect):
        styles = StyleSheet(rule("body", fill=RED), rule("ruby", stroke_width=1))

        def compose(self):
            yield Lyrics(Body(stroke_width=5), Ruby(font_size=20))

        def configure(self):
            self.text.sweep()

    source = document(fontname="DejaVu Sans", text="ABC|abc")
    result = render_karaoke(source, effect=RubyEffect)
    ruby = [e for e, _ in result.event_origins if e.style.endswith("-ruby")]
    assert ruby and all(
        r"\1c&H0000FF&" in e.text and r"\bord1" in e.text and r"\fs20" in e.text
        for e in ruby
    )


def test_ambiguous_ruby_requires_an_explicit_color():
    from kara_templater import Ruby

    class RubyEffect(DirectAlternating):
        def compose(self):
            yield Lyrics(Body(), Ruby())

    source = document(fontname="DejaVu Sans", text="ABCABC|abcdef")
    with pytest.raises(ValueError, match="ruby needs explicit appearance"):
        render_karaoke(source, effect=RubyEffect)

    class ExplicitRuby(RubyEffect):
        def compose(self):
            yield Lyrics(Body(), Ruby(fill=WHITE))

    assert render_karaoke(source, effect=ExplicitRuby).event_count > 0


@pytest.mark.parametrize("selector", ["body[", "[", "body]", "body ["])
def test_unmatched_selector_brackets_fail(selector):
    with pytest.raises(ValueError):
        Selector.parse(selector)


def test_range_across_source_units_preserves_both_segment_clocks():
    class Across(Effect):
        def compose(self):
            yield Lyrics(Body(fill=WHITE))

        def configure(self):
            self.body.text_range(1, 3).style.sung.fill = RED
            self.text.sweep()

    source = document(fontname="DejaVu Sans", text="unused")
    item = KaraokeItem(
        "multi",
        KaraokeLine(
            (
                TextUnit("AB", (Segment(0, 1000),)),
                TextUnit("CD", (Segment(2000, 3000),)),
            )
        ),
        "Default",
        DisplayWindow(0, 4000),
    )
    result = render_karaoke(source, (item,), effect=Across)
    final = [e for e, _ in result.event_origins if e.start_time <= 3500 < e.end_time]
    assert [
        e.text.endswith(("B", "C")) for e in final if r"\1c&H0000FF&" in e.text
    ] == [True, True]
    assert item.source.units[0].segments == (Segment(0, 1000),)
    assert item.source.units[1].segments == (Segment(2000, 3000),)
    assert {
        (ref.unit_index, ref.segment_index)
        for _, origin in result.event_origins
        for ref in origin.sources
    } == {(0, 0), (1, 0)}
