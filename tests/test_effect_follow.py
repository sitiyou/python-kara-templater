from dataclasses import replace

import pytest
from effect_values import properties_at, same_effect, sampled_layers
from test_effect_halo import build

from kara_templater import (
    Body,
    DisplayWindow,
    Effect,
    Follow,
    Halo,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    Segment,
    compile_layers,
    display,
)


def sample(plan, layer, time):
    return properties_at(plan, layer, time)


class Linked(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby(follow="syllable"), Halo())

    def configure(self):
        self.text.sweep()
        self.text.fade(in_ms=200, out_ms=300)
        self.syllables.on_singing(pulse=1.2)
        self.syllables.on_singing(
            offset_x=lambda p: 20 * p, opacity=lambda p: 1 - p / 2
        )


def test_halo_follow_switches_are_independent_and_default_is_unchanged():
    class Independent(Linked):
        def compose(self):
            yield Lyrics(
                Body(),
                Ruby(follow="syllable"),
                Halo(
                    follow=Follow(
                        scale=False, position=False, opacity=False, fade=False
                    )
                ),
            )

    linked, _, _ = build(Linked())
    detached, _, _ = build(Independent())
    assert [same_effect(l) for l in linked.layers if l.component != "glow"] == [
        same_effect(l) for l in detached.layers if l.component != "glow"
    ]
    for layer in detached.layers:
        if layer.component == "glow":
            assert not layer.animations
            assert layer.fade.in_ms == layer.fade.out_ms == 0
            state = sample(detached, layer, 1700)
            assert state.offset_x == 0 and state.opacity == 1
    first = next(l for l in linked.layers if l.component == "glow")
    assert first.animations and sample(linked, first, 1700).offset_x == 10


def test_ruby_can_follow_translation_without_scale_or_fade():
    class Selective(Linked):
        def compose(self):
            yield Lyrics(Body(), Ruby(follow=Follow(scale=False, fade=False)), Halo())

    plan, _, _ = build(Selective())
    for layer in plan.layers:
        if layer.style.name == "ruby":
            assert not layer.animations
            assert layer.fade.in_ms == layer.fade.out_ms == 0
            assert sample(plan, layer, 1700).offset_x == 10
        else:
            assert layer.animations
            assert layer.fade.in_ms == 200


def test_sung_clip_uses_single_union_coverage_and_preserves_body_output():
    class Clipped(Linked):
        def compose(self):
            yield Lyrics(
                Body(), Ruby(follow="syllable"), Halo(clip="sung", width=8, blur=10)
            )

    plan, _, _ = build(Clipped())
    baseline, _, _ = build(Linked())
    assert [same_effect(l) for l in plan.layers if l.component != "glow"] == [
        same_effect(l) for l in baseline.layers if l.component != "glow"
    ]
    halos = [l for l in plan.layers if l.component == "glow"]
    assert halos and len({l.animation_id for l in halos}) == 4
    assert all(l.paint.glow is not None for l in halos)
    assert any(l.clips is not None and l.paint.opacity == 1 for l in halos)
    assert any(l.clips is None and l.active_window.start_ms >= 2400 for l in halos)
    assert all(l.animations for l in halos)
    assert any("ASS hard-clips" in d for d in plan.diagnostics)
    assert compile_layers(sampled_layers(plan)).events


def test_opacity_animation_cannot_reveal_unsung_clip_regions():
    class Bright(Linked):
        def compose(self):
            yield Lyrics(Body(), Halo(clip="sung", width=8, blur=10, opacity=0.2))

        def configure(self):
            self.text.sweep()
            self.query_one(Halo).on_singing(opacity=(0.2, 0.8), keep=True)

    plan, _, _ = build(Bright(), segments=(Segment(1000, 2000),))
    sampled = sampled_layers(plan)
    before = [
        e
        for e in compile_layers([l for l in sampled if l.component == "glow"]).events
        if e.end_time <= 1000
    ]
    assert before and all(r"\alpha&HFF&" in e.text for e in before)


def test_overlapping_tracks_do_not_duplicate_sung_glow_brightness():
    from kara_templater import tracks_from_layout

    class Union(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(clip="sung", blur=5))

        def configure(self):
            self.text.sweep()

    class Twice(Union):
        def configure(self):
            def tracks(layout):
                track = tracks_from_layout(layout)[0]
                return (track, replace(track, id="second"))

            self.text.sweep(tracks=tracks)

    one, _, _ = build(Union(), segments=(Segment(1000, 2000),))
    two, _, _ = build(Twice(), segments=(Segment(1000, 2000),))

    def events(plan):
        return sorted(
            (e.start_time, e.end_time, e.layer, e.text)
            for e in compile_layers(plan.layers).events
        )

    assert events(one) == events(two)


def test_custom_halo_window_keeps_source_fade_clock_and_singing_clock():
    class Extended(Linked):
        def compose(self):
            yield Lyrics(Body(), Halo(window=(display.start - 300, display.end + 500)))

        def configure(self):
            self.text.fade(in_ms=200, out_ms=300)
            self.query_one(Halo).on_singing(opacity=(0.2, 0.8), keep=True)

    plan, _, _ = build(Extended(), segments=(Segment(1000, 2000),))
    halo = next(l for l in plan.layers if l.component == "glow")
    assert halo.window == DisplayWindow(200, 3500)
    assert halo.fade_window == DisplayWindow(500, 3000)
    assert sample(plan, halo, 1500).glow_opacity == pytest.approx(0.5)
    events = compile_layers((halo,)).events
    before = [e for e in events if e.end_time <= 500]
    after = [e for e in events if e.start_time >= 3000]
    assert before and after
    assert all(r"\alpha&HFF&" in e.text for e in (*before, *after))
    assert any(
        e.start_time == 500 and r"\t(0,200,1,\alpha&H00&)" in e.text for e in events
    )


def test_extended_halo_rechecks_followed_conflicts_outside_body_window():
    class HiddenConflict(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(window=(display.start, display.end + 1000)))

        def configure(self):
            self.syllables.animate(offset_x=2, during=(display.end, display.end + 500))
            self.syllables.animate(
                offset_x=3, during=(display.end + 200, display.end + 700)
            )

    with pytest.raises(
        OutputCapabilityError, match="offset_x conflict at 3200..3500 ms"
    ):
        build(HiddenConflict())


def test_clipped_decorations_enforce_combined_layer_budget_before_callbacks():
    calls = []

    class Many(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(clip="sung"), Halo(clip="sung"))

        def configure(self):
            self.text.sweep()
            self.characters.on_singing(offset_y=lambda p: calls.append(p) or 0)

    from kara_templater import (
        EffectContext,
        KaraokeItem,
        KaraokeLine,
        Style,
        TextUnit,
        layout_line,
    )

    item = KaraokeItem(
        "limited",
        KaraokeLine((TextUnit("AB", (Segment(1000, 2000),)),)),
        "Default",
        DisplayWindow(500, 3000),
    )
    style = Style(fontname="DejaVu Sans", fontsize=40)
    bound, style, ruby = Many()._prepare(item, style, replace(style, name="ruby"))
    context = EffectContext(
        layout_line(item.source, style=style, resolution=(640, 480)),
        style,
        ruby,
        (640, 480),
        max_regions=8,
    )
    with pytest.raises(OutputCapabilityError, match="exceed"):
        bound.build(item, context)
    assert calls == []
