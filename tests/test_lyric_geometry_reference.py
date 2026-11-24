"""Compiled lyric geometry compared with independent whole-text ASS rendering."""


import pytest

from kara_templater import (
    Document,
    LayoutCapabilityError,
    Line,
    LyricLine,
    SceneBudget,
    Track,
    prepare_tracks,
)

SIZE = (160, 100)
BUDGET = SceneBudget(max_events=100_000, max_active=20_000)


@pytest.mark.parametrize("field,value", (("Angle", "10"), ("BorderStyle", "3")))
def test_unsupported_source_geometry_fails_before_visual_factory(field, value):
    source = Document.create(width=160, height=100)
    source.styles["Default"].fields[field] = value
    source.records.append(Line(text=r"{\k20}A", start_time=0, end_time=400))
    original = source.dumps()
    calls = []

    def factory(line: LyricLine) -> LyricLine:
        calls.append(line)
        return line

    with pytest.raises(
        LayoutCapabilityError, match="border style 1 and zero style angle"
    ):
        prepare_tracks(source, tracks=(Track(id="invalid", effects=(factory,)),))
    assert not calls
    assert source.dumps() == original
