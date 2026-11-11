"""Source-mapped visual targets, before sweep partitioning or ASS expansion."""

from dataclasses import dataclass, replace

from .animation import ScaleAnimation
from .appearance import PaintPair, resolve_ruby_paints
from .ass import Style
from .ass_output import Fade, OutputCapabilityError
from .characters import TextRange
from .model import Box, Segment
from .sources import EventOrigin, SourceRef
from .timeline import DisplayWindow, HighlightTrack, Region


@dataclass(frozen=True)
class VisualTarget:
    id: str
    text: str
    box: Box
    body: Region
    paints: PaintPair
    tracks: tuple[HighlightTrack, ...]
    animations: tuple[ScaleAnimation, ...]
    style: Style
    sources: tuple[SourceRef, ...]
    ink: Box | None = None
    kind: str = "body"
    singing: tuple[Segment, ...] = ()
    text_range: TextRange | None = None
    fade: Fade | None = None


@dataclass(frozen=True)
class PreparedLyrics:
    targets: tuple[VisualTarget, ...]
    window: DisplayWindow
    diagnostics: tuple[str, ...] = ()


def layout_targets(
    target,
    context,
    *,
    characters,
    appearances,
    tracks,
    animation,
    ruby,
    ruby_paints,
    pulses,
    effect_name,
):
    layout = context.layout
    result = []

    def emit(*args, **kwargs):
        result.append(VisualTarget(*args, **kwargs))

    for appearance in appearances:
        char = appearance.character
        if not char.target.drawable:
            continue
        box = layout.units[char.source.unit_index].box
        emit(
            char.id,
            char.text,
            char.box,
            Region(box.left, box.right),
            appearance.paints,
            tuple(t for t in tracks if t.unit_index == char.source.unit_index),
            tuple(a for a in animation.animations if a.target_id == char.id),
            context.style,
            tuple(
                SourceRef(target.id, char.source.unit_index, si)
                for si in range(len(layout.units[char.source.unit_index].segments))
            )
            or (SourceRef(target.id, char.source.unit_index),),
            char.ink_bounds,
            singing=layout.units[char.source.unit_index].source.segments,
            text_range=char.source,
        )

    if ruby.enabled:
        ruby_paints = resolve_ruby_paints(layout, appearances, overrides=ruby_paints)
        if ruby.follow == "syllable" and any(p.target != "syllable" for p in pulses):
            raise OutputCapabilityError(
                f"{target.id}: ruby syllable following requires syllable-target pulses",
                origin=EventOrigin((SourceRef(target.id),), effect_name),
            )
        for appearance in ruby_paints:
            ui, si = appearance.unit_index, appearance.segment_index
            segment = layout.units[ui].segments[si]
            box = replace(segment.ruby, top=segment.ruby.top + ruby.offset_y)
            if segment.right <= segment.left:
                raise OutputCapabilityError(
                    f"{target.id}/ruby:{ui}:{si}: zero-width body mapping requires explicit timing",
                    origin=EventOrigin((SourceRef(target.id, ui, si),), effect_name),
                )
            ratio = box.width / (segment.right - segment.left)
            mapped = []
            for track in tracks:
                if track.unit_index != ui:
                    continue
                passes = tuple(
                    replace(
                        p,
                        region=Region(
                            box.left + (p.region.left - segment.left) * ratio,
                            box.left + (p.region.right - segment.left) * ratio,
                        ),
                    )
                    for p in track.passes
                )
                if passes:
                    mapped.append(replace(track, passes=passes))
            followers = ()
            if ruby.follow == "syllable":
                first = next(
                    (
                        c
                        for c in characters
                        if c.source.unit_index == ui and c.target.drawable
                    ),
                    None,
                )
                if first:
                    followers = tuple(
                        a for a in animation.animations if a.target_id == first.id
                    )
            emit(
                f"ruby:{ui}:{si}",
                segment.source.ruby,
                box,
                Region(box.left, box.right),
                appearance.paints,
                tuple(mapped),
                followers,
                context.ruby_style,
                (SourceRef(target.id, ui, si),),
                kind="ruby",
                singing=(segment.source,),
            )
    return PreparedLyrics(tuple(result), animation.window, animation.diagnostics)
