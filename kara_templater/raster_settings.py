"""Output capability diagnostics for the raster preview."""

from .sources import EventOrigin


class OutputCapabilityError(ValueError):
    """An output failure with optional source and absolute-time context."""

    def __init__(
        self,
        message: str,
        *,
        origin: EventOrigin | None = None,
        time_ms: float | None = None,
    ) -> None:
        super().__init__(message)
        self.origin = origin
        self.time_ms = time_ms
        if origin is not None:
            self.add_note(
                f"effect={origin.effect}; sources={origin.sources!r}; "
                f"tracks={origin.track_ids!r}"
            )

