"""Source traversal independent of layout, paint ranges and singing tracks."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@contextmanager
def _source_location(unit_index, segment_index=None):
    """Carry local indices until the caller can supply an item/effect identity."""
    try:
        yield
    except Exception as error:
        if not hasattr(error, "source_indices"):
            # Metadata is attached to arbitrary exception types.
            setattr(  # noqa: B010
                error, "source_indices", ((unit_index, segment_index),)
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

    def __post_init__(self) -> None:
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

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id:
            raise ValueError("source reference needs a nonempty item id")
        for index in (self.unit_index, self.segment_index):
            if index is not None and (type(index) is not int or index < 0):
                raise ValueError("source indices must be nonnegative integers")
        if self.segment_index is not None and self.unit_index is None:
            raise ValueError("segment reference requires a unit index")
