from dataclasses import replace

import pytest

from kara_templater.appearance import ColorSpan, PaintPair, RubyPaint
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT, Document, Line, Style
from kara_templater.ass_output import OutputCapabilityError
from kara_templater.characters import TextRange
from kara_templater.composition import Color, Paint
from kara_templater.model import KaraokeLine, Segment, TextUnit
from kara_templater.recipe import (
    EffectPlan,
    KaraokeEffect,
    KaraokeItem,
    RubyPolicy,
    TrackStyle,
)
from kara_templater.render import render_karaoke
from kara_templater.timeline import DisplayWindow, HighlightTrack, Region, SingingPass

RED, BLUE = Paint(Color(255, 0, 0)), Paint(Color(0, 0, 255))


def test_decoration_boundary_diagnostic_identifies_source_time_and_tracks():
    from kara_templater import Glow

    recipe = KaraokeEffect(paints=PaintPair(after=replace(RED, glow=Glow(blur=20))))
    lyric = item()
    result = render_karaoke(document(), (lyric,), effect=recipe)
    messages = [d for d in result.diagnostics if "ASS hard-clips" in d]
    assert messages
    assert all(
        lyric.id + "/unit:0/text:" in d
        and "tracks=" in d
        and " ms" in d
        and "temporal sampling cannot" in d
        for d in messages
    )
    # All spatial transitions have finished before this display window.
    completed = render_karaoke(
        document(), (replace(lyric, window=DisplayWindow(2200, 2500)),), effect=recipe
    )
    assert not any("ASS hard-clips" in d for d in completed.diagnostics)


def test_partial_highlight_keeps_partition_clip_after_track_completion():
    def build(target, context):
        box = context.layout.units[0].box
        track = HighlightTrack(
            "half", 0, (SingingPass(1000, 2000, Region(box.left, box.center)),)
        )
        return KaraokeEffect(paints=PaintPair(after=RED), tracks=(track,)).build(
            target, context
        )

    result = render_karaoke(document(), (item(),), effect=build)
    final = [event for event, _ in result.event_origins if event.end_time > 2000]
    assert final and all(r"\clip" in event.text for event in final)


@pytest.mark.parametrize("completion", ["release", "clip"])
def test_sweep_completion_removes_clip_only_after_tail_without_restarting_clocks(
    completion,
):
    from kara_templater import EdgeSweep, Fade, Glow, Pulse, Sweep

    plans = []
    recipe = KaraokeEffect(
        paints=PaintPair(after=Paint(RED.fill, glow=Glow(blur=30))),
        sweep=Sweep(edges=EdgeSweep(tail_ms=200), completion=completion),
        fade=Fade(100, 400),
        pulses=(Pulse.whole_syllable(duration_ms=1800),),
    )

    def build(target, context):
        plan = recipe.build(target, context)
        plans.append(plan)
        return plan

    lyric = item()
    result = render_karaoke(document(), (lyric,), effect=build)
    released = [layer for layer in plans[0].layers if layer.clips is None]
    if completion == "release":
        assert released
        assert all(
            layer.active_window == DisplayWindow(2200, 2500) for layer in released
        )
        assert all(layer.window == lyric.window for layer in released)
        assert all(layer.animations[0].start_ms == 1000 for layer in released)
    else:
        assert not released
    final = [event for event, _ in result.event_origins if event.start_time >= 2200]
    assert final
    assert all((r"\clip" in event.text) == (completion == "clip") for event in final)
    assert all(event.end_time <= 2500 for event, _ in result.event_origins)


@pytest.mark.parametrize("incomplete", [False, True])
def test_pulse_planning_failure_identifies_unit_and_independent_tracks(incomplete):
    from kara_templater import Pulse, SourceRef

    lyric = replace(
        item(),
        source=KaraokeLine(
            (
                TextUnit("prefix"),
                TextUnit("AB", (Segment(1000, 2000),)),
            )
        ),
    )

    def custom(target, context):
        box = context.layout.units[1].box
        region = (
            Region(box.left, box.left + 1)
            if incomplete
            else Region(box.left, box.right)
        )
        tracks = (HighlightTrack("main", 1, (SingingPass(1000, 2000, region),)),)
        if not incomplete:
            tracks += (HighlightTrack("echo", 1, (SingingPass(1000, 2000, region),)),)
        return KaraokeEffect(
            tracks=tracks, pulses=(Pulse.each_char(tracks="each"),)
        ).build(target, context)

    with pytest.raises(
        ValueError, match="incomplete traversal" if incomplete else "scale conflict"
    ) as caught:
        render_karaoke(document(), (lyric,), effect=custom)
    origin = caught.value.origin
    assert origin.sources == (SourceRef(lyric.id, 1),)
    assert set(origin.track_ids) == ({"main"} if incomplete else {"main", "echo"})
    assert origin.sources[0].resolve(lyric) is lyric.source.units[1]
    assert len(caught.value.__notes__) == 1


@pytest.mark.parametrize(
    "failure",
    [
        "style",
        "ruby_style",
        "dispatch",
        "builder",
        "result",
        "raw_time",
        "raw_style",
        "layer_style",
    ],
)
def test_document_validation_keeps_item_origin_and_precedes_sampling(failure):
    from kara_templater import DynamicEffect, DynamicProperties, SourceRef

    calls = []

    def sample(context):
        calls.append(context.time_ms)
        return DynamicProperties()

    def custom(target, context):
        if failure == "result":
            return None
        plan = KaraokeEffect(dynamic=DynamicEffect(sample)).build(target, context)
        if failure == "raw_time":
            return replace(
                plan, raw_lines=(Line(text="raw", start_time=200, end_time=100),)
            )
        if failure == "raw_style":
            return replace(
                plan,
                raw_lines=(
                    Line(text="raw", style="Missing", start_time=0, end_time=100),
                ),
            )
        if failure == "layer_style":
            return replace(
                plan,
                layers=tuple(
                    replace(layer, style=replace(layer.style, name="Missing"))
                    for layer in plan.layers
                ),
            )
        return plan

    lyric = item()
    if failure in {"style", "ruby_style"}:
        lyric = replace(lyric, **{failure: "Missing"})
    effect = (
        {} if failure == "dispatch" else object() if failure == "builder" else custom
    )
    source = document()
    original = source.dumps()
    with pytest.raises((ValueError, TypeError)) as caught:
        render_karaoke(source, (lyric,), effect=effect)
    assert not calls
    origin = caught.value.origin
    assert origin.sources[0].item_id == lyric.id
    if failure == "layer_style":
        assert origin.sources == (SourceRef(lyric.id, 0, 0),)
    else:
        assert origin.sources == (SourceRef(lyric.id),)
    assert len(caught.value.__notes__) == 1
    assert source.dumps() == original


def test_early_layout_and_ruby_errors_resolve_precise_source_locations():
    from kara_templater import LayoutCapabilityError, SourceRef

    source = document()
    unchanged = source.dumps()
    lyric = replace(
        item(),
        source=KaraokeLine(
            (
                TextUnit("A"),
                TextUnit("مرحبا", (Segment(1000, 2000),)),
            )
        ),
    )
    with pytest.raises(LayoutCapabilityError) as caught:
        render_karaoke(source, (lyric,), effect=KaraokeEffect())
    assert caught.value.origin.sources == (SourceRef(lyric.id, 1),)
    assert caught.value.origin.sources[0].resolve(lyric) is lyric.source.units[1]
    assert len(caught.value.__notes__) == 1

    lyric = replace(
        lyric,
        source=KaraokeLine(
            (
                TextUnit("A"),
                TextUnit("AB", (Segment(1000, 2000, "ab"),)),
            )
        ),
    )
    recipe = KaraokeEffect(spans=(ColorSpan(TextRange(1, 1, 2), after=RED),))
    with pytest.raises(ValueError, match="ambiguous body colors") as caught:
        render_karaoke(source, (lyric,), effect=recipe)
    assert caught.value.origin.sources == (SourceRef(lyric.id, 1, 0),)
    assert (
        caught.value.origin.sources[0].resolve(lyric)
        is lyric.source.units[1].segments[0]
    )
    assert caught.value.origin.effect == "KaraokeEffect"
    assert len(caught.value.__notes__) == 1
    assert source.dumps() == unchanged


def test_color_range_failure_and_custom_builder_keep_exception_identity():
    from kara_templater import LayoutCapabilityError, SourceRef

    recipe = KaraokeEffect(spans=(ColorSpan(TextRange(0, 0, 100), after=RED),))
    with pytest.raises(LayoutCapabilityError, match="outside text") as caught:
        render_karaoke(document(), (item(),), effect=recipe)
    assert caught.value.origin.sources == (SourceRef(item().id, 0),)
    failure = TypeError("custom configuration failed")

    def custom(target, context):
        raise failure

    with pytest.raises(TypeError, match="custom configuration") as caught:
        render_karaoke(document(), (item(),), effect=custom)
    assert caught.value is failure
    assert failure.origin.sources == (SourceRef(item().id),)
    assert failure.origin.effect.endswith("custom")


def test_generated_event_origins_keep_segments_ruby_and_dynamic_sources():
    from kara_templater import (
        DynamicEffect,
        DynamicProperties,
        KaraokeLine,
        Segment,
        SourceRef,
        TextUnit,
    )

    lyric = replace(
        item(),
        source=KaraokeLine(
            (
                TextUnit(
                    "AB",
                    (
                        Segment(1000, 1400, "a"),
                        Segment(1600, 2000, "b"),
                    ),
                ),
            )
        ),
    )
    recipe = KaraokeEffect(
        dynamic=DynamicEffect(
            lambda ctx: DynamicProperties(offset_y=ctx.time_ms % 80 / 10),
        )
    )
    result = render_karaoke(document(), (lyric,), effect=recipe, owner="trace:/test")
    assert len(result.event_origins) == result.event_count
    generated = [
        r
        for r in result.document.records
        if isinstance(r, Line) and r.effect.startswith("karaoke:v1:trace")
    ]
    assert [id(event) for event, _ in result.event_origins] == list(map(id, generated))
    for event, origin in result.event_origins:
        assert origin.effect == "KaraokeEffect"
        assert origin.track_ids
        for ref in origin.sources:
            assert (
                ref.resolve(lyric) is lyric.source.units[0].segments[ref.segment_index]
            )
        if "ruby" in event.effect:
            assert len(origin.sources) == 1
        else:
            assert origin.sources == (
                SourceRef(lyric.id, 0, 0),
                SourceRef(lyric.id, 0, 1),
            )


def test_custom_and_raw_events_fall_back_to_item_origin_without_index_drift():
    from kara_templater import SourceRef

    def custom(target, context):
        plan = KaraokeEffect().build(target, context)
        return replace(
            plan,
            layers=tuple(replace(layer, origin=None) for layer in plan.layers),
            raw_lines=(
                Line(text="gone", start_time=1, end_time=4),
                Line(text="kept", start_time=0, end_time=100),
            ),
        )

    result = render_karaoke(document(), (item(),), effect=custom)
    assert len(result.event_origins) == result.event_count
    assert result.event_origins[-1][0].text == "kept"
    for _, origin in result.event_origins:
        assert origin.sources == (SourceRef(item().id),)
        assert origin.effect.endswith("custom")


def test_document_estimate_precedes_properties_and_can_cancel_without_mutation():
    from kara_templater import DynamicEffect, DynamicProperties

    calls, estimates = [], []

    def properties(ctx):
        assert estimates
        calls.append(ctx.time_ms)
        return DynamicProperties()

    def build(target, context):
        plan = KaraokeEffect().build(target, context)
        return (
            plan
            if target.id == "static"
            else replace(
                plan,
                dynamic=DynamicEffect(properties),
                raw_lines=(
                    Line(text="raw", start_time=0, end_time=100),
                    Line(text="vanished", start_time=1, end_time=4),
                ),
            )
        )

    source = document()
    original = source.dumps()
    items = (replace(item(), id="static"), item())

    def cancel(estimate):
        assert not calls
        estimates.append(estimate)
        raise ValueError("caller cancelled")

    with pytest.raises(ValueError, match="caller cancelled"):
        render_karaoke(source, items, effect=build, on_estimate=cancel)
    assert source.dumps() == original and not calls
    estimates.clear()
    result = render_karaoke(source, items, effect=build, on_estimate=estimates.append)
    assert len(estimates) == 1 and calls
    estimate = estimates[0]
    assert estimate.static_events > 0 and estimate.raw_events == 1
    assert len(estimate.sampling) == 1 and estimate.target_samples > 0
    assert estimate.estimated_events >= result.event_count
    assert source.dumps() == original


def test_invalid_raw_event_fails_before_properties_or_cost_report():
    from kara_templater import DynamicEffect, DynamicProperties

    def forbidden(_):
        pytest.fail("evaluation started before raw validation")
        return DynamicProperties()

    def build(target, context):
        return replace(
            KaraokeEffect().build(target, context),
            dynamic=DynamicEffect(forbidden),
            raw_lines=(Line(text="invalid", start_time=200, end_time=100),),
        )

    with pytest.raises(ValueError, match="positive-duration"):
        render_karaoke(document(), (item(),), effect=build, on_estimate=forbidden)


def test_occluded_track_still_triggers_named_first_and_each_pulses():
    from kara_templater import ProgressCurve, Pulse

    plans = {}

    def build(target, context):
        box = context.layout.units[0].box
        region = Region(box.left, box.right)
        main = HighlightTrack("main", 0, (SingingPass(1000, 2000, region),))
        cover = HighlightTrack(
            "cover",
            0,
            (
                SingingPass(
                    500, 2500, region, ProgressCurve(((0, 0), (0.05, 1), (1, 1)))
                ),
            ),
        )
        base = KaraokeEffect(
            paints=PaintPair(after=RED),
            tracks=(main,),
            pulses=(Pulse.each_char(tracks="named", track_id="main", duration_ms=50),),
        )
        plans["baseline"] = base.build(target, context)
        covered = replace(
            base,
            tracks=(main, cover),
            overlap="priority",
            track_styles=(TrackStyle("cover", BLUE, 10),),
        )
        plans["named"] = covered.build(target, context)
        plans["first"] = replace(
            covered, pulses=(Pulse.each_char(duration_ms=50),)
        ).build(target, context)
        plans["each"] = replace(
            covered, pulses=(Pulse.each_char(tracks="each", duration_ms=50),)
        ).build(target, context)
        return plans["named"]

    render_karaoke(document(), (item(),), effect=build)

    def animations(name):
        return {a for layer in plans[name].layers for a in layer.animations}

    assert animations("named") == animations("baseline")
    assert {a.track_id for a in animations("first")} == {"cover"}
    assert {a.track_id for a in animations("each")} == {"main", "cover"}
    assert len(animations("each")) == 4
    # During the lower track's animation it contributes no visible foreground.
    for time in (1000, 1500, 1900):
        visible = {
            layer.paint
            for layer in plans["named"].layers
            for span in layer.clips
            if span.start_ms <= time < span.end_ms
            and span.at(time).left <= layer.box.center < span.at(time).right
        }
        assert visible == {BLUE}


def test_decoration_bounds_do_not_split_body_sweep_at_character_edges():
    from kara_templater import Glow

    boundaries = []
    for blur in (0, 3, 30):

        def build(target, context, blur=blur):
            plan = KaraokeEffect(
                paints=PaintPair(after=Paint(RED.fill, glow=Glow(blur=blur)))
            ).build(target, context)
            moving = [
                s
                for layer in plan.layers
                for s in (layer.clips or ())
                if s.start != s.end and s.start_ms < 2000 and s.end_ms > 1000
            ]
            boundaries.append({(s.start_ms, s.end_ms) for s in moving})
            return plan

        render_karaoke(document(), (item(),), effect=build)
    assert boundaries == [{(1000, 2000)}] * 3


def test_dynamic_decoration_and_padding_do_not_retime_character_pulses():
    from kara_templater import (
        DynamicEffect,
        DynamicProperties,
        EdgeSweep,
        Glow,
        Pulse,
        Sweep,
    )

    variants = (
        KaraokeEffect(pulses=(Pulse.each_char(),)),
        KaraokeEffect(
            pulses=(Pulse.each_char(),),
            spans=(
                ColorSpan(TextRange(0, 0, 1), before=RED, after=BLUE),
                ColorSpan(TextRange(0, 1, 2), before=BLUE, after=RED),
            ),
        ),
        KaraokeEffect(
            paints=PaintPair(after=Paint(RED.fill, border=20, glow=Glow(blur=30))),
            pulses=(Pulse.each_char(),),
            sweep=Sweep(edges=EdgeSweep(100, 200, 300)),
        ),
        KaraokeEffect(
            paints=PaintPair(after=Paint(RED.fill, glow=Glow(blur=3))),
            pulses=(Pulse.each_char(),),
            dynamic=DynamicEffect(
                lambda ctx: DynamicProperties(glow_blur=ctx.progress * 40),
                max_glow_blur=40,
            ),
        ),
    )
    timings = []
    for recipe in variants:

        def build(target, context, recipe=recipe):
            plan = recipe.build(target, context)
            timings.append(
                {animation for layer in plan.layers for animation in layer.animations}
            )
            return plan

        render_karaoke(document(), (item(),), effect=build)
    assert timings[0] and all(timing == timings[0] for timing in timings[1:])


def test_dynamic_render_and_whole_document_preflight():
    from kara_templater import DynamicEffect, DynamicProperties, OutputSettings

    calls = []

    def sample(ctx):
        calls.append(ctx)
        return DynamicProperties(offset_y=ctx.progress * 5)

    effect = KaraokeEffect(dynamic=DynamicEffect(sample))
    one = render_karaoke(document(), (item(),), effect=effect)
    assert calls
    assert any("target samples" in d for d in one.diagnostics)
    calls.clear()
    with pytest.raises(OutputCapabilityError, match="preflight"):
        render_karaoke(
            document(),
            (item(), replace(item(), id="second")),
            effect=effect,
            settings=OutputSettings(resolution=(640, 480), max_events=one.event_count),
        )
    assert not calls


def document():
    return Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style(fontname="DejaVu Sans", fontsize=40).serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )


def item(ruby=False):
    return KaraokeItem(
        "line:1",
        KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "ab" if ruby else ""),)),)),
        "Default",
        DisplayWindow(500, 2500),
    )


def test_structured_render_is_immutable_and_repeatable_with_ruby():
    source = document()
    before = source.dumps()
    effect = KaraokeEffect(paints=PaintPair(after=RED))
    result = render_karaoke(source, (item(True),), effect=effect)
    assert source.dumps() == before
    assert result.event_count > 0
    assert "Default-ruby" in result.document.styles
    assert any(line.style == "Default-ruby" for line in result.document.lines)
    reloaded = Document.parse(result.document.dumps())
    repeated = render_karaoke(reloaded, (item(True),), effect=effect)
    assert repeated.document.dumps() == result.document.dumps()


def test_owner_cleanup_preserves_source_and_other_generated_owners():
    source = document()
    original = Line(text="untouched", start_time=0, end_time=500, effect="source")
    source.records.append(original)
    effect = KaraokeEffect(paints=PaintPair(after=RED))
    first = render_karaoke(source, (item(),), effect=effect, owner="one")
    second = render_karaoke(
        first.document, (replace(item(), id="other"),), effect=effect, owner="two"
    )
    cleared = render_karaoke(second.document, (), effect=effect, owner="one")
    assert any(
        line.text == "untouched" and line.effect == "source"
        for line in cleared.document.lines
    )
    assert all(
        not line.effect.startswith("karaoke:v1:one:") for line in cleared.document.lines
    )
    assert any(
        line.effect.startswith("karaoke:v1:two:") for line in cleared.document.lines
    )


def test_color_spans_and_explicit_ruby_palette_reach_ass():
    effect = KaraokeEffect(
        spans=(
            ColorSpan(TextRange(0, 0, 1), after=RED),
            ColorSpan(TextRange(0, 1, 2), after=BLUE),
        ),
        ruby_paints=(RubyPaint(0, 0, PaintPair(after=RED)),),
    )
    result = render_karaoke(document(), (item(True),), effect=effect)
    assert any(
        line.text.endswith("A") and r"\1c&H0000FF&" in line.text
        for line in result.document.lines
    )
    assert any(
        line.text.endswith("B") and r"\1c&HFF0000&" in line.text
        for line in result.document.lines
    )


def test_function_recipe_and_style_dispatch():
    def effect(target, context):
        return KaraokeEffect(paints=PaintPair(after=RED)).build(target, context)

    result = render_karaoke(document(), (item(),), effect={"Default": effect})
    assert result.event_count > 0
    raw = render_karaoke(
        document(),
        (item(),),
        effect=lambda target, ctx: EffectPlan(
            raw_lines=(Line(text="custom", start_time=0, end_time=1000),)
        ),
    )
    assert raw.event_count == 1


def test_guide_does_not_generate_ruby():
    result = render_karaoke(
        document(),
        (item(True),),
        effect=KaraokeEffect.guide(paints=PaintPair(after=RED)),
    )
    assert all(line.style == "Default" for line in result.document.lines)


def test_multitrack_conflict_is_reported_with_source():
    def effect(target, context):
        box = context.layout.box
        tracks = tuple(
            HighlightTrack(
                name, 0, (SingingPass(1000, 2000, Region(box.left, box.right)),)
            )
            for name in ("a", "b")
        )
        return KaraokeEffect(
            tracks=tracks, track_styles=(TrackStyle("a", RED), TrackStyle("b", BLUE))
        ).build(target, context)

    with pytest.raises(
        OutputCapabilityError, match="line:1/unit:0/text:0:1.*identical"
    ):
        render_karaoke(document(), (item(),), effect=effect)


def test_follow_ruby_requires_group_pulses():
    from kara_templater.animation import Pulse

    effect = KaraokeEffect(
        pulses=(Pulse.each_char(),), ruby=RubyPolicy(follow="syllable")
    )
    with pytest.raises(OutputCapabilityError, match="requires syllable-target"):
        render_karaoke(document(), (item(True),), effect=effect)


def test_duplicate_union_track_has_identical_output_and_no_brightness_duplication():
    def build(count):
        def effect(target, context):
            box = context.layout.box
            tracks = tuple(
                HighlightTrack(
                    str(i), 0, (SingingPass(1000, 2000, Region(box.left, box.right)),)
                )
                for i in range(count)
            )
            return KaraokeEffect(paints=PaintPair(after=RED), tracks=tracks).build(
                target, context
            )

        return render_karaoke(document(), (item(),), effect=effect)

    assert build(1).document.dumps() == build(2).document.dumps()


def test_generated_records_stay_in_their_ass_sections():
    source = document()
    index = source.records.index("[Events]")
    source.records[index:index] = ["[Fonts]", "fontname: untouched.ttf"]
    source.records.extend(("[Graphics]", "filename: untouched.png"))
    result = render_karaoke(
        source, (item(True),), effect=KaraokeEffect(paints=PaintPair(after=RED))
    )
    parsed = Document.parse(result.document.dumps())
    assert "Default-ruby" in parsed.styles
    assert len(parsed.lines) == result.event_count
    assert "fontname: untouched.ttf" in parsed.records
    assert "filename: untouched.png" in parsed.records
