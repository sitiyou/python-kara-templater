"""Layered karaoke effects use common hierarchy, timing and paint strategies."""

from pathlib import Path

import pytest

from examples.layered_glow import CURVE, build, highlights
from kara_templater import Document, ObjectGroup

SOURCE = Path(__file__).parent / "fixtures/layered_glow.ass"


def test_glow_preserves_lyric_timing_and_composes_line_fade_with_syllable_pulse():
    document = Document.load(SOURCE)
    original = document.dumps()
    scene = build(document)
    evaluator = scene.evaluator()
    line = scene.lines[0]
    target = line.query("syllable")[0]
    for time, scale in ((2.78, 1.05), (1.08, 1.1), (2.9, 1), (1, 1)):
        assert evaluator.at(target.node_id, time).scale.x == pytest.approx(scale)
    assert evaluator.at(target.node_id, 0.4).opacity == pytest.approx(0.5)
    assert evaluator.at(target.node_id, 3.9).opacity == pytest.approx(0.5)
    assert (target.singing[0].start, target.singing[0].end) == (1, 2.7)
    lead = scene.lines[2]
    assert evaluator.at(lead.query("syllable")[0].node_id, 1.08).scale.x == 1
    sweep = highlights(line)[0].passes[0]
    assert sweep.front(1.3) == pytest.approx(
        sweep.region.left + 0.3 * sweep.region.width
    )
    assert sweep.rate(0.5) == CURVE.at(0.5)
    assert highlights(lead)[0].passes[0].rate(0.5) == 0.5
    assert document.dumps() == original


def test_body_and_ruby_glow_geometry_follows_shared_target_hierarchy():
    scene = build(Document.load(SOURCE))
    line = scene.lines[0]
    nodes = {}

    def collect(node):
        nodes[node.id] = node
        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child)

    collect(line)
    for role, border in (("character", 10), ("ruby", 6)):
        target = line.query(role)[0]
        halos = [
            nodes[identity]
            for identity in target.aliases
            if nodes[identity].state.blur == 10
        ]
        assert len(halos) == 2
        assert all(
            node.state.border == border and node.state.opacity == 0.8 for node in halos
        )
        assert all(
            node.state.position == nodes[target.node_id].state.position
            for node in halos
        )
