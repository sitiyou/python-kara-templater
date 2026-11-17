"""Local gradient strips follow scale and drift without sliding through glyphs."""

from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneBudget,
    SceneCompileError,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def node():
    return PathObject(
        id="glyph",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(24, 24),
        state=VisualState(position=Vec2(8, 8)),
        material=LinearGradient(
            axis="y",
            space="local",
            fill=ColorRamp(
                (
                    ColorStop(0, Color.hex("#FFFF00")),
                    ColorStop(24, Color.hex("#FF0088")),
                )
            ),
        ),
        clip=RectangleClip(
            0,
            0,
            24,
            24,
            space="local",
            deform=RectangleKeyframes(
                ((0, (0, 0, 0, 24)), (0.5, (0, 0, 24, 24)), (1, (0, 0, 24, 24)))
            ),
        ),
    ).animate(Tween(StatePatch(scale=Vec2(2, 2), position=Vec2(12, 4))), duration=1)


@pytest.mark.parametrize("native", (False, True))
def test_local_gradient_moves_with_scaled_shape(native):
    original = node()
    doc = Document.create(width=80, height=80)
    result = (
        Scene(doc)
        .add(original)
        .compile(native_tweens=native, budget=SceneBudget(fps=50))
    )
    assert result.objects[0].strategy == (
        "native-clip-bands" if native else "sampled-bands"
    )
    # Exact raster reference: independent solid paths, one transformed local strip each.
    for ms in (250, 750):
        time = ms / 1000
        state = original.at(time)
        front = min(24, 48 * time)
        reference = Scene(doc)
        assert isinstance(original.material, LinearGradient)
        for band in original.material.bands(0, 24, 0, state):
            a = state.transform.apply(Vec2(0, band.start))
            b = state.transform.apply(Vec2(front, band.end))
            # Native clips retain integer-coordinate rounding. The curve proof
            # allows subpixel edge error; choose width checks away from its edge.
            reference.add(
                replace(
                    original,
                    id=f"band{band.start}",
                    animations=(),
                    material=None,
                    state=replace(state, fill=band.fill, outline=band.outline),
                    clip=RectangleClip(round(a.x), round(a.y), round(b.x), round(b.y)),
                )
            )
        actual = rasterize(result.document.dumps(), ms, (80, 80)).rgba
        expected = rasterize(reference.compile().document.dumps(), ms, (80, 80)).rgba
        # Compare the interior gradient; edge rounding is covered by native clip tests.
        for y in range(8, 30):
            for x in range(14, 20):
                offset = (y * 80 + x) * 4
                assert actual[offset + 3] == expected[offset + 3]
                # Animated integer clip edges can choose a neighboring 1px band.
                # One ramp step is <= 11 encoded RGB levels in this small fixture.
                assert max(
                    abs(a - b)
                    for a, b in zip(
                        actual[offset : offset + 3],
                        expected[offset : offset + 3],
                        strict=True,
                    )
                ) <= (12 if native else 0)


@pytest.mark.parametrize("bad", ("screen", "inverse", "crossing"))
def test_local_gradient_rejects_unsupported_mask_contracts(bad):
    original = node()
    assert isinstance(original.clip, RectangleClip)
    if bad == "screen":
        mask = replace(original.clip, space="screen")
    elif bad == "inverse":
        mask = replace(original.clip, inverse=True)
    else:
        mask = replace(
            original.clip,
            deform=RectangleKeyframes(((0, (0, 0, 24, 24)), (1, (0, 0, 24, 32)))),
        )
    with pytest.raises(SceneCompileError, match="local gradient"):
        Scene(Document.create()).add(replace(original, clip=mask)).compile(
            native_tweens=True
        )


def test_local_gradient_combines_centered_scale_curves_and_one_drift():
    original = replace(node(), animations=())
    original = original.animate(
        Tween(StatePatch(scale=Vec2(1.1, 1.1))), at=0.1, duration=0.1
    )
    original = original.animate(
        Tween(StatePatch(scale=Vec2(1, 1))), at=0.2, duration=0.2
    )
    original = original.animate(
        Tween(StatePatch(position=Vec2(12, 4))), at=0.5, duration=0.5
    )
    original = original.animate(Tween(StatePatch(opacity=0)), at=0.6, duration=0.4)
    result = (
        Scene(Document.create(width=80, height=80))
        .add(original)
        .compile(native_tweens=True)
    )
    assert result.event_count == 24
    events = [line for line in result.document.lines if not line.comment]
    assert all(r"\move(8,8,12,4,500,1000)" in line.text for line in events)
    # At the return/hold boundary native geometry and the gradient must both be
    # back at their original location; later alpha reaches zero continuously.
    reference = (
        Scene(Document.create(width=80, height=80))
        .add(
            replace(
                original,
                animations=(),
                state=original.at(0.5),
                clip=RectangleClip(
                    0,
                    0,
                    24,
                    24,
                    space="local",
                    deform=RectangleKeyframes(((0, (0, 0, 24, 24)),)),
                ),
            )
        )
        .compile(native_tweens=True)
    )
    assert (
        rasterize(result.document.dumps(), 500, (80, 80)).rgba
        == rasterize(reference.document.dumps(), 500, (80, 80)).rgba
    )
    earlier = rasterize(result.document.dumps(), 750, (80, 80)).rgba[3::4]
    later = rasterize(result.document.dumps(), 990, (80, 80)).rgba[3::4]
    assert sum(later) < sum(earlier) / 10


def test_local_gradient_does_not_silently_become_screen_space_in_coverage():
    from kara_templater import Coverage, ObjectGroup

    original = replace(node(), animations=())
    group = ObjectGroup(
        id="covered",
        lifetime=original.lifetime,
        children=(original,),
        coverage=Coverage(),
    )
    with pytest.raises(SceneCompileError, match="local gradients"):
        Scene(Document.create(width=80, height=80)).add(group).compile()
