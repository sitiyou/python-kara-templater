from dataclasses import replace

import pytest

from kara_templater import Color, CueMarker, Document, Line, Record, Style
from kara_templater.characters import LayoutCapabilityError
from kara_templater.cues import (
    BarsCue,
    CueContent,
    CueContext,
    CuePreset,
    TextCue,
    bind_cues,
)
from kara_templater.geometry import Vec2, VectorPath
from kara_templater.scene import Lifetime, PathObject, Scene
from kara_templater.scene_animation import StateFunction, Timeline, VisualState
from kara_templater.scene_text import layout_document_text


def document(text: str) -> Document:
    return Document(
        [
            Style(fontname="DejaVu Sans", fontsize=48, shadow=0),
            Line(text=text, start_time=1000, end_time=5000),
        ],
        Record(res_x=640, res_y=360),
    )


def test_following_word_background_preserves_internal_motion_breakpoint():
    from kara_templater import _metrics

    doc = Document.create(width=640, height=360)
    doc.records.append(Line(text="A", start_time=1000, end_time=3000))
    layout = layout_document_text(doc, len(doc.records) - 1, display=Lifetime(1, 3))

    def jump(state: VisualState, progress: float) -> VisualState:
        return replace(state, position=Vec2(200 if progress >= 0.35 else 100, 100))

    timeline = (
        Timeline()
        .wait(0.1)
        .play(
            StateFunction(jump, frozenset(("position",))),
            duration=1,
            breakpoints=(0.35,),
        )
    )
    item = layout.characters[0]
    layout = replace(
        layout,
        characters=(
            replace(item, object=replace(item.object, animations=timeline.clips)),
        ),
    )
    background = layout.background(0, 1, id="bg", color=Color(255, 0, 0), follow=True)
    script = Scene(doc).add(background).compile().document.dumps()

    def left_at(time: int) -> int:
        images = _metrics.rasterize(script, time, 640, 360, 1_000_000, 100)
        return min(
            left
            for left, _, width, height, _, color, _ in images
            if width and height and color >> 8 == 0xFF0000
        )

    initial = left_at(1449)
    assert left_at(1440) == initial
    assert left_at(1450) == initial + 100
    assert left_at(1451) == initial + 100
    assert left_at(1449) == initial


def test_binding_preserves_color_scope_source_and_timing():
    doc = document(r"{\k100\1c&H0000FF&}AB{\k0\c} {\kt250\kf50}CD")
    before = doc.dumps()
    layout = layout_document_text(doc, 1, display=Lifetime(0, 5))
    assert doc.dumps() == before
    assert layout.source.text == "AB CD"
    assert layout.characters[0].object.state.fill == Color(255, 0, 0)
    assert layout.characters[2].object.state.fill == Color(255, 255, 255)
    assert [(s.start, s.end, s.start_offset, s.end_offset) for s in layout.singing] == [
        (1, 2, 0, 2),
        (2, 2, 2, 3),
        (3.5, 4, 3, 5),
    ]
    assert all(item.object.origin is not None for item in layout.characters)


def test_ligature_is_one_drawable_and_cannot_be_cut_for_color_or_cue():
    layout = layout_document_text(document("ffi"), 1)
    assert len(layout.characters) == 1
    assert (layout.characters[0].start, layout.characters[0].end) == (0, 3)
    with pytest.raises(LayoutCapabilityError, match="cluster"):
        layout.range_bounds(0, 1)
    with pytest.raises(LayoutCapabilityError, match="cluster"):
        layout_document_text(document(r"f{\c&HFF&}fi"), 1)
    with pytest.raises(ValueError, match="cluster"):
        bind_cues(
            layout,
            {"bars": CuePreset(factory=BarsCue(), trigger=2)},
            markers=(CueMarker("a", "bars", 1),),
        )


def test_word_background_uses_measured_bounds_and_padding():
    layout = layout_document_text(document("HELLO WORLD"), 1)
    box = layout.range_bounds(6, 11)
    shape = layout.background(
        6, 11, id="word", color=Color(30, 40, 50), padding=Vec2(10, 6)
    )
    assert shape.state.position == Vec2(box.left - 10, box.top - 6)
    assert shape.path == VectorPath.rectangle(box.width + 20, box.height + 12)
    assert shape.origin is not None
    assert shape.layer == -1


def test_inline_and_independent_cues_share_model_without_changing_times():
    marker = CueMarker("intro", "bars")
    other = CueMarker("counter", "numbers", 0, "independent")
    doc = document(marker.markup() + other.markup() + r"{\k300}Hello")
    layout = layout_document_text(doc, 1, display=Lifetime(0, 5))
    presets = {
        "bars": CuePreset(factory=BarsCue()),
        "numbers": CuePreset(factory=TextCue(), position=Vec2(50, 60)),
    }
    bound = bind_cues(layout, presets)
    direct = bind_cues(
        replace(layout, source=replace(layout.source, cues=())),
        presets,
        markers=(marker, other),
    )
    assert bound.text.characters == direct.text.characters
    assert bound.inline == direct.inline
    assert bound.independent == direct.independent
    assert bound.text.singing == layout.singing
    assert bound.text.source.text == layout.source.text
    assert bound.text.characters[0].bounds.left == layout.characters[0].bounds.left + 84
    assert bound.independent[0].state.position == Vec2(50, 60)
    scene = Scene(doc).add(bound.group(position=Vec2(100, 200)), *bound.independent)
    scene.replace_source(1)
    result = scene.compile()
    assert not any(
        "kara:v1 cue" in line.text for line in result.document.lines if not line.comment
    )
    assert any(
        "kara:v1 cue" in line.text for line in result.document.lines if line.comment
    )


def test_release_space_is_seekable_and_keeps_source_timing():
    layout = layout_document_text(document(r"{\k300}AB"), 1, display=Lifetime(0, 5))
    bound = bind_cues(
        layout,
        {"bars": CuePreset(factory=BarsCue(), keep_space=False)},
        markers=(CueMarker("intro", "bars"),),
    )
    letter = bound.text.characters[0].object
    assert (
        letter.at(0.5).position.x == layout.characters[0].object.state.position.x + 84
    )
    assert letter.at(2).position.x == layout.characters[0].object.state.position.x
    assert letter.at(1).position.x == letter.at(2).position.x
    assert (
        letter.at(0.5).position.x == layout.characters[0].object.state.position.x + 84
    )
    assert bound.text.singing == layout.singing


def test_custom_factory_gets_explicit_steps_and_source():
    received: list[CueContext] = []

    def custom(context: CueContext) -> CueContent:
        received.append(context)
        return CueContent(
            (
                PathObject(
                    id=context.id + "/triangle",
                    lifetime=context.lifetime,
                    path=VectorPath.polygon(Vec2(), Vec2(20, 10), Vec2(0, 20)),
                ),
            ),
            20,
            20,
        )

    layout = layout_document_text(document("HI"), 1)
    bound = bind_cues(
        layout,
        {
            "custom": CuePreset(
                factory=custom, trigger=3, lead=2, duration=2, steps=(0, 0.25, 1)
            )
        },
        markers=(CueMarker("intro", "custom"),),
    )
    assert received[0].steps == (1, 1.5, 3)
    assert bound.inline[0].children[0].origin == received[0].origin


@pytest.mark.parametrize("value", [r"{\t(\c&HFF&)}A", "A|a", "#"])
def test_unsupported_semantics_are_not_silently_dropped(value: str):
    with pytest.raises(ValueError):
        layout_document_text(document(value), 1)


def test_unknown_presets_and_untimed_default_are_diagnosed():
    layout = layout_document_text(document("HI"), 1)
    marker = CueMarker("intro", "bars")
    with pytest.raises(ValueError, match="unknown preset"):
        bind_cues(layout, {}, markers=(marker,))
    with pytest.raises(ValueError, match="absolute trigger"):
        bind_cues(layout, {"bars": CuePreset(factory=BarsCue())}, markers=(marker,))


def test_reflow_moves_later_inline_cues_and_following_backgrounds():
    layout = layout_document_text(document(r"{\k300}AB"), 1, display=Lifetime(0, 5))
    bound = bind_cues(
        layout,
        {
            "short": CuePreset(factory=BarsCue(), keep_space=False),
            "long": CuePreset(factory=BarsCue(), trigger=2, lead=2, duration=2),
        },
        markers=(CueMarker("first", "short"), CueMarker("second", "long")),
    )
    assert bound.inline[1].at(0.5).position.x == 84
    assert bound.inline[1].at(1.5).position.x == 0
    before = bound.text.range_bounds(0, 2, time=0.5)
    after = bound.text.range_bounds(0, 2, time=1.5)
    assert before.left - after.left == 84
    background = bound.text.background(0, 2, id="bg", color=Color(0, 0, 0), follow=True)
    assert background.at(0.5).position.x - background.at(1.5).position.x == 84
    Scene(document("source")).add(bound.group(), background).compile()


def test_document_file_and_direct_layout_are_equivalent():
    from examples.scene_cues import build

    original = build().document
    parsed = Document.parse(original.dumps())
    index = next(
        i for i, record in enumerate(original.records) if isinstance(record, Line)
    )
    before = layout_document_text(original, index, id="line")
    after = layout_document_text(parsed, index, id="line")
    assert before == after


def test_style_reset_changes_font_metrics_and_python_overrides_are_explicit():
    doc = document(r"A{\rBig}B{\r}C")
    doc.records.insert(
        0, Style(name="Big", fontname="DejaVu Sans", fontsize=96, shadow=0)
    )
    layout = layout_document_text(doc, 2)
    assert [item.object.font_size for item in layout.characters] == [48, 96, 48]
    assert layout.characters[1].bounds.height > layout.characters[0].bounds.height
    overridden = replace(
        layout.characters[1].object,
        state=replace(layout.characters[1].object.state, fill=Color(12, 34, 56)),
    )
    assert overridden.at(2).fill == Color(12, 34, 56)


@pytest.mark.parametrize("color", ("&H80FFFFFF", str(0x80FFFFFF - 2**32)))
def test_unknown_style_opacity_is_diagnosed_before_drawing(color):
    doc = document("A")
    doc.styles["Default"].fields["PrimaryColour"] = color
    with pytest.raises(LayoutCapabilityError, match="alpha"):
        layout_document_text(doc, 1)


def test_bound_clusters_render_like_a_whole_shaped_run():
    from examples.scene_cues import build
    from kara_templater._raster import rasterize
    from kara_templater.scene import TextObject
    from kara_templater.scene_animation import VisualState

    doc = build().document
    index = next(i for i, record in enumerate(doc.records) if isinstance(record, Line))
    doc.records[index] = Line(text="AV ffi cafe", start_time=1000, end_time=5000)
    layout = layout_document_text(doc, index)
    bound = Scene(doc).add(layout.group(position=Vec2(200, 200)))
    bound.replace_source(index)
    reference = Scene(doc).add(
        TextObject(
            id="whole",
            text="AV ffi cafe",
            font_size=64,
            lifetime=Lifetime(1, 5),
            state=VisualState(position=Vec2(200, 200), border=1),
        )
    )
    reference.replace_source(index)
    actual = rasterize(bound.compile().document.dumps(), 2000, (1280, 720))
    expected = rasterize(reference.compile().document.dumps(), 2000, (1280, 720))
    # Existing cluster verification allows one 1/64-pixel positioning step.
    differences = [abs(a - b) for a, b in zip(actual.rgba, expected.rgba, strict=True)]
    assert max(differences) <= 8
    assert sum(differences) / len(differences) < 0.01


def test_direct_script_info_and_parsed_script_info_have_same_soft_breaks():
    from examples.scene_cues import build

    original = build().document
    index = next(
        i for i, record in enumerate(original.records) if isinstance(record, Line)
    )
    original.records[index] = Line(text=r"A\nB", start_time=1000, end_time=5000)
    assert original.text_at(index).text == "A\nB"
    assert original.text_at(index) == Document.parse(original.dumps()).text_at(index)
