"""Reusable ordinary Python factories compose lyric envelopes on the shared clock."""

from collections.abc import Callable
from dataclasses import dataclass, replace

import pytest

from kara_templater import (
    AnimationSequence,
    Document,
    Lifetime,
    Line,
    LyricAnimationContext,
    LyricRule,
    StateFunction,
    StatePatch,
    Style,
    TextObject,
    Timeline,
    Track,
    Tween,
    Vec2,
    linear_rate,
    prepare_tracks,
)


def squared(progress: float) -> float:
    return progress * progress


@dataclass(frozen=True)
class Accent:
    peak: float = 1.2
    rise: Callable[[float], float] = squared
    fall: Callable[[float], float] = squared

    def sequence(self, singing: float) -> AnimationSequence:
        attack = min(0.1, singing)
        if not attack:
            release = Tween(StatePatch(scale=Vec2(1, 1)), self.fall)
            return (
                Timeline()
                .play(
                    StateFunction(
                        lambda base, p: release.sample(
                            replace(base, scale=Vec2(self.peak, self.peak)), p
                        ),
                        frozenset(("scale",)),
                    ),
                    duration=0.2,
                )
                .animation
            )
        return (
            Timeline()
            .play(
                Tween(StatePatch(scale=Vec2(self.peak, self.peak)), self.rise),
                duration=attack,
            )
            .wait(singing - attack)
            .play(Tween(StatePatch(scale=Vec2(1, 1)), self.fall), duration=0.2)
            .animation
        )

    def __call__(self, timing: LyricAnimationContext) -> AnimationSequence:
        return self.sequence(timing.duration)


class LinearRelease(Accent):
    def sequence(self, singing: float) -> AnimationSequence:
        return Accent.sequence(replace(self, fall=linear_rate), singing)


@pytest.mark.parametrize("singing", (0, 0.03, 1.0))
def test_reusable_factory_extends_layout_and_matches_direct_animation(singing):
    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(
        Line(
            text=rf"{{\k{round(singing * 100)}}}A|a",
            start_time=1000,
            end_time=1000 + max(10, round(singing * 1000)),
        )
    )
    original = source.dumps()
    accent = Accent()
    config = Track(
        id="lyrics",
        preview=0,
        tail=0,
        effects=(LyricRule("syllable", "singing", accent),),
    )
    first = prepare_tracks(source, tracks=(config,))
    second = prepare_tracks(source, tracks=(config,))
    target = first.lines[0].children[0]
    assert target is not second.lines[0].children[0]
    assert first.plans[0].input.required.end == pytest.approx(1 + singing + 0.2)
    direct = TextObject(
        id="direct", text="A", lifetime=Lifetime(1, 1 + singing + 0.2)
    ).animate(accent.sequence(singing), duration=singing + 0.2)
    attack = min(0.1, singing)
    for time, expected in (
        (1 + singing + 0.1, 1.15),
        (1 + attack / 2, 1.05 if attack else 1.2),
        (1 + singing, 1.2),
        (1 + singing + 0.2, 1),
    ):
        assert target.at(time).scale.x == pytest.approx(expected)
        assert target.at(time).scale.x == pytest.approx(direct.at(time).scale.x)
        assert target.at(time).scale.y == pytest.approx(direct.at(time).scale.y)
    assert source.dumps() == original
    assert isinstance(config.effects[0], LyricRule)
    assert config.effects[0].animation is accent


def test_plain_subclass_override_changes_only_the_authored_release_rate():
    base = TextObject(id="plain", text="A", lifetime=Lifetime(0, 2))
    squared_node = base.animate(Accent().sequence(1), duration=1.2)
    linear_node = base.animate(LinearRelease().sequence(1), duration=1.2)
    assert squared_node.at(0.05).scale == linear_node.at(0.05).scale
    assert squared_node.at(1.1).scale.x == pytest.approx(1.15)
    assert linear_node.at(1.1).scale.x == pytest.approx(1.1)
    assert not base.animations


def test_zero_singing_without_authored_duration_keeps_base_drawing():
    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(Line(text=r"{\k0}A", start_time=1000, end_time=1010))
    scene = prepare_tracks(
        source,
        tracks=(
            Track(
                id="zero",
                preview=0,
                tail=0,
                effects=(
                    LyricRule(
                        "syllable", "singing", Tween(StatePatch(scale=Vec2(2, 2)))
                    ),
                ),
            ),
        ),
    )
    target = scene.lines[0].children[0]
    assert target.animations == ()
    assert target.at(1).scale == Vec2(1, 1)
    assert scene.lines[0].query("syllable")[0].singing[0].start == 1
    assert scene.lines[0].query("syllable")[0].singing[0].end == 1
    assert scene.ass.compile().event_count > 0
