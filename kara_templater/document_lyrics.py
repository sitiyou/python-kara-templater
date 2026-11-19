"""Non-executable lyric projections retaining colors, source ranges and timing."""

from dataclasses import dataclass, replace
from typing import Literal

from .document_text import DocumentText, SingingSpan, TextRun, resolve_singing


@dataclass(frozen=True)
class LyricMapping:
    """One unchanged text slice from the original decoded text into a component."""

    source_start: int
    source_end: int
    start: int
    end: int


@dataclass(frozen=True)
class RubyText:
    """A reading text view with mappings back to source text and join/break/spill mode.

    Its source indices are local to the reading view.
    """

    source: DocumentText
    mapping: tuple[LyricMapping, ...]
    mode: Literal["join", "break", "spill"] = "join"


@dataclass(frozen=True)
class LyricSegment:
    """One absolute-seconds singing interval and its optional RubyText, retaining source text bounds.

    Repeated singing adds segments without duplicating the body.
    """

    singing: SingingSpan
    source_start: int
    source_end: int
    ruby: RubyText | None = None


@dataclass(frozen=True)
class LyricUnit:
    """A decoded body range and its ordered singing segments.

    Ranges count Unicode code points and must later respect shaped cluster
    boundaries.
    """

    start: int
    end: int
    segments: tuple[LyricSegment, ...] = ()

    def _body_singing(self) -> tuple[SingingSpan, ...]:
        """Adjacent timed readings share a single body sweep."""
        spans = tuple(segment.singing for segment in self.segments)
        if (
            len(spans) > 1
            and all(s.ruby is not None for s in self.segments)
            and all(
                abs(a.end - b.start) < 1e-8
                for a, b in zip(spans, spans[1:], strict=False)
            )
        ):
            return (replace(spans[0], end=spans[-1].end),)
        return spans

    def _body_parts(self, *, reading_units: bool = False) -> tuple[tuple[SingingSpan, float, float], ...]:
        """Split a merged body sweep by checkpoints or by visible reading characters."""
        spans = self._body_singing()
        if len(spans) == 1 and len(self.segments) > 1:
            weights = [1] * len(self.segments)
            if reading_units:
                # Studio attaches combining dakuten and handakuten to their kana.
                counts = [
                    sum(i == 0 or ch not in "\u3099\u309a" for i, ch in enumerate(seg.ruby.source.text))
                    if seg.ruby else 0
                    for seg in self.segments
                ]
                if any(counts):
                    weights = counts
            total = sum(weights)
            distance = 0
            parts = []
            for seg, weight in zip(self.segments, weights, strict=True):
                parts.append((seg.singing, distance / total, (distance + weight) / total))
                distance += weight
            duration = spans[0].end - spans[0].start
            if any(abs(s.end - s.start - duration * (b - a)) > 1e-9 for s, a, b in parts):
                return tuple(parts)
        return tuple((span, 0.0, 1.0) for span in spans)


@dataclass(frozen=True)
class DocumentLyrics:
    """A decoded body/ruby projection with source mappings and ordered lyric units.

    Original DocumentText remains available for diagnostics and round trips.
    """

    source: DocumentText
    body: DocumentText
    mapping: tuple[LyricMapping, ...]
    units: tuple[LyricUnit, ...]

    def _reverse_timing(self) -> "DocumentLyrics":
        """Assign authored time windows to body units in reverse spatial order."""
        # Studio's whole-line reverse uses main-text intervals and hides readings.
        # Collapse contiguous ruby checkpoints to their host note before reversing.
        clocks = tuple((unit, unit._body_singing()) for unit in self.units)
        windows = iter(span for unit, spans in clocks
                       if unit.end > unit.start for span in spans)
        timed_units = []
        for unit, spans in reversed(clocks):
            segments = unit.segments
            if len(spans) == 1 and len(segments) > 1:
                segments = (replace(segments[0], source_end=segments[-1].source_end),)
            timed = []
            for segment in segments:
                window = next(windows) if unit.end > unit.start else segment.singing
                singing = replace(segment.singing, start=window.start, end=window.end)
                timed.append(replace(segment, singing=singing, ruby=None))
            timed_units.append(replace(unit, segments=tuple(timed)))
        return replace(self, units=tuple(reversed(timed_units)))


def _slice(
    source: DocumentText, start: int, end: int, offset: int = 0
) -> tuple[TextRun, ...]:
    return tuple(
        TextRun(
            run.text[max(start, run.start) - run.start : min(end, run.end) - run.start],
            max(start, run.start) - start + offset,
            min(end, run.end) - start + offset,
            run.appearance,
        )
        for run in source.runs
        if run.start < end and run.end > start
    )


def parse_document_lyrics(source: DocumentText, *, start: float) -> DocumentLyrics:
    """Project text|ruby and # continuations; all singing times remain absolute.

    Syntax is recognized within each explicit karaoke interval. Untimed text is
    preserved, but ruby/continuation syntax requires a karaoke time tag. Body
    and ruby views retain the original tokens for provenance, not serialization.
    """
    source.require_supported()
    text = source.text
    if "\n" in text or "\r" in text:
        raise ValueError(
            f"record {source.record_index}: multiline lyric layout is not yet supported"
        )
    spans = resolve_singing(source, start)
    units: list[LyricUnit] = []
    body: list[TextRun] = []
    mapping: list[LyricMapping] = []
    size = 0

    def append_body(a: int, b: int) -> tuple[int, int]:
        nonlocal size
        first = size
        body.extend(_slice(source, a, b, size))
        size += b - a
        if b > a:
            mapping.append(LyricMapping(a, b, first, size))
        return first, size

    first_timed = spans[0].start_offset if spans else len(text)
    prefix = text[:first_timed]
    if any(c in prefix for c in "|｜#＃"):
        raise ValueError(
            f"record {source.record_index}: ruby or continuation requires a singing tag"
        )
    if prefix:
        units.append(LyricUnit(*append_body(0, first_timed)))
    previous = first_timed
    for span in spans:
        if span.start_offset > previous:
            gap = text[previous : span.start_offset]
            if any(c in gap for c in "|｜#＃"):
                raise ValueError("ruby or continuation requires a singing tag")
            units.append(LyricUnit(*append_body(previous, span.start_offset)))
        a, b = span.start_offset, span.end_offset
        previous = b
        value = text[a:b]
        separators = [i for i, c in enumerate(value) if c in "|｜"]
        if len(separators) > 1:
            raise ValueError(
                f"record {source.record_index}, text offset {a}: multiple ruby separators"
            )
        split = a + separators[0] if separators else b
        base = text[a:split]
        continuation = base.strip(" \t") in ("#", "＃")
        if any(c in base for c in "#＃") and not continuation:
            raise ValueError(
                f"record {source.record_index}, text offset {a}: continuation must be a standalone #"
            )
        ruby_end = a + len(value.rstrip(" \t")) if separators else b
        if continuation:
            if not units or not units[-1].segments or units[-1].start == units[-1].end:
                raise ValueError(
                    f"record {source.record_index}, text offset {a}: continuation needs a preceding timed text unit"
                )
            unit = units[-1]
            first, last = unit.start, unit.end
        else:
            first, last = append_body(a, split)
            if ruby_end < b:
                _, last = append_body(ruby_end, b)
        ruby = None
        if separators:
            ruby_start = split + 1
            mode: Literal["join", "break", "spill"] = "join"
            if ruby_start < ruby_end and text[ruby_start] in "!！<＜":
                mode = "break" if text[ruby_start] in "!！" else "spill"
                ruby_start += 1
            if first == last and ruby_start < ruby_end:
                raise ValueError(
                    f"record {source.record_index}, text offset {a}: ruby needs visible body text"
                )
            ruby = RubyText(
                replace(source, runs=_slice(source, ruby_start, ruby_end), timing=(), cues=()),
                (LyricMapping(ruby_start, ruby_end, 0, ruby_end - ruby_start),),
                mode,
            )
        segment = LyricSegment(
            replace(span, start_offset=first, end_offset=last), a, b, ruby
        )
        if continuation:
            units[-1] = replace(units[-1], segments=(*units[-1].segments, segment))
        else:
            units.append(LyricUnit(first, last, (segment,)))

    if previous < len(text):
        if any(c in text[previous:] for c in "|｜#＃"):
            raise ValueError("ruby or continuation requires a singing tag")
        units.append(LyricUnit(*append_body(previous, len(text))))

    # Anchor positions must resolve to body text, never silently jump out of ruby.
    cues = []
    for cue in source.cues:
        choices = [
            m.start + cue.offset - m.source_start
            for m in mapping
            if m.source_start <= cue.offset <= m.source_end
        ]
        if cue.offset == 0:
            choices.append(0)
        if cue.offset == len(text):
            choices.append(size)
        if not choices:
            raise ValueError(
                f"record {source.record_index}, cue {cue.id}: anchor lies inside ruby or continuation syntax"
            )
        cues.append(replace(cue, offset=choices[-1]))
    projected = replace(source, runs=tuple(body), timing=(), cues=tuple(cues))
    return DocumentLyrics(source, projected, tuple(mapping), tuple(units))
