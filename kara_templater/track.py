"""Explicit track configuration; binding is separate from reusable declarations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import replace
from typing import Literal

from ._track_compiler import BoundTrack, bind_track
from .components import Body, Ruby
from .composition import Paint
from .karaoke import HighlightStyle, KaraokeItem, Sweep
from .matching import SourceMatch
from .model import LaidOutLine
from .motion import Animation
from .sampling import SamplingSettings
from .stylesheet import UNSET, StyleKeyword, StyleSheet
from .text_style import PaintStyle, TextStyle
from .timeline import EdgeSweep, HighlightTrack
from .track_layout import Layout

_DEFAULT_PAINT = PaintStyle()
_DEFAULT_SWEEP = Sweep()
_DEFAULT_SAMPLING = SamplingSettings()


class Overlay:
    """A sung paint/reveal declaration for Body and Ruby roles.

    Optional named highlights, styles, and overlap policy provide explicit parallel
    composition.
    """

    def __init__(
        self,
        *,
        style: PaintStyle = _DEFAULT_PAINT,
        reveal: Sweep = _DEFAULT_SWEEP,
        targets: tuple[type[Body] | type[Ruby], ...] | None = None,
        body: PaintStyle | None | Literal[StyleKeyword.UNSET] = UNSET,
        ruby: PaintStyle | None | Literal[StyleKeyword.UNSET] = UNSET,
        highlights: tuple[HighlightTrack, ...]
        | Callable[[LaidOutLine], tuple[HighlightTrack, ...]]
        | None = None,
        styles: tuple[HighlightStyle, ...] = (),
        overlap: Literal["union", "priority", "layer"] = "union",
    ) -> None:
        if (
            isinstance(style, TextStyle)
            or isinstance(body, TextStyle)
            or isinstance(ruby, TextStyle)
        ):
            raise TypeError("Overlay accepts PaintStyle, not layout-changing TextStyle")
        if targets is not None and (
            len(set(targets)) != len(targets)
            or any(t not in (Body, Ruby) for t in targets)
        ):
            raise ValueError("overlay targets must be distinct Body/Ruby roles")
        if reveal.edges != EdgeSweep():
            raise ValueError(
                "Track overlays do not accept edge padding or timing compensation"
            )
        self.style, self.reveal, self.targets = style, reveal, targets
        self.body, self.ruby = body, ruby
        if overlap not in {"union", "priority", "layer"}:
            raise ValueError("overlay overlap must be union, priority or layer")
        self.highlights, self.styles, self.overlap = highlights, styles, overlap

    def enabled(self, role: type[Body] | type[Ruby]) -> bool:
        """Whether this overlay applies to the requested Body or Ruby role."""
        return (self.targets is None or role in self.targets) and (
            self.body if role is Body else self.ruby
        ) is not None

    def resolve(self, role: type[Body] | type[Ruby], base: Paint) -> Paint:
        """Resolve shared and role-specific sung paint against the selected base Paint."""
        if not self.enabled(role):
            return base
        result = self.style.resolve(base)
        local = self.body if role is Body else self.ruby
        return (
            local.resolve(result, inherited=base)
            if isinstance(local, PaintStyle)
            else result
        )


class Track:
    """Reusable lyric selection, body/ruby appearance, overlay, layout, and animation declarations.

    prepare_tracks binds a fresh configuration per source and produces composable
    Scene content.
    """

    def __init__(
        self,
        *,
        source: SourceMatch,
        body: Body | None = None,
        ruby: Ruby | None = None,
        overlay: Overlay | None = None,
        layout: Layout | None = None,
        animations: Iterable[Animation] = (),
        sampling: SamplingSettings = _DEFAULT_SAMPLING,
        styles: StyleSheet | None = None,
    ) -> None:
        self.source = source
        self.body = Body() if body is None else body
        self.ruby, self.overlay, self.layout = ruby, overlay, layout
        self.animations, self.sampling = tuple(animations), sampling
        self.styles = StyleSheet() if styles is None else styles
        if (
            overlay is not None
            and overlay.targets is not None
            and Ruby in overlay.targets
            and ruby is None
        ):
            raise ValueError(
                "overlay explicitly targets Ruby but the track has no Ruby"
            )

    def bind(self, items: tuple[KaraokeItem, ...]) -> dict[str, BoundTrack]:
        """Bind fresh Track configurations to structured source items for internal/backend inspection.

        Use prepare_tracks for normal Document authoring.
        """
        return bind_track(self, items)


class TrackGroup:
    """Explicit shared row allocation for independently configured tracks.

    Children keep their source selectors, styles and animations. The group owns
    placement; children must omit layout. A shared absolute origin is required
    so different input style positions cannot move the allocated rows apart.
    """

    def __init__(self, *tracks: Track, layout: Layout) -> None:
        if not tracks or any(not isinstance(track, Track) for track in tracks):
            raise TypeError("TrackGroup requires one or more Track instances")
        if layout.position is None:
            raise ValueError("TrackGroup layout requires an explicit position")
        if any(track.layout is not None for track in tracks):
            raise ValueError("TrackGroup owns layout; child Tracks must omit layout")
        self.tracks = tracks
        self.layout = layout

    def bind(self, items: tuple[KaraokeItem, ...]) -> dict[str, BoundTrack]:
        """Bind child configurations with shared row allocation for internal/backend inspection."""
        return bind_tracks((self,), items)


def bind_tracks(
    declarations: tuple[Track | TrackGroup, ...],
    items: tuple[KaraokeItem, ...],
) -> dict[str, BoundTrack]:
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate karaoke item ids")
    entries: list[tuple[Track, int | None]] = []
    for index, declaration in enumerate(declarations):
        if isinstance(declaration, TrackGroup):
            if declaration.layout.position is None:
                raise ValueError("TrackGroup layout requires an explicit position")
            for child in declaration.tracks:
                if child.layout is not None:
                    raise ValueError(
                        "TrackGroup owns layout; child Tracks must omit layout"
                    )
                entries.append((child, index))
        else:
            entries.append((declaration, None))
    selected: list[list[KaraokeItem]] = [[] for _ in entries]
    grouped: dict[int, list[KaraokeItem]] = {}
    for item in items:
        matches = [
            index for index, (track, _) in enumerate(entries) if track.source(item)
        ]
        if len(matches) > 1:
            raise ValueError(f"{item.id}: multiple Tracks match the same input")
        if matches:
            index = matches[0]
            selected[index].append(item)
            group_index = entries[index][1]
            if group_index is not None:
                grouped.setdefault(group_index, []).append(item)
    bound: dict[str, BoundTrack] = {}
    for (track, _), selection in zip(entries, selected, strict=True):
        bound.update(track.bind(tuple(selection)))
    for index, selection in grouped.items():
        group = declarations[index]
        assert isinstance(group, TrackGroup)
        layout = deepcopy(group.layout)
        rows = layout.allocate(
            tuple(replace(item, window=bound[item.id].window) for item in selection)
        )
        for item in selection:
            value = bound[item.id]
            # bind() returns isolated per-line configuration. Neither the shared
            # declaration nor the allocator's transient state escapes this render.
            value.config.layout = deepcopy(group.layout)
            bound[item.id] = replace(value, row=rows[item.id])
    return bound
