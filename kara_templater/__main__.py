import argparse
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ._cli_preset import preset_scene
from .ass import Document
from .composition import Color
from .engine import apply_templates
from .orchestration import Track, prepare_tracks
from .raster_settings import RasterSettings
from .scene import Scene
from .scene_output import SceneBudget


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
        help="explicit coverage compositing for the default preset (higher output cost)",
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
        if min(args.lead_ms, args.tail_ms, args.fade_in_ms, args.fade_out_ms) < 0:
            raise ValueError("display padding and fade durations must be nonnegative")
        if args.raster_color_error is not None and not args.raster:
            raise ValueError("--raster-color-error requires --raster")
        raster_settings = (
            RasterSettings(max_channel_error=args.raster_color_error or 0)
            if args.raster
            else None
        )
        document = Document.load(args.input)
        scene: Scene | None = None
        tracks: tuple[Track, ...] | None = None
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
                if args.raster or args.lead_ms or args.tail_ms or args.style:
                    raise ValueError(
                        "configure timing, selection and materials inside tracks"
                    )
                if not isinstance(declared_tracks, (tuple, list)) or not all(
                    isinstance(track, Track) for track in declared_tracks
                ):
                    raise TypeError(
                        "tracks must be a sequence of orchestration.Track instances"
                    )
                validated_tracks: list[Track] = []
                for track in declared_tracks:
                    assert isinstance(track, Track)
                    validated_tracks.append(track)
                tracks = tuple(validated_tracks)
            if scene is None and tracks is None:
                raise ValueError(
                    "effect file must export tracks or build(document) -> Scene"
                )
        else:
            scene = preset_scene(
                document,
                owner=args.owner,
                before=args.before,
                after=args.after,
                pulse=args.pulse,
                fade_in=args.fade_in_ms / 1000,
                fade_out=args.fade_out_ms / 1000,
                preview=args.lead_ms / 1000,
                tail=args.tail_ms / 1000,
                styles=tuple(args.style) if args.style else None,
                raster=raster_settings,
            )
        if scene is None:
            assert tracks is not None
            scene = prepare_tracks(document, tracks=tracks, owner=args.owner)
        if raster_settings is not None:
            print(
                f"Coverage: spatial color tolerance {raster_settings.max_channel_error}/255 "
                "before ASS transforms; not a YUV420 video error bound.",
                flush=True,
            )
        result = scene.compile(budget=budget)
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
