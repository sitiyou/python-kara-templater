"""Lyric binding produces the same clips and hierarchy as direct authoring."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    FadeIn,
    FadeOut,
    Jump,
    Lifetime,
    Line,
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    Scene,
    StateFunction,
    Style,
    TextObject,
    Vec2,
    layout_document_lyrics,
)


def subject(text=r"{\k50}AB|ab{\k50}CD|cd"):
    document = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    document.records.append(Line(text=text, start_time=1000, end_time=2000))
    layout = layout_document_lyrics(
        document, len(document.records) - 1, id="main:0", display=Lifetime(0, 3)
    )
    return document, LyricLine.from_layout(layout, tags=frozenset(("main",)))


def test_whole_line_fade_and_syllable_jump_compose_without_manual_target_loop():
    doc, original = subject()
    fade = FadeIn()
    line = original.bind(
        LyricRule("line", "enter", fade, duration=0.2),
        LyricRule("line", "exit", FadeOut(), duration=0.2),
        LyricRule("syllable", "singing", Jump(height=10)),
    )
    assert line.animations[0].animation is fade
    assert line.at(0.1).opacity == pytest.approx(0.5)
    assert line.at(2.9).opacity == pytest.approx(0.5)
    original_scene = Scene(doc).add(original).evaluator()
    animated = Scene(doc).add(line)
    evaluator = animated.evaluator()
    character = line.query("character")[0].node_id
    ruby = line.query("ruby")[0].node_id
    for target in (character, ruby):
        assert evaluator.at(target, 1.25).position == (
            original_scene.at(target, 1.25).position + Vec2(0, -10)
        )
        assert evaluator.at(target, 0.1).opacity == pytest.approx(0.5)
    assert all(not child.animations for child in original.children)
    assert line.layout.lyrics == original.layout.lyrics


def test_custom_animation_is_identical_on_direct_object_and_semantic_line():
    _, line = subject()
    animation = StateFunction(
        lambda base, p: replace(base, rotation=base.rotation + 30 * p),
        frozenset(("rotation",)),
    )
    direct = TextObject(id="plain", text="x", lifetime=line.lifetime).animate(
        animation, duration=0.5
    )
    bound = line.bind(LyricRule("line", "enter", animation, duration=0.5))
    for time in (0.5, 0.1, 0, 0.3):
        assert direct.at(time).rotation == bound.at(time).rotation
    assert bound.animations[0].animation is animation
    assert line.animate(animation, duration=0.5).animations == bound.animations


def test_repeated_segments_have_distinct_identity_and_original_clocks():
    _, line = subject(r"{\k25}AB|ab{\kt50\k25}#|cd")
    segments = line.query("segment")
    assert len(segments) == 2
    assert segments[0].id != segments[1].id
    assert segments[0].node_id == segments[1].node_id
    assert [(t.singing[0].start, t.singing[0].end) for t in segments] == [
        (1, 1.25),
        (1.5, 1.75),
    ]
    bound = line.bind(LyricRule("segment", "singing", Jump()))
    for time in (1.625, 1.125):
        assert bound.children[0].at(time).position.y == pytest.approx(
            line.children[0].state.position.y - 12
        )
    assert line.query("syllable")[0].singing[0].end == 1.75


def test_query_keeps_hierarchy_and_suppresses_descendant_double_transform():
    _, line = subject()
    before = line.children
    assert line.query("line", "character") == line.query("line")
    assert line.query("syllable", "ruby") == line.query("syllable")
    assert len(line.query("character")) == 4
    assert line.query("line", tags=frozenset(("missing",))) == ()
    assert line.children is before
    assert line.query(tags=frozenset(("main",))) == line.query("line")


def test_rule_errors_use_common_time_and_conflict_validation():
    _, line = subject()
    with pytest.raises(ValueError, match="explicit duration"):
        LyricRule("line", "enter", FadeIn())
    with pytest.raises(ValueError, match="overlapping"):
        line.bind(
            LyricRule("line", "enter", FadeIn(), duration=0.2),
            LyricRule("line", "enter", FadeOut(), duration=0.2),
        )
    with pytest.raises(ValueError, match="absolute time zero"):
        line.bind(LyricRule("line", "enter", FadeIn(), duration=0.2, offset=-0.1))
    assert not line.animations


def test_copying_a_parent_group_retargets_nested_lyric_metadata():
    from kara_templater import ObjectGroup

    doc, line = subject()
    parent = ObjectGroup(id="parent", lifetime=Lifetime(0, 3), children=(line,))
    copied = parent.copy(id="copy", delay=4)
    nested = copied.children[0]
    assert isinstance(nested, LyricLine)
    assert nested.query("line")[0].node_id == nested.id
    animated = nested.bind(LyricRule("syllable", "singing", Jump()))
    target = animated.query("character")[0].node_id
    baseline = Scene(doc).add(nested).evaluator().at(target, 5.25)
    actual = Scene(doc).add(animated).evaluator().at(target, 5.25)
    assert actual.position == baseline.position + Vec2(0, -12)
    assert nested.query("syllable")[0].singing == line.query("syllable")[0].singing


def test_explicit_target_collection_deduplicates_ancestors_without_reparenting():
    document, original = subject()
    root = original.query("line")[0]
    character = original.query("character")[0]
    bound = original.bind(
        LyricRule((character, root, character), "enter", FadeIn(), duration=0.2)
    )
    assert len(bound.animations) == 1
    assert all(not child.animations for child in bound.children)
    assert Scene(document).add(bound).evaluator().at(
        character.node_id, 0.1
    ).opacity == pytest.approx(0.5)
    assert not original.animations
    assert bound.targets == original.targets


def test_explicit_foreign_targets_fail_before_any_animation_factory():
    _, original = subject()
    foreign = original.copy(id="other").query("ruby")[0]
    calls = []

    def factory(timing: LyricAnimationContext):
        calls.append(timing.target.id)
        return Jump()

    with pytest.raises(ValueError, match="does not belong to line"):
        original.bind(
            LyricRule("character", "singing", factory),
            LyricRule(foreign, "singing", Jump()),
        )
    assert not calls
    with pytest.raises(ValueError, match="unknown lyric target role"):
        original.query("typo")


def test_empty_and_filtered_selections_skip_factories_but_explicit_ruby_binds():
    _, original = subject(r"{\k50}AB")
    calls = []

    def factory(timing: LyricAnimationContext):
        calls.append(timing.target.id)
        return Jump()

    original.bind(
        LyricRule("ruby", "singing", factory),
        LyricRule((), "singing", factory),
        LyricRule("character", "singing", factory, tags=frozenset(("other",))),
    )
    assert not calls
    _, with_ruby = subject()
    ruby = with_ruby.query("ruby")[0]
    bound = with_ruby.bind(
        LyricRule(ruby, "singing", factory, tags=frozenset(("main",)))
    )
    assert calls == [ruby.id]
    evaluator = Scene(Document.create()).add(bound).evaluator()
    baseline = Scene(Document.create()).add(with_ruby).evaluator()
    assert evaluator.at(ruby.node_id, 1.25).position == baseline.at(
        ruby.node_id, 1.25
    ).position + Vec2(0, -12)
    other = with_ruby.query("ruby")[1]
    assert (
        evaluator.at(other.node_id, 1.25).position
        == baseline.at(other.node_id, 1.25).position
    )


def test_reading_ranges_validate_bounds_and_preserve_combining_clusters():
    from kara_templater import LayoutCapabilityError

    document = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    document.records.append(
        Line(text="{\\k100}A|a\u0301b", start_time=1000, end_time=2000)
    )
    original = document.dumps()
    layout = layout_document_lyrics(document, len(document.records) - 1)
    reading = layout.ruby[0].layout
    assert [(c.start, c.end) for c in reading.characters] == [(0, 2), (2, 3)]
    assert reading.range_bounds(0, 2) == reading.characters[0].bounds
    for start, end in ((-1, 1), (0, 4), (2, 2)):
        with pytest.raises(ValueError, match="within the source"):
            reading.range_bounds(start, end)
    with pytest.raises(LayoutCapabilityError, match="cluster"):
        reading.range_bounds(0, 1)
    line = LyricLine.from_layout(layout)
    assert len(line.query("ruby")) == 2
    assert document.dumps() == original
