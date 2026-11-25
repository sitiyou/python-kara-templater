# 为高亮添加自定义动画

在卡拉 OK 走字前沿抵达每个字符的瞬间触发逐字动画。当跳跃、脉冲或装饰需要严格贴合高亮推进进度、而不是整块音节同时启动时，就适合采用这种写法。

## 将动画绑定到走字前沿

这份完整脚本会让歌词整行淡入淡出，同时在青色走字扫过每个字符时，让该字符向上弹跳 24 px。脚本只依赖已安装的库，运行后会在当前目录写出 `lyric-arc.hook`。

```python
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    FadeOut,
    Highlight,
    HighlightArrival,
    HighlightPass,
    Jump,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    Region,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    build_lyric_scene,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=44, shadow=0),),
)
document.records.append(
    Line(
        text=r"{\k100}Sing {\k100}with {\k100}me",
        start_time=1000,
        end_time=4000,
    )
)


def highlights(line: LyricLine) -> tuple[Highlight, ...]:
    return tuple(
        Highlight(
            f"unit:{index}",
            index,
            tuple(
                HighlightPass(
                    TimeSpan(segment.timing.start, segment.timing.end),
                    Region(box.left, box.right),
                    round=round_id,
                )
                for round_id, segment in enumerate(unit.segments)
            ),
            StatePatch(fill=CYAN),
            repeat="reset",
        )
        for index, unit in enumerate(line.layout.lyrics.units)
        if unit.segments
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )


scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            layout=Layout(position=Vec2(70, 160)),
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.25),
                LyricRule(
                    "character", HighlightArrival(highlights=highlights), Jump(24)
                ),
                LyricRule("line", "exit", FadeOut(), duration=0.4),
                LyricHighlights.from_timing(StatePatch(fill=CYAN)),
            ),
        ),
    ),
)
scene.export("lyric-arc.hook", fps=60)
```

## 抵达时间是如何计算的

`highlights` 工厂把每个带时间轴的音节转换成一个 `Highlight`，其中包含覆盖该音节实测水平区域 `Region` 的一段或多段 `HighlightPass`。

把 `HighlightArrival(highlights=highlights)` 传给 `LyricRule` 作为时间锚点后，引擎会自动推算走字穿过每个实测字符的时刻，不需要你手写字符循环或手工换算绝对时间。默认情况下，动画在前沿刚进入字符时启动（`threshold="enter"`），持续时长等于走字完全扫过该字符的时长。

你可以通过 `HighlightArrival` 和 `LyricRule` 的参数微调触发方式：

| 参数 | 设置位置 | 作用 |
| --- | --- | --- |
| `duration=0.25` | `LyricRule` | 使用固定动画时长，覆盖默认的字符穿越时长 |
| `threshold="center"` 或 `"complete"` | `HighlightArrival` | 改为在走字扫到字符中心或右边缘时启动动画 |
| `selection="each"` | `HighlightArrival` | 每次匹配的高亮都触发，而非每轮只取最早一次 |
| `names=frozenset(...)` | `HighlightArrival` | 仅对指定名称的高亮触发 |
| `retrigger=False` | `HighlightArrival` | 同一音节重复走字时只在首次经过触发 |

> [!NOTE]
> 如果某段 `HighlightPass` 使用了非线性缓动 `rate`，必须同时提供对应的反函数 `inverse_rate`。`HighlightArrival` 依赖反函数精确求解交汇时刻，不做近似搜索。

## 为斜体歌词倾斜走字前沿

`LyricHighlights.from_timing` 与 `KaraokeEffects` 会为水平排布的斜体或伪斜体文本自动倾斜走字前沿；提示工厂中的计时矢量引导图形也会跟随自身样式。

如需手动覆盖角度，可以传入以角度为单位的 `sweep_angle`：

- `sweep_angle=0` 强制保持垂直前沿，即便字体本身是斜体。
- 正角度使前沿顶部向右倾斜；负角度使顶部向左倾斜。

```python
from kara_templater import CYAN, LyricHighlights, StatePatch

straight_sweep = LyricHighlights.from_timing(
    StatePatch(fill=CYAN),
    sweep_angle=0,
)
```

## 与整行动画及自定义动画组合

整行动画与逐字高亮动画会通过场景树层级自然叠加：行组的 `FadeIn` 与 `FadeOut` 控制整行不透明度，内部的 `Jump` 负责各字符弹跳，而高亮着色副本会自动跟随对应目标字符一起运动。

歌词节点与普通场景对象遵循同一套动画协议。若想把 `Jump(24)` 替换成自己的动效，直接传入 `Transform`、`StateFunction`、`ShaderMotion`，或实现声明了写入通道的自定义 `StateAnimation` 即可。

## 下一步

- [编写自定义动画](custom-animation.md)：编写可直接在 GPU Hook 中执行的自定义运动函数。
- [动画与时间轴](../guides/animation.md)：查看内置动画、缓动曲线与 `Timeline`。
- [布置声部轨道](../guides/tracks.md)：深入了解 `LyricRule` 锚点、角色筛选与轨道组合。
- [API 参考：Colors and appearance](../../reference/paint.md)：查阅 `Highlight`、`HighlightPass`、`HighlightArrival` 与 `LyricHighlights` 的完整签名。
