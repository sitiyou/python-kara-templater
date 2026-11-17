"""Pre-blur lyric ownership compared with independent Pillow Gaussian planes."""

from dataclasses import replace
from math import floor, log, sqrt
from typing import Literal

import pytest
from PIL import Image, ImageChops, ImageFilter

from kara_templater import (
    BLUE,
    RED,
    Document,
    Glow,
    GlowFunction,
    Highlight,
    HighlightPass,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    ObjectGroup,
    Region,
    Scene,
    SceneBudget,
    StateFunction,
    StatePatch,
    Style,
    TimeSpan,
    Vec2,
    layout_document_lyrics,
)
from kara_templater._raster import rasterize

SIZE = (128, 96)


def attenuate(image: Image.Image, opacity: float) -> Image.Image:
    result = image.copy()
    result.putalpha(
        image.getchannel("A").point(lambda value: floor(value * opacity + 0.5))
    )
    return result


@pytest.mark.parametrize("after_opacity", (0, 0.25, 0.75, 1))
@pytest.mark.parametrize("scope", ("line", "syllable"))
def test_sweep_materials_match_independent_gaussian_reference(
    after_opacity: float, scope: Literal["line", "syllable"]
):
    source = Document.create(
        width=128,
        height=96,
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=0, shadow=0),),
    )
    source.records.append(Line(text=r"{\k10}A", start_time=100, end_time=200))
    layout = layout_document_lyrics(
        source, len(source.records) - 1, display=Lifetime(0, 0.3)
    )
    line = LyricLine.from_layout(layout)
    box = layout.body.bounds
    # Before paint has component opacity .75; the highlight replaces that value.
    group = line.children[0]
    assert isinstance(group, ObjectGroup)
    line = replace(
        line,
        children=(
            replace(
                group,
                children=tuple(
                    replace(child, state=replace(child.state, opacity=0.75))
                    for child in group.children
                ),
            ),
        ),
    )
    before_glow = GlowFunction(
        lambda state, t: Glow(RED, blur=2 * state.scale.x, opacity=0.8),
        max_blur=2.4,
        max_border=0,
    )
    after_glow = GlowFunction(
        lambda state, t: Glow(BLUE, blur=6 * state.scale.x, opacity=0.8),
        max_blur=7.2,
        max_border=0,
    )
    line = LyricHighlights(
        highlights=(
            Highlight(
                "sung",
                0,
                (HighlightPass(TimeSpan(0.1, 0.2), Region(box.left, box.right)),),
                StatePatch(fill=BLUE, opacity=after_opacity),
                glow=after_glow,
            ),
        ),
        glow=before_glow,
        strategy="coverage",
    )(line)
    line = line.bind(
        LyricRule(
            scope,
            "enter",
            StateFunction(
                lambda base, p: replace(
                    base,
                    scale=Vec2(1 + 0.2 * p, 1 + 0.2 * p),
                    position=base.position + Vec2(30 + 10 * p, 25),
                    opacity=0.6,
                ),
                frozenset(("position", "scale", "opacity")),
            ),
            duration=0.3,
        )
    )
    budget = SceneBudget(fps=50, max_events=100_000, max_active=10_000)
    output = (
        Scene(Document.create(width=128, height=96)).add(line).compile(budget=budget)
    )
    # Compile once; seek in a deliberately nonchronological order.
    for time in (210, 110, 150):
        assert time / 1000 == pytest.approx(
            min(output.objects[0].sample_times, key=lambda t: abs(t - time / 1000))
        )
        actual = Image.frombytes(
            "RGBA", SIZE, rasterize(output.document.dumps(), time, SIZE).rgba
        )
        scale, dx = 1 + 0.2 * time / 300, 30 + 10 * time / 300
        obj = layout.body.characters[0].object
        pivot = Vec2() if scope == "line" else Vec2(box.center, box.middle)
        point = pivot + (obj.state.position - pivot) * scale + Vec2(dx, 25)
        reference = Document.create(width=128, height=96)
        reference.records.append(
            Line(
                text=rf"{{\an7\pos({point.x},{point.y})\fn{obj.font}\fs{obj.font_size}\fscx{scale * 100}\fscy{scale * 100}\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}A",
                start_time=0,
                end_time=300,
            )
        )
        mask = Image.frombytes(
            "RGBA", SIZE, rasterize(reference.dumps(), time, SIZE).rgba
        ).getchannel("A")
        front = (
            pivot.x + (box.left + box.width * (time - 100) / 100 - pivot.x) * scale + dx
        )
        selection = Image.frombytes(
            "L",
            SIZE,
            bytes(
                floor(255 * (1 if time >= 200 else max(0, min(1, front - x))) + 0.5)
                for x in range(SIZE[0])
            )
            * SIZE[1],
        )
        sung = ImageChops.multiply(mask, selection)
        unsung = ImageChops.subtract(mask, sung)
        # Red and blue planes are premultiplied; disjoint material coverage is
        # filtered before the two contributions are added, then alpha is applied
        # after filling the letter and composing its glow.
        red = unsung.point(lambda v: floor(v * 0.8 + 0.5)).filter(
            ImageFilter.GaussianBlur(2 * scale * 2 / sqrt(log(256)))
        )
        blue = sung.point(lambda v: floor(v * 0.8 + 0.5)).filter(
            ImageFilter.GaussianBlur(6 * scale * 2 / sqrt(log(256)))
        )
        pixels = []
        for r, b, a, u in zip(
            red.tobytes(), blue.tobytes(), mask.tobytes(), unsung.tobytes(), strict=True
        ):
            # The unweighted fill occludes its own glow before component opacity.
            # Different material weights travel with their pre-blur contributions.
            normalize = max(1, (r + b) / 255)
            glow_r = r * 0.75 / normalize * (1 - a / 255)
            glow_b = b * after_opacity / normalize * (1 - a / 255)
            fill_u, fill_s = u * 0.75, (a - u) * after_opacity
            alpha = glow_r + glow_b + fill_u + fill_s
            pixels.extend(
                (
                    min(255, round(255 * (glow_r + fill_u) / alpha)),
                    min(255, round(255 * fill_u / alpha)),
                    min(255, round(255 * (glow_b + fill_u + fill_s) / alpha)),
                    min(255, round(alpha)),
                )
                if alpha
                else (0, 0, 0, 0)
            )
        expected = attenuate(Image.frombytes("RGBA", SIZE, bytes(pixels)), 0.6)
        for background in ("black", "white"):
            backdrop = Image.new("RGBA", SIZE, background)
            a = Image.alpha_composite(backdrop, actual).convert("RGB")
            b = Image.alpha_composite(backdrop, expected).convert("RGB")
            assert max(ImageChops.difference(a, b).tobytes()) <= 4
