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
    build_lyric_scene,
    linear_rate,
)


def squared(progress: float) -> float:
    return progress * progress


@dataclass(frozen=True)
class Accent:
    peak: float = 1.2
    rise: Callable[[float], float] = squared
    fall: Callable[[float], float] = squared

    def sequence(self, timing: float) -> AnimationSequence:
        attack = min(0.1, timing)
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
            .wait(timing - attack)
            .play(Tween(StatePatch(scale=Vec2(1, 1)), self.fall), duration=0.2)
            .animation
        )

    def __call__(self, timing: LyricAnimationContext) -> AnimationSequence:
        return self.sequence(timing.duration)


class LinearRelease(Accent):
    def sequence(self, timing: float) -> AnimationSequence:
        return Accent.sequence(replace(self, fall=linear_rate), timing)


@pytest.mark.parametrize("timing", (0, 0.03, 1.0))
def test_reusable_factory_extends_layout_and_matches_direct_animation(timing):
    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(
        Line(
            text=rf"{{\k{round(timing * 100)}}}A|a",
            start_time=1000,
            end_time=1000 + max(10, round(timing * 1000)),
        )
    )
    original = source.dumps()
    accent = Accent()
    config = Track(
        id="lyrics",
        preview=0,
        tail=0,
        effects=(LyricRule("syllable", "timing", accent),),
    )
    first = build_lyric_scene(source, tracks=(config,))
    second = build_lyric_scene(source, tracks=(config,))
    target = first.lines[0].children[0]
    assert target is not second.lines[0].children[0]
    assert first.plans[0].layout_request.required_display.end == pytest.approx(1 + timing + 0.2)
    direct = TextObject(
        id="direct", text="A", lifetime=Lifetime(1, 1 + timing + 0.2)
    ).animate(accent.sequence(timing), duration=timing + 0.2)
    attack = min(0.1, timing)
    for time, expected in (
        (1 + timing + 0.1, 1.15),
        (1 + attack / 2, 1.05 if attack else 1.2),
        (1 + timing, 1.2),
        (1 + timing + 0.2, 1),
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


def test_zero_timing_without_authored_duration_keeps_base_drawing():
    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(Line(text=r"{\k0}A", start_time=1000, end_time=1010))
    scene = build_lyric_scene(
        source,
        tracks=(
            Track(
                id="zero",
                preview=0,
                tail=0,
                effects=(
                    LyricRule(
                        "syllable", "timing", Tween(StatePatch(scale=Vec2(2, 2)))
                    ),
                ),
            ),
        ),
    )
    target = scene.lines[0].children[0]
    assert target.animations == ()
    assert target.at(1).scale == Vec2(1, 1)
    assert scene.lines[0].query("syllable")[0].timing[0].start == 1
    assert scene.lines[0].query("syllable")[0].timing[0].end == 1
    assert scene.ass.compile().event_count > 0
