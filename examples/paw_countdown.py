"""Four paw prints above the lyric row, with one crisp cut per counted step."""

from dataclasses import replace

from kara_templater import (
    AnimationClip,
    CueContent,
    CueContext,
    CuePreset,
    SignalCue,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
)


def _paw() -> VectorPath:
    circle = VectorPath.circle(1)

    def oval(x: float, y: float, rx: float, ry: float) -> VectorPath:
        return circle.map(lambda point: Vec2(x + rx * point.x, y + ry * point.y))

    contours = []
    # Pad and toes in the unit square used by SignalCue.
    for x, y, rx, ry in (
        (0.50, 0.69, 0.34, 0.25),
        (0.13, 0.37, 0.10, 0.14),
        (0.37, 0.22, 0.11, 0.16),
        (0.63, 0.22, 0.11, 0.16),
        (0.87, 0.37, 0.10, 0.14),
    ):
        contours.extend(oval(x, y, rx, ry).contours)
    return VectorPath(tuple(contours))


def _count(context: CueContext) -> CueContent:
    lamps = SignalCue(shape=_paw(), direction="left_to_right", transition=0)(context)
    paws = []
    for lamp, start, end in zip(
        lamps.objects, context.steps[:-1], context.steps[1:], strict=True
    ):
        span = end - start
        middle = (start + end) / 2 - lamp.lifetime.start
        paws.append(
            replace(
                lamp,
                animations=(
                    AnimationClip(
                        middle - span / 16,
                        span / 16,
                        Tween(StatePatch(scale=Vec2(1.22, 0.84))),
                    ),
                    AnimationClip(
                        middle, span / 8, Tween(StatePatch(scale=Vec2(1, 1)))
                    ),
                ),
            )
        )
    return replace(lamps, objects=tuple(paws))


def paw_countdown(step_seconds: float) -> CuePreset:
    """Use the song's chosen step length, e.g. two beats at a fast tempo."""
    return CuePreset(
        factory=_count,
        steps=(0, 0.25, 0.5, 0.75, 1),
        duration=4 * step_seconds,
        line_edge="above",
    )
