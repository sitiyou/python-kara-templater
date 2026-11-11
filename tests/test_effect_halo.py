from dataclasses import replace

import pytest
from effect_values import properties_at, same_effect, sampled_layers

from kara_templater import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    Body,
    DisplayWindow,
    Effect,
    EffectContext,
    Halo,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    Segment,
    Style,
    TextUnit,
    Transition,
    compile_layers,
    layout_line,
    prepare_sampling,
    smooth,
    there_and_back,
)

SEGMENTS = (Segment(1000, 1600, "a"), Segment(1800, 2400, "b"))
WINDOW = DisplayWindow(500, 3000)


def build(
    effect,
    *,
    segments=SEGMENTS,
    window=WINDOW,
):
    item = KaraokeItem(
        "line", KaraokeLine((TextUnit("AB", segments),)), "Default", window
    )
    style = Style(fontname="DejaVu Sans", fontsize=40)
    ruby = replace(style, name="ruby", fontsize=20)
    bound, style, ruby = effect._prepare(item, style, ruby)
    context = EffectContext(
        layout_line(item.source, style=style, ruby_style=ruby, resolution=(640, 480)),
        style,
        ruby,
        (640, 480),
    )
    return bound.build(item, context), item, context


class Decorated(Effect):
    def compose(self):
        yield Lyrics(
            Body(fill=WHITE, stroke=BLACK, stroke_width=3),
            Ruby(offset_y=7, fill=WHITE),
            Halo(id="base", color=RED, width=8, ruby_width=4, blur=10, opacity=0.8),
            Halo(id="sung", color=BLUE, width=12, ruby_width=6, blur=14, opacity=0.2),
        )

    def configure(self):
        self.body.text_range(0, 1).style.sung.fill = RED
        self.body.text_range(1, 2).style.sung.fill = BLUE
        self.text.sweep()
        self.text.fade(in_ms=200, out_ms=300)
        self.query_one("#sung").on_singing(opacity=(0.2, 0.8), keep=True)


def test_halos_bind_once_before_sweep_split_and_keep_global_windows():
    plan, item, context = build(Decorated())
    halos = [layer for layer in plan.layers if layer.component == "glow"]
    text = [layer for layer in plan.layers if layer.component != "glow"]
    assert len(halos) == 8  # two body glyphs and two ruby readings, twice
    assert len({layer.animation_id for layer in halos}) == 8
    assert all(layer.clips is None and layer.active_window is None for layer in halos)
    assert all(layer.window == item.window for layer in halos)
    assert all(
        layer.fade.in_ms == 200 and layer.fade.out_ms == 300 for layer in plan.layers
    )
    assert max(layer.order for layer in halos) < min(layer.order for layer in text)
    for index, layer in enumerate(halos):
        assert layer.paint.glow.color == (RED if index < 4 else BLUE)
        assert layer.order == (-2 if index < 4 else -1)
        ruby = layer.style.name == "ruby"
        assert layer.paint.glow.border == (
            (4 if ruby else 8) if index < 4 else (6 if ruby else 12)
        )
        assert all(ref.item_id == item.id for ref in layer.origin.sources)
        assert layer.window == item.window
    assert context.layout.units[0].source is item.source.units[0]


def value(plan, layer, time):
    return properties_at(plan, layer, time)


def test_body_envelope_and_ruby_segment_clocks_are_independent():
    plan, _, _ = build(Decorated())
    sung = [
        layer
        for layer in plan.layers
        if layer.component == "glow" and layer.order == -1
    ]
    body = [layer for layer in sung if layer.style.name != "ruby"]
    ruby = [layer for layer in sung if layer.style.name == "ruby"]
    assert value(plan, body[0], 1700).glow_opacity == pytest.approx(0.5)
    assert value(plan, ruby[0], 1700).glow_opacity == pytest.approx(0.8)
    assert value(plan, ruby[1], 1700).glow_opacity == pytest.approx(0.2)
    assert all(
        value(plan, layer, 2800).glow_opacity == pytest.approx(0.8) for layer in sung
    )
    # Sampling keeps the body native sweep identical even with a glow callback.
    bodies = [layer for layer in plan.layers if layer.component != "glow"]
    original = compile_layers(bodies).events
    sampled = compile_layers(sampled_layers(plan, bodies)).events
    assert sorted((e.start_time, e.end_time, e.text) for e in original) == sorted(
        (e.start_time, e.end_time, e.text) for e in sampled
    )


@pytest.mark.parametrize("segments", [(), (Segment(1500, 1500),)])
def test_static_and_zero_duration_halo_timing(segments):
    plan, _, _ = build(Decorated(), segments=segments)
    layer = next(
        layer
        for layer in plan.layers
        if layer.component == "glow" and layer.order == -1
    )
    assert value(plan, layer, 1490).glow_opacity == 0.2
    assert value(plan, layer, 1500).glow_opacity == pytest.approx(
        0.8 if segments else 0.2
    )


def test_hiding_ruby_hides_attached_halos_and_keeps_body_ids():
    class Hidden(Decorated):
        def configure(self):
            super().configure()
            self.ruby.hide()

    visible, _, _ = build(Decorated())
    hidden, _, _ = build(Hidden())
    assert all(layer.style.name != "ruby" for layer in hidden.layers)
    visible_ids = {
        layer.animation_id for layer in visible.layers if layer.style.name != "ruby"
    }
    assert {layer.animation_id for layer in hidden.layers} == visible_ids


def test_decoration_width_does_not_change_sweep_geometry_or_clocks():
    class Wider(Decorated):
        def configure(self):
            super().configure()
            self.query_one("#sung").width = 40

    narrow, _, _ = build(Decorated())
    wide, _, _ = build(Wider())
    assert [
        same_effect(layer) for layer in narrow.layers if layer.component != "glow"
    ] == [same_effect(layer) for layer in wide.layers if layer.component != "glow"]


def test_callable_opacity_evaluates_only_after_sampling_preflight():
    calls = []

    class FunctionGlow(Decorated):
        def configure(self):
            self.query_one("#sung").on_singing(opacity=lambda p: calls.append(p) or p)

    plan, _, _ = build(FunctionGlow())
    assert calls == []
    with pytest.raises(OutputCapabilityError, match="preflight"):
        prepare_sampling(plan.layers, plan.dynamic, max_events=1)
    assert calls == []
    sampled_layers(plan)
    assert calls and all(0 <= p <= 1 for p in calls)


def test_property_failure_reports_target_time_and_source():
    class Bad(Decorated):
        def configure(self):
            self.query_one("#sung").on_singing(opacity=lambda p: 2)

    plan, _, _ = build(Bad())
    with pytest.raises(
        OutputCapabilityError, match="opacity must be in 0..1"
    ) as failure:
        sampled_layers(plan)
    assert failure.value.origin.sources[0].item_id == "line"
    assert failure.value.time_ms >= 1000


def test_duplicate_behavior_is_not_silently_replaced():
    halo = Halo(id="sung")
    halo.on_singing(opacity=(0.2, 0.8))
    with pytest.raises(ValueError, match="overlapping opacity"):
        halo.on_singing(opacity=1)


def test_custom_rate_and_direct_property_function_have_distinct_semantics():
    assert Transition(0.2, 0.8, rate=smooth)(0.5) == pytest.approx(0.5)
    rate = there_and_back(peak_at=0.2, return_at=0.65)
    motion = Transition(0.2, 0.8, rate=rate)
    assert motion(0.1) == pytest.approx(0.5)
    assert motion(0.4) == pytest.approx(0.8)
    assert motion(1) == pytest.approx(0.2)

    class Returning(Decorated):
        def configure(self):
            self.query_one("#sung").on_singing(opacity=motion, keep=True)

    plan, _, _ = build(Returning())
    layer = next(layer for layer in plan.layers if layer.order == -1)
    assert value(plan, layer, 2800).glow_opacity == pytest.approx(0.2)


def test_sampled_declarative_halo_matches_existing_whole_glow_output():
    import hashlib
    import json

    class Equivalent(Effect):
        def compose(self):
            yield Lyrics(
                Body(fill="#c8c8c8", stroke=BLACK, stroke_width=0),
                Halo(id="whole", color="#28dcff", blur=24, width=3, opacity=0.2),
            )

        def configure(self):
            self.text.sweep(fill="#28dcff")
            self.query_one("#whole").on_singing(
                opacity=lambda p: 0.2 + 0.6 * p, keep=True
            )

    actual, _item, _context = build(Equivalent(), segments=(Segment(1000, 2000),))

    def compiled(plan):
        layers = sampled_layers(plan)
        return sorted(
            (event.start_time, event.end_time, event.layer, event.text)
            for event in compile_layers(layers).events
        )

    # Captured from the pre-migration WholeGlow on this exact input/context.
    digest = hashlib.sha256(json.dumps(compiled(actual)).encode()).hexdigest()
    assert digest == "ac9e27708178cadbfac682ffea4d0008e9c0819b08501778ce96da785afd49b0"
