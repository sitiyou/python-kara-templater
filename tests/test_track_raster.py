"""Track integration for pre-blur materials, time, alpha and resource limits."""

from dataclasses import replace

import pytest
from track_helpers import compile_tracks

from examples._lyrics import document
from kara_templater import (
    BLUE,
    RED,
    WHITE,
    Animate,
    Blur,
    Body,
    Display,
    DisplayWindow,
    Document,
    KaraokeItem,
    KaraokeLine,
    Line,
    LineMatch,
    On,
    OutputCapabilityError,
    OutputSettings,
    Overlay,
    PaintStyle,
    RasterSettings,
    Ruby,
    SceneBudget,
    Segment,
    SingleLine,
    Syllable,
    TextStyle,
    TextUnit,
    Track,
    layout_line,
)
from kara_templater._raster import RasterBudget, RasterCanvas, RasterFrame, rasterize


def scene(text="AB", ruby="ab"):
    source = document(fontname="DejaVu Sans", text=text)
    source.styles["Default"].fontsize = 20
    source.records = [r for r in source.records if not isinstance(r, Line)]
    item = KaraokeItem(
        "test",
        KaraokeLine((TextUnit(text, (Segment(100, 200, ruby),)),)),
        "Default",
        DisplayWindow(0, 320),
    )
    return source, item


def track(**kwargs):
    return Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(
                fill=WHITE,
                stroke_width=1,
                blur=Blur(color=RED, radius=2, width=2, opacity=0.7),
            )
        ),
        overlay=Overlay(style=PaintStyle(fill=BLUE, blur=Blur(color=BLUE))),
        **kwargs,
    )


def render(config, source=None, item=None, **kwargs):
    if source is None or item is None:
        source, item = scene()
    return compile_tracks(
        source,
        items=(item,),
        tracks=(config,),
        settings=OutputSettings(
            resolution=(640, 480), max_events=20000, raster=RasterSettings()
        ),
        budget=SceneBudget(
            max_events=40000, max_active=20000, max_bytes=128 * 1024 * 1024
        ),
        **kwargs,
    )


def frame(result, time):
    # Explicit items leave source dialogue untouched; fixtures contain none.
    return rasterize(
        result.document.dumps(),
        time,
        (640, 480),
        budget=RasterBudget(max_images=50000, max_events=50000),
    )


def test_track_sweep_endpoints_and_hold_merging_preserve_source_time():
    result = render(track())
    assert frame(result, 0) == frame(result, 100)
    assert frame(result, 200) == frame(result, 280)
    assert frame(result, 120) != frame(result, 200)
    assert result.event_count < 10000
    assert not any("hard-clip" in diagnostic for diagnostic in result.diagnostics)
    assert any("YUV420" in diagnostic for diagnostic in result.diagnostics)
    assert any(
        line.start_time == 0 and line.end_time >= 100
        for line, _ in result.event_origins
    )
    assert all(
        origin.sources[0].item_id == "test" for _, origin in result.event_origins
    )


def test_group_opacity_is_applied_once_after_body_and_ruby_composition():
    full = render(track(ruby=Ruby()))
    half = render(
        track(
            ruby=Ruby(),
            animations=(On(Display.Start, Animate(opacity=0.5, duration=320)),),
        )
    )
    a, b = frame(full, 160).rgba, frame(half, 160).rgba
    assert any(a[3::4])
    for index in range(0, len(a), 4):
        assert b[index + 3] == (a[index + 3] + 1) // 2
        if b[index + 3]:
            assert a[index : index + 3] == b[index : index + 3]


def test_sampling_preflight_can_cancel_before_callbacks_and_exposes_raster_cost():
    calls = []

    def scale(progress):
        calls.append(progress)
        return 1.0

    def cancel(estimate):
        assert estimate.raster and estimate.raster[0].frames > 0
        assert estimate.target_samples > 0 and estimate.estimated_events > 0
        assert not calls
        raise RuntimeError("cancel")

    with pytest.raises(RuntimeError, match="cancel"):
        render(
            track(animations=(On(Syllable.Singing, Animate(scale=scale)),)),
            on_estimate=cancel,
        )
    assert not calls


def test_frame_budget_rejects_before_user_code_and_input_stays_unchanged():
    source, item = scene()
    before = source.dumps()
    calls = []
    config = track(
        animations=(
            On(
                Display.Start,
                Animate(scale=lambda p: calls.append(p) or 1, duration=320),
            ),
        )
    )
    with pytest.raises(OutputCapabilityError, match="preflight"):
        compile_tracks(
            source,
            items=(item,),
            tracks=(config,),
            settings=OutputSettings(
                resolution=(640, 480), raster=RasterSettings(max_frames=1)
            ),
        )
    assert not calls and source.dumps() == before
    with pytest.raises(OutputCapabilityError, match="event budget"):
        compile_tracks(
            source,
            items=(item,),
            tracks=(track(),),
            settings=OutputSettings(
                resolution=(640, 480), raster=RasterSettings(), max_events=1
            ),
        )
    assert source.dumps() == before


def test_different_material_radii_widths_and_disabled_glow_render_without_hard_clips():
    config = track()
    config.overlay = Overlay(
        style=PaintStyle(
            fill=BLUE, stroke_width=3, blur=Blur(color=BLUE, radius=5, width=4)
        )
    )
    result = render(config)
    assert frame(result, 160) != frame(result, 80)
    config.overlay = Overlay(style=PaintStyle(fill=BLUE, blur=None))
    disabled = render(config)
    assert sum(frame(disabled, 280).rgba[3::4]) < sum(frame(result, 280).rgba[3::4])


def test_hierarchical_geometry_and_dynamic_materials_use_original_target():
    result = render(
        track(
            animations=(
                On(Display.Start, Animate(scale=1.1, duration=320)),
                On(
                    Syllable.Singing,
                    Animate(scale=1.2, blur_radius=(2, 4), blur_width=(2, 3)),
                ),
            )
        )
    )
    plain = render(track())
    assert frame(result, 160) != frame(plain, 160)
    assert max(line.end_time for line, _ in result.event_origins) == 320


def test_raster_rerender_uses_owned_sources_and_stable_neutral_style():
    source, _ = scene()
    source.records.append(Line(text=r"{\k10}AB", start_time=0, end_time=320))
    settings = OutputSettings(
        resolution=(640, 480), raster=RasterSettings(), max_events=20000
    )
    first = compile_tracks(source, tracks=(track(),), settings=settings)
    second = compile_tracks(first.document, tracks=(track(),), settings=settings)
    assert first.document.dumps() == second.document.dumps()


def test_empty_targets_and_unmatched_sources_do_not_invent_pixels():
    source, item = scene(text="   ", ruby="")
    result = render(track(), source, item)
    assert result.event_count == 0
    unmatched = render(Track(source=LineMatch(style="missing")))
    assert unmatched.event_count == 0


def test_unsupported_style_geometry_is_explicit():
    source, item = scene()
    source.styles["Default"].fields["Angle"] = "10"
    with pytest.raises(OutputCapabilityError, match="Angle"):
        render(track(), source, item)


def test_additive_material_energy_is_clamped_before_group_opacity():
    canvas = RasterCanvas(1, 1)
    frame = RasterFrame(1, 1, bytes((255, 0, 0, 255)))
    canvas.add_frame(frame)
    canvas.add_frame(frame)
    assert canvas.finish(opacity=0.5).rgba == bytes((255, 0, 0, 128))


def test_raster_extension_occupancy_and_clock_remain_distinct():
    source, item = scene()
    config = track(
        animations=(
            On(Display.End, Animate(opacity=(1, 0), duration=80), extend_display=True),
        )
    )
    result = render(config, source, item)
    assert max(line.end_time for line, _ in result.event_origins) == 400
    assert frame(result, 280) == frame(result, 320)
    assert sum(frame(result, 360).rgba[3::4]) < sum(frame(result, 320).rgba[3::4])


def test_native_group_fade_matches_sampled_composite_with_less_output():
    config = track(
        animations=(On(Display.Start, Animate(opacity=(0, 1), duration=320)),)
    )
    native = render(config)
    sampled = render(
        track(
            animations=(
                On(
                    Display.Start,
                    Animate(opacity=lambda progress: progress, duration=320),
                ),
            )
        )
    )
    assert native.event_count < sampled.event_count
    # Geometry and sweep remain sampled; alpha alone can use native transforms.
    for time in (0, 40, 80, 120, 160, 200, 240, 280):
        a, b = frame(native, time).rgba, frame(sampled, time).rgba
        assert max(abs(x - y) for x, y in zip(a[3::4], b[3::4], strict=True)) <= 1


def test_discontinuous_group_opacity_preserves_reset():
    result = render(
        track(animations=(On(Display.Start, Animate(opacity=0.5, duration=80)),))
    )
    full = render(track())
    assert frame(result, 80) == frame(full, 80)
    assert sum(frame(result, 40).rgba[3::4]) < sum(frame(full, 40).rgba[3::4])


@pytest.mark.parametrize("position", ((-24, 30), (620, 30), (30, -24), (30, 468)))
def test_offscreen_glow_matches_crop_of_complete_scene(position):
    source, item = scene(text="A", ruby="")

    def render_at(where, resolution):
        resized = Document.parse(
            source.dumps()
            .replace("PlayResX: 640", f"PlayResX: {resolution[0]}")
            .replace("PlayResY: 480", f"PlayResY: {resolution[1]}")
        )
        config = Track(
            source=LineMatch(),
            layout=SingleLine(position=where),
            body=Body(
                style=TextStyle(fill=WHITE, blur=Blur(color=RED, radius=10, width=4))
            ),
        )
        return compile_tracks(
            resized,
            items=(item,),
            tracks=(config,),
            settings=OutputSettings(
                resolution=resolution, max_events=50000, raster=RasterSettings()
            ),
            budget=SceneBudget(
                max_events=100000, max_active=20000, max_bytes=128 * 1024 * 1024
            ),
        )

    edge = frame(render_at(position, (640, 480)), 160)
    margin = 100
    full = render_at((position[0] + margin, position[1] + margin), (840, 680))
    large = rasterize(
        full.document.dumps(),
        160,
        (840, 680),
        budget=RasterBudget(max_images=50000),
    )
    expected = b"".join(
        large.rgba[
            ((y + margin) * 840 + margin) * 4 : ((y + margin) * 840 + margin + 640) * 4
        ]
        for y in range(480)
    )
    assert any(edge.rgba[3::4])
    assert edge.rgba == expected


def test_output_character_budget_is_shared_by_all_source_lines():
    source, item = scene(text="A", ruby="")
    config = track()
    first = render(config, source, item)
    characters = sum(len(line.text) for line, _ in first.event_origins)
    second_item = replace(
        item,
        id="second",
        window=DisplayWindow(400, 720),
        source=KaraokeLine((TextUnit("A", (Segment(500, 600, ""),)),)),
    )
    before = source.dumps()
    with pytest.raises(OutputCapabilityError, match="output character budget") as error:
        compile_tracks(
            source,
            items=(item, second_item),
            tracks=(config,),
            settings=OutputSettings(
                resolution=(640, 480),
                max_events=50000,
                raster=RasterSettings(max_output_chars=characters + 100),
            ),
        )
    assert error.value.origin is not None
    assert all(ref.item_id == "second" for ref in error.value.origin.sources)
    assert source.dumps() == before


@pytest.mark.parametrize("text", ("office", " A  B ", "fj AV"))
@pytest.mark.parametrize("italic", (False, True))
def test_raster_geometry_matches_independent_whole_text(text, italic):
    source, item = scene(text=text, ruby="")
    style = source.styles["Default"]
    style.fontsize = 24
    style.italic = italic
    result = render(
        Track(
            source=LineMatch(),
            body=Body(style=TextStyle(fill=WHITE, stroke_width=0, blur=None)),
        ),
        source,
        item,
    )
    layout = layout_line(item.source, style=style, resolution=(640, 480))
    reference = Document.parse(source.dumps())
    reference.records.append(
        Line(
            text=rf"{{\an5\pos({layout.box.center},{layout.box.middle})\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}"
            + text,
            start_time=0,
            end_time=320,
        )
    )
    expected = rasterize(reference.dumps(), 160, (640, 480))
    assert frame(result, 160) == expected


def test_explicit_color_budget_reduces_output_with_bounded_composite_error():
    from PIL import Image, ImageChops

    source, item = scene(text="A", ruby="")
    config = track()
    exact = render(config, source, item)
    estimates = []
    reduced = compile_tracks(
        source,
        items=(item,),
        tracks=(config,),
        settings=OutputSettings(
            resolution=(640, 480),
            max_events=20000,
            raster=RasterSettings(max_channel_error=4),
        ),
        on_estimate=estimates.append,
    )
    assert estimates[0].raster[0].max_channel_error == 4
    assert reduced.event_count < exact.event_count
    assert any("4/255" in diagnostic for diagnostic in reduced.diagnostics)
    for time in (0, 120, 160, 200, 280):
        a = Image.frombytes("RGBA", (640, 480), frame(exact, time).rgba)
        b = Image.frombytes("RGBA", (640, 480), frame(reduced, time).rgba)
        for color in ("black", "white", "gray"):
            background = Image.new("RGBA", (640, 480), color)
            before = Image.alpha_composite(background, a).convert("RGB")
            after = Image.alpha_composite(background, b).convert("RGB")
            assert max(ImageChops.difference(before, after).tobytes()) <= 4


def test_unequal_material_opacity_runs_with_custom_group_animation():
    calls = []
    config = track(
        animations=(
            On(
                Display.Start,
                Animate(opacity=lambda p: calls.append(p) or 0.5, duration=320),
            ),
        )
    )
    config.overlay = Overlay(style=PaintStyle(opacity=0.5))
    result = render(config)
    assert calls
    assert any(frame(result, 160).rgba[3::4])


def test_native_alpha_limit_is_explicit_and_absent_from_material_backend():
    source, item = scene()
    config = track(animations=(On(Display.Start, Animate(opacity=0.5, duration=320)),))
    native = compile_tracks(source, items=(item,), tracks=(config,))
    material = render(config, source, item)
    assert any(
        "post-composite group alpha" in message for message in native.diagnostics
    )
    assert not any(
        "post-composite group alpha" in message for message in material.diagnostics
    )


def test_frame_character_budget_includes_native_opacity_transform_tags():
    source, item = scene(text="A", ruby="")
    config = track()
    config.overlay = None
    plain = render(config, source, item)
    characters = sum(len(line.text) for line, _ in plain.event_origins)
    config.animations = (On(Display.Start, Animate(opacity=(0, 1), duration=320)),)
    with pytest.raises(OutputCapabilityError, match="frame character budget") as error:
        compile_tracks(
            source,
            items=(item,),
            tracks=(config,),
            settings=OutputSettings(
                resolution=(640, 480),
                max_events=20000,
                raster=RasterSettings(max_frame_chars=characters + 1),
            ),
        )
    assert error.value.time_ms == 0
    assert error.value.origin is not None
