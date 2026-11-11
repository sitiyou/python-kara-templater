from dataclasses import replace

import pytest
from effect_values import properties_at, same_effect, sampled_layers
from test_effect_halo import build

from kara_templater import (
    BLUE,
    RED,
    UNSET,
    Body,
    Effect,
    Halo,
    Lyrics,
    Segment,
    StyleSheet,
    compile_layers,
    rule,
)


class States(Effect):
    styles = StyleSheet(
        rule("halo", fill=RED, opacity=0.3),
        rule("halo:sung", fill=BLUE, opacity=0.8),
    )
    clip = "none"

    def compose(self):
        yield Lyrics(Body(), Halo(clip=self.clip, width=4, blur=6))

    def configure(self):
        self.text.sweep()


def halos(plan):
    return [l for l in plan.layers if l.component == "glow"]


def at(plan, time, *, sampled=False):
    layers = sampled_layers(plan) if sampled else plan.layers
    result = compile_layers([l for l in layers if l.component == "glow"])
    return [e for e in result.events if e.start_time <= time < e.end_time]


def test_halo_state_colors_and_opacity_are_spatial_and_keep_stable_target_ids():
    plan, _, _ = build(States(), segments=(Segment(1000, 2000),))
    assert all(r"\1c&H0000FF&" in e.text for e in at(plan, 500))
    assert all(r"\1c&HFF0000&" in e.text for e in at(plan, 2500))
    assert {l.paint.glow.opacity for l in halos(plan)} == {0.3, 0.8}
    mid = at(plan, 1500)
    assert any(r"\1c&H0000FF&" in e.text for e in mid)
    assert any(r"\1c&HFF0000&" in e.text for e in mid)
    assert len({l.animation_id for l in halos(plan)}) == 2
    assert any("hard-clips" in d for d in plan.diagnostics)


def test_sung_only_halo_never_reveals_before_state():
    class Sung(States):
        clip = "sung"

    plan, _, _ = build(Sung(), segments=(Segment(1000, 2000),))
    assert all(r"\alpha&HFF&" in e.text for e in at(plan, 500))
    assert all(r"\1c&HFF0000&" in e.text for e in at(plan, 2500))


def test_halo_direct_sung_override_and_unset_use_same_cascade():
    class Direct(States):
        def configure(self):
            super().configure()
            self.query_one("halo").style.sung.fill = RED
            self.query_one("halo").style.sung.fill = UNSET

    expected, _, _ = build(States())
    actual, _, _ = build(Direct())
    assert [l.paint for l in halos(expected)] == [l.paint for l in halos(actual)]


def test_identical_states_keep_full_halo_without_masks():
    class Equal(States):
        def configure(self):
            super().configure()
            self.query_one("halo").style.sung.fill = RED
            self.query_one("halo").style.sung.opacity = 0.3

    plan, _, _ = build(Equal())
    assert halos(plan) and all(
        l.clips is None and l.active_window is None for l in halos(plan)
    )


@pytest.mark.parametrize("keep", [False, True])
def test_opacity_animation_overrides_active_states_then_restores_state_opacity(keep):
    class Animated(States):
        def configure(self):
            super().configure()
            self.query_one("halo").on_singing(opacity=(0.2, 0.6), keep=keep)

    plan, _, _ = build(Animated(), segments=(Segment(1000, 2000),))
    sampled = sampled_layers(plan)
    for time, expected in (
        (500, {0.3, 0.8}),
        (1500, {0.4}),
        (2500, {0.6} if keep else {0.3, 0.8}),
    ):
        # State paints are restored outside the native animation. Final ASS
        # events below additionally verify visibility and quantized alpha.
        values = {
            (
                properties_at(plan, l, time).glow_opacity
                if l.opacity_animations
                else l.paint.glow.opacity
            )
            for l in sampled
            if l.component == "glow"
            and (l.active_window or l.window).start_ms
            <= time
            < (l.active_window or l.window).end_ms
        }
        if time == 1500:
            assert values and all(0.38 < v < 0.42 for v in values)
        else:
            assert values <= expected and values
    final = at(plan, 2500, sampled=True)
    assert final and all(r"\1c&HFF0000&" in e.text for e in final)
    # 0.8 => 51; held 0.6 => 102 in ASS alpha.
    assert all((r"\alpha&H66&" if keep else r"\alpha&H33&") in e.text for e in final)


def test_parallel_coverage_does_not_duplicate_stateful_halo():
    from kara_templater import tracks_from_layout

    class Twice(States):
        def configure(self):
            def tracks(layout):
                track = tracks_from_layout(layout)[0]
                return (track, replace(track, id="parallel"))

            self.text.sweep(tracks=tracks)

    one, _, _ = build(States(), segments=(Segment(1000, 2000),))
    two, _, _ = build(Twice(), segments=(Segment(1000, 2000),))
    for time in (500, 1500, 2500):
        assert [(e.start_time, e.end_time, e.text) for e in at(one, time)] == [
            (e.start_time, e.end_time, e.text) for e in at(two, time)
        ]


def test_halo_sung_state_requires_sweep_coverage_not_just_elapsed_time():
    class NoSweep(States):
        def configure(self):
            pass

    plan, _, _ = build(NoSweep(), segments=(Segment(1000, 2000),))
    final = at(plan, 2500)
    assert final and all(r"\1c&H0000FF&" in e.text for e in final)


def test_stateful_halo_does_not_change_body_layers():
    class Plain(States):
        def compose(self):
            yield Lyrics(Body())

    decorated, _, _ = build(States())
    plain, _, _ = build(Plain())
    assert [same_effect(l) for l in decorated.layers if l.component != "glow"] == [
        same_effect(l) for l in plain.layers
    ]


@pytest.mark.parametrize("declaration", ["constructor", "rule", "sung_only", "unset"])
def test_halo_explicit_color_inheritance_uses_each_attachment_state(declaration):
    from kara_templater import CYAN, GREEN, INHERIT, WHITE, Ruby

    class Inherited(Effect):
        styles = (
            StyleSheet(rule("halo", fill=INHERIT))
            if declaration == "rule"
            else StyleSheet()
        )

        def compose(self):
            yield Lyrics(
                Body(fill=RED),
                Ruby(fill=GREEN),
                Halo(
                    color=INHERIT if declaration in {"constructor", "unset"} else UNSET
                ),
            )

        def configure(self):
            self.characters[0].style.sung.fill = BLUE
            self.characters[1].style.sung.fill = CYAN
            self.rubies.style.sung.fill = GREEN
            if declaration == "sung_only":
                self.query_one("halo").style.sung.fill = INHERIT
            elif declaration == "unset":
                self.query_one("halo").style.fill = UNSET
            self.text.sweep()

    plan, _, _ = build(Inherited())
    for time, colors in (
        (500, {"A": RED, "B": RED, "a": GREEN, "b": GREEN}),
        (2500, {"A": BLUE, "B": CYAN, "a": GREEN, "b": GREEN}),
    ):
        events = at(plan, time)
        assert {e.text.rsplit("}", 1)[-1] for e in events} == set(colors)
        for event in events:
            glyph = event.text.rsplit("}", 1)[-1]
            color = (
                WHITE
                if declaration == "unset"
                or (declaration == "sung_only" and time == 500)
                else colors[glyph]
            )
            assert (
                rf"\1c&H{color.blue:02X}{color.green:02X}{color.red:02X}&" in event.text
            )
    assert len({layer.animation_id for layer in halos(plan)}) == 4
