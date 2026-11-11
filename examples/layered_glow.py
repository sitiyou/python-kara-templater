"""多层辉光与整音节强调：python -m examples.layered_glow input.ass output.ass。"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    WHITE,
    Body,
    Color,
    Document,
    Effect,
    Halo,
    Line,
    Lyrics,
    OutputSettings,
    ProgressCurve,
    Ruby,
    render_karaoke,
)

BASE_GLOW = Color.hex("#9e6d64")
SUNG_GLOW = Color.hex("#67e5ff")
SUNG_FILL = Color.hex("#01829d")


class LayeredGlow(Effect):
    """白字黑边 → 青字白边，配合整音节辉光增强和 1.1 倍缩放。"""

    def compose(self):
        yield Lyrics(
            Body(fill=WHITE, stroke=BLACK, stroke_width=5),
            Ruby(stroke_width=3, offset_y=10, follow="syllable"),
            Halo(
                id="base", color=BASE_GLOW, opacity=0.8, blur=10, width=10, ruby_width=6
            ),
            Halo(
                id="sung", color=SUNG_GLOW, opacity=0.2, blur=10, width=10, ruby_width=6
            ),
        )

    def configure(self):
        guide = self.source.style == "LEAD"
        curve = (
            "linear"
            if guide
            else ProgressCurve.two_stage(time_fraction=3 / 17, progress_fraction=0.3)
        )
        self.text.sweep(
            fill=SUNG_FILL,
            stroke=WHITE,
            curve=curve,
            padding=24,
            lead=24,
            tail=24,
        )
        self.query_one("#sung", Halo).on_singing(opacity=(0.2, 0.8), keep=True)
        self.text.fade(in_ms=800, out_ms=200)
        if guide:
            self.ruby.hide()
        else:
            self.syllables.on_singing(pulse=1.1)


effect = LayeredGlow


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
