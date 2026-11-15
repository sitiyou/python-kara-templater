"""Import ASS singing times into structured lyrics, without executing ASS code."""

import hashlib
import re
from dataclasses import dataclass, replace
from urllib.parse import quote, unquote

from .appearance import PaintPair
from .ass import Document, Line, Style
from .composition import Color, Paint
from .karaoke import KaraokeItem
from .model import KaraokeLine, Segment, TextUnit
from .sources import EventOrigin, SourceRef
from .timeline import DisplayWindow, _milliseconds

TIMING = re.compile(r"\\(kf|ko|kt|k|K)(\d+)")
HAS_TIMING = re.compile(r"\{[^}]*\\(?:kf|ko|kt|k|K)")
SOURCE_PREFIX = "karaoke:source:v1:"


class AssImportError(ValueError):
    """Failure at a zero-based Document.records position, before a lyric exists."""

    def __init__(
        self, message: str, *, record_index: int, style: str, item_id: str | None = None
    ) -> None:
        super().__init__(f"event {record_index} ({style}): {message}")
        self.record_index = record_index
        self.style = style
        self.origin = (
            EventOrigin((SourceRef(item_id),), "ASS import") if item_id else None
        )
        if self.origin is not None:
            self.add_note(f"effect=ASS import; sources={self.origin.sources!r}")


@dataclass(frozen=True)
class ImportSettings:
    """Track ASS-import display padding and optional style selection.

    lead_ms/tail_ms extend visibility independently of the original singing
    intervals.
    """

    lead_ms: int = 0
    tail_ms: int = 0
    styles: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        _milliseconds(self.lead_ms, "display lead")
        _milliseconds(self.tail_ms, "display tail")


@dataclass(frozen=True)
class SourceBinding:
    record_index: int
    item_id: str
    original_effect: str


@dataclass(frozen=True)
class ImportedKaraoke:
    """Structured lyric items plus source-record bindings for owner-aware regeneration.

    Importing does not itself replace or execute source events.
    """

    items: tuple[KaraokeItem, ...]
    sources: tuple[SourceBinding, ...]


def source_prefix(owner: str) -> str:
    return SOURCE_PREFIX + quote(owner, safe="") + ":"


def source_marker(owner: str, source: SourceBinding) -> str:
    return (
        source_prefix(owner)
        + quote(source.item_id, safe="")
        + ":"
        + quote(source.original_effect, safe="")
    )


def parse_karaoke(line: Line) -> KaraokeLine:
    """Read k/kf/K/ko durations, kt offsets, text|ruby, and # continuations.

    These tags import timing only; appearance and animation come from the recipe.
    Unsupported override tags are diagnosed instead of silently losing layout.
    """
    start_time = _milliseconds(line.start_time, "ASS event start")
    cursor = start_time
    text, units = "", []
    pending = None

    def flush():
        nonlocal text, pending, cursor
        if not text and pending is None:
            return
        base, separator, ruby = text.replace("｜", "|").partition("|")
        if "|" in ruby:
            raise ValueError("multiple ruby separators in one singing segment")
        continuation = base in {"#", "＃"}
        ruby_continuation = ruby.startswith(("<", "＜"))
        if ruby.startswith(("<", "＜", "!", "！")):
            ruby = ruby[1:]
        if pending is None:
            if separator or continuation:
                raise ValueError("ruby or continuation requires a singing time tag")
            if text:
                units.append(TextUnit(text))
        else:
            start, duration = pending
            segment = Segment(start, start + duration, ruby)
            cursor = segment.end_ms
            if continuation:
                if not units or not units[-1].segments:
                    raise ValueError(
                        "continuation requires a preceding timed text unit"
                    )
                units[-1] = replace(units[-1], segments=(*units[-1].segments, segment))
            else:
                units.append(TextUnit(base, (segment,), ruby_continuation))
        text, pending = "", None

    offset = 0
    while offset < len(line.text):
        char = line.text[offset]
        if char == "{":
            end = line.text.find("}", offset + 1)
            if end < 0:
                raise ValueError("unclosed ASS override block")
            block = line.text[offset + 1 : end]
            position = 0
            if "\\" in block:
                for match in TIMING.finditer(block):
                    if block[position : match.start()].strip():
                        raise ValueError(
                            f"unsupported ASS override: {block[position : match.start()]!r}; configure it in a Python recipe"
                        )
                    flush()
                    value = int(match[2]) * 10
                    if match[1] == "kt":
                        next_start = start_time + value
                        if next_start < cursor:
                            raise ValueError(
                                "kt cannot reverse time within a unit sequence; use explicit HighlightTrack objects"
                            )
                        cursor = next_start
                    else:
                        pending = (cursor, value)
                    position = match.end()
                if block[position:].strip():
                    raise ValueError(
                        f"unsupported ASS override: {block[position:]!r}; configure it in a Python recipe"
                    )
            offset = end + 1
        elif char in "}\r\n":
            raise ValueError("unmatched brace or multiline ASS text is not supported")
        elif char == "\\":
            if line.text[offset : offset + 2] == r"\h":
                text += "\u00a0"
                offset += 2
            else:
                raise ValueError(
                    "ASS text escapes other than hard space require explicit structured input"
                )
        else:
            text += char
            offset += 1
    flush()
    return KaraokeLine(tuple(units))


def import_karaoke(
    document: Document,
    *,
    owner: str = "default",
    settings: ImportSettings | None = None,
) -> ImportedKaraoke:
    """Import supported timed ASS lyrics into KaraokeItem values with stable source bindings.

    Preserve source timing and report unsupported tags with record/style context.
    """
    settings = settings or ImportSettings()
    prefix = source_prefix(owner)
    items, bindings, seen = [], [], set()
    for index, line in enumerate(document.records):
        if not isinstance(line, Line):
            continue
        marked = line.comment and line.effect.startswith(prefix)
        if line.comment and not marked:
            continue
        if line.effect.startswith(("karaoke:v1:", "kara:scene:v1:")) or (
            line.effect.startswith(SOURCE_PREFIX) and not marked
        ):
            continue
        if settings.styles is not None and line.style not in settings.styles:
            continue
        if not HAS_TIMING.search(line.text):
            continue
        if marked:
            identifier, separator, original = line.effect[len(prefix) :].partition(":")
            if not separator:
                raise AssImportError(
                    "malformed karaoke source marker",
                    record_index=index,
                    style=line.style,
                )
            identifier, original = unquote(identifier), unquote(original)
            if not identifier:
                raise AssImportError(
                    "empty karaoke source id", record_index=index, style=line.style
                )
        else:
            digest = hashlib.sha256(line.serialize().encode()).hexdigest()[:20]
            identifier, occurrence = f"ass:{digest}", 1
            while identifier in seen:
                identifier = f"ass:{digest}:{occurrence}"
                occurrence += 1
            original = line.effect
        if identifier in seen:
            raise AssImportError(
                f"duplicate source id {identifier!r}",
                record_index=index,
                style=line.style,
                item_id=identifier,
            )
        seen.add(identifier)
        try:
            source = parse_karaoke(line)
            window = DisplayWindow(
                _milliseconds(
                    max(0, line.start_time - settings.lead_ms), "display start"
                ),
                _milliseconds(line.end_time + settings.tail_ms, "display end"),
            )
        except ValueError as error:
            raise AssImportError(
                str(error), record_index=index, style=line.style, item_id=identifier
            ) from error
        items.append(
            KaraokeItem(
                identifier,
                source,
                line.style,
                window,
                margins=(line.margin_l, line.margin_r, line.margin_v),
            )
        )
        bindings.append(SourceBinding(index, identifier, original))
    return ImportedKaraoke(tuple(items), tuple(bindings))


def paint_pair_from_style(style: Style) -> PaintPair:
    """ASS secondary is unsung, primary is sung; decode AABBGGRR at this boundary."""

    def decode(key, default):
        value = next(
            (v for k, v in style.fields.items() if k.lower() == key.lower()), default
        )
        try:
            token = value.strip().upper().removeprefix("&H").removesuffix("&")
            packed = (
                int(token, 16)
                if value.strip().upper().startswith("&H")
                else int(token) & 0xFFFFFFFF
            )
        except ValueError as error:
            raise ValueError(f"style {style.name}: invalid {key}") from error
        return (
            Color(packed & 255, (packed >> 8) & 255, (packed >> 16) & 255),
            1 - ((packed >> 24) & 255) / 255,
        )

    outline, outline_opacity = decode("OutlineColour", "&H00000000")
    before, before_opacity = decode("SecondaryColour", "&H000000FF")
    after, after_opacity = decode("PrimaryColour", "&H00FFFFFF")
    if style.outline and (
        outline_opacity != before_opacity or outline_opacity != after_opacity
    ):
        raise ValueError(
            f"style {style.name}: independent outline alpha needs an explicit Paint recipe"
        )
    return PaintPair(
        Paint(before, outline, style.outline, before_opacity),
        Paint(after, outline, style.outline, after_opacity),
    )
