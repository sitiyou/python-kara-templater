import argparse
import runpy
from dataclasses import replace
from pathlib import Path

from .animation import Pulse
from .appearance import PaintPair
from .ass import Document
from .ass_output import Fade, OutputSettings
from .composition import Color
from .import_ass import ImportSettings, paint_pair_from_style
from .recipe import KaraokeEffect
from .render import render_karaoke


def main():
    parser = argparse.ArgumentParser(
        description="Render ASS karaoke using Python effect recipes"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--effect",
        type=Path,
        help="Python file exporting effect or build(item, context)",
    )
    parser.add_argument("--owner", default="default")
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
    args = parser.parse_args()
    try:
        document = Document.load(args.input)
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
            effect = namespace.get("effect", namespace.get("build"))
            if effect is None:
                raise ValueError(
                    "effect file must export effect or build(item, context)"
                )
        else:
            pulses = {
                "none": (),
                "char": (Pulse.each_char(),),
                "chars": (Pulse.simultaneous_chars(),),
                "syllable": (Pulse.whole_syllable(),),
            }[args.pulse]

            def effect(target, context):
                paints = paint_pair_from_style(context.style)
                paints = PaintPair(
                    replace(paints.before, fill=args.before)
                    if args.before
                    else paints.before,
                    replace(paints.after, fill=args.after)
                    if args.after
                    else paints.after,
                )
                return KaraokeEffect(
                    paints=paints,
                    pulses=pulses,
                    fade=Fade(args.fade_in_ms, args.fade_out_ms),
                ).build(target, context)

        def report_estimate(estimate):
            if estimate.sampling:
                print(
                    f"Preflight: {estimate.target_samples} property samples, "
                    f"estimated {estimate.estimated_events} events before merging/subdivision "
                    f"(limit {estimate.event_limit})",
                    flush=True,
                )

        result = render_karaoke(
            document,
            effect=effect,
            owner=args.owner,
            on_estimate=report_estimate,
            import_settings=ImportSettings(
                args.lead_ms, args.tail_ms, tuple(args.style) if args.style else None
            ),
            settings=OutputSettings(
                (document.meta.res_x, document.meta.res_y), max_events=args.max_events
            ),
        )
        result.document.save(args.output)
        print(
            f"Generated {result.event_count} events ({result.layer_count} planned layers)"
        )
        for diagnostic in dict.fromkeys(result.diagnostics):
            print(diagnostic)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        notes = "".join(f"  {note}\n" for note in getattr(error, "__notes__", ()))
        parser.exit(1, f"kara-templater: {error}\n{notes}")


if __name__ == "__main__":
    main()
