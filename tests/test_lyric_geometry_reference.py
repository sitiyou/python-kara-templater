"""Compiled lyric geometry compared with independent whole-text ASS rendering."""

from dataclasses import replace

import pytest

from kara_templater import (
    RED,
    Coverage,
    Document,
    Glow,
    Layout,
    LayoutCapabilityError,
    Line,
    LyricLine,
    SceneBudget,
    Style,
    Track,
    Vec2,
    prepare_tracks,
)
from kara_templater._raster import rasterize

SIZE = (160, 100)
BUDGET = SceneBudget(fps=10, max_events=100_000, max_active=20_000)


def coverage(line: LyricLine) -> LyricLine:
    return replace(line, coverage=Coverage())


@pytest.mark.parametrize("field,value", (("Angle", "10"), ("BorderStyle", "3")))
def test_unsupported_source_geometry_fails_before_visual_factory(field, value):
    source = Document.create(width=160, height=100)
    source.styles["Default"].fields[field] = value
    source.records.append(Line(text=r"{\k20}A", start_time=0, end_time=400))
    original = source.dumps()
    calls = []

    def factory(line: LyricLine) -> LyricLine:
        calls.append(line)
        return coverage(line)

    with pytest.raises(
        LayoutCapabilityError, match="border style 1 and zero style angle"
    ):
        prepare_tracks(source, tracks=(Track(id="invalid", effects=(factory,)),))
    assert not calls
    assert source.dumps() == original


@pytest.mark.parametrize("text", ("office", " A  B ", "fj AV"))
@pytest.mark.parametrize("italic", (False, True))
def test_shaped_coverage_matches_independent_whole_text(text, italic):
    style = Style(
        fontname="DejaVu Sans", fontsize=24, italic=italic, outline=0, shadow=0
    )
    source = Document.create(width=160, height=100, styles=(style,))
    source.records.append(Line(text=r"{\k20}" + text, start_time=0, end_time=400))
    scene = prepare_tracks(
        source,
        tracks=(
            Track(
                id="words",
                preview=0,
                tail=0,
                layout=Layout(position=Vec2(30, 40)),
                effects=(coverage,),
            ),
        ),
    )
    actual = scene.compile(budget=BUDGET)
    # The allocator aligns the complete measured cluster bounds. A descender
    # can contribute a fractional top offset, so the original text origin need
    # not equal the requested top-left of those bounds.
    origin = scene.lines[0].state.position
    reference = Document.create(width=160, height=100, styles=(style,))
    reference.records.append(
        Line(
            # Plain-text objects preserve spaces, including leading/trailing
            # ones. Native ASS needs hard spaces to request the same behavior.
            text=rf"{{\an7\pos({origin.x},{origin.y})\blur0}}"
            + text.replace(" ", r"\h"),
            start_time=0,
            end_time=400,
        )
    )
    expected = rasterize(reference.dumps(), 150, SIZE)
    assert any(expected.rgba[3::4])
    assert rasterize(actual.document.dumps(), 150, SIZE) == expected


@pytest.mark.parametrize(
    "position", (Vec2(-8, 40), Vec2(155, 40), Vec2(40, -10), Vec2(40, 95))
)
def test_compiled_edge_glow_matches_large_canvas_crop(position):
    def glowing(line: LyricLine) -> LyricLine:
        return replace(
            line,
            coverage=Coverage(
                glows={
                    target.node_id: Glow(RED, blur=10, border=4)
                    for target in line.query("character")
                }
            ),
        )

    def render(size, point):
        source = Document.create(
            width=size[0],
            height=size[1],
            styles=(Style(fontname="DejaVu Sans", fontsize=24, outline=0, shadow=0),),
        )
        source.records.append(Line(text=r"{\k20}A", start_time=0, end_time=400))
        scene = prepare_tracks(
            source,
            tracks=(
                Track(
                    id="edge",
                    preview=0,
                    tail=0,
                    layout=Layout(position=point),
                    effects=(glowing,),
                ),
            ),
        )
        return rasterize(scene.compile(budget=BUDGET).document.dumps(), 150, size)

    actual = render(SIZE, position)
    margin = 100
    large_size = (SIZE[0] + 2 * margin, SIZE[1] + 2 * margin)
    full = render(large_size, position + Vec2(margin, margin))
    expected = b"".join(
        full.rgba[
            ((y + margin) * large_size[0] + margin) * 4 : (
                (y + margin) * large_size[0] + margin + SIZE[0]
            )
            * 4
        ]
        for y in range(SIZE[1])
    )
    assert any(actual.rgba[3::4])
    assert actual.rgba == expected
