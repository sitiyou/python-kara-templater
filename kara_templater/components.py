"""Reusable visual components, independent of effect lifecycle and compilation."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from typing import Literal, Self, TypedDict, Unpack

from .behaviors import (
    TargetSelection,
    declare_properties,
)
from .characters import (
    LayoutCapabilityError,
)
from .composition import Glow
from .follow import DEFAULT_FOLLOW, Follow
from .properties import (
    CompositionMode,
    ProgressMode,
    PropertyValue,
    TimeInterval,
    singing,
)
from .recipe import (
    RubyPolicy,
)
from .stylesheet import (
    UNSET,
    ColorStyle,
    NumberStyle,
    StyleKeyword,
    StyleOverrides,
    StyleProperties,
)
from .text_style import RubySpan, TextSpan, TextStyle


class ComponentOptions(StyleProperties, total=False):
    id: str | None
    classes: str | Iterable[str]


class HaloOptions(TypedDict, total=False):
    id: str | None
    classes: str | Iterable[str]
    fill: ColorStyle
    stroke: ColorStyle
    stroke_width: NumberStyle
    font_size: NumberStyle


class Component:
    kind: str = "component"
    id: str | None
    classes: set[str]
    children: tuple[Component, ...]
    parent: Component | None
    attributes: dict[str, str | int]
    _ranges: dict[tuple[int, int], Component]
    _length: int | None

    def __init__(
        self,
        *children: Component,
        id: str | None = None,
        classes: str | Iterable[str] = (),
        **style: Unpack[StyleProperties],
    ) -> None:
        if id is not None and (not isinstance(id, str) or not id):
            raise ValueError("component id must be a nonempty string")
        self.id = id
        self.classes = set()
        self.add_class(*(classes.split() if isinstance(classes, str) else classes))
        self.style = StyleOverrides(**style)
        self.children = tuple(children)
        self.parent = None
        self.attributes = {}
        self._ranges = {}
        self._length = None
        for child in children:
            if not isinstance(child, Component):
                raise TypeError("component children must be components")
            if child.parent is not None:
                raise ValueError("a component cannot have two parents")
            child.parent = self

    def add_class(self, *names: str) -> Self:
        for name in names:
            if not isinstance(name, str) or not name or any(c.isspace() for c in name):
                raise ValueError("class names must be nonempty without whitespace")
            self.classes.add(name)
        return self

    def walk(self) -> Iterator[Component]:
        yield self
        for child in self.children:
            yield from child.walk()

    def text_range(self, start: int, end: int) -> Component:
        if self.kind != "body" or self._length is None:
            raise ValueError("text_range requires a source-bound Body")
        if (
            any(type(v) is not int for v in (start, end))
            or not 0 <= start < end <= self._length
        ):
            raise ValueError(
                f"invalid body range {start}:{end} for {self._length} codepoints"
            )
        if (start, end) not in self._ranges:
            node = Component()
            node.kind = "body"
            node.parent = self
            node.attributes = {"start": start, "end": end}
            self._ranges[start, end] = node
        return self._ranges[start, end]


class Lyrics(Component):
    kind = "lyrics"


class _StyledText(Component):
    def __init__(
        self,
        *,
        style: TextStyle | None = None,
        id: str | None = None,
        classes: str | Iterable[str] = (),
        fill: ColorStyle = UNSET,
        stroke: ColorStyle = UNSET,
        stroke_width: NumberStyle = UNSET,
        opacity: NumberStyle = UNSET,
        font_size: NumberStyle = UNSET,
    ) -> None:
        self.text_style = TextStyle() if style is None else style
        values = self.text_style
        super().__init__(
            id=id,
            classes=classes,
            fill=values.fill if fill is UNSET else fill,
            stroke=values.stroke if stroke is UNSET else stroke,
            stroke_width=values.stroke_width if stroke_width is UNSET else stroke_width,
            opacity=values.opacity if opacity is UNSET else opacity,
            font_size=values.font_size if font_size is UNSET else font_size,
        )


class Body(_StyledText):
    kind = "body"

    def __init__(
        self,
        *,
        style: TextStyle | None = None,
        spans: Iterable[TextSpan] = (),
        id: str | None = None,
        classes: str | Iterable[str] = (),
        fill: ColorStyle = UNSET,
        stroke: ColorStyle = UNSET,
        stroke_width: NumberStyle = UNSET,
        opacity: NumberStyle = UNSET,
        font_size: NumberStyle = UNSET,
    ) -> None:
        super().__init__(
            style=style,
            id=id,
            classes=classes,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            font_size=font_size,
        )
        self.spans = tuple(spans)


class Ruby(_StyledText):
    kind = "ruby"

    def __init__(
        self,
        *,
        offset_y: float = 0,
        follow: Literal["none", "syllable"] | Follow = "none",
        style: TextStyle | None = None,
        spans: Iterable[RubySpan] = (),
        id: str | None = None,
        classes: str | Iterable[str] = (),
        fill: ColorStyle = UNSET,
        stroke: ColorStyle = UNSET,
        stroke_width: NumberStyle = UNSET,
        opacity: NumberStyle = UNSET,
        font_size: NumberStyle = UNSET,
    ) -> None:
        super().__init__(
            style=style,
            id=id,
            classes=classes,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            font_size=font_size,
        )
        self.spans = tuple(spans)
        self.following = (
            follow
            if isinstance(follow, Follow)
            else (
                Follow(position=False, scale=False, opacity=False)
                if follow == "none"
                else DEFAULT_FOLLOW
            )
        )
        self.policy = RubyPolicy(
            offset_y=offset_y,
            follow="syllable" if isinstance(follow, Follow) else follow,
        )

    def hide(self) -> None:
        self.policy = replace(self.policy, enabled=False)


class Halo(Component):
    """Independent full-target decoration, before any body sweep partitioning."""

    kind = "halo"

    def __init__(
        self,
        *,
        color: ColorStyle = UNSET,
        opacity: NumberStyle = UNSET,
        width: float = 0,
        ruby_width: float | None = None,
        blur: float = 0,
        max_blur: float | None = None,
        targets: Literal["text", "body", "ruby"] | TargetSelection = "text",
        clip: Literal["none", "sung"] = "none",
        follow: Follow = DEFAULT_FOLLOW,
        window: TimeInterval | None = None,
        **kwargs: Unpack[HaloOptions],
    ) -> None:
        super().__init__(**kwargs)
        if color is not UNSET:
            self.style.fill = color
        if opacity is not UNSET:
            self.style.opacity = opacity
        self._selected_targets = None
        if isinstance(targets, TargetSelection):
            if targets.mode == "segment":
                raise ValueError(
                    "Halo targets require visual sources, not temporal segments"
                )
            self._selected_targets = (
                targets.item_id,
                targets.mode,
                targets.units,
                targets._members,
            )
            targets = {"character": "body", "ruby": "ruby", "syllable": "text"}[
                targets.mode
            ]
        elif targets not in {"text", "body", "ruby"}:
            raise ValueError(
                "Halo targets must be text, body, ruby or a source selection"
            )
        self.width = width
        self.ruby_width = width if ruby_width is None else ruby_width
        self.blur = blur
        self.targets = targets
        if clip not in {"none", "sung"}:
            raise ValueError("Halo clip must be none or sung")
        if not isinstance(follow, Follow):
            raise TypeError("Halo follow must be Follow")
        if window is not None and (not isinstance(window, tuple) or len(window) != 2):
            raise ValueError("Halo window must be a start/end tuple")
        self.clip, self.following, self.window = clip, follow, window
        # Validate geometry at declaration time, before loading or laying out text.
        Glow(blur=blur, border=width)
        Glow(blur=blur, border=self.ruby_width)
        if max_blur is not None:
            Glow(blur=max_blur)
            if max_blur < blur:
                raise ValueError("Halo max_blur must cover its base blur")
        self.max_blur = max_blur
        self._property_rules = []

    def _selects(self, visual, item_id):
        if self.targets != "text" and self.targets != visual.kind:
            return False
        if self._selected_targets is None:
            return True
        owner, mode, units, members = self._selected_targets
        if owner != item_id:
            raise ValueError("Halo target selection belongs to another source item")
        unit = visual.sources[0].unit_index
        if unit not in units:
            return False
        if mode == "ruby":
            return any(
                (r.unit_index, r.segment_index) in members for r in visual.sources
            )
        if mode == "character":
            span = visual.text_range
            covered = [
                any(r.unit_index == unit and r.start <= index < r.end for r in members)
                for index in range(span.start, span.end)
            ]
            if any(covered) and not all(covered):
                raise LayoutCapabilityError(
                    "Halo target selection cuts a drawable cluster"
                )
            return bool(covered) and all(covered)
        return True

    def on_singing(
        self,
        *,
        opacity: PropertyValue | StyleKeyword = UNSET,
        blur: PropertyValue | StyleKeyword = UNSET,
        keep: bool = False,
        compose: CompositionMode = "replace",
        progress: ProgressMode = "envelope",
    ) -> Self:
        during = (singing.start, singing.end)
        if any(
            r.during == during
            and r.compose == compose == "replace"
            and (
                (r.property == "opacity" and opacity is not UNSET)
                or (r.property == "glow_blur" and blur is not UNSET)
            )
            for r in self._property_rules
        ):
            raise ValueError(f"halo {self.id!r}: overlapping opacity or blur behaviors")
        return self.animate(
            opacity=opacity,
            blur=blur,
            during=during,
            keep=keep,
            compose=compose,
            progress=progress,
        )

    def animate(
        self,
        *,
        opacity: PropertyValue | StyleKeyword = UNSET,
        blur: PropertyValue | StyleKeyword = UNSET,
        during: TimeInterval,
        keep: bool = False,
        compose: CompositionMode = "replace",
        progress: ProgressMode = "envelope",
    ) -> Self:
        properties = {}
        if opacity is not UNSET:
            properties["opacity"] = opacity
        if blur is not UNSET:
            if self.max_blur is None:
                raise ValueError("animated Halo blur requires max_blur")
            properties["glow_blur"] = blur
        self._property_rules.extend(
            declare_properties(
                properties,
                during=during,
                keep=keep,
                compose=compose,
                progress=progress,
            )
        )
        return self
