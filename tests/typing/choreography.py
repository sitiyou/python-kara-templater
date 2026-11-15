"""Both animation authoring forms preserve concrete context and return types."""

from typing import assert_type

from kara_templater import (
    Animation,
    AnimationContext,
    AnimationTarget,
    Composition,
    Display,
    On,
    ScaleTo,
    Timeline,
    TimeSpan,
    Transform,
)


class Pulse(Animation):
    def sample(self, t: float, context: AnimationContext) -> Transform:
        assert_type(context.duration, float)
        assert_type(context.initial, Transform)
        assert_type(context.target, AnimationTarget)
        return Transform(scale=1 + 0.1 * t / context.duration)


class Accent(Composition):
    def compose(self, timeline: Timeline, context: AnimationContext) -> None:
        assert_type(context.syllable, TimeSpan)
        assert_type(context.next_syllable, TimeSpan | None)
        timeline.play(ScaleTo(1.1), during=context.syllable.interval)
        following = context.next_syllable
        if following is not None:
            timeline.play(ScaleTo(1), during=following.interval)


def contracts(context: AnimationContext, timeline: Timeline) -> None:
    assert_type(Pulse().sample(0.1, context), Transform)
    assert_type(Accent().sample(0.1, context), Transform)
    Animation(lambda t, ctx: Transform(scale=1 + t), duration=0.3)
    On(Display.Start, ScaleTo(1.1, duration=0.3))
    timeline.play(Pulse(), Accent(), at=0.5)
    timeline.play(ScaleTo("large"))  # ty: ignore[invalid-argument-type]
    timeline.play("pulse")  # ty: ignore[invalid-argument-type]
    timeline.play(Pulse(), during=(0, 1))  # ty: ignore[invalid-argument-type]
    Animation(lambda t, ctx: "scale")  # ty: ignore[invalid-argument-type]
    Transform(scale="large")  # ty: ignore[invalid-argument-type]
