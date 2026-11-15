"""Reusable visual components, independent of effect lifecycle and compilation."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from typing import Literal, Self, Unpack

from ._track_types import RubyPolicy
from .follow import DEFAULT_FOLLOW, Follow
from .stylesheet import (
    UNSET,
    ColorStyle,
    NumberStyle,
    StyleOverrides,
    StyleProperties,
)
from .text_style import RubySpan, TextSpan, TextStyle


class ComponentOptions(StyleProperties, total=False):
    id: str | None
    classes: str | Iterable[str]


class Component:
    kind: str = "component"
    id: str | None
    classes: set[str]
    children: tuple[Component, ...]
    parent: Component | None
    attributes: dict[str, str | int]

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
        for child in children:
            if not isinstance(child, Component):
                raise TypeError("component children must be components")
            if child.parent is not None:
                raise ValueError("a component cannot have two parents")
            child.parent = self

    def add_class(self, *names: str) -> Self:
        """Add validated nonempty style class names and return this component."""
        for name in names:
            if not isinstance(name, str) or not name or any(c.isspace() for c in name):
                raise ValueError("class names must be nonempty without whitespace")
            self.classes.add(name)
        return self

    def walk(self) -> Iterator[Component]:
        """Iterate this style component and its descendants in declaration order."""
        yield self
        for child in self.children:
            yield from child.walk()


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
    """Track body text configuration with TextStyle, source-wide TextSpan declarations, and optional style classes.

    Each Track binding uses fresh configuration without changing the source text or
    timing.
    """

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
    """Track reading configuration with font/paint style, reading spans, vertical offset, and following policy.

    hide disables the reading while retaining its declaration.
    """

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
        """Disable reading output while retaining its style and source-span declaration."""
        self.policy = replace(self.policy, enabled=False)
