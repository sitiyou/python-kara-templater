"""Document/Track ownership and advanced edits through the public coverage exit."""

from dataclasses import replace

import pytest
from test_track_coverage import canvas, reference
from test_track_preparation import binding
from test_track_scene import source, track

from kara_templater import (
    CYAN,
    PINK,
    Animate,
    Blur,
    Body,
    Display,
    Document,
    Lifetime,
    Line,
    LineMatch,
    ObjectGroup,
    On,
    Overlay,
    PaintStyle,
    PathObject,
    Ruby,
    SceneBudget,
    Syllable,
    TextStyle,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_track_coverage,
)
from kara_templater._raster import rasterize

BUDGET = SceneBudget(fps=10, max_events=100_000, max_active=10_000)


def prepare(document, tracks=None, **kwargs):
    return prepare_track_coverage(
        document,
        tracks=(track(),) if tracks is None else tracks,
        max_glow_blur=6,
        max_glow_border=3,
        **kwargs,
    )


def test_public_preparation_defers_callbacks_and_preserves_document():
    calls = []
    config = track(
        animations=(
            On(
                Syllable.Singing,
                Animate(scale=(1, 1.2), rate=lambda t: calls.append(t) or t),
            ),
        )
    )
    document = source()
    before = document.dumps()
    prepared = prepare(document, (config,))
    assert not calls
    assert document.dumps() == before
    assert prepared.partitions and prepared.components
    assert isinstance(prepared.group.children[0], ObjectGroup)
    assert not any("per drawing layer" in message for message in prepared.diagnostics)
    result = prepared.compile(budget=BUDGET)
    assert calls and result.output.event_count
    assert document.dumps() == before
    assert any(
        line.comment and r"{\k20}AB" in line.text for line in result.document.lines
    )


def test_repeat_generation_selection_restore_and_other_owners():
    document = source()
    document.records.append(Line(text=r"{\k20}CD", start_time=0, end_time=400))
    selected = Track(source=LineMatch(text="AB"), body=Body(style=TextStyle(fill=CYAN)))
    first = prepare(document, (selected,), owner="one").compile(budget=BUDGET).document
    again = prepare(first, (selected,), owner="one").compile(budget=BUDGET).document
    assert first.dumps() == again.dumps()
    assert any(not line.comment and line.text == r"{\k20}CD" for line in first.lines)
    second = (
        prepare(
            first,
            (Track(source=LineMatch(text="CD"), body=Body()),),
            owner="two",
        )
        .compile(budget=BUDGET)
        .document
    )
    restored = prepare(second, (), owner="one").compile(budget=BUDGET).document
    assert any(not line.comment and line.text == r"{\k20}AB" for line in restored.lines)
    assert any("karaoke%3Atwo" in line.effect for line in restored.lines)
    assert not any("karaoke%3Aone" in line.effect for line in restored.lines)


def test_editable_root_translation_and_custom_decoration_reach_actual_ass():
    prepared = prepare(source())
    before = prepared.compile(budget=BUDGET)
    moved = replace(
        prepared, group=replace(prepared.group, state=VisualState(position=Vec2(8, 4)))
    )
    after = moved.compile(budget=BUDGET)
    original = rasterize(before.document.dumps(), 350, (320, 240))
    actual = rasterize(after.document.dumps(), 350, (320, 240))
    for y in range(236):
        assert (
            actual.rgba[((y + 4) * 320 + 8) * 4 : ((y + 4) * 320 + 320) * 4]
            == original.rgba[(y * 320) * 4 : (y * 320 + 312) * 4]
        )
    decoration = PathObject(
        id="accent",
        lifetime=Lifetime(0, 0.4),
        path=VectorPath.rectangle(10, 5),
        state=VisualState(position=Vec2(5, 5), fill=PINK),
    )
    decorated = replace(
        prepared,
        group=replace(prepared.group, children=(*prepared.group.children, decoration)),
    )
    picture = rasterize(
        decorated.compile(budget=BUDGET).document.dumps(), 350, (320, 240)
    )
    offset = (7 * 320 + 7) * 4
    assert picture.rgba[offset : offset + 4] == bytes(
        (PINK.red, PINK.green, PINK.blue, 255)
    )


def test_glow_only_animation_declares_its_boundaries_without_fill_motion():
    config = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(blur=Blur(color=PINK, radius=2, width=1))),
        animations=(On(Display.Start, Animate(blur_radius=(2, 4), duration=30)),),
    )
    prepared = prepare(source(), (config,))
    assert prepared.glows
    assert all(0.03 in glow.breakpoints for glow in prepared.glows.values())
    result = prepared.compile(budget=BUDGET)
    assert result.sample_times[:2] == pytest.approx((0.015, 0.065))


def test_preparation_object_budget_and_runtime_glow_bound_are_enforced():
    with pytest.raises(ValueError, match="object budget"):
        prepare(source(), max_objects=1)
    config = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(blur=Blur(color=PINK, radius=8, width=1))),
    )
    prepared = prepare(source(), (config,))
    with pytest.raises(ValueError, match="bounds"):
        prepared.compile(budget=BUDGET)


def test_explicit_items_and_nested_alpha_match_existing_track_coverage():
    bound, item, context = binding(
        On(Display.Start, Animate(opacity=0.7, duration=2000)),
        On(Syllable.Singing, Animate(opacity=(0.3, 0.8))),
    )
    item = replace(item, ruby_style=context.ruby_style.name)
    document = Document.create(
        width=320, height=240, styles=(context.style, context.ruby_style)
    )
    document.records.append(Line(text="preserved", start_time=3000, end_time=4000))
    prepared = prepare_track_coverage(
        document,
        (item,),
        tracks=(
            Track(
                source=LineMatch(),
                body=Body(style=TextStyle(fill=CYAN)),
                ruby=Ruby(),
                overlay=Overlay(style=PaintStyle(fill=PINK)),
                animations=bound.config.animations,
            ),
        ),
        max_glow_blur=6,
        max_glow_border=3,
    )
    old = reference(item, bound.prepare(item, context))
    result = prepared.compile(budget=BUDGET)
    for seconds in (0.55, 0.85, 1.15, 1.45, 1.85):
        time = round(seconds * 1000)
        expected = canvas(old._frame(old._states(time)), (320, 240))
        actual = rasterize(result.document.dumps(), time, (320, 240))
        # The old backend factors uniform alpha out after 8-bit composition;
        # the scoped scene carries weighted planes throughout. At 1.85s this
        # fixture differs by one rounding unit, including alpha. Compare actual
        # displayed RGB on both extreme backgrounds, not just raw color bytes.
        assert max(abs(a - b) for a, b in zip(actual.rgba, expected.rgba, strict=True)) <= 1
        for background in (0, 255):
            for offset in range(0, len(actual.rgba), 4):
                aa, ea = actual.rgba[offset + 3], expected.rgba[offset + 3]
                for channel in range(3):
                    a = round(
                        (actual.rgba[offset + channel] * aa + background * (255 - aa))
                        / 255
                    )
                    e = round(
                        (expected.rgba[offset + channel] * ea + background * (255 - ea))
                        / 255
                    )
                    assert abs(a - e) <= 1
    assert any(
        not line.comment and line.text == "preserved" for line in result.document.lines
    )
