"""Explicit continuous ASS interpolation, independent native reference and guards."""

from dataclasses import replace

import pytest
from PIL import Image, ImageChops

from kara_templater import (
    AnimationClip,
    Color,
    Document,
    Lifetime,
    Line,
    ObjectGroup,
    Scene,
    SceneBudget,
    StatePatch,
    Style,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    _metrics,
    smooth_rate,
)


def subject() -> TextObject:
    return TextObject(
        id="word",
        text="W",
        font_size=64,
        lifetime=Lifetime(0, 2),
        state=VisualState(position=Vec2(200, 180), opacity=0),
        animations=(
            AnimationClip(
                0.25,
                1,
                Tween(
                    StatePatch(
                        scale=Vec2(1.2, 1.1),
                        rotation=20,
                        opacity=1,
                        fill=Color(255, 128, 64),
                        outline=Color(64, 128, 255),
                        border=2,
                        blur=1,
                        shadow=Vec2(2, 3),
                    )
                ),
            ),
        ),
    )


def rgba(script: str, ms: int) -> Image.Image:
    canvas = Image.new("RGBA", (640, 360))
    for x, y, width, height, _, color, data in _metrics.rasterize(
        script, ms, 640, 360, 4_000_000, 10_000
    ):
        if not width or not height:
            continue
        alpha = 255 - (color & 255)
        mask = Image.frombytes("L", (width, height), data).point(
            [round(v * alpha / 255) for v in range(256)]
        )
        tile = Image.new(
            "RGBA",
            (width, height),
            tuple((color >> shift) & 255 for shift in (24, 16, 8)),
        )
        tile.putalpha(mask)
        canvas.alpha_composite(tile, (x, y))
    return canvas


def test_continuous_tween_matches_handwritten_ass_and_reduces_cost():
    scene = Scene(Document.create(width=640, height=360)).add(subject())
    sampled = scene.compile()
    native = scene.compile(native_tweens=True, budget=SceneBudget(max_events=1))
    assert native.event_count == native.estimated_events == 1
    assert sampled.event_count > 40
    assert native.objects[0].strategy == "native-tween"
    reference = Document.create(
        width=640,
        height=360,
        styles=(
            Style(fontname="DejaVu Sans", fontsize=64, align=7, outline=0, shadow=0),
        ),
    )
    reference.records.append(
        Line(
            start_time=0,
            end_time=2000,
            text=(
                r"{\an7\pos(200,180)\alpha&HFF&\t(250,1250,\fscx120\fscy110\frz-20"
                r"\alpha&H00&\1c&H4080FF&\2c&H4080FF&\3c&HFF8040&\bord2\blur1\xshad2\yshad3)}W"
            ),
        )
    )
    script = native.document.dumps()
    for ms in (0, 249, 250, 251, 499, 500, 750, 999, 1249, 1250, 1251, 1999, 2000):
        actual = rgba(script, ms)
        expected = rgba(reference.dumps(), ms)
        assert ImageChops.difference(actual, expected).getbbox(alpha_only=False) is None
    assert native.document.dumps() == scene.compile(native_tweens=True).document.dumps()


@pytest.mark.parametrize(
    "change",
    [
        "ease",
        "release",
        "position",
        "negative-scale",
        "skew",
        "fractional-birth",
        "parent",
    ],
)
def test_ineligible_tweens_remain_sampled(change: str):
    node = subject()
    clip = node.animations[0]
    if change == "ease":
        clip = replace(clip, animation=Tween(StatePatch(opacity=1), smooth_rate))
    elif change == "release":
        clip = replace(clip, hold=False)
    elif change == "position":
        clip = replace(
            clip, animation=Tween(StatePatch(position=Vec2(300, 200), opacity=1))
        )
    elif change == "negative-scale":
        clip = replace(clip, animation=Tween(StatePatch(scale=Vec2(-1, 1))))
    elif change == "skew":
        node = replace(node, state=replace(node.state, skew=Vec2(0.1, 0)))
    elif change == "fractional-birth":
        node = replace(node, lifetime=Lifetime(0.001, 2))
    node = replace(node, animations=(clip,))
    root = (
        ObjectGroup(
            id="parent",
            lifetime=Lifetime(0, 2),
            state=VisualState(opacity=0.5),
            children=(node,),
        )
        if change == "parent"
        else node
    )
    result = Scene(Document.create()).add(root).compile(native_tweens=True)
    assert result.objects[0].strategy.startswith("sampled")


def test_sequential_and_parallel_path_tweens_preserve_capture_and_birth_clock():
    from kara_templater import PathObject, VectorPath

    clips = (
        AnimationClip(0, 1, Tween(StatePatch(rotation=20))),
        AnimationClip(1.5, 1, Tween(StatePatch(rotation=-20))),
        AnimationClip(0.5, 1, Tween(StatePatch(opacity=1))),
        AnimationClip(2, 0.5, Tween(StatePatch(opacity=0.3))),
    )
    node = PathObject(
        id="tile",
        path=VectorPath.rectangle(60, 30),
        lifetime=Lifetime(1, 5),
        state=VisualState(position=Vec2(200, 180), opacity=0.2),
        animations=tuple(reversed(clips)),
    )
    scene = Scene(Document.create(width=640, height=360)).add(node)
    result = scene.compile(native_tweens=True, budget=SceneBudget(max_events=1))
    assert result.event_count == 1
    assert result.objects[0].strategy == "native-tween"
    reference = Document.create(
        width=640, height=360, styles=(Style(align=7, outline=0, shadow=0),)
    )
    reference.records.append(
        Line(
            start_time=1000,
            end_time=5000,
            text=(
                r"{\an7\pos(200,180)\p1\alpha&HCC&"
                r"\t(0,1000,\frz-20)\t(500,1500,\alpha&H00&)"
                r"\t(1500,2500,\frz20)\t(2000,2500,\alpha&HB2&)}"
                "m 0 0 l 60 0 l 60 30 l 0 30 l 0 0"
            ),
        )
    )
    script = result.document.dumps()
    # Reverse and repeat requests to catch accidental stateful evaluation.
    for ms in (
        3499,
        999,
        1000,
        1499,
        1500,
        1999,
        2000,
        2499,
        2500,
        2999,
        3000,
        3500,
        3501,
        4999,
        5000,
        1500,
    ):
        assert (
            ImageChops.difference(
                rgba(script, ms), rgba(reference.dumps(), ms)
            ).getbbox(alpha_only=False)
            is None
        )
        alphas = {
            color & 255
            for _, _, w, h, kind, color, _ in _metrics.rasterize(
                script, ms, 640, 360, 4_000_000, 10_000
            )
            if kind == 0 and w and h
        }
        if 1000 <= ms < 5000:
            expected = round((1 - node.at(ms / 1000).opacity) * 255)
            assert alphas and all(abs(alpha - expected) <= 1 for alpha in alphas)
        else:
            assert not alphas
