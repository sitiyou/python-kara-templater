"""Public coverage output: actual ASS replay, ownership and sampling contracts."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    CoveragePartition,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    Line,
    ObjectGroup,
    PathFunction,
    PathObject,
    RasterSettings,
    SceneBudget,
    ScopeOpacity,
    Vec2,
    VectorPath,
    VisualState,
    compile_coverage,
)
from kara_templater._raster import RasterCanvas, rasterize
from kara_templater._scene_coverage import SceneCoverageSampler

RESOLUTION = (64, 48)
BUDGET = SceneBudget(fps=10, max_active=5000, max_events=20000)
LIFETIME = Lifetime(0, 1)


def group(lifetime=LIFETIME):
    return ObjectGroup(
        id="word",
        lifetime=lifetime,
        children=(
            PathObject(
                id="body",
                lifetime=lifetime,
                path=VectorPath.rectangle(20, 15),
                state=VisualState(
                    position=Vec2(20, 15), fill=BLUE, outline=RED, border=1
                ),
            ),
        ),
    )


def document():
    return Document.create(width=64, height=48)


def test_standard_ass_matches_coverage_samples_and_merges_static_frames():
    source = document()
    before = source.dumps()
    root = group()
    glows = {"body": Glow(color=RED, blur=2, border=1)}
    result = compile_coverage(source, root, glows=glows, budget=BUDGET)
    assert source.dumps() == before
    assert result.sample_times == pytest.approx(tuple(0.05 + i / 10 for i in range(10)))
    assert all((e.start_time, e.end_time) == (0, 1000) for e in result.document.lines)
    sampler = SceneCoverageSampler(
        root,
        resolution=RESOLUTION,
        glows=glows,
        settings=RasterSettings(),
        budget=BUDGET,
    )
    positioned = sampler.frame(0.05)
    assert positioned is not None
    x, y, frame = positioned
    canvas = RasterCanvas(*RESOLUTION)
    canvas.over_frame(frame, x, y)
    expected = canvas.finish()
    for time in (50, 350, 950):
        assert rasterize(result.document.dumps(), time, RESOLUTION) == expected
    assert result.output.byte_count == len(result.document.dumps().encode()) + 3
    regenerated = compile_coverage(result.document, root, glows=glows, budget=BUDGET)
    assert regenerated.document.dumps() == result.document.dumps()


def test_preserves_document_records_and_replaces_only_selected_source():
    source = document()
    source.records.extend(
        (
            Line(text="remove", start_time=0, end_time=1000),
            Line(text="keep", start_time=0, end_time=1000),
        )
    )
    index = len(source.records) - 2
    before = source.dumps()
    result = compile_coverage(source, group(), replace_records=(index,), budget=BUDGET)
    assert source.dumps() == before
    assert "keep" in [line.text for line in result.document.lines]
    assert "remove" not in [
        line.text for line in result.document.lines if not line.comment
    ]
    assert result.document.meta.res_x == 64
    assert all(line.style in result.document.styles for line in result.document.lines)


def test_owner_and_leaf_discontinuities_split_grid_before_sampling():
    seen: list[float] = []
    root = group(Lifetime(2, 3))

    def glow(state, local):
        seen.append(local)
        return None

    result = compile_coverage(
        document(),
        root,
        budget=BUDGET,
        glows={
            "body": GlowFunction(glow, max_blur=0, max_border=0, breakpoints=(0.034,))
        },
        scope_opacities={
            "body": (ScopeOpacity("word", lambda t: 1, breakpoints=(0.07,)),)
        },
        partitions={
            "body": CoveragePartition(
                lambda state, t: (), 1, inside=False, breakpoints=(0.09,)
            )
        },
    )
    assert result.sample_times[:4] == pytest.approx((2.015, 2.05, 2.08, 2.095))
    assert seen == pytest.approx([t - 2 for t in result.sample_times])
    assert result.output.max_time_quantization == pytest.approx(0.004)


def test_frame_budget_precedes_callbacks_including_discontinuities():
    calls = []
    glow = GlowFunction(
        lambda state, t: calls.append(t), max_blur=0, max_border=0, breakpoints=(0.03,)
    )
    with pytest.raises(ValueError, match="boundary splitting"):
        compile_coverage(
            document(),
            group(),
            glows={"body": glow},
            budget=BUDGET,
            settings=RasterSettings(max_frames=10),
        )
    assert not calls


@pytest.mark.parametrize("kind", ("events", "characters", "bytes", "active"))
def test_output_budget_is_enforced(kind):
    budget = replace(BUDGET, **{"max_" + kind: 1}) if kind != "characters" else BUDGET
    settings = (
        RasterSettings(max_output_chars=1) if kind == "characters" else RasterSettings()
    )
    with pytest.raises(ValueError, match="budget"):
        compile_coverage(document(), group(), budget=budget, settings=settings)


def test_style_collision_and_invalid_source_index_do_not_execute_callbacks():
    source = compile_coverage(document(), group(), budget=BUDGET).document
    style = next(
        s for name, s in source.styles.items() if name.startswith("KaraCoverage_")
    )
    style.outline = 9
    calls = []
    glow = GlowFunction(lambda state, t: calls.append(t), max_blur=0, max_border=0)
    with pytest.raises(ValueError, match="collides"):
        compile_coverage(source, group(), glows={"body": glow}, budget=BUDGET)
    with pytest.raises(ValueError, match="replacement"):
        compile_coverage(
            document(), group(), replace_records=(0,), glows={"body": glow}
        )
    assert not calls


def test_dynamic_ass_replay_keeps_gaps_and_merges_unchanged_rectangles():
    root = group()
    fixed = replace(root.children[0], state=VisualState(position=Vec2(2, 2), fill=RED))
    blinking = PathObject(
        id="blink",
        lifetime=LIFETIME,
        path=VectorPath.rectangle(8, 8),
        state=VisualState(position=Vec2(40, 30), fill=BLUE),
        deform=PathFunction(
            lambda path, t: None if 0.2 <= t < 0.4 else path,
            max_points=4,
            breakpoints=(0.2, 0.4),
        ),
    )
    root = replace(root, children=(fixed, blinking))
    result = compile_coverage(document(), root, budget=BUDGET)
    sampler = SceneCoverageSampler(
        root, resolution=RESOLUTION, glows={}, settings=RasterSettings(), budget=BUDGET
    )
    # Seek in reverse order through both sides of the disappearance interval.
    for ms in (950, 400, 399, 200, 199, 0):
        positioned = sampler.frame((ms // 100 * 100 + 50) / 1000)
        assert positioned is not None
        x, y, image = positioned
        canvas = RasterCanvas(*RESOLUTION)
        canvas.over_frame(image, x, y)
        assert rasterize(result.document.dumps(), ms, RESOLUTION) == canvas.finish()
    lines = [line for line in result.document.lines if not line.comment]
    assert any((line.start_time, line.end_time) == (0, 1000) for line in lines)
    assert any((line.start_time, line.end_time) == (0, 200) for line in lines)
    assert any((line.start_time, line.end_time) == (400, 1000) for line in lines)
