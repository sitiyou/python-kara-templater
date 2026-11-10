"""Explicit sampling of user property functions on an absolute time grid."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace

from .timeline import DisplayWindow, Region, _finite


@dataclass(frozen=True)
class SampleContext:
    time_ms: int
    progress: float
    window: DisplayWindow
    target_id: str
    seed: int

    def noise(self, channel: str = "default", *, animated: bool = True) -> float:
        """Stable [0, 1) noise, shared by all visual layers of a target.

        No mutable RNG or Python process-dependent hash is involved. Set
        animated=False to obtain a stable per-target phase or amplitude.
        """
        key = repr(
            (self.seed, self.target_id, channel, self.time_ms if animated else None)
        ).encode()
        return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64


@dataclass(frozen=True)
class DynamicProperties:
    offset_x: float = 0
    offset_y: float = 0
    opacity: float = 1
    glow_blur: float | None = None
    glow_opacity: float | None = None

    def __post_init__(self):
        for name in ("offset_x", "offset_y", "opacity"):
            _finite(getattr(self, name), name)
        if not 0 <= self.opacity <= 1:
            raise ValueError("dynamic opacity must be in 0..1")
        if self.glow_opacity is not None:
            _finite(self.glow_opacity, "dynamic glow opacity")
            if not 0 <= self.glow_opacity <= 1:
                raise ValueError("dynamic glow opacity must be in 0..1")
        if self.glow_blur is not None:
            _finite(self.glow_blur, "dynamic glow blur")
            if self.glow_blur < 0:
                raise ValueError("dynamic glow blur cannot be negative")


@dataclass(frozen=True)
class SamplingSettings:
    step_ms: int = 40
    max_samples: int = 100000

    def __post_init__(self):
        if type(self.step_ms) is not int or self.step_ms < 10 or self.step_ms % 10:
            raise ValueError("sampling step must be a positive multiple of 10 ms")
        if type(self.max_samples) is not int or self.max_samples <= 0:
            raise ValueError("max_samples must be positive")


@dataclass(frozen=True)
class DynamicEffect:
    function: Callable[[SampleContext], DynamicProperties]
    sampling: SamplingSettings = SamplingSettings()
    seed: int = 0
    max_glow_blur: float | None = None

    def __post_init__(self):
        if not callable(self.function):
            raise TypeError("dynamic effect requires a property function")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if self.max_glow_blur is not None:
            _finite(self.max_glow_blur, "maximum glow blur")
            if self.max_glow_blur < 0:
                raise ValueError("maximum glow blur cannot be negative")


@dataclass(frozen=True)
class SamplingEstimate:
    target_samples: int
    layer_intervals: int
    estimated_events: int
    step_ms: int


@dataclass(frozen=True)
class SamplingPlan:
    """Prepared without calling user code. Inspect estimate before evaluate()."""

    effect: DynamicEffect
    # layer, output start/end, absolute sample timestamp
    intervals: tuple
    estimate: SamplingEstimate

    def evaluate(self):
        from .ass_output import OutputCapabilityError

        cache, result = {}, []
        previous_layer, previous_state = None, None
        for layer, start, end, time in self.intervals:
            target_id = layer.animation_id or layer.source_id
            key = (target_id, layer.window, time)
            if key not in cache:
                context = SampleContext(
                    time,
                    min(
                        1,
                        max(
                            0,
                            (time - layer.window.start_ms)
                            / (layer.window.end_ms - layer.window.start_ms),
                        ),
                    ),
                    layer.window,
                    target_id,
                    self.effect.seed,
                )
                try:
                    value = self.effect.function(context)
                    if not isinstance(value, DynamicProperties):
                        raise TypeError(
                            "property function must return DynamicProperties"
                        )
                    if value.glow_blur is not None and (
                        self.effect.max_glow_blur is None
                        or value.glow_blur > self.effect.max_glow_blur
                    ):
                        raise ValueError(
                            "glow_blur requires a declared max_glow_blur bound and cannot exceed it"
                        )
                except Exception as error:
                    raise OutputCapabilityError(
                        f"{target_id} at {time} ms: {error}",
                        origin=layer.origin,
                        time_ms=time,
                    ) from error
                cache[key] = value
            value = cache[key]
            paint = replace(layer.paint, opacity=layer.paint.opacity * value.opacity)
            if paint.glow is not None and value.glow_blur is not None:
                paint = replace(paint, glow=replace(paint.glow, blur=value.glow_blur))
            if paint.glow is not None and value.glow_opacity is not None:
                paint = replace(
                    paint, glow=replace(paint.glow, opacity=value.glow_opacity)
                )
            clips = (
                None
                if layer.clips is None
                else tuple(
                    replace(
                        span,
                        start=Region(
                            span.start.left + value.offset_x,
                            span.start.right + value.offset_x,
                        ),
                        end=Region(
                            span.end.left + value.offset_x,
                            span.end.right + value.offset_x,
                        ),
                    )
                    for span in layer.clips
                )
            )
            animations = tuple(
                replace(
                    a, pivot=(a.pivot[0] + value.offset_x, a.pivot[1] + value.offset_y)
                )
                for a in layer.animations
            )
            box = replace(
                layer.box,
                left=layer.box.left + value.offset_x,
                top=layer.box.top + value.offset_y,
            )
            state = (box, paint, clips, animations)
            # Only merge contiguous exposures of this exact source layer. All
            # callbacks still run; compare effective properties without a float
            # tolerance, so no motion or opacity changes are discarded.
            if (
                previous_layer is layer
                and previous_state == state
                and result[-1].active_window.end_ms == start
            ):
                result[-1] = replace(
                    result[-1],
                    active_window=DisplayWindow(result[-1].active_window.start_ms, end),
                )
                continue
            previous_layer, previous_state = layer, state
            result.append(
                replace(
                    layer,
                    source_id=f"{layer.source_id}/sample:{time}",
                    box=box,
                    paint=paint,
                    clips=clips,
                    animations=animations,
                    active_window=DisplayWindow(start, end),
                )
            )
        return tuple(result)


def prepare_sampling(
    layers, effect: DynamicEffect, *, max_events: int = 10000
) -> SamplingPlan:
    """Compute cost and reject budgets before any property function evaluation.

    Values are held constant over each absolute-grid bucket. Native fades, pulse
    timing and sweep interpolation retain global time within the bucket. The
    estimate counts bucket/pass exposures; native clip refinements can add more
    events and remain subject to the output compiler's actual event limit.
    """
    from .ass_output import OutputCapabilityError, quantize

    if type(max_events) is not int or max_events < 0:
        raise ValueError("max_events must be a nonnegative integer")
    intervals, keys, estimated = [], set(), 0
    step = effect.sampling.step_ms
    for layer in layers:
        if not layer.text.strip():
            continue
        start, end = quantize(layer.window.start_ms), quantize(layer.window.end_ms)
        if layer.active_window is not None:
            start = max(start, quantize(layer.active_window.start_ms))
            end = min(end, quantize(layer.active_window.end_ms))
        cursor = start
        while cursor < end:
            stop = min(end, (cursor // step + 1) * step)
            active = layer.clips is None or any(
                quantize(s.start_ms) < stop
                and quantize(s.end_ms) > cursor
                and (s.start.width or s.end.width)
                for s in layer.clips
            )
            if active:
                time = max(quantize(layer.window.start_ms), cursor // step * step)
                keys.add((layer.animation_id or layer.source_id, layer.window, time))
                estimated += layer.pass_count
                if len(keys) > effect.sampling.max_samples or estimated > max_events:
                    raise OutputCapabilityError(
                        f"{layer.source_id}: sampling preflight exceeds budget ({len(keys)} target samples, estimated {estimated} events)",
                        origin=layer.origin,
                        time_ms=time,
                    )
                intervals.append((layer, cursor, stop, time))
            cursor = stop
    return SamplingPlan(
        effect,
        tuple(intervals),
        SamplingEstimate(len(keys), len(intervals), estimated, step),
    )
