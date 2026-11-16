"""Completed highlight paint agrees with independently constructed static layers."""

import pytest

from kara_templater import Document
from kara_templater._raster import rasterize
from tools.validate_track_matrix import Case, generate


@pytest.mark.parametrize("coverage", (False, True))
def test_highlight_owns_italic_overhang_and_complete_glow_at_endpoints(
    tmp_path, coverage
):
    case = Case("edge", text="f", italic=True, radius=2, opacity=0.35)
    outputs = {}
    for mode in ("before", "sweep", "after"):
        path = tmp_path / f"{mode}.ass"
        generate(case, mode, path, raster=coverage, font_size=20)
        outputs[mode] = Document.load(path).dumps()
    for time, mode in ((500, "before"), (2500, "after")):
        actual = rasterize(outputs["sweep"], time, (640, 480)).rgba
        reference = rasterize(outputs[mode], time, (640, 480)).rgba
        assert any(actual[3::4])
        # Alpha and displayed RGB on both backgrounds; transparent RGB is undefined.
        for background in (0, 255):

            def composite(data, background):
                return [
                    round(
                        data[i + c] * data[i + 3] / 255
                        + background * (1 - data[i + 3] / 255)
                    )
                    for i in range(0, len(data), 4)
                    for c in range(3)
                ]

            assert (
                max(
                    abs(a - b)
                    for a, b in zip(
                        composite(actual, background),
                        composite(reference, background),
                        strict=True,
                    )
                )
                <= 1
            )
        assert (
            max(abs(a - b) for a, b in zip(actual[3::4], reference[3::4], strict=True))
            <= 1
        )
