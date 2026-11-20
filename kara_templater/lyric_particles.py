"""Measured karaoke emitters and reusable ordinary Scene particle factories."""

from dataclasses import dataclass, replace
from math import ceil, cos, pi, sin
from typing import Literal

from .appearance import _DEFAULT_SUNG
from .composition import Color
from .geometry import Contour, CubicSegment, Vec2, VectorPath, finite
from .lyric_line import LyricLine
from .particles import Emission, ParticleContext, ParticleFactory, emit_particles
from .path_animation import TrailPath
from .scene import Lifetime, PathObject, SceneObject
from .scene_animation import (
    StatePatch,
    TimeSpan,
    Transform,
    Tween,
    VisualState,
    smooth_rate,
)


@dataclass(frozen=True, kw_only=True)
class Sparkle:
    """A small four-point sparkle drifting upward while fading.

    A ParticleFactory usable with LyricParticles or emit_particles. size and
    travel are script pixels, duration is seconds; variation uses keyed seed
    channels. The ordinary linear Tween can compile to one ASS event per spark.
    """

    color: Color | None = None
    size: float = 3
    duration: float = 0.45
    travel: Vec2 = Vec2(12, -24)

    def __post_init__(self) -> None:
        finite(self.size, self.duration)
        if self.size <= 0 or self.duration <= 0:
            raise ValueError("sparkle size and duration must be positive")

    def __call__(self, context: ParticleContext) -> PathObject:
        """Create one seeded sparkle from the captured emitter position."""
        size = self.size * context.uniform("size", 0.65, 1.2)
        position = context.position + Vec2(0, context.uniform("spread", -8, 8))
        destination = position + Vec2(
            self.travel.x * context.uniform("wind", -1, 1),
            self.travel.y * context.uniform("rise", 0.65, 1.2),
        )
        path = VectorPath.polygon(
            Vec2(0, -size), Vec2(size * 0.2, -size * 0.2),
            Vec2(size, 0), Vec2(size * 0.2, size * 0.2),
            Vec2(0, size), Vec2(-size * 0.2, size * 0.2),
            Vec2(-size, 0), Vec2(-size * 0.2, -size * 0.2),
        )
        return PathObject(
            id=context.id, lifetime=Lifetime(context.birth, context.birth + self.duration),
            path=path, origin=context.origin, layer=1,
            state=VisualState(position=position, fill=self.color or context.color or _DEFAULT_SUNG, border=0, opacity=0.9),
        ).animate(Tween(StatePatch(position=destination, opacity=0)), duration=self.duration)


@dataclass(frozen=True, kw_only=True)
class Petal:
    """A seeded falling petal with curved drift, rotation and projected flutter.

    size/fall are script pixels, duration is seconds. Unlike Sparkle this uses
    a sampled custom Transform for flutter, so inspect compilation cost.
    """

    color: Color | None = None
    size: float = 4
    duration: float = 0.9
    fall: float = 40

    def __post_init__(self) -> None:
        finite(self.size, self.duration, self.fall)
        if self.size <= 0 or self.duration <= 0:
            raise ValueError("petal size and duration must be positive")

    def __call__(self, context: ParticleContext) -> PathObject:
        """Build an ordinary path object with deterministic custom motion."""
        size = self.size * context.uniform("size", 0.7, 1.3)
        wind = context.uniform("wind", -25, 25)
        spin = context.uniform("spin", -130, 130)
        phase = context.uniform("phase", 0, pi)
        path = VectorPath((Contour(Vec2(0, -size), (
            CubicSegment(Vec2(-2 * size, -size), Vec2(-size, size), Vec2(0, 1.5 * size)),
            CubicSegment(Vec2(size, size), Vec2(2 * size, -size), Vec2(0, -size)),
        )),))
        return PathObject(
            id=context.id, lifetime=Lifetime(context.birth, context.birth + self.duration),
            path=path, origin=context.origin, layer=1,
            state=VisualState(position=context.position, fill=self.color or context.color or _DEFAULT_SUNG, border=0,
                              rotation=context.uniform("angle", 0, 360)),
        ).animate(Transform(
            offset=lambda p: Vec2(wind * p + 10 * sin(pi * p), self.fall * p),
            rotation=lambda p: spin * p,
            scale=lambda p: Vec2(0.25 + 0.75 * abs(cos(2 * pi * p + phase)), 1),
            opacity=lambda p: 1 - smooth_rate(p),
        ), duration=self.duration)


@dataclass(frozen=True, kw_only=True)
class Ribbon:
    """A curved luminous strand whose tail follows its head along one path.

    duration is head travel time and lag is tail delay in seconds. width, travel
    and bend use local script pixels. Keyed variation changes travel/bend once
    at birth; geometry then uses the same TrailPath available to custom authors.
    ASS samples the changing stroke, so inspect output costs at high rates.
    """

    color: Color | None = None
    width: float = 1.5
    duration: float = 0.55
    lag: float = 0.18
    travel: Vec2 = Vec2(52, -18)
    bend: Vec2 = Vec2(16, -46)

    def __post_init__(self) -> None:
        finite(self.width, self.duration, self.lag)
        if min(self.width, self.duration, self.lag) <= 0:
            raise ValueError("ribbon width, duration and lag must be positive")
        if self.travel == Vec2() and self.bend == Vec2():
            raise ValueError("ribbon path must have nonzero length")

    def __call__(self, context: ParticleContext) -> PathObject:
        """Create one seeded path trail with an independent head/tail clock."""
        travel = self.travel * context.uniform("travel", 0.75, 1.25)
        bend = self.bend * context.uniform("bend", 0.65, 1.25)
        trail = TrailPath(Contour(Vec2(), (
            CubicSegment(bend, travel + bend * 0.5, travel),
        ), closed=False), duration=self.duration, lag=self.lag, width=self.width)
        return PathObject(
            id=context.id,
            lifetime=Lifetime(context.birth, context.birth + self.duration + self.lag),
            path=trail.full_path, deform=trail, origin=context.origin, layer=1,
            state=VisualState(position=context.position, fill=self.color or context.color or _DEFAULT_SUNG,
                              outline=self.color or context.color or _DEFAULT_SUNG, border=0.5, blur=0.6),
        )


@dataclass(frozen=True, kw_only=True)
class LyricParticles:
    """Emit particles at the singing front or throughout the measured lyric line.

    placement="front" uses each singing segment. placement="line" scatters
    particles across the body bounds from the original preview start through the
    last positive singing end, including unsung text and pauses. Its rate is per
    whole line, not per character or segment. Empty/zero-only lines emit nothing.
    Copy delays shift both schedules; later visual tails never extend emission.
    Line placement uses stable named random channels and captures a fixed point.

    color overrides the emission tint. Catalog or Track ink supplies the default;
    without one the emitter reads the source run. A factory color overrides it.
    rate is particles per second per singing segment in front mode; duration comes from the
    particle factory. Repeated segments restart the front. Zero-length segments
    emit nothing. Particle births are rounded to the ASS 10 ms grid; source
    singing clocks are unchanged. Position is captured in line-local layout coordinates at birth;
    line transforms apply to particles, independent character motion does not
    retarget already emitted particles. Use a custom factory for different paths,
    shapes, animation and lifetimes through the existing ParticleContext protocol.
    """

    factory: ParticleFactory = Sparkle()
    rate: float = 12
    seed: int = 0
    id: str = "particles"
    max_particles: int = 256
    placement: Literal["front", "line"] = "front"
    color: Color | None = None

    def __post_init__(self) -> None:
        finite(self.rate)
        if self.placement not in ("front", "line"):
            raise ValueError("particle placement must be front or line")
        if self.rate <= 0 or type(self.seed) is not int or not self.id:
            raise ValueError("lyric particles need positive rate, integer seed and id")
        if type(self.max_particles) is not int or self.max_particles < 1:
            raise ValueError("max_particles must be a positive integer")

    def __call__(self, line: LyricLine) -> LyricLine:
        """Preflight all emissions, then construct visuals and reserve their tails."""
        if line.coverage is not None:
            raise ValueError("lyric particles require ordinary clip-mode visuals")
        plans = []
        total = 0
        if self.placement == "line":
            target = line.query("line")[0]
            spans = [span for span in target.singing if span.end > span.start]
            box = line.layout.body.bounds
            if not spans or not line.layout.lyrics.body.text.strip() or box.width <= 0:
                return line
            start = line.time_origin
            duration = max(span.end for span in spans) + target.delay - start
            if duration <= 0:
                return line
            if duration * self.rate > self.max_particles:
                raise ValueError("lyric particle budget exceeded before factory execution")
            count = ceil(round(duration * self.rate, 10))
            plans.append((0, 0, start, duration, count, box))
        else:
            units = ((index, unit) for index, unit in enumerate(line.layout.lyrics.units)
                     if unit.start != unit.end)
            for (unit_index, unit), target in zip(units, line.query("syllable"), strict=True):
                if not line.layout.lyrics.body.text[unit.start:unit.end].strip():
                    continue
                box = line.layout.body.range_bounds(unit.start, unit.end)
                for segment_index, segment in enumerate(unit.segments):
                    span = segment.singing
                    duration = span.end - span.start
                    if duration <= 0 or box.width <= 0:
                        continue
                    if duration * self.rate > self.max_particles - total:
                        raise ValueError("lyric particle budget exceeded before factory execution")
                    count = ceil(round(duration * self.rate, 10))
                    total += count
                    if total > self.max_particles:
                        raise ValueError("lyric particle budget exceeded before factory execution")
                    plans.append((unit_index, segment_index, span.start + target.delay, duration, count, box))

        generated = []
        for unit, segment, start, duration, count, box in plans:
            def emitter(time: float, start: float = start, duration: float = duration,
                        left: float = box.left, width: float = box.width,
                        middle: float = box.middle) -> Vec2:
                return Vec2(left + width * min(1, max(0, (time - start) / duration)), middle)

            offset = 0 if self.placement == "line" else line.layout.lyrics.units[unit].start
            source_color = next((r.appearance.primary for r in line.layout.body.source.runs
                                 if r.start <= offset < r.end), _DEFAULT_SUNG)

            def factory(context: ParticleContext, left: float = box.left,
                        right: float = box.right, top: float = box.top,
                        bottom: float = box.top + box.height, source_color: Color = source_color) -> SceneObject:
                if self.placement == "line":
                    context = replace(context, position=Vec2(
                        context.uniform("placement:x", left, right),
                        context.uniform("placement:y", top, bottom),
                    ), emitter=None)
                return self.factory(replace(context, color=self.color or source_color))

            generated.extend(emit_particles(
                (Emission(str(index), round(start + index / self.rate, 2)) for index in range(count)),
                factory, seed=self.seed, emitter=emitter, origin=line.origin,
                id=f"{line.id}/{self.id}:{unit}:{segment}", max_particles=self.max_particles,
            ))
        if not generated:
            return line
        names = {node.id for node in line.children}
        if any(node.id in names for node in generated):
            raise ValueError("duplicate lyric particle id")
        windows = tuple(TimeSpan(node.lifetime.start, node.lifetime.end) for node in generated)
        result = line.with_display(Lifetime(
            min(line.lifetime.start, *(span.start for span in windows)),
            max(line.lifetime.end, *(span.end for span in windows)),
        ))
        return replace(result, children=(*result.children, *generated),
                       required_display=(*result.required_display, *windows))
