from copy import deepcopy

import pytest
from kara_templater import (
    Box,
    Document,
    LaidOutLine,
    LaidOutSegment,
    LaidOutUnit,
    Line,
    Record,
    Segment,
    Style,
    TemplateError,
    TextUnit,
    apply_templates,
)


def structured_document(*templates):
    segments = (Segment(1003, 1507, "a"), Segment(2011, 2509, "b"))
    unit = LaidOutUnit(
        TextUnit("字", segments),
        Box(100, 200, 80, 80),
        tuple(
            LaidOutSegment(s, 100 + i * 40, 140 + i * 40, Box(100 + i * 40, 160, 40, 40))
            for i, s in enumerate(segments)
        ),
    )
    layout = LaidOutLine(unit.box, (unit,))
    source = Line(text="字", style="K1", start_time=503, end_time=3000)
    document = Document(
        [Style(name="K1"), Style(name="K1-furigana", fontsize=20), *templates, source],
        Record(res_x=1920, res_y=1080, video_x_correct_factor=1),
    )
    return document, {len(templates) + 1: layout}


def template(effect, text):
    return Line(comment=True, style="K1", effect=effect, text=text)


def test_structured_multi_preserves_millisecond_intervals_without_remeasurement(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("structured templates must not remeasure or parse karaoke text")

    monkeypatch.setattr("kara_templater.engine.preprocess", unexpected)
    document, layouts = structured_document(template("template syl multi noblank", '!retime("syl")!$sstart,$send:'))
    before = deepcopy(document)
    result = apply_templates(document, layouts=layouts)
    events = [line for line in result.lines if line.effect == "fx"]
    assert [(line.start_time, line.end_time) for line in events] == [(1003, 1507), (2011, 2509)]
    assert [line.text for line in events] == ["500,1004:字", "1508,2006:字"]
    assert document == before
    assert result.lines[-3].comment


def test_structured_ruby_uses_supplied_geometry_and_style():
    document, layouts = structured_document(
        template("template furi", '!retime("syl")!{$sleft,$stop,$smiddle,$sbottom}')
    )
    events = [line for line in apply_templates(document, layouts=layouts).lines if line.effect == "fx"]
    assert [line.text for line in events] == ["{100,160,180,200}a", "{140,160,180,200}b"]
    assert all(line.style == "K1-furigana" for line in events)
    assert [(line.start_time, line.end_time) for line in events] == [(1003, 1507), (2011, 2509)]


def test_structured_template_errors_keep_event_context():
    document, layouts = structured_document(template("template syl", "$unknown"))
    with pytest.raises(TemplateError, match=r"Event 1 .*Unknown variable"):
        apply_templates(document, layouts=layouts)
    with pytest.raises(ValueError, match="premeasured"):
        apply_templates(document, layouts=layouts, video_size=(1920, 1080))


def test_structured_templates_obey_output_limit():
    document, layouts = structured_document(template("template syl multi noblank", ""))
    with pytest.raises(TemplateError, match="Output line limit"):
        apply_templates(document, layouts=layouts, max_output_lines=1)
