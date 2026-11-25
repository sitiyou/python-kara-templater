# 命令行

在终端中把带时间轴的 ASS 歌词做成卡拉 OK 特效，再导出着色器或标准 ASS 字幕。内置预设参数适合快速套用样式，也可以通过 Python 特效文件加载可复用的声部轨道或自定义场景。

## 使用预设选项导出

执行 `kara-templater` 并传入输入 `.ass` 文件和输出路径。如果该命令不在 `PATH` 中，可改用 `python -m kara_templater`。

```sh
kara-templater input.ass output.hook --after '#33ddff'
```

内置预设使用自带的默认字体、颜色、对齐方式与边距，不会直接沿用源 ASS 的样式。你可以通过以下选项调整颜色、显示窗口与动效：

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--before '#RRGGBB'` | 预设颜色 | 走字前的唱前填充颜色。 |
| `--after '#RRGGBB'` | 预设颜色 | 走字后的唱后填充颜色。 |
| `--pulse MODE` | `none` | 缩放脉冲模式：`none`（关闭）、`char`（扫色到达时逐字脉冲）、`chars`（同音节字符各自围绕中心同步脉冲）或 `syllable`（整段音节一起脉冲）。 |
| `--fade-in-ms MS` | `0` | 整行歌词（含阴影）的入场淡入时长，单位毫秒。 |
| `--fade-out-ms MS` | `0` | 整行歌词（含阴影）的退场淡出时长，单位毫秒。 |
| `--lead-ms MS` | `0` | 在源歌词行开始前延长显示时间，不改变歌词计时。 |
| `--tail-ms MS` | 自动 | 覆盖计时结束后的停留时长。省略时自动预留 1 秒尾段（含淡出，空间允许时优先保留 200 ms 停留）；传 `0` 则只保留动画所需的最短时间。 |
| `--style NAME` | 全部样式 | 仅导入匹配该源样式的歌词行，可重复传入多个样式。 |
| `--owner NAME` | `default` | 稳定的归属标识，重新导出 ASS 时用于替换旧的生成事件。 |

淡入与淡出时长会在歌词计时区间之外预留空间。如果入场淡入需要占用 0 秒之前的时间，命令行会直接报错，不会悄悄缩短动画时长。关于支持的 `\k` 计时与注音语法，请参阅[导入带时间轴的歌词](documents.md)。

## 复用 Track 配置

需要自定义排版、多声部轨道或更丰富的特效时，可以把 `tracks` 元组写进 Python 文件，并通过 `--effect` 传入。

```python
from kara_templater import CYAN, FadeIn, LyricHighlights, LyricRule, StatePatch, Track

tracks = (
    Track(
        id="main",
        effects=(
            LyricRule("line", "enter", FadeIn(), duration=0.2),
            LyricHighlights.from_timing(StatePatch(fill=CYAN)),
        ),
    ),
)
```

```sh
kara-templater input.ass output.hook --effect my_tracks.py
```

命令行会按与 `build_lyric_scene` 相同的流程，将这些 `Track`（声部轨道）组装为一个 `Scene`（场景）。声部筛选、显示时长、颜色与动画都应在 `tracks` 内配置；搭配 `--effect` 使用时，命令行会拒绝 `--before`、`--after`、`--pulse`、`--fade-in-ms`、`--fade-out-ms`、`--lead-ms`、`--tail-ms` 和 `--style` 等预设或导入选项，但仍允许指定 `--owner`。

## 构建自定义 Scene

当你需要完整控制 `Scene`——例如添加背景装饰形状、额外图层或直接操作记录时，可以在特效文件中改为导出 `build(document) -> Scene` 函数。

```python
from kara_templater import Document, KaraokeEffects, Scene, Track, build_lyric_scene


def build(document: Document) -> Scene:
    lead = Track(id="lead", effects=(KaraokeEffects(),))
    return build_lyric_scene(document, tracks=(lead,), owner="custom")
```

```sh
kara-templater input.ass output.hook --effect my_scene.py
```

特效文件只能在 `tracks` 与 `build` 中二选一，不可同时导出。由于 `build` 自行负责输入筛选、计时、样式和 `owner`，命令行也会同时拒绝 `--owner` 及所有预设选项。

## 选择输出格式与预算上限

命令行默认以 60 fps 将着色器与纹理打包为 `.hook`，供 mpv 或 FFmpeg 使用。用 `--fps`（`1`–`240`）指定交付帧率，或加上 `--ass` 改为编译标准 ASS。

```sh
kara-templater input.ass output.hook --fps 30
kara-templater input.ass output.ass --ass
```

在 Python 中构建的场景可以直接打开浏览器实时预览，见[预览与导出](../output/README.md)。启用 `--ass` 后，命令行会打印生成的事件数、峰值并发事件数、输出字节数以及编译器诊断信息。

| 选项 | 适用格式 | 默认值 | 用途 |
| --- | --- | --- | --- |
| `--fps N` | Hook | `60` | 输出帧率（`1`–`240`）。 |
| `--max-bytes N` | Hook 与 `--ass` | 不限（Hook）/ 10 MiB（ASS） | 限制完整 Hook 文件或编译后 ASS 的字节上限。 |
| `--max-events N` | 仅 `--ass` | `10,000` | 限制生成的 ASS 事件数上限。 |
| `--max-active N` | 仅 `--ass` | `1,000` | 限制同时显示的 ASS 事件数上限。 |

> [!NOTE]
> 命令行将 `--max-events` 默认为 `10,000`，而 Python 中的 `AssBudget` 默认为 `25,000`。未加 `--ass` 时传入 `--max-events` 或 `--max-active` 会报错。无论哪种预算（资源上限）超标，原有输出文件都不会被覆盖。

## 下一步

- [预览与导出](../output/README.md)
- [播放与渲染 Hook](../output/hook.md)
- [导出标准 ASS](../output/ass.md)
- [布置声部轨道](tracks.md)
