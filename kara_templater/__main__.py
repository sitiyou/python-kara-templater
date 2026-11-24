import argparse
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ._cli_preset import preset_scene
from .ass import Document
from .composition import Color
from .lyrics.tracks import Track, build_lyric_scene
from .output.ass_export import AssBudget
from .scene import Scene


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export lyric Tracks or Scenes as a standalone libplacebo hook"
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
        help="output owner for presets and Tracks (default: default)",
    )
    parser.add_argument(
        "--style",
        action="append",
        help="import only this style; repeat for several styles",
    )
    parser.add_argument(
        "--before",
        type=Color.hex,
        help="fill before the wipe #RRGGBB",
    )
    parser.add_argument(
        "--after", type=Color.hex, help="fill after the wipe #RRGGBB"
    )
    parser.add_argument(
        "--pulse", choices=("none", "char", "chars", "syllable"), default="none"
    )
    parser.add_argument(
        "--lead-ms", type=int, default=0, help="extend display before source event"
    )
    parser.add_argument(
        "--tail-ms", type=int, help="override automatic display tail (milliseconds)"
    )
    parser.add_argument("--fade-in-ms", type=int, default=0)
    parser.add_argument("--fade-out-ms", type=int, default=0)
    parser.add_argument("--ass", action="store_true", help="export native ASS")
    parser.add_argument("--fps", type=int, default=60, help="hook frame rate")
    parser.add_argument("--max-events", type=int, help="limit generated ASS events")
    parser.add_argument("--max-bytes", type=int, help="limit Hook file or generated ASS event bytes")
    parser.add_argument("--max-active", type=int, help="limit simultaneously active ASS events")
    args = parser.parse_args()
    owner = "default" if args.owner is None else args.owner
    try:
        if not args.ass and (args.max_events is not None or args.max_active is not None):
            raise ValueError("--max-events and --max-active require --ass; use --max-bytes for Hook output")
        if args.max_bytes is not None and args.max_bytes < 1:
            raise ValueError("byte budget must be a positive integer")
        defaults = AssBudget()
        budget = AssBudget(
            max_events=10000 if args.max_events is None else args.max_events,
            max_bytes=defaults.max_bytes if args.max_bytes is None else args.max_bytes,
            max_active=defaults.max_active if args.max_active is None else args.max_active,
        )
        if min(args.lead_ms, args.tail_ms or 0, args.fade_in_ms, args.fade_out_ms) < 0:
            raise ValueError("display padding and fade durations must be nonnegative")
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
                    args.lead_ms
                    or args.tail_ms
                    or args.style
                    or args.owner is not None
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
                if args.lead_ms or args.tail_ms or args.style:
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
                owner=owner,
                before=args.before,
                after=args.after,
                pulse=args.pulse,
                fade_in=args.fade_in_ms / 1000,
                fade_out=args.fade_out_ms / 1000,
                preview=args.lead_ms / 1000,
                tail=None if args.tail_ms is None else args.tail_ms / 1000,
                styles=tuple(args.style) if args.style else None,
            )
        if scene is None:
            assert tracks is not None
            scene = build_lyric_scene(document, tracks=tracks, owner=owner)
        if not args.ass:
            scene.export(args.output, fps=args.fps, max_bytes=args.max_bytes)
            return
        result = scene.ass.compile(budget=budget)
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
