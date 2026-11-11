from dataclasses import replace
from urllib.parse import unquote

import pytest
from effect_values import properties_at, sampled_layers

from examples.staggered_path import scene
from examples.whole_glow import WholeGlow
from kara_templater import (
    DisplayWindow,
    DynamicProperties,
    EffectContext,
    KaraokeItem,
    KaraokeLine,
    Segment,
    Style,
    TextUnit,
    compile_layers,
    layout_line,
)


@pytest.mark.parametrize(
    "segments", [(Segment(1000, 2000),), (Segment(1500, 1500),), ()]
)
def test_whole_glow_is_unique_unclipped_and_keeps_body_events(segments):
    source = KaraokeLine((TextUnit("AB", segments),))
    style = Style(fontname="DejaVu Sans", fontsize=40)
    ruby = replace(style, name="ruby", fontsize=20)
    window = DisplayWindow(500, 3000)
    layout = layout_line(source, style=style, ruby_style=ruby, resolution=(640, 480))
    item = KaraokeItem("glow", source, "Default", window)
    bound, style, ruby = WholeGlow()._prepare(item, style, ruby)
    plan = bound.build(item, EffectContext(layout, style, ruby, (640, 480)))
    glows = [layer for layer in plan.layers if layer.component == "glow"]
    bodies = [layer for layer in plan.layers if layer.component != "glow"]
    assert [layer.text for layer in glows] == ["A", "B"]
    assert all(layer.clips is None and layer.active_window is None for layer in glows)
    assert max(layer.order for layer in glows) < min(layer.order for layer in bodies)
    for time in (500, 1000, 1500, 2000, 2500):
        values = [properties_at(plan, l, time) for l in glows]
        progress = (
            float(time >= 1500)
            if segments and segments[0].start_ms == 1500
            else min(1, max(0, (time - 1000) / 1000)) if segments else 0
        )
        assert all(
            v.glow_opacity == pytest.approx(0.2 + 0.6 * progress) for v in values
        )
        assert all(properties_at(plan, l, time) == DynamicProperties() for l in bodies)
    # Sampling an identity body must preserve native clip timing, event count,
    # text and layer order exactly, despite the separate glow callback.
    sampled = sampled_layers(plan, bodies)

    def visual_events(layers):
        return [
            (e.start_time, e.end_time, e.layer, e.style, e.text)
            for e in compile_layers(layers).events
        ]

    assert visual_events(sampled) == visual_events(bodies)


def test_whole_glow_script_is_deterministic_and_bounded():
    result = scene(WholeGlow())
    assert result.document.dumps() == scene(WholeGlow()).document.dumps()
    assert result.event_count < 500
    glow_events = [e for e, _ in result.event_origins if "/halo:" in unquote(e.effect)]
    assert all(origin.effect == "WholeGlow" for _, origin in result.event_origins)
    assert glow_events
    assert all(r"\clip" not in event.text for event in glow_events)
