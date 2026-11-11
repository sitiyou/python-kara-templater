import pytest
from test_effect_halo import build

from kara_templater import (
    BLUE,
    GREEN,
    INHERIT,
    RED,
    UNSET,
    Body,
    Effect,
    Lyrics,
    Ruby,
    Segment,
    StyleSheet,
    compile_layers,
    rule,
)


class Styled(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby())


def final(effect):
    plan, _, _ = build(effect, segments=(Segment(1000, 2000, "ab"),))
    return [
        e
        for e in compile_layers(plan.layers).events
        if e.start_time <= 2500 < e.end_time
    ]


def test_syllable_character_and_ruby_target_styles_share_cascade():
    class Selected(Styled):
        styles = StyleSheet(rule(".accent:sung", fill=RED))

        def configure(self):
            self.syllables[0].add_class("accent")
            self.characters[1].style.sung.fill = BLUE
            self.rubies[0].style.sung.fill = GREEN
            self.text.sweep()

    events = final(Selected())
    expected = {"A": "0000FF", "B": "FF0000", "ab": "00FF00"}
    assert {e.text.rsplit("}", 1)[-1] for e in events} == expected.keys()
    for event in events:
        text = event.text.rsplit("}", 1)[-1]
        assert rf"\1c&H{expected[text]}&" in event.text


@pytest.mark.parametrize("operation", ["read", "unset", "inherit"])
def test_target_style_access_and_reset_preserve_component_overrides(operation):
    class Selected(Styled):
        styles = StyleSheet(rule("body:sung", fill=RED), rule("ruby:sung", fill=RED))

        def configure(self):
            self.text.sweep(fill=BLUE)
            for selection in (self.characters, self.rubies):
                if operation == "read":
                    assert selection.style.sung.fill is UNSET
                else:
                    selection.style.sung.fill = GREEN
                    selection.style.sung.fill = (
                        UNSET if operation == "unset" else INHERIT
                    )

    events = final(Selected())
    assert events and all(r"\1c&HFF0000&" in e.text for e in events)


def test_target_ruby_class_overrides_parent_and_direct_override_can_be_removed():
    class Selected(Styled):
        styles = StyleSheet(rule("ruby.accent:sung", fill=GREEN))

        def configure(self):
            self.text.sweep(fill=BLUE)
            self.rubies.add_class("accent")
            self.rubies.style.sung.fill = RED
            self.rubies.style.sung.fill = UNSET

    events = final(Selected())
    assert all(r"\1c&H00FF00&" in e.text for e in events if e.style == "ruby")
    assert all(r"\1c&HFF0000&" in e.text for e in events if e.style == "Default")


def test_broadcast_style_reads_require_equal_explicit_declarations():
    class Selected(Styled):
        def configure(self):
            self.characters.style.fill = BLUE
            assert self.characters.style.fill == BLUE
            self.characters[0].style.fill = RED
            with pytest.raises(ValueError, match="different fill"):
                _ = self.characters.style.fill
            assert self.characters[0:0].style.fill is UNSET
            with pytest.raises(ValueError):
                self.characters[0:0].style.fill = "invalid"
            with pytest.raises(ValueError, match="timing targets"):
                self.segments.style.fill = RED
            self.rubies.style.fill = GREEN

    final(Selected())


def test_target_ruby_font_size_does_not_silently_diverge_from_layout():
    class Selected(Styled):
        def configure(self):
            self.rubies.style.font_size = 50

    with pytest.raises(ValueError, match="mixed-style layout"):
        final(Selected())
