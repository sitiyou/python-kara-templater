"""多层辉光与整音节强调：python -m examples.layered_glow input.ass output.ass。"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    Color,
    Document,
    DynamicEffect,
    DynamicProperties,
    EdgeSweep,
    Fade,
    Glow,
    KaraokeEffect,
    Line,
    OutputSettings,
    Paint,
    PaintPair,
    ProgressCurve,
    Pulse,
    RubyPolicy,
    SamplingSettings,
    Segment,
    Sweep,
    render_karaoke,
)


class LayeredGlow:
    """白字黑边 → 青字白边，配合整音节辉光增强和 1.1 倍缩放。"""

    def build(self, item, context):
        guide = item.style == "LEAD"
        plan = KaraokeEffect(
            paints=PaintPair(
                before=Paint(Color.hex("#ffffff"), Color.hex("#000000"), border=5),
                after=Paint(Color.hex("#01829d"), Color.hex("#ffffff"), border=5),
            ),
            sweep=Sweep(
                progress_curve=ProgressCurve()
                if guide
                else ProgressCurve.two_stage(
                    time_fraction=3 / 17, progress_fraction=0.3
                ),
                edges=EdgeSweep(padding_px=24, lead_ms=24, tail_ms=24),
            ),
            pulses=() if guide else (Pulse.whole_syllable(scale=1.1),),
            ruby=RubyPolicy(enabled=not guide, offset_y=10, follow="syllable"),
            fade=Fade(in_ms=800, out_ms=200),
        ).build(item, context)

        body, halos, timings, seen = [], [], {}, set()
        for layer in plan.layers:
            ruby = layer.style.name == context.ruby_style.name
            if ruby:
                layer = replace(layer, paint=replace(layer.paint, border=3))
            body.append(layer)
            identity = layer.animation_id
            if identity in seen:
                continue
            seen.add(identity)

            # 扫色会把同一个字拆成多个区域/时段；辉光只画一次，且不随前沿裁剪。
            halo = replace(layer, clips=None, active_window=None)
            for suffix, order, color, opacity in (
                ("base-glow", -2, "#9e6d64", 0.8),
                ("sung-glow", -1, "#67e5ff", 0.2),
            ):
                glow_id = f"{identity}/{suffix}"
                glow = Glow(
                    Color.hex(color), blur=10, border=6 if ruby else 10, opacity=opacity
                )
                halos.append(
                    replace(
                        halo,
                        source_id=glow_id,
                        animation_id=glow_id,
                        component="glow",
                        order=order,
                        paint=Paint(glow=glow),
                    )
                )
                if suffix == "sung-glow":
                    segments = [ref.resolve(item) for ref in layer.origin.sources]
                    segments = [s for s in segments if isinstance(s, Segment)]
                    if segments:
                        timings[glow_id] = (
                            min(s.start_ms for s in segments),
                            max(s.end_ms for s in segments),
                        )

        def brightness(sample):
            if sample.target_id not in timings:
                return DynamicProperties()
            start, end = timings[sample.target_id]
            progress = (sample.time_ms - start) / max(1, end - start)
            return DynamicProperties(glow_opacity=0.2 + 0.6 * min(1, max(0, progress)))

        return replace(
            plan,
            layers=(*halos, *body),
            dynamic=DynamicEffect(brightness, SamplingSettings(step_ms=40)),
        )


def apply(input_path, output_path):
    document = Document.load(input_path)
    # 仅读取歌词时间，不保留或执行输入中的 template/code 注释。
    document.records = [
        r for r in document.records if not isinstance(r, Line) or not r.comment
    ]
    # 字体沿用输入中各个样式的设置，由系统字体提供器查找。
    for name, style in document.styles.items():
        style.fontsize, style.spacing, style.shadow = 96, 0, 0
        style.margin_l = style.margin_r = 64
        style.align, style.margin_v = {"K1": (1, 240), "K2": (3, 48), "LEAD": (1, 432)}[
            name
        ]

    result = render_karaoke(
        document,
        effect=LayeredGlow(),
        owner="layered-glow",
        settings=OutputSettings(resolution=(1920, 1080), max_events=1_000_000),
    )
    result.document.save(output_path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = apply(args.input, args.output)
    print(
        f"已生成 {args.output}：{result.event_count} 个事件，{len(result.diagnostics)} 条诊断。"
    )


if __name__ == "__main__":
    main()
