"""Source traversal independent of layout, paint ranges and singing tracks."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .model import KaraokeLine, Segment, TextUnit

if TYPE_CHECKING:
    from .recipe import KaraokeItem


@contextmanager
def _source_location(unit_index, segment_index=None, *, track_ids=()):
    """Carry local indices until the caller can supply an item/effect identity."""
    try:
        yield
    except Exception as error:
        if not hasattr(error, "source_indices"):
            error.source_indices = ((unit_index, segment_index),)
        if track_ids and not hasattr(error, "source_track_ids"):
            error.source_track_ids = tuple(dict.fromkeys(track_ids))
        raise


@contextmanager
def _source_context(origin):
    """Enrich the original exception without replacing its type or traceback."""
    try:
        yield
    except Exception as error:
        if getattr(error, "origin", None) is None:
            indices = getattr(error, "source_indices", ())
            track_ids = getattr(error, "source_track_ids", origin.track_ids)
            if indices and len(origin.sources) == 1:
                origin = EventOrigin(
                    tuple(
                        SourceRef(origin.sources[0].item_id, ui, si)
                        for ui, si in indices
                    ),
                    origin.effect,
                    track_ids,
                )
            error.origin = origin
            error.add_note(
                f"effect={origin.effect}; sources={origin.sources!r}; tracks={origin.track_ids!r}"
            )
        raise


@dataclass(frozen=True)
class EventOrigin:
    """Source dependencies, not a claim that one segment owns an event's time.

    A body glyph can depend on every segment in its unit. Explicit tracks are
    independent of source segments; their IDs are recorded separately.
    """

    sources: tuple["SourceRef", ...]
    effect: str
    track_ids: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "track_ids", tuple(self.track_ids))
        if not self.sources or not all(isinstance(s, SourceRef) for s in self.sources):
            raise ValueError("event origin requires source references")
        if not isinstance(self.effect, str) or not self.effect:
            raise ValueError("event origin requires an effect name")
        if any(not isinstance(t, str) or not t for t in self.track_ids):
            raise ValueError("event origin track ids must be nonempty strings")


@dataclass(frozen=True)
class SourceRef:
    """Address within an item, stable while its source structure is unchanged.

    Item order, layout and effects do not affect addresses. Editing/reordering
    units or segments creates a new source structure; indices are not edit IDs.
    """

    item_id: str
    unit_index: int | None = None
    segment_index: int | None = None

    def __post_init__(self):
        if not isinstance(self.item_id, str) or not self.item_id:
            raise ValueError("source reference needs a nonempty item id")
        for index in (self.unit_index, self.segment_index):
            if index is not None and (type(index) is not int or index < 0):
                raise ValueError("source indices must be nonnegative integers")
        if self.segment_index is not None and self.unit_index is None:
            raise ValueError("segment reference requires a unit index")

    def resolve(self, item: "KaraokeItem") -> KaraokeLine | TextUnit | Segment:
        """Return the original source object; never a layout or generated copy."""
        if item.id != self.item_id:
            raise ValueError(
                f"source reference belongs to {self.item_id!r}, not {item.id!r}"
            )
        if self.unit_index is None:
            return item.source
        try:
            unit = item.source.units[self.unit_index]
            return (
                unit
                if self.segment_index is None
                else unit.segments[self.segment_index]
            )
        except IndexError as error:
            raise ValueError(
                f"source reference is outside item structure: {self!r}"
            ) from error


def walk_karaoke(
    items: Iterable["KaraokeItem"],
    *,
    level: Literal["line", "unit", "segment"] = "segment",
) -> Iterator[tuple[SourceRef, KaraokeLine | TextUnit | Segment]]:
    """Visit sources in input order, including empty and zero-duration sources.

    Static units appear at unit level and have no segment visits. Times never
    sort or filter the source; simultaneous lines and repeated readings retain
    distinct addresses. IDs are validated before any visits are yielded.
    """
    if level not in {"line", "unit", "segment"}:
        raise ValueError("source traversal level must be line, unit or segment")
    items = tuple(items)
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate karaoke item ids")
    for item in items:
        if level == "line":
            yield SourceRef(item.id), item.source
            continue
        for unit_index, unit in enumerate(item.source.units):
            if level == "unit":
                yield SourceRef(item.id, unit_index), unit
                continue
            for segment_index, segment in enumerate(unit.segments):
                yield SourceRef(item.id, unit_index, segment_index), segment
