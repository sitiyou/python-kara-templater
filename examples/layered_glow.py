"""Track 辉光与整音节强调：python -m examples.layered_glow input.ass output.ass。

固定输入见 tests/fixtures/layered_glow.ass；无需输入文件的场景版见 scene_lyrics。
Track 的变色 Blur 与旧双 Halo 不逐像素等价，详见 docs/scene-authoring.md。
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    WHITE,
    Blur,
    Body,
    Color,
    Document,
    FadeInAnimation,
    FadeOutAnimation,
    Line,
    LineMatch,
    OutputSettings,
    Overlay,
    PaintStyle,
    ProgressCurve,
    RenderResult,
    Ruby,
    SingingPulseAnimation,
    Sweep,
    TextStyle,
    Track,
    render_karaoke,
)

BASE_GLOW = Color.hex("#9e6d64")
SUNG_GLOW = Color.hex("#67e5ff")
SUNG_FILL = Color.hex("#01829d")
SUNG = PaintStyle(fill=SUNG_FILL, stroke=WHITE, blur=Blur(color=SUNG_GLOW))


def glow_body() -> Body:
    return Body(
        style=TextStyle(
            fill=WHITE,
            stroke=BLACK,
            stroke_width=5,
            blur=Blur(color=BASE_GLOW, radius=10, width=10, opacity=0.8),
        )
    )


def glow_ruby() -> Ruby:
    return Ruby(
        style=TextStyle(
            fill=WHITE,
            stroke=BLACK,
            stroke_width=3,
            blur=Blur(color=BASE_GLOW, radius=10, width=6, opacity=0.8),
        ),
        offset_y=10,
        follow="syllable",
    )


# 配置直接使用普通实例；共享不可变颜色，逐次构造文字组件。
# 省略 layout 保留输入位置。子类版本见 layered_glow_classes.py。
tracks = (
    *(
        Track(
            source=LineMatch(style=name),
            body=glow_body(),
            ruby=glow_ruby(),
            overlay=Overlay(
                style=SUNG,
                reveal=Sweep(
                    curve=ProgressCurve.two_stage(
                        time_fraction=3 / 17,
                        progress_fraction=0.3,
                    )
                ),
            ),
            animations=(
                FadeInAnimation(duration=800),
                FadeOutAnimation(duration=200),
                SingingPulseAnimation(peak=1.1, attack=80, release=160),
            ),
        )
        for name in ("K1", "K2")
    ),
    Track(
        source=LineMatch(style="LEAD"),
        body=glow_body(),
        overlay=Overlay(style=SUNG),
        animations=(FadeInAnimation(duration=800), FadeOutAnimation(duration=200)),
    ),
)


def apply(input_path: str | Path, output_path: str | Path) -> RenderResult:
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
        tracks=tracks,
        owner="layered-glow",
        settings=OutputSettings(resolution=(1920, 1080), max_events=1_000_000),
    )
    result.document.save(output_path)
    return result


def main() -> None:
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
