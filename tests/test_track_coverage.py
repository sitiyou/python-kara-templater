"""PreparedTrack → editable coverage scene against the existing raster backend."""

from dataclasses import replace

import pytest
from test_track_preparation import binding

from kara_templater import (
    BLUE,
    RED,
    Animate,
    Display,
    Glow,
    On,
    RasterSettings,
    SamplingSettings,
    SceneBudget,
    Syllable,
    Vec2,
)
from kara_templater._raster import RasterCanvas
from kara_templater._track_coverage import track_coverage
from kara_templater._track_raster import TrackRasterPlan


def canvas(positioned, resolution):
    result = RasterCanvas(*resolution)
    if positioned is not None:
        x, y, image = positioned
        result.over_frame(image, x, y)
    return result.finish()


def reference(item, prepared):
    plan = TrackRasterPlan(
        prepared.lyrics,
        prepared.properties,
        prepared.materials,
        item_id=item.id,
        resolution=prepared.context.resolution,
        sampling=SamplingSettings(step_ms=20),
        settings=RasterSettings(),
        effect_name="Track",
    )
    # Compare explicit sampled coverage at this timestamp, before either output
    # encoder. Native root-alpha curve lowering is tested separately elsewhere.
    plan.opacity_curve = None
    return plan


def compare(item, prepared, times):
    converted = track_coverage(item.id, prepared, max_glow_blur=12, max_glow_border=8)
    sample = converted.sampler(settings=RasterSettings(), budget=SceneBudget())
    old = reference(item, prepared)
    for time in times:
        actual = canvas(sample.frame(time / 1000), prepared.context.resolution)
        expected = canvas(old._frame(old._states(time)), prepared.context.resolution)
        assert actual.rgba == expected.rgba
    return converted


def test_track_material_partitions_preserve_fractional_sweep_and_endpoints():
    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    converted = compare(item, prepared, (0, 500, 613, 887, 1237, 1500, 1900))
    assert len(converted.components) == 2  # Body and its reading retain ownership.
    assert converted.partitions
    assert all(part.inside in (True, False) for part in converted.partitions.values())


def test_track_glow_and_geometry_motion_share_source_components():
    bound, item, context = binding(
        On(Syllable.Singing, Animate(scale=(1, 1.2), offset_x=(0, 8)))
    )
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(
                    target,
                    paints=replace(
                        target.paints,
                        before=replace(
                            target.paints.before, glow=Glow(RED, blur=2, border=1)
                        ),
                        after=replace(
                            target.paints.after, glow=Glow(BLUE, blur=4, border=2)
                        ),
                    ),
                )
                for target in prepared.lyrics.targets
            ),
        ),
    )
    compare(item, prepared, (600, 713, 1000, 1327, 1500))


def test_track_alpha_scope_hierarchy_and_unequal_material_opacities():
    bound, item, context = binding(
        On(Display.Start, Animate(opacity=0.7, duration=2000)),
        On(Syllable.Singing, Animate(opacity=(0.3, 0.8))),
    )
    prepared = bound.prepare(item, context)
    prepared = replace(
        prepared,
        lyrics=replace(
            prepared.lyrics,
            targets=tuple(
                replace(
                    target,
                    paints=replace(
                        target.paints,
                        before=replace(target.paints.before, opacity=0.8),
                        after=replace(target.paints.after, opacity=0.4),
                    ),
                )
                for target in prepared.lyrics.targets
            ),
        ),
    )
    compare(item, prepared, (600, 913, 1200, 1437))


def test_conversion_does_not_sample_callbacks_and_geometry_remains_editable():
    calls = []

    def rate(progress):
        calls.append(progress)
        return progress

    bound, item, context = binding(
        On(Syllable.Singing, Animate(scale=(1, 1.2), rate=rate))
    )
    converted = track_coverage(
        item.id, bound.prepare(item, context), max_glow_blur=12, max_glow_border=8
    )
    assert not calls
    with pytest.raises(ValueError, match="event budget"):
        converted.sampler(settings=RasterSettings(), budget=SceneBudget(max_events=1))
    assert not calls
    original = converted.sampler(settings=RasterSettings(), budget=SceneBudget()).frame(
        1
    )
    shifted = replace(
        converted,
        group=replace(
            converted.group, state=replace(converted.group.state, position=Vec2(10, 0))
        ),
    )
    moved = shifted.sampler(settings=RasterSettings(), budget=SceneBudget()).frame(1)
    assert original is not None and moved is not None
    assert moved[0] == original[0] + 10
    assert moved[1:] == original[1:]


def test_dynamic_track_glow_material_bindings_keep_color_width_and_radius():
    from kara_templater import CYAN, Blur, Body, Ruby, TextStyle, Track

    bound, item, context = binding()
    config = Track(
        source=bound.config.source,
        body=Body(style=TextStyle(fill=CYAN, blur=Blur(color=RED, radius=2, width=1))),
        ruby=Ruby(style=TextStyle(blur=Blur(color=RED, radius=2, width=1))),
        overlay=bound.config.overlay,
        animations=(
            On(
                Display.Start,
                Animate(
                    blur_color=(RED, BLUE),
                    blur_radius=(2, 5),
                    blur_width=(1, 3),
                    duration=2000,
                ),
            ),
        ),
    )
    prepared = config.bind((item,))[item.id].prepare(item, context)
    compare(item, prepared, (400, 713, 1000, 1437, 1800))


def test_existing_track_standard_ass_matches_converted_sample_grid():
    from kara_templater import Document, Style
    from kara_templater._raster import rasterize

    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    old = reference(item, prepared)
    lines = old.evaluate(
        style="Pixels", layer=0, max_events=100_000, max_chars=64_000_000
    )
    document = Document.create(
        width=320,
        height=240,
        styles=(Style(name="Pixels", outline=0, shadow=0, align=7),),
    )
    document.records.extend(lines)
    converted = track_coverage(item.id, prepared, max_glow_blur=12, max_glow_border=8)
    sample = converted.sampler(settings=RasterSettings(), budget=SceneBudget())
    for time in (600, 900, 1200, 1900):
        assert (
            canvas(sample.frame(time / 1000), (320, 240)).rgba
            == rasterize(document.dumps(), time, (320, 240)).rgba
        )


@pytest.mark.parametrize(
    "left,top", [(-12, 100), (315, 100), (150, -20), (150, 230), (-12, -20), (330, 100)]
)
@pytest.mark.parametrize("radius", [0.1, 2, 8])
def test_offscreen_glyph_glow_reenters_the_viewport_like_track_raster(
    left, top, radius
):
    bound, item, context = binding()
    prepared = bound.prepare(item, context)
    target = prepared.lyrics.targets[0]
    paint = replace(target.paints.before, glow=Glow(RED, blur=radius, border=1))
    target = replace(
        target,
        box=replace(target.box, left=left, top=top),
        tracks=(),
        paints=replace(target.paints, before=paint, after=paint),
    )
    prepared = replace(prepared, lyrics=replace(prepared.lyrics, targets=(target,)))
    compare(item, prepared, (1000,))
