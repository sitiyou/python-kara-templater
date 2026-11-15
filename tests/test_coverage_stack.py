"""Analytical opacity ownership checks independent of glyph rasterization."""

import pytest

from kara_templater._coverage_stack import compose_stacks
from kara_templater._raster import RasterBudget, RasterFrame
from kara_templater.ass_output import OutputCapabilityError


def pixel(red, green, blue, alpha):
    return (0, 0, RasterFrame(1, 1, bytes((red, green, blue, alpha))))


def test_opacity_does_not_reveal_a_components_hidden_glow():
    glow = (pixel(255, 0, 0, 255), pixel(255, 0, 0, 128))
    fill = (pixel(0, 0, 255, 255), pixel(0, 0, 255, 64))
    result = compose_stacks((glow, fill), additive=False, budget=RasterBudget())
    assert result[1][2].rgba == bytes((0, 0, 255, 64))


def test_additive_saturation_uses_intrinsic_coverage_for_every_weight():
    red = (pixel(255, 0, 0, 255), pixel(255, 0, 0, 128))
    blue = (pixel(0, 0, 255, 255), pixel(0, 0, 255, 64))
    result = compose_stacks((red, blue), additive=True, budget=RasterBudget())
    assert result[0][2].rgba == bytes((128, 0, 128, 255))
    assert result[1][2].rgba == bytes((170, 0, 85, 96))


def test_parent_uses_completed_child_coverage_for_occlusion():
    # Completed children have intrinsic local alpha 128 and 64. Their parent
    # opacity is 0.5, so root-weighted red is attenuated by (1 - 64/255), not
    # (1 - 32/255). Applying opacity individually would expose excess red.
    red = (pixel(255, 0, 0, 128), pixel(255, 0, 0, 64))
    blue = (pixel(0, 0, 255, 64), pixel(0, 0, 255, 32))
    result = compose_stacks((red, blue), additive=False, budget=RasterBudget())
    assert result[1][2].rgba == bytes((153, 0, 102, 80))


def test_coverage_stack_budgets_and_geometry_are_checked():
    p = pixel(255, 0, 0, 128)
    with pytest.raises(OutputCapabilityError, match="coverage budget"):
        compose_stacks(((p,), (p,)), additive=False, budget=RasterBudget(max_images=1))
    with pytest.raises(ValueError, match="share geometry"):
        compose_stacks(((p, (1, 0, p[2])),), additive=False, budget=RasterBudget())
    with pytest.raises(ValueError, match="matching nonempty"):
        compose_stacks(((p,), (p, p)), additive=False, budget=RasterBudget())
