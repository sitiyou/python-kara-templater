"""Combined author example: source ownership, repeated ruby pulses and references."""

from dataclasses import replace

import pytest

from examples.scene_bilingual import build
from kara_templater import PINK, ObjectGroup, Vec2


def test_repeated_singing_keeps_body_and_ruby_together():
    scene = build()
    top = next(
        node
        for node in scene.objects
        if isinstance(node, ObjectGroup) and node.id == "top"
    )
    assert isinstance(top, ObjectGroup)
    unit = top.children[0]
    assert isinstance(unit, ObjectGroup)
    assert {child.origin.effect for child in unit.children if child.origin} == {
        "document lyric body",
        "document ruby",
    }
    for time in (2.5, 1.3, 2.5):
        assert unit.at(time).scale.x == pytest.approx(1.1)
        assert all(child.at(time).fill == PINK for child in unit.children)
    for time in (0.5, 1.8, 2.9):
        assert unit.at(time).scale == Vec2(1, 1)
    bottom = next(node for node in scene.objects if node.id == "bottom")
    assert isinstance(bottom, ObjectGroup)
    assert all(child.at(1.9).scale == Vec2(1, 1) for child in bottom.children)


def test_shared_decoration_uses_both_parents_and_independent_cue_stays_fixed():
    scene = build()
    before = scene.evaluator()
    shifted = build()
    shifted.objects = [
        replace(
            node,
            state=replace(node.state, position=node.state.position + Vec2(40, 20)),
            animations=(),
        )
        if isinstance(node, ObjectGroup) and node.id == "top"
        else node
        for node in shifted.objects
    ]
    after = shifted.evaluator()
    for time in (2.5, 0.5, 4.5):
        top = after.at("top-center", time).position
        bottom = after.at("bottom-center", time).position
        assert after.at("between-lines", time).position == top.lerp(bottom, 0.5)
        assert after.at("bottom-center", time) == before.at("bottom-center", time)
    cues = [node for node in scene.objects if "/cue:" in node.id]
    assert cues
    for cue in cues:
        assert after.at(cue.id, 0.5) == before.at(cue.id, 0.5)


def test_export_preserves_both_sources_and_consumes_markers():
    scene = build()
    source = scene.document.dumps()
    result = scene.compile()
    assert scene.document.dumps() == source
    comments = [line for line in result.document.lines if line.comment]
    assert len(comments) == 2
    assert any("kara:v1" in line.text for line in comments)
    assert all(
        "kara:v1" not in line.text for line in result.document.lines if not line.comment
    )
    assert result.document.dumps() == scene.compile().document.dumps()
