"""Lossless ASS text tokens and typed, non-executable input annotations.

Offsets address Python Unicode code points, not shaped glyphs. Original tokens
remain available even when an effect cannot interpret an override. Time values
in this module are seconds; the file-level Line continues to use milliseconds.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

from .ass import Document, Line, Style
from .composition import Color
from .geometry import finite


@dataclass(frozen=True)
class TextToken:
    """An original literal or override token with its source Text-string offset.

    Raw text is retained even if a particular effect cannot interpret it.
    """

    raw: str
    offset: int
    override: bool = False


@dataclass(frozen=True)
class TextAppearance:
    """The active style and resolved RGB channel colors for a text run.

    inline_colors records channels explicitly supplied by override tags.
    """

    style: str
    primary: Color
    secondary: Color
    outline: Color
    shadow: Color
    inline_colors: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TextRun:
    """A half-open decoded text range with its resolved appearance.

    It preserves color/reset scopes independently of later glyph shaping.
    """

    text: str
    start: int
    end: int
    appearance: TextAppearance


@dataclass(frozen=True)
class TimingTag:
    """A decoded karaoke timing tag at a text offset.

    Its seconds value is a duration for k/K/kf/ko and an absolute cursor offset for
    kt.
    """

    offset: int
    kind: Literal["k", "K", "kf", "ko", "kt"]
    seconds: float


@dataclass(frozen=True)
class CueMarker:
    """A non-executable cue anchor with ID, preset key, decoded body offset, and inline/independent placement.

    markup quotes the declaration; its insertion point carries the serialized
    offset.
    """

    id: str
    preset: str
    offset: int = 0
    placement: Literal["inline", "independent"] = "inline"

    def __post_init__(self) -> None:
        if not self.id or not self.preset or self.offset < 0:
            raise ValueError("cue needs a nonempty id/preset and nonnegative offset")
        if self.placement not in ("inline", "independent"):
            raise ValueError("invalid cue placement")
        if any(c in self.id + self.preset for c in "{}\r\n\\"):
            raise ValueError(
                "cue identifiers cannot contain braces, slashes or newlines"
            )

    def markup(self) -> str:
        """Encode a non-executable comment block at the desired text position."""
        return (
            "{kara:v1 cue "
            f"id={shlex.quote(self.id)} preset={shlex.quote(self.preset)} "
            f"placement={self.placement}" + "}"
        )


@dataclass(frozen=True)
class TextIssue:
    """A source offset and diagnostic message for text semantics a binder may reject.

    Parsing retains the original tokens for unsupported overrides.
    """

    record_index: int | None
    raw_offset: int
    raw: str
    reason: str


@dataclass(frozen=True)
class DocumentText:
    """A source-preserving decoded ASS text view with tokens, appearance runs, karaoke tags, cues, and issues.

    Offsets count Unicode code points rather than bytes or shaped glyphs.
    """

    record_index: int | None
    tokens: tuple[TextToken, ...]
    runs: tuple[TextRun, ...]
    timing: tuple[TimingTag, ...]
    cues: tuple[CueMarker, ...]
    unsupported: tuple[TextIssue, ...]

    @property
    def text(self) -> str:
        """Concatenate decoded text runs without override/comment markup."""
        return "".join(run.text for run in self.runs)

    def original(self) -> str:
        """Reconstruct the original source Text from its preserved raw tokens."""
        return "".join(token.raw for token in self.tokens)

    def require_supported(self) -> None:
        """Raise a contextual error when the text contains unsupported semantics for a binder."""
        if self.unsupported:
            issue = self.unsupported[0]
            raise ValueError(
                f"record {issue.record_index}, text offset {issue.raw_offset}: "
                f"{issue.reason}: {issue.raw!r}"
            )


def _packed_color(raw: str) -> int:
    """Decode ASS hexadecimal or signed decimal AABBGGRR without dropping alpha."""
    token = raw.strip()
    match = re.fullmatch(r"&[Hh]([0-9a-fA-F]{1,8})&?", token)
    if match is not None:
        return int(match[1], 16)
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token) & 0xFFFFFFFF
    raise ValueError(f"invalid ASS color: {raw!r}")


def _color(raw: str) -> Color:
    value = _packed_color(raw)
    return Color(value & 255, (value >> 8) & 255, (value >> 16) & 255)


def _appearance(style: Style) -> TextAppearance:
    fields = {key.lower(): value for key, value in style.fields.items()}
    return TextAppearance(
        style.name,
        _color(fields.get("primarycolour", "&HFFFFFF")),
        _color(fields.get("secondarycolour", "&H0000FF")),
        _color(fields.get("outlinecolour", "&H000000")),
        _color(fields.get("backcolour", "&H000000")),
    )


def _overrides(block: str) -> tuple[str, ...]:
    """Split top-level tags without interpreting nested transform arguments."""
    starts: list[int] = []
    depth = 0
    for index, char in enumerate(block):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "\\" and depth == 0:
            starts.append(index)
    if not starts:
        return ()
    starts.append(len(block))
    return tuple(block[a:b] for a, b in zip(starts, starts[1:], strict=False))


def _cue(block: str, offset: int) -> CueMarker:
    parts = shlex.split(block)
    if parts[:2] != ["kara:v1", "cue"]:
        raise ValueError("unsupported kara annotation version or kind")
    values: dict[str, str] = {}
    for part in parts[2:]:
        key, sep, value = part.partition("=")
        if not sep or key not in {"id", "preset", "placement"} or key in values:
            raise ValueError(f"invalid or duplicate cue parameter: {part!r}")
        values[key] = value
    placement = values.get("placement", "inline")
    if placement not in ("inline", "independent"):
        raise ValueError("cue placement must be inline or independent")
    return CueMarker(values.get("id", ""), values.get("preset", ""), offset, placement)


def _soft_break(document: Document) -> str:
    # Records are the serialized source of truth. Direct Document construction
    # need not duplicate every Script Info entry in its metrics metadata cache.
    wrapstyle = str(document.meta.get("wrapstyle", "0"))
    in_info = False
    for record in document.records:
        if not isinstance(record, str):
            continue
        raw = record.strip()
        if raw.startswith("[") and raw.endswith("]"):
            in_info = raw.lower() == "[script info]"
        elif in_info:
            key, separator, value = raw.partition(":")
            if separator and key.strip().lower() == "wrapstyle":
                wrapstyle = value.strip()
    return "\n" if wrapstyle == "2" else " "


def read_document_text(document: Document, record_index: int) -> DocumentText:
    """Bind one event's text while preserving every original byte of its text.

    Standard inline colors override the current style. An empty color tag resets
    that channel to the current style; r resets all channels to the named style
    or the event style. Unhandled tags are retained and explicitly diagnosed.
    Cue presets are resolved later by the effect registry, never executed here.
    """
    return _read_document_text(document, record_index, document.styles, _soft_break(document))


def _read_document_text(
    document: Document, record_index: int, styles: Mapping[str, Style], soft_break: str
) -> DocumentText:
    record = document.records[record_index]
    if not isinstance(record, Line):
        raise TypeError(f"record {record_index} is not an ASS event")
    if record.style not in styles:
        raise ValueError(f"record {record_index}: unknown style {record.style!r}")
    baseline = _appearance(styles[record.style])
    appearance = baseline
    tokens: list[TextToken] = []
    runs: list[TextRun] = []
    timing: list[TimingTag] = []
    cues: list[CueMarker] = []
    issues: list[TextIssue] = []
    offset = 0
    position = 0
    while position < len(record.text):
        start = position
        if record.text[position] != "{":
            decoded: list[str] = []
            escapes = {
                "N": "\n",
                "n": soft_break,
                "h": "\u00a0",
                "{": "{",
                "}": "}",
                "\u2060": "\\",
            }
            while position < len(record.text) and record.text[position] != "{":
                char = record.text[position]
                if (
                    char == "\\"
                    and position + 1 < len(record.text)
                    and record.text[position + 1] in escapes
                ):
                    decoded.append(escapes[record.text[position + 1]])
                    position += 2
                else:
                    decoded.append(char)
                    position += 1
            raw = record.text[start:position]
            text = "".join(decoded)
            tokens.append(TextToken(raw, offset))
            runs.append(TextRun(text, offset, offset + len(text), appearance))
            offset += len(text)
            continue
        end = record.text.find("}", position)
        if end < 0:
            raise ValueError(
                f"record {record_index}, text offset {start}: unclosed block"
            )
        position = end + 1
        raw = record.text[start:position]
        tokens.append(TextToken(raw, offset, True))
        block = raw[1:-1]
        if block.startswith("kara:"):
            try:
                cue = _cue(block, offset)
                if any(previous.id == cue.id for previous in cues):
                    raise ValueError(f"duplicate cue id {cue.id!r}")
                cues.append(cue)
            except ValueError as error:
                raise ValueError(
                    f"record {record_index}, text offset {start}: {error}"
                ) from error
            continue
        for tag in _overrides(block):
            color = re.fullmatch(r"\\([1-4]?)c(&H[0-9a-fA-F]{1,6}&?)?", tag)
            timing_match = re.fullmatch(r"\\(kf|ko|kt|k|K)(\d+)", tag)
            if color:
                channel = {
                    "": "primary",
                    "1": "primary",
                    "2": "secondary",
                    "3": "outline",
                    "4": "shadow",
                }[color[1]]
                value = (
                    _color(color[2])
                    if color[2]
                    else {
                        "primary": baseline.primary,
                        "secondary": baseline.secondary,
                        "outline": baseline.outline,
                        "shadow": baseline.shadow,
                    }[channel]
                )
                inline = (
                    appearance.inline_colors | {channel}
                    if color[2]
                    else appearance.inline_colors - {channel}
                )
                appearance = replace(
                    appearance, **{channel: value}, inline_colors=frozenset(inline)
                )
            elif tag.startswith(r"\r"):
                name = tag[2:] or record.style
                if name not in styles:
                    raise ValueError(
                        f"record {record_index}: unknown reset style {name!r}"
                    )
                baseline = _appearance(styles[name])
                appearance = baseline
            elif timing_match:
                kind = timing_match[1]
                assert kind in ("k", "K", "kf", "ko", "kt")
                timing.append(TimingTag(offset, kind, int(timing_match[2]) / 100))
            else:
                issues.append(
                    TextIssue(record_index, start, tag, "unsupported override")
                )
    return DocumentText(
        record_index,
        tuple(tokens),
        tuple(runs),
        tuple(timing),
        tuple(cues),
        tuple(issues),
    )


@dataclass(frozen=True)
class TimedTextSpan:
    """Source text offsets and absolute timing intervals, including zero duration."""

    start_offset: int
    end_offset: int
    start: float
    end: float
    kind: Literal["k", "K", "kf", "ko"]

    def __post_init__(self) -> None:
        finite(self.start, self.end)
        if (
            self.start < 0
            or self.end < self.start
            or self.start_offset < 0
            or self.end_offset < self.start_offset
        ):
            raise ValueError("invalid timing interval or source range")


def resolve_timing(source: DocumentText, start: float) -> tuple[TimedTextSpan, ...]:
    finite(start)
    if start < 0:
        raise ValueError("timing start must be nonnegative")
    cursor = start
    result: list[TimedTextSpan] = []
    for index, tag in enumerate(source.timing):
        if tag.kind == "kt":
            if start + tag.seconds < cursor - 1e-9:
                raise ValueError(
                    f"record {source.record_index}, decoded text offset {tag.offset}: "
                    "kt reverses the timing cursor"
                )
            cursor = start + tag.seconds
            continue
        end_offset = (
            source.timing[index + 1].offset
            if index + 1 < len(source.timing)
            else len(source.text)
        )
        result.append(
            TimedTextSpan(tag.offset, end_offset, cursor, cursor + tag.seconds, tag.kind)
        )
        cursor += tag.seconds
    return tuple(result)
