"""The CLI recipe preserves source placement/clocks through common orchestration."""

from dataclasses import replace
from typing import Literal

import pytest

from kara_templater import Document, Line, Style
from kara_templater._cli_preset import preset_scene
from kara_templater._raster import rasterize
from kara_templater.lyrics import tracks
from kara_templater.output.hook.draws import HookDrawResolver


def preset(
    document: Document,
    *,
    pulse: Literal["none", "char", "chars", "syllable"] = "none",
    fade_in: float = 0,
    fade_out: float = 0,
    preview: float = 0,
    tail: float = 0,
    styles: tuple[str, ...] | None = None,
):
    return preset_scene(
        document,
        owner="preset-test",
        before=None,
        after=None,
        pulse=pulse,
        fade_in=fade_in,
        fade_out=fade_out,
        preview=preview,
        tail=tail,
        styles=styles,
    )


def test_preset_reads_each_lyric_record_once(monkeypatch):
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", outline=0, shadow=0),)
    )
    document.records.append(Line(text=r"{\k50}春|はる{\k50}office", end_time=1000))
    index = len(document.records) - 1
    read = tracks._read_document_text
    calls = []

    def count(source, record_index, styles, soft_break):
        calls.append(record_index)
        return read(source, record_index, styles, soft_break)

    monkeypatch.setattr(tracks, "_read_document_text", count)
    (plan,) = preset(document).plans
    assert calls == [index]
    assert plan.source.lyrics == document.lyrics_at(index)


@pytest.mark.parametrize("alignment", range(1, 10))
@pytest.mark.parametrize("annotation", ["", "|<long reading"])
def test_source_alignment_and_event_margins_survive_common_allocation(alignment, annotation):
    document = Document.create(
        width=320,
        height=180,
        styles=(
            Style(
                fontname="DejaVu Sans",
                fontsize=24,
                align=alignment,
                outline=0,
                shadow=0,
            ),
        ),
    )
    document.records.append(
        Line(
            text=r"{\k100}AB" + annotation,
            start_time=1000,
            end_time=3000,
            margin_l=35,
            margin_r=45,
            margin_v=25,
        )
    )
    scene = preset(document, preview=0.2, tail=0.4, fade_in=0.1, fade_out=0.2)
    plan = scene.plans[0]
    box = plan.line.layout.body.bounds
    x = plan.placement.position.x + box.left
    y = plan.placement.position.y + box.top
    column, row = (alignment - 1) % 3, (alignment - 1) // 3
    width, height = box.width, box.height
    assert x == pytest.approx((35, 35 + (320 - 35 - 45 - width) / 2, 320 - 45 - width)[column])
    assert y == pytest.approx((180 - 25 - height, (180 - height) / 2, 25)[row])
    assert plan.placement.display.start == 0.8
    assert plan.placement.display.end == 3.4
    assert [(s.start, s.end) for s in plan.line.query("syllable")[0].timing] == [
        (1, 2)
    ]


@pytest.mark.parametrize("decimal", (False, True))
def test_fill_alpha_and_instantaneous_highlight_render_without_style_mutation(decimal):
    style = Style(
        fontname="DejaVu Sans",
        fontsize=24,
        shadow=0,
        outline=0,
    )
    document = Document.create(width=96, height=64, styles=(style,))
    document.styles["Default"].fields.update(
        PrimaryColour=str(0x800000FF - 2**32) if decimal else "&H800000FF",
        SecondaryColour=str(0xC000FF00) if decimal else "&HC000FF00",
    )
    document.records.append(Line(text=r"{\k100}{\k0}A", start_time=0, end_time=2000))
    original = document.dumps()
    scene = preset(document, pulse="char")
    span = scene.lines[0].query("character")[0].timing[0]
    assert span.start == span.end == 1
    result = scene.ass.compile()
    before = rasterize(result.document.dumps(), 500, (96, 64)).rgba
    after = rasterize(result.document.dumps(), 1500, (96, 64)).rgba
    assert max(before[3::4]) == pytest.approx(63, abs=1)
    assert max(after[3::4]) == pytest.approx(127, abs=1)
    assert document.dumps() == original


def test_changing_style_selection_restores_unselected_source_and_preserves_other_events():
    style = Style(fontname="DejaVu Sans", fontsize=20, shadow=0, outline=0)
    document = Document.create(
        width=320, height=180, styles=(style, replace(style, name="Other"))
    )
    document.records.extend(
        (
            Line(text=r"{\k100}A", start_time=1000, end_time=2000),
            Line(text=r"{\k100}B", style="Other", start_time=3000, end_time=4000),
            Line(text="untimed caption", start_time=0, end_time=500),
        )
    )
    first = preset(document, styles=("Default",)).ass.compile().document
    second = preset(first, styles=("Other",)).ass.compile().document
    assert any(not line.comment and line.text == r"{\k100}A" for line in second.lines)
    assert any(
        not line.comment and line.text == "untimed caption" for line in second.lines
    )
    assert not any(
        not line.comment and line.text == r"{\k100}B" for line in second.lines
    )
    assert (
        preset(second, styles=("Other",)).ass.compile().document.dumps() == second.dumps()
    )


@pytest.mark.parametrize("alpha", [127, 255])
def test_preset_keeps_independent_shadow_alpha_in_both_outputs(alpha):
    document = Document.create(
        width=160, height=120,
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=0, shadow=18),),
    )
    document.styles["Default"].fields.update(
        PrimaryColour="&HC00000FF", SecondaryColour="&HC00000FF",
        BackColour=f"&H{alpha:02X}000000",
    )
    document.records.append(Line(text=r"{\k100}A", start_time=1000, end_time=2000))
    scene = preset(document, fade_in=0.2)
    compiled = scene.ass.compile().document
    assert all(
        rf"\4a&H{alpha:02X}&" in line.text for line in compiled.lines if not line.comment
    )
    rgba = rasterize(compiled.dumps(), 1999, (160, 120)).rgba
    shadow = max(a for r, a in zip(rgba[::4], rgba[3::4], strict=True) if r == 0)
    assert shadow == pytest.approx(255 - alpha, abs=1)
    assert max(a for r, a in zip(rgba[::4], rgba[3::4], strict=True) if r > 0) == pytest.approx(63, abs=1)

    planes = {
        (image[4], image[5] & 255)
        for draw in HookDrawResolver(scene).at(2 - 0.001)
        for image in draw.mask_planes
    }
    assert planes == ({(0, 192)} if alpha == 255 else {(0, 192), (2, alpha)})
