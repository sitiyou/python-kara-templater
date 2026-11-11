"""Small Python style cascade, independent of layout and output layers."""

import re
from dataclasses import dataclass
from enum import Enum

from .colors import color
from .timeline import _finite


class _Keyword(Enum):
    INHERIT = "inherit"
    UNSET = "unset"


INHERIT = _Keyword.INHERIT
UNSET = _Keyword.UNSET
_COLORS = {"fill", "stroke"}
_NUMBERS = {"stroke_width", "opacity", "font_size"}


def _value(name, value):
    if name not in _COLORS | _NUMBERS:
        raise ValueError(f"unknown style property {name!r}")
    if isinstance(value, _Keyword):
        return value
    if name in _COLORS:
        return color(value)
    _finite(value, name)
    if (
        value < 0
        or (name == "opacity" and value > 1)
        or (name == "font_size" and value == 0)
    ):
        raise ValueError(f"invalid {name}: {value!r}")
    return value


class StyleValues:
    """Explicit declarations. Assigning UNSET removes this level's override."""

    def __init__(self, **values):
        object.__setattr__(self, "_values", {})
        for name, value in values.items():
            setattr(self, name, value)

    def __setattr__(self, name, value):
        value = _value(name, value)
        if value is UNSET:
            self._values.pop(name, None)
        else:
            self._values[name] = value

    def __getattr__(self, name):
        if name not in _COLORS | _NUMBERS:
            raise AttributeError(name)
        return self._values.get(name, UNSET)


class StyleOverrides(StyleValues):
    def __init__(self, **values):
        super().__init__(**values)
        object.__setattr__(self, "sung", StyleValues())


class SelectionStyle:
    """Broadcast declarations to a selection without introducing a cascade level."""

    def __init__(self, targets, *, sung=False):
        object.__setattr__(self, "_targets", targets)
        if not sung:
            object.__setattr__(
                self, "sung", SelectionStyle(tuple(t.sung for t in targets), sung=True)
            )

    def __setattr__(self, name, value):
        value = _value(name, value)
        for target in self._targets:
            setattr(target, name, value)

    def __getattr__(self, name):
        if name not in _COLORS | _NUMBERS:
            raise AttributeError(name)
        values = [getattr(target, name) for target in self._targets]
        if not values:
            return UNSET
        if any(value != values[0] for value in values[1:]):
            raise ValueError(
                f"selection has different {name} declarations; inspect individual targets"
            )
        return values[0]


_IDENT = r"[A-Za-z_][\w-]*"
_TOKEN = re.compile(
    rf"(?P<type>{_IDENT})|(?P<id>\#{_IDENT})|(?P<class>\.{_IDENT})"
    rf"|(?P<state>:sung)|\[(?P<attr>{_IDENT})=(?P<value>\"[^\"]*\"|'[^']*'|[\w-]+)\]"
)
_PARTS = re.compile(r"(?:\[[^\]]*\]|[^\s\[])+")


@dataclass(frozen=True)
class Selector:
    parts: tuple
    specificity: tuple[int, int, int]

    @classmethod
    def parse(cls, text):
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
        return cls(tuple(parts), tuple(specificity))

    def matches(self, node, *, sung=False):
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
    declarations: tuple


def rule(selector, **properties):
    return StyleRule(
        Selector.parse(selector),
        tuple((k, _value(k, v)) for k, v in properties.items()),
    )


@dataclass(frozen=True, init=False)
class StyleSheet:
    rules: tuple[StyleRule, ...]

    def __init__(self, *rules):
        if any(not isinstance(r, StyleRule) for r in rules):
            raise TypeError("StyleSheet expects rule() declarations")
        object.__setattr__(self, "rules", tuple(rules))

    def resolve(self, node, base, *, sung=False, inherited=None, resolved_parent=None):
        """Resolve properties, preserving unspecified values in the source base.

        UNSET rules contribute no declaration. INHERIT reads the corresponding
        source/parent value, rather than the previous winning rule.
        Source targets refine a component's resolved appearance. When supplied,
        resolved_parent excludes rules already applied at that component level,
        so merely creating a range cannot override explicit component styles.
        """
        inherited = base if inherited is None else inherited
        result = dict(base)
        matching = sorted(
            (
                r
                for r in self.rules
                if r.selector.matches(node, sung=sung)
                and not (
                    resolved_parent is not None
                    and r.selector.matches(resolved_parent, sung=sung)
                )
            ),
            key=lambda r: r.selector.specificity,
        )
        declarations = [r.declarations for r in matching]
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
