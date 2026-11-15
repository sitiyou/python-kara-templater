import argparse
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

from .animation import Pulse
from .ass import Document
from .ass_output import OutputSettings
from .components import Body, Ruby
from .composition import Color
from .engine import apply_templates
from .import_ass import ImportSettings, paint_pair_from_style
from .matching import LineMatch
from .motion import (
    Animate,
    Animation,
    FadeInAnimation,
    FadeOutAnimation,
    HighlightAnimation,
    On,
    Syllable,
)
from .properties import Transition, there_and_back
from .raster_settings import RasterSettings
from .render import RenderEstimate, prepare_tracks
from .scene import Scene
from .scene_output import SceneBudget
from .text_style import PaintStyle, TextStyle
from .track import Overlay, Track, TrackGroup


def _preset_tracks(
    document: Document,
    *,
    before: Color | None,
    after: Color | None,
    pulse: str,
    fade_in_ms: int,
    fade_out_ms: int,
) -> tuple[Track, ...]:
    animations: list[Animation] = []
    if fade_in_ms:
        animations.append(FadeInAnimation(duration=fade_in_ms))
    if fade_out_ms:
        animations.append(FadeOutAnimation(duration=fade_out_ms))
    if pulse in {"char", "chars"}:
        trigger = Pulse() if pulse == "char" else Pulse.simultaneous_chars()
        animations.append(HighlightAnimation(trigger=trigger))
    elif pulse == "syllable":
        animations.append(
            On(Syllable.Singing, Animate(scale=Transition(1, 1.1, rate=there_and_back)))
        )
    return tuple(
        Track(
            source=LineMatch(style=name),
            body=Body(
                style=TextStyle(
                    fill=paints.before.fill if before is None else before,
                    opacity=paints.before.opacity,
                )
            ),
            ruby=Ruby(),
            overlay=Overlay(
                style=PaintStyle(
                    fill=paints.after.fill if after is None else after,
                    opacity=paints.after.opacity,
                )
            ),
            animations=animations,
        )
        for name, style in document.styles.items()
        for paints in (paint_pair_from_style(style),)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate standard ASS from lyric Tracks, Scenes, or Python templates"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--effect",
        type=Path,
        help="Python file exporting tracks or build(document) -> Scene",
    )
    parser.add_argument(
        "--owner",
        help="output owner (defaults to legacy-templates with --templates, otherwise default)",
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="explicitly execute trusted v0.1.0 Python templates",
    )
    parser.add_argument(
        "--video-size",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        help="legacy template aspect correction (requires --templates)",
    )
    parser.add_argument(
        "--raster",
        action="store_true",
        help="pre-blur material compositing for Track scripts (higher output cost)",
    )
    parser.add_argument(
        "--raster-color-error",
        type=int,
        help="maximum spatial color error in 0..255 before ASS transforms (requires --raster; default 0)",
    )
    parser.add_argument(
        "--style",
        action="append",
        help="import only this style; repeat for several styles",
    )
    parser.add_argument(
        "--before",
        type=Color.hex,
        help="unsung #RRGGBB; defaults to ASS secondary color",
    )
    parser.add_argument(
        "--after", type=Color.hex, help="sung #RRGGBB; defaults to ASS primary color"
    )
    parser.add_argument(
        "--pulse", choices=("none", "char", "chars", "syllable"), default="none"
    )
    parser.add_argument(
        "--lead-ms", type=int, default=0, help="extend display before source event"
    )
    parser.add_argument(
        "--tail-ms", type=int, default=0, help="extend display after source event"
    )
    parser.add_argument("--fade-in-ms", type=int, default=0)
    parser.add_argument("--fade-out-ms", type=int, default=0)
    parser.add_argument("--max-events", type=int, default=10000)
    parser.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--max-active", type=int, default=1000)
    args = parser.parse_args()
    requested_owner = args.owner
    if args.owner is None:
        args.owner = "legacy-templates" if args.templates else "default"
    try:
        budget = SceneBudget(
            max_events=args.max_events,
            max_bytes=args.max_bytes,
            max_active=args.max_active,
        )
        if args.video_size is not None and not args.templates:
            raise ValueError("--video-size requires --templates")
        if args.templates:
            if (
                args.effect
                or args.raster
                or args.raster_color_error is not None
                or args.style
                or args.before
                or args.after
                or args.pulse != "none"
                or args.lead_ms
                or args.tail_ms
                or args.fade_in_ms
                or args.fade_out_ms
            ):
                raise ValueError(
                    "--templates cannot be combined with effect/preset options"
                )
            size = (
                None
                if args.video_size is None
                else (args.video_size[0], args.video_size[1])
            )
            result = apply_templates(
                Document.load(args.input),
                video_size=size,
                owner=args.owner,
                budget=budget,
            )
            result.save(args.output)
            return
        if args.raster_color_error is not None and not args.raster:
            raise ValueError("--raster-color-error requires --raster")
        raster_settings = (
            RasterSettings(max_channel_error=args.raster_color_error or 0)
            if args.raster
            else None
        )
        document = Document.load(args.input)
        scene: Scene | None = None
        tracks: tuple[Track | TrackGroup, ...] | None = None
        if args.effect:
            if (
                args.before
                or args.after
                or args.pulse != "none"
                or args.fade_in_ms
                or args.fade_out_ms
            ):
                raise ValueError(
                    "configure colors, pulses and fades in --effect rather than combining recipe and preset options"
                )
            namespace = runpy.run_path(str(args.effect))
            builder = namespace.get("build")
            declared_tracks = namespace.get("tracks")
            if builder is not None and declared_tracks is not None:
                raise ValueError(
                    "effect file must export either tracks or build, not both"
                )
            if builder is not None:
                if (
                    args.raster
                    or args.lead_ms
                    or args.tail_ms
                    or args.style
                    or requested_owner is not None
                ):
                    raise ValueError(
                        "configure input, timing, materials and owner inside build(document)"
                    )
                if not callable(builder):
                    raise TypeError(
                        "build must be callable as build(document) -> Scene"
                    )
                built = cast(Callable[[Document], object], builder)(document)
                if not isinstance(built, Scene):
                    raise TypeError("build(document) must return Scene")
                scene = built
            if declared_tracks is not None:
                if not isinstance(declared_tracks, (tuple, list)) or not all(
                    isinstance(track, (Track, TrackGroup)) for track in declared_tracks
                ):
                    raise TypeError(
                        "tracks must be a sequence of Track or TrackGroup instances"
                    )
                validated_tracks: list[Track | TrackGroup] = []
                for track in declared_tracks:
                    assert isinstance(track, (Track, TrackGroup))
                    validated_tracks.append(track)
                tracks = tuple(validated_tracks)
            if scene is None and tracks is None:
                raise ValueError(
                    "effect file must export tracks or build(document) -> Scene"
                )
        else:
            tracks = _preset_tracks(
                document,
                before=args.before,
                after=args.after,
                pulse=args.pulse,
                fade_in_ms=args.fade_in_ms,
                fade_out_ms=args.fade_out_ms,
            )

        def report_estimate(estimate: RenderEstimate) -> None:
            if estimate.sampling or estimate.raster:
                print(
                    f"Preflight: {estimate.target_samples} property samples, "
                    f"estimated {estimate.estimated_events} events before merging/subdivision "
                    f"(limit {estimate.event_limit})",
                    flush=True,
                )

        if scene is not None:
            result = scene.compile(budget=budget)
        else:
            assert tracks is not None
            prepared = prepare_tracks(
                document,
                tracks=tracks,
                mode="native",
                owner=args.owner,
                on_estimate=report_estimate,
                import_settings=ImportSettings(
                    args.lead_ms,
                    args.tail_ms,
                    tuple(args.style) if args.style else None,
                ),
                settings=OutputSettings(
                    (document.meta.res_x, document.meta.res_y),
                    max_events=args.max_events,
                    raster=raster_settings,
                ),
            )
            result = prepared.compile(budget=budget)
        result.document.save(args.output)
        print(
            f"Generated {result.event_count} events ({result.peak_active} active, {result.byte_count} bytes)"
        )
        for diagnostic in dict.fromkeys(result.diagnostics):
            print(diagnostic)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        notes = "".join(f"  {note}\n" for note in getattr(error, "__notes__", ()))
        parser.exit(1, f"kara-templater: {error}\n{notes}")


if __name__ == "__main__":
    main()
