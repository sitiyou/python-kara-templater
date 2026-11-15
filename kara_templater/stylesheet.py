"""Small Python style cascade, independent of layout and output layers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypedDict, Unpack, cast

from .colors import color
from .composition import Color
from .timeline import _finite

if TYPE_CHECKING:
    from .components import Component


class StyleKeyword(Enum):
    """Explicit UNSET and INHERIT declarations for the style cascade.

    UNSET contributes no override; INHERIT reads the relevant source/parent value.
    """

    INHERIT = "inherit"
    UNSET = "unset"


INHERIT = StyleKeyword.INHERIT
UNSET = StyleKeyword.UNSET
_COLORS = {"fill", "stroke"}
_NUMBERS = {"stroke_width", "opacity", "font_size"}


def _value(name: str, value: object) -> StyleValue:
    if name not in _COLORS | _NUMBERS:
        raise ValueError(f"unknown style property {name!r}")
    if isinstance(value, StyleKeyword):
        return value
    if name in _COLORS:
        if not isinstance(value, (str, Color)):
            raise TypeError("color must be Color or #RRGGBB")
        return color(value)
    _finite(value, name)
    assert isinstance(value, (int, float))
    if (
        value < 0
        or (name == "opacity" and value > 1)
        or (name == "font_size" and value == 0)
    ):
        raise ValueError(f"invalid {name}: {value!r}")
    return value


type ColorStyle = Color | str | StyleKeyword
type NumberStyle = float | StyleKeyword
type StyleValue = Color | float | StyleKeyword


class StyleProperties(TypedDict, total=False):
    """Typed optional style-declaration keys used by constructors and rule().

    Color and scalar fields retain explicit UNSET/INHERIT support.
    """

    fill: ColorStyle
    stroke: ColorStyle
    stroke_width: NumberStyle
    opacity: NumberStyle
    font_size: NumberStyle


class _StyleAccess:
    """Typed read/write surface shared by component and selection declarations."""

    def _read(self, name: str) -> StyleValue:
        raise NotImplementedError

    def _write(self, name: str, value: ColorStyle | NumberStyle) -> None:
        raise NotImplementedError

    @property
    def fill(self) -> Color | StyleKeyword:
        """Read or set the RGB fill declaration, including explicit style keywords."""
        return cast(Color | StyleKeyword, self._read("fill"))

    @fill.setter
    def fill(self, value: ColorStyle) -> None:
        """Read or set the RGB fill declaration, including explicit style keywords."""
        self._write("fill", value)

    @property
    def stroke(self) -> Color | StyleKeyword:
        """Read or set the RGB outline declaration, including explicit style keywords."""
        return cast(Color | StyleKeyword, self._read("stroke"))

    @stroke.setter
    def stroke(self, value: ColorStyle) -> None:
        """Read or set the RGB outline declaration, including explicit style keywords."""
        self._write("stroke", value)

    @property
    def stroke_width(self) -> NumberStyle:
        """Read or set the nonnegative outline-width declaration in script pixels or a style keyword."""
        return cast(NumberStyle, self._read("stroke_width"))

    @stroke_width.setter
    def stroke_width(self, value: NumberStyle) -> None:
        """Read or set the nonnegative outline-width declaration in script pixels or a style keyword."""
        self._write("stroke_width", value)

    @property
    def opacity(self) -> NumberStyle:
        """Read or set opacity in 0 through 1, including explicit style keywords."""
        return cast(NumberStyle, self._read("opacity"))

    @opacity.setter
    def opacity(self, value: NumberStyle) -> None:
        """Read or set opacity in 0 through 1, including explicit style keywords."""
        self._write("opacity", value)

    @property
    def font_size(self) -> NumberStyle:
        """Read or set the positive font-size declaration in script pixels or a style keyword."""
        return cast(NumberStyle, self._read("font_size"))

    @font_size.setter
    def font_size(self, value: NumberStyle) -> None:
        """Read or set the positive font-size declaration in script pixels or a style keyword."""
        self._write("font_size", value)


class StyleValues(_StyleAccess):
    """Explicit declarations. Assigning UNSET removes this level's override."""

    _values: dict[str, StyleValue]

    def __init__(self, **values: Unpack[StyleProperties]) -> None:
        object.__setattr__(self, "_values", {})
        for name, value in values.items():
            setattr(self, name, value)

    def _write(self, name: str, value: ColorStyle | NumberStyle) -> None:
        value = _value(name, value)
        if value is UNSET:
            self._values.pop(name, None)
        else:
            self._values[name] = value

    if not TYPE_CHECKING:
        # Runtime setattr validates names; static callers see only named properties.
        __setattr__ = _write

    def _read(self, name: str) -> StyleValue:
        if name not in _COLORS | _NUMBERS:
            raise AttributeError(name)
        return self._values.get(name, UNSET)


class StyleOverrides(StyleValues):
    """Typed mutable base and sung-state style declarations.

    Only supported paint and font-size fields participate in the cascade.
    """

    sung: StyleValues

    def __init__(self, **values: Unpack[StyleProperties]) -> None:
        super().__init__(**values)
        object.__setattr__(self, "sung", StyleValues())


_IDENT = r"[A-Za-z_][\w-]*"
_TOKEN = re.compile(
    rf"(?P<type>{_IDENT})|(?P<id>\#{_IDENT})|(?P<class>\.{_IDENT})"
    rf"|(?P<state>:sung)|\[(?P<attr>{_IDENT})=(?P<value>\"[^\"]*\"|'[^']*'|[\w-]+)\]"
)
_PARTS = re.compile(r"(?:\[[^\]]*\]|[^\s\[])+")


@dataclass(frozen=True)
class Selector:
    parts: tuple[tuple[tuple[str, str | tuple[str, str]], ...], ...]
    specificity: tuple[int, int, int]

    @classmethod
    def parse(cls, text: str) -> Selector:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("selector must be a nonempty string")
        parts, specificity = [], [0, 0, 0]
        consumed = 0
        for part_match in _PARTS.finditer(text):
            if text[consumed : part_match.start()].strip():
                raise ValueError(f"unsupported selector {text!r}")
            consumed = part_match.end()
            part = part_match.group()
            position, tokens = 0, []
            for token in _TOKEN.finditer(part):
                if token.start() != position:
                    raise ValueError(f"unsupported selector {text!r}")
                position = token.end()
                kind = token.lastgroup
                if token.group("attr") is not None:
                    tokens.append(
                        (
                            "attr",
                            (token.group("attr"), token.group("value").strip("\"'")),
                        )
                    )
                    specificity[1] += 1
                else:
                    value = token.group()
                    if kind == "type":
                        if tokens:
                            raise ValueError(f"misplaced type in selector {text!r}")
                        specificity[2] += 1
                    else:
                        value = value[1:]
                        specificity[0 if kind == "id" else 1] += 1
                    tokens.append((kind, value))
            if position != len(part) or not tokens:
                raise ValueError(f"unsupported selector {text!r}")
            parts.append(tuple(tokens))
        if not parts or text[consumed:].strip():
            raise ValueError(f"unsupported selector {text!r}")
        return cls(tuple(parts), (specificity[0], specificity[1], specificity[2]))

    def matches(self, node, *, sung: bool = False) -> bool:
        def matches_part(part, candidate):
            for kind, value in part:
                if kind == "type" and candidate.kind != value:
                    return False
                if kind == "id" and candidate.id != value:
                    return False
                if kind == "class" and value not in candidate.classes:
                    return False
                if kind == "state" and not sung:
                    return False
                if kind == "attr" and (
                    value[0] not in candidate.attributes
                    or str(candidate.attributes[value[0]]) != value[1]
                ):
                    return False
            return True

        if not matches_part(self.parts[-1], node):
            return False
        ancestor = node.parent
        for part in reversed(self.parts[:-1]):
            while ancestor is not None and not matches_part(part, ancestor):
                ancestor = ancestor.parent
            if ancestor is None:
                return False
            ancestor = ancestor.parent
        return True


@dataclass(frozen=True)
class StyleRule:
    selector: Selector
    declarations: tuple[tuple[str, StyleValue], ...]


def rule(selector: str, **properties: Unpack[StyleProperties]) -> StyleRule:
    """Build a validated selector rule from typed style declarations.

    Supported selectors identify roles, IDs, classes, attributes, and sung state.
    """
    return StyleRule(
        Selector.parse(selector),
        tuple((k, _value(k, v)) for k, v in properties.items()),
    )


@dataclass(frozen=True, init=False)
class StyleSheet:
    """An immutable ordered collection of selector rules for Track components and

    source ranges. Rules combine specificity with explicit declarations and sung-
    state scope.
    """

    rules: tuple[StyleRule, ...]

    def __init__(self, *rules: StyleRule) -> None:
        if any(not isinstance(r, StyleRule) for r in rules):
            raise TypeError("StyleSheet expects rule() declarations")
        object.__setattr__(self, "rules", tuple(rules))

    def _resolve(
        self,
        node: Component,
        base: Mapping[str, Color | float],
        *,
        sung: bool = False,
        inherited: Mapping[str, Color | float] | None = None,
        resolved_parent: Component | None = None,
        state_only: bool = False,
    ) -> dict[str, Color | float]:
        """Resolve properties, preserving unspecified values in the source base.

        UNSET rules contribute no declaration. INHERIT reads the corresponding
        source/parent value, rather than the previous winning rule.
        Source targets refine a component's resolved appearance. When supplied,
        resolved_parent excludes rules already applied at that component level,
        so merely creating a range cannot override explicit component styles.
        """
        if state_only and not sung:
            raise ValueError("state_only requires sung=True")
        inherited = base if inherited is None else inherited
        result = dict(base)
        matching = sorted(
            (
                r
                for r in self.rules
                if r.selector.matches(node, sung=sung)
                and (not state_only or not r.selector.matches(node, sung=False))
                and not (
                    resolved_parent is not None
                    and r.selector.matches(resolved_parent, sung=sung)
                )
            ),
            key=lambda r: r.selector.specificity,
        )
        declarations = [r.declarations for r in matching]
        if not state_only:
            declarations.append(tuple(node.style._values.items()))
        if sung:
            declarations.append(tuple(node.style.sung._values.items()))
        for values in declarations:
            for name, value in values:
                if value is UNSET:
                    continue
                if value is INHERIT:
                    if name in inherited:
                        result[name] = inherited[name]
                    else:
                        result.pop(name, None)
                else:
                    result[name] = value
        return result
