"""Independent arithmetic for lyric parent, syllable and reading transforms."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Line,
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    ObjectGroup,
    Scene,
    StateFunction,
    Style,
    Vec2,
    layout_document_lyrics,
)


@pytest.mark.parametrize("follow", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
def test_body_and_ruby_compose_local_motion_under_one_line(follow: bool, reverse: bool):
    document = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    document.records.append(
        Line(text=r"{\k50}AB|ab{\k50}CD|cd", start_time=1000, end_time=2000)
    )
    layout = layout_document_lyrics(
        document, len(document.records) - 1, display=Lifetime(0, 3)
    )
    line = LyricLine.from_layout(layout)
    channels = frozenset(("position", "scale", "opacity"))
    root = StateFunction(
        lambda base, p: replace(
            base,
            position=base.position + Vec2(11, 0),
            scale=base.scale * 2,
            opacity=base.opacity * 0.5,
        ),
        channels,
    )
    unit = StateFunction(
        lambda base, p: replace(
            base,
            position=base.position + Vec2(7, 0),
            scale=base.scale * 3,
            opacity=base.opacity * 0.5,
        ),
        channels,
    )
    # Applying the body transform to each glyph in the syllable's coordinate
    # system preserves its common pivot while leaving ruby local state alone.
    body = StateFunction(
        lambda base, p: replace(
            base,
            position=base.position * 3 + Vec2(7, 0),
            scale=base.scale * 3,
            opacity=base.opacity * 0.5,
        ),
        channels,
    )
    reading = StateFunction(
        lambda base, p: replace(
            base,
            position=base.position + Vec2(5, 0),
            scale=base.scale * 4,
            opacity=base.opacity * 0.5,
        ),
        channels,
    )
    rules = (
        LyricRule("line", "enter", root, duration=3),
        LyricRule(
            "syllable" if follow else "character",
            "enter",
            unit if follow else body,
            duration=3,
        ),
        LyricRule("ruby", "enter", reading, duration=3),
    )
    animated = line.bind(*(reversed(rules) if reverse else rules))
    evaluator = Scene(document).add(animated).evaluator()
    ruby_ids = {target.node_id for target in line.query("ruby")}
    for time in (2.5, 0.5, 1.5):
        for group in line.children:
            assert isinstance(group, ObjectGroup)
            pivot = group.state.position
            for leaf in group.children:
                ruby = leaf.id in ruby_ids
                local = leaf.state.position
                if ruby:
                    local += Vec2(5, 0)
                    middle = pivot + (Vec2(7, 0) + local * 3 if follow else local)
                else:
                    middle = pivot + Vec2(7, 0) + local * 3
                expected = Vec2(11, 0) + middle * 2
                actual = evaluator.at(leaf.id, time)
                assert actual.position.x == pytest.approx(expected.x)
                assert actual.position.y == pytest.approx(expected.y)
                scale = 24 if ruby and follow else 8 if ruby else 6
                assert actual.scale == Vec2(scale, scale)
                assert actual.opacity == pytest.approx(
                    0.125 if ruby and follow else 0.25
                )
    assert line.children == LyricLine.from_layout(layout).children
    assert animated.targets == line.targets
    # Independent target declarations may be reordered without changing output.


def test_colored_ruby_glyphs_share_reading_pivot_and_sweep_clock():
    from kara_templater import BLUE, GREEN, RED, LyricSweep, ScalePulse

    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=0, shadow=0),)
    )
    document.records.append(
        Line(text=r"{\k100}AB|ABC", start_time=1000, end_time=2000)
    )
    original = document.dumps()
    line = LyricLine.from_layout(
        layout_document_lyrics(document, len(document.records) - 1, display=Lifetime(0, 3))
    )
    reading = line.layout.ruby[0].layout
    center = Vec2(reading.bounds.center, reading.bounds.middle)
    characters = {item.object.id: item for item in reading.characters}
    colors = dict(zip(characters, (RED, GREEN, BLUE), strict=True))

    def pulse(timing: LyricAnimationContext):
        # Convert the shared reading center to each glyph's local coordinates.
        character = characters[timing.target.node_id]
        return ScalePulse(pivot=center - character.object.state.position, peak=1.4)

    painted = LyricSweep(
        fill=lambda line, target: colors.get(target.node_id), width=0
    )(line)
    animated = painted.bind(LyricRule("ruby", "singing", pulse))
    scene = Scene(document).add(animated)
    evaluator = scene.evaluator()
    baseline = Scene(document).add(line).evaluator()
    group = animated.children[0]
    assert isinstance(group, ObjectGroup)
    nodes = {node.id: node for node in group.children}
    for time, factor in ((1.5, 1.4), (1.25, 1.2), (2.5, 1), (1.5, 1.4)):
        fronts = []
        for target in animated.query("ruby"):
            state = evaluator.at(target.node_id, time)
            before = baseline.at(target.node_id, time)
            expected = center + (before.position - center) * factor
            assert state.position.x == pytest.approx(expected.x)
            assert state.position.y == pytest.approx(expected.y)
            assert state.scale == Vec2(factor, factor)
            material = nodes[target.node_id].material
            assert material is not None
            assert material.breakpoints == (1, 2)
            bands = material.bands(-1000, 1000, time, state)
            if time < 2:
                # The boundary is the same across glyphs, although their colors differ.
                fronts.append(next(b.end for b in bands if b.fill == colors[target.node_id]))
            else:
                assert all(b.fill == colors[target.node_id] for b in bands)
        assert len(set(fronts)) <= 1
        for target in animated.query("character"):
            assert evaluator.at(target.node_id, time) == baseline.at(target.node_id, time)
    assert document.dumps() == original
