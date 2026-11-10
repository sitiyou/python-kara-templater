from dataclasses import replace

from examples.staggered_path import ArcWave, scene
from kara_templater import (
    DisplayWindow,
    DynamicProperties,
    EffectContext,
    KaraokeItem,
    KaraokeLine,
    SampleContext,
    Segment,
    Style,
    TextUnit,
    layout_line,
)


def test_arc_staggers_by_character_arrival_and_returns_to_layout():
    source = KaraokeLine((TextUnit("AB", (Segment(1000, 2000),)),))
    style = Style(fontname="DejaVu Sans", fontsize=40)
    ruby = replace(style, name="ruby", fontsize=20)
    window = DisplayWindow(500, 3000)
    layout = layout_line(source, style=style, ruby_style=ruby, resolution=(640, 480))
    plan = ArcWave().build(
        KaraokeItem("arc", source, "Default", window),
        EffectContext(layout, style, ruby, (640, 480)),
    )
    ids = {layer.text: layer.animation_id for layer in plan.layers}
    assert set(ids) == {"A", "B"}
    assert all(not layer.animations for layer in plan.layers)

    def at(text, time):
        return plan.dynamic.function(SampleContext(time, 0, window, ids[text], 0))

    assert at("A", 999) == at("B", 1200) == DynamicProperties()
    assert at("A", 1200).offset_y == -24
    assert at("A", 1400) == DynamicProperties()
    assert at("B", 1700).offset_y < -20
    for text in ids:
        assert at(text, 2400) == DynamicProperties()


def test_arc_script_output_is_deterministic_and_bounded():
    first = scene()
    assert first.document.dumps() == scene().document.dumps()
    assert first.event_count < 500
    assert first.event_count > scene(ArcWave(height=0, width=0)).event_count
    assert all(
        500 <= event.start_time < event.end_time <= 3000
        for event, _ in first.event_origins
    )
