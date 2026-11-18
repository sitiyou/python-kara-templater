"""Singing paint fields using the common Scene material protocol."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import ceil
from typing import Literal

from .composition import Color
from .geometry import finite
from .lyric_line import LyricLine, LyricTarget
from .paint_fields import PaintBand, SoftSweep
from .scene import ObjectGroup, SceneObject
from .scene_animation import TimeSpan, VisualState
from .scene_text import PositionedText


@dataclass(frozen=True)
class _SingingSweep:
    left: float
    right: float
    intervals: tuple[tuple[float, float], ...]
    fill: Color | None
    outline: Color | None
    width: float
    outline_width: float
    step: int

    @property
    def axis(self) -> Literal["x"]:
        return "x"

    @property
    def max_bands(self) -> int:
        return ceil(max(self.width, self.outline_width) / self.step) + 4

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return tuple(sorted({t for interval in self.intervals for t in interval}))

    @property
    def active_intervals(self) -> tuple[TimeSpan, ...]:
        return tuple(
            TimeSpan(start, end) for start, end in self.intervals if end > start
        )

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        if base.rotation % 360 or base.skew.x or base.scale.x <= 0:
            raise ValueError(
                "lyric sweep requires a positive axis-aligned horizontal transform"
            )
        # Repeated singing restarts its own sweep; otherwise the completed state holds.
        interval = self.intervals[0]
        for candidate in self.intervals:
            if time >= candidate[0]:
                interval = candidate
        if interval[0] == interval[1]:
            sung = time >= interval[0]
            return (
                PaintBand(
                    start,
                    end,
                    self.fill if sung and self.fill is not None else base.fill,
                    self.outline if sung and self.outline is not None else base.outline,
                ),
            )
        return SoftSweep(
            left=base.position.x + self.left * base.scale.x,
            right=base.position.x + self.right * base.scale.x,
            start=interval[0],
            duration=interval[1] - interval[0],
            fill=None if self.fill is None else (base.fill, self.fill),
            outline=None if self.outline is None else (base.outline, self.outline),
            width=self.width,
            outline_width=self.outline_width,
            step=self.step,
        ).bands(start, end, time, base)


@dataclass(frozen=True, kw_only=True)
class LyricSweep:
    """Apply per-syllable singing sweeps to body and ruby, using Scene paint fields.

    Widths are soft-front widths in screen pixels; zero is a hard edge. Repeated
    singing restarts the sweep for the new interval. Zero-duration singing
    changes to the sung color at its exact start without reserving animation time. Translation and positive
    horizontal scaling follow the actual evaluated state; rotated/sheared fronts
    require an explicit custom material and raise instead of silently changing
    the effect. This is color replacement, not translucent overlay composition.
    Fill/outline may be factories receiving the measured line and semantic target;
    they resolve once per target when applying the sweep, not on every frame.
    A factory may return None to preserve that target's animated channel. If both
    channels are omitted, the target is left untouched, including its material.
    """

    fill: Color | Callable[[LyricLine, LyricTarget], Color | None] | None = None
    outline: Color | Callable[[LyricLine, LyricTarget], Color | None] | None = None
    width: float = 12
    outline_width: float | None = None
    step: int = 1

    def __post_init__(self) -> None:
        for color in (self.fill, self.outline):
            if (
                color is not None
                and not isinstance(color, Color)
                and not callable(color)
            ):
                raise TypeError("lyric sweep colors must be Color values or factories")
        finite(
            self.width, self.width if self.outline_width is None else self.outline_width
        )
        if (
            self.width < 0
            or (self.outline_width is not None and self.outline_width < 0)
            or type(self.step) is not int
            or self.step < 1
        ):
            raise ValueError("sweep needs nonnegative widths and positive integer step")
        if self.fill is None and self.outline is None:
            raise ValueError("sweep needs a sung fill or outline")

    def __call__(self, line: LyricLine) -> LyricLine:
        """Bind paint to measured clusters without splitting text or singing spans."""
        fields: dict[str, _SingingSweep] = {}
        nodes: dict[str, SceneObject] = {}

        def collect(node: SceneObject) -> None:
            nodes[node.id] = node
            if isinstance(node, ObjectGroup):
                for child in node.children:
                    collect(child)

        collect(line)

        def resolve_color(
            value: Color | Callable[[LyricLine, LyricTarget], Color | None] | None,
            target: LyricTarget,
        ) -> Color | None:
            if value is None or isinstance(value, Color):
                return value
            color = value(line, target)
            if color is not None and not isinstance(color, Color):
                raise TypeError("lyric sweep color factory must return Color or None")
            return color

        def bind(
            target: LyricTarget, character: PositionedText, left: float, right: float
        ) -> None:
            node = nodes[target.node_id]
            intervals = tuple(
                (
                    span.start + target.delay - node.time_origin,
                    span.end + target.delay - node.time_origin,
                )
                for span in target.singing
            )
            if not intervals or left == right:
                return
            fill, outline = (
                resolve_color(self.fill, target),
                resolve_color(self.outline, target),
            )
            if fill is None and outline is None:
                return
            if node.material is not None or target.aliases:
                raise ValueError(
                    f"{node.id}: compose existing material/highlight contributions explicitly"
                )
            scale = character.layout_scale
            assert scale is not None
            fields[node.id] = _SingingSweep(
                (left - character.bounds.left) / scale.x,
                (right - character.bounds.left) / scale.x,
                intervals,
                fill,
                outline,
                self.width,
                self.width if self.outline_width is None else self.outline_width,
                self.step,
            )

        layout = line.layout
        for target, character in zip(
            line.query("character"), layout.body.characters, strict=True
        ):
            unit = next(
                unit
                for unit in layout.lyrics.units
                if unit.start <= character.start and character.end <= unit.end
            )
            box = layout.body._sweep_bounds(unit.start, unit.end, character)
            bind(target, character, box.left, box.right)
        readings = tuple(
            (
                character,
                ruby.layout._sweep_bounds(0, len(ruby.layout.source.text), character),
            )
            for ruby in layout.ruby
            for character in ruby.layout.characters
        )
        for target, (character, box) in zip(line.query("ruby"), readings, strict=True):
            bind(target, character, box.left, box.right)

        def apply(node: SceneObject) -> SceneObject:
            if isinstance(node, ObjectGroup):
                return replace(
                    node, children=tuple(apply(child) for child in node.children)
                )
            return replace(node, material=fields.get(node.id, node.material))

        result = apply(line)
        assert isinstance(result, LyricLine)
        return result
