# 布置声部轨道

将带时间轴的歌词编排成带自动换行轮转、多声部分离、字符间距控制与竖排日语的声部轨道。你可以精确控制歌词出现在画布的哪个位置、停留多久，以及各声部的表现方式。

## 用 Track 构建场景

`Track`（声部轨道）会从 `Document`（歌词文档）中筛选歌词行，并为其应用独立的样式、排布、提示与特效。将一个或多个轨道传给 `build_lyric_scene` 即可得到 `LyricScene`（场景），然后调用 `scene.preview()` 在浏览器里查看效果，或用 `scene.export()` 打包播放用的着色器。

```python
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    FadeOut,
    Line,
    LyricHighlights,
    LyricRule,
    ScalePulse,
    StatePatch,
    Style,
    Track,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3500, text=r"{\k80}Sing {\k80}out {\k90}loud")
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("syllable", "timing", ScalePulse()),
                LyricRule("line", "exit", FadeOut(), duration=0.2),
                LyricHighlights.from_timing(StatePatch(fill=CYAN)),
            ),
        ),
    ),
)
scene.export("output.hook")
```

`Track` 上所有时间参数均以**秒**为单位。省略可选参数时，默认行为如下：

- **排布**：不传 `layout` 时，默认使用底部双行轮转（`KaraokeRows()`），上一行靠左、下一行靠右，较短的页会自动向画面中央均匀收拢。
- **提前显示与尾留**：`preview` 默认提前 `5.0` s 显示；`tail=None`（自动模式）目标是在最后一个音节结束后停留 `1.0` s 再完全消失（含退场动画），并尽量在退场前保留至少 `0.2` s 的静止停留。
- **紧凑行交接**：当同一行的前后两句间隔较紧时，后一句会先让出多余的提前显示时间，再压缩前一句的静止停留；如果连退场与入场动画本身也放不下，两者会按比例加快播放；间隔为零时则直接切换。传入明确数值的 `tail` 可关闭这种自适应压缩；音节本身的时间轴和提示窗口绝不会被挪动。

如果想只为当前轨道更换字体或字号而不改动原 `Document`，请传入 `Track(styles=(Style(...),))`。对于导入的 ASS 文件，覆盖 `Default` 和 `Default-furigana` 即可——测量阶段会直接使用轨道样式，字号变化会自动反映到行高和注音位置上。

`build_lyric_scene` 返回的 `LyricScene` 就是一个普通 `Scene`，额外附带两个便于检查的属性：`scene.lines`（已定位的 `LyricLine` 对象）和 `scene.plans`（每条 `LyricLinePlan` 包含 `track_id`、`source`、`layout_request`、`placement` 和 `line`）。导出前还可以用 `scene.add(...)` 叠加自定义图形或背景。

## 分离多个声部轨道

为主唱、和声、翻译等不同声部各自添加一个 `Track`，分别指定唯一的 `id`、`source` 筛选条件和排布区域：

```python
from kara_templater import (
    CYAN,
    PINK,
    Document,
    KaraokeEffects,
    KaraokeRows,
    Line,
    Style,
    Track,
    build_lyric_scene,
)

document = Document.create(
    styles=(
        Style(name="Lead", fontname="DejaVu Sans", fontsize=56, shadow=0),
        Style(name="Harmony", fontname="DejaVu Sans", fontsize=38, shadow=0),
    )
)
document.records.extend(
    (
        Line(start_time=1000, end_time=3500, style="Lead", text=r"{\k120}Hold {\k130}on"),
        Line(start_time=1500, end_time=4000, style="Harmony", text=r"{\k250}Ooh"),
    )
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="lead",
            source=lambda s: s.style == "Lead",
            effects=(KaraokeEffects(after_fill=PINK),),
        ),
        Track(
            id="harmony",
            source=lambda s: s.style == "Harmony",
            layout=KaraokeRows(rows=1, anchor="top"),
            effects=(KaraokeEffects(after_fill=CYAN),),
        ),
    ),
)
scene.export("duet.hook")
```

每条轨道维护独立的行轮转和分页时钟。两条轨道也可以刻意选中同一行源码，各自渲染出独立的视觉层。如果歌词来自 Python 结构化对象而非 ASS 对白，可通过 `build_lyric_scene(..., inputs=...)` 传入 `LyricSource.from_lyrics(..., chapter=...)`。

## 读取可编辑组件目录

通过 [`component_catalog()`](../../reference/tracks.md#component_catalog) 获取可序列化为 JSON 的组件声明，用于构建组件选择器。传入脚本高度即可得到与 `compose_track()` 相同的默认值和范围。素材可用时，目录会为可编辑组件提供首选预览卡片。通过 [`component_preview_resource()`](../../reference/tracks.md#component_preview_resource) 打开卡片记录的相对素材名。读取目录不会渲染素材。

## 行预设与分页时机

常见 1 至 8 行卡拉 OK 排版可以直接使用 `KaraokeRows`；需要固定坐标、逐行自定义对齐或自写分行策略时，改用 `Layout`。

### KaraokeRows 预设

`KaraokeRows` 以 1080p 为基准按脚本高度等比缩放边距和行距，并根据每行实际的正文、注音和预留提示尺寸排布。1 行居中，3 行依次左/中/右对齐，其余行数左右交替。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `rows` | `2` | 行数（1 至 8），竖排模式下表示列数 |
| `anchor` | `"bottom"` | 在 `Track.region` 中的纵向停靠位置：`"top"`、`"center"` 或 `"bottom"` |
| `smart_horizontal` | `"equal_margins"` | 将短页的左右行整体向中间收拢；`"center_position"` 逐行独立内收；`"none"` 保持贴边对齐 |
| `section_gap` | `4.0` | 触发新段落并重置行轮转的静音阈值（秒，`0` 表示关闭） |
| `lane_gap` | `0.3` | 同一行先后两句之间的理想空隙（秒） |
| `sync_entry` | `True` | 让每个段落首页的全部歌词行同步入场 |
| `sync_ending` | `False` | 让每个段落末页的全部歌词行同步退场 |
| `sync_each_page` | `False` | 将已启用的同步规则应用到每一页，而非仅限首末页 |
| `fill_section` | `True` | 将每行保持到下一句占用前 `lane_gap` 秒，并对齐末页尾留 |
| `reset_on_lead` | `True` | 遇到领唱提示或章节切换时从第一行重新排起 |

页面里只有单独一行时，`smart_horizontal` 会自动将其居中。在底部三行预设中，只有两行的残页会落在下方两行并双双右对齐。如果希望每行完全按各自的 `preview` 和 `tail` 独立进出，设置 `KaraokeRows(sync_entry=False, fill_section=False)` 即可。

要根据源码元数据（例如 `actor` 为 `verse-start`）手动断页或断段，可以继承 `KaraokeRows` 并重写 `break_before`：

```python
from typing import Literal

from kara_templater import KaraokeRows, LineLayoutRequest, Track


class VerseRows(KaraokeRows):
    def break_before(
        self, previous: LineLayoutRequest, line: LineLayoutRequest
    ) -> Literal["none", "page", "section"]:
        if "verse-start" in line.tags:
            return "section"
        return super().break_before(previous, line)


main = Track(
    id="main",
    layout=VerseRows(),
    tags=lambda source: frozenset((source.actor,)),
)
```

返回 `"section"` 会开启新段落（同步首页提前显示）；返回 `"page"` 只在当前段落内重置行号；返回 `"none"` 则保持自动分页。

### 固定行道与自定义排布

使用 `Layout` 可以指定精确的起始坐标、逐行对齐方式或自定义排布策略：

```python
from kara_templater import Layout, Vec2

lanes = Layout(
    rows=2,
    position=Vec2(80, 520),
    alignment=("center", "right"),
    offsets=(Vec2(), Vec2(-20, 8)),
    policy="available",
)
```

- **行间距**：省略 `gap` 时，引擎按同时可见的各行实际高度（含注音）排布，并在行间额外留出最大正文字号 20% 的间距；传入数字 `gap` 则按固定脚本像素行距排列。
- **选行策略**：`policy="strict"`（默认）严格按顺序轮转；`policy="available"` 选择下一个空闲行。`reset_after` 在静音超过指定秒数后重置行号；`reset_on_lead=False` 在领唱提示或章节切换时继续轮转。
- **自定义分配**：继承 `Layout` 并重写 `allocate(lines, context)` 可实现特殊编排（例如把独唱行移出常规轮转）。分配好行号与交接时间后，调用 `self.row_offsets(lines, placements)` 即可算出带实测间距的纵向偏移。需要参考其他轨道时，通过 `Track.references` 传入请求，并在 `context.other_lines` 中读取。完整示例见 [lyric_orchestration.py](../../../examples/lyric_orchestration.py)。

## 组合特效与挂接图形

`Track.effects` 接收一个元组，可以混排 `LyricRule` 声明与可调用特效（如 `KaraokeEffects`、`LyricHighlights`、`LyricEcho`、`LyricParticles`、`lyric_effects(...)`，或任何接收并返回 `LyricLine` 的普通函数）。

1. 引擎先按源码时间轴解析全部 `LyricRule` 的触发区间。
2. 可调用特效按元组顺序依次作用于已测量、尚未定位的歌词行。
3. 排布阶段汇总所有必须占用的显示区间（来自规则、高亮层、子对象生命周期及 `line.required_display`）并完成一次定位。（`line.independent` 中的独立对象保持自身时间窗口，不占用歌词行道。）
4. 最后把规则动画绑定到最终字形以及可调用特效生成的高亮层上。

在自定义可调用特效内部添加动画时，请调用 `line.schedule(...)` 而非 `line.bind(...)`，这样动画时长才能参与行排布并同步作用于后续高亮层：

```python
from kara_templater import DriftOut, LyricLine, LyricRule, Transform, Vec2


def drift(line: LyricLine) -> LyricLine:
    return line.schedule(
        LyricRule(
            "character",
            "timing",
            Transform(scale=lambda p: 1 + 0.06 * 16 * p * p * (1 - p) ** 2),
        ),
        LyricRule(
            "character",
            "after_timing",
            DriftOut(offset=Vec2(12, -36)),
            offset=0.14,
            duration=0.56,
        ),
    )
```

在 `Track.effects` 之外（即对 `scene.lines` 中已定位的歌词行），请改用 `line.bind(...)` 或 `line.animate(...)`，直接绑定的动画必须落在该行已分配的生命周期之内。

`LyricRule` 与 `line.query(...)` 支持六种目标角色：`"line"`（整行）、`"syllable"`（音节，包含正文与注音）、`"segment"`（每个分段计时区间）、`"character"`（仅正文字形）、`"ruby"`（单个注音字形）和 `"cue"`（提示）。重复目标和已选中祖先的后代会被自动去重；查不到目标（例如对无注音歌词行查询 `"ruby"`）会安全跳过。组透明度会与子对象透明度相乘。若要让整组读音绕同一中心缩放脉冲，可在规则工厂中读取 `line.layout.ruby` 计算局部枢轴点。

如果自定义特效在正文之外增添了装饰图形，请返回更新后的 `line.layout.bounds`（行内局部像素坐标），让排布阶段为装饰留出空间。更多特效用法见[内置卡拉 OK 特效](karaoke-effects.md)与[动画与时间控制](animation.md)。

### 为带时间轴的词组挂接图形

调用 `build_lyric_scene` 后，遍历 `scene.plans` 即可按实测文字边界定位额外图形：

```python
from kara_templater import (
    PINK,
    Document,
    Lifetime,
    Line,
    PathObject,
    Style,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3000, text=r"{\k100}Star {\k100}light")
)
scene = build_lyric_scene(document, tracks=(Track(id="main"),))

for plan in scene.plans:
    body = plan.line.layout.body
    for index, span in enumerate(body.timing):
        if span.end <= span.start or span.end_offset <= span.start_offset:
            continue
        box = body.range_bounds(span.start_offset, span.end_offset)
        origin = plan.line.state.position + Vec2(box.left, box.top + box.height + 6)
        scene.add(
            PathObject(
                id=f"{plan.line.id}/underline/{index}",
                lifetime=Lifetime(span.start, span.end),
                path=VectorPath.rectangle(box.width, 4),
                state=VisualState(position=origin, fill=PINK),
            )
        )

scene.export("underlines.hook")
```

创建路径前请跳过空文本区间和零时长分段。如果歌词行本身会移动，请把图形作为歌词行的子对象添加，或通过引用跟随其世界坐标，而不是直接写死静态 `position`。

## 字符间距与描边避让

默认情况下，`KaraokeRows` 按每个字符的可见墨迹、侧边距和主描边计算字格（Studio 间距），除非开启了 `palt=True`；而普通 `Layout` 使用字体原生步进宽度。你可以通过 `Track(studio_spacing=True)` 或 `False` 显式覆盖。

需要微调 Studio 字格间距时，传入 `StudioSpacing`：

```python
from kara_templater import StudioSpacing, Track

spaced = Track(
    id="main",
    studio_spacing=StudioSpacing(space_width_percent=50, allow_biting=True),
)
```

- `space_width_percent` 设定 ASCII 空格占字体 em 宽度的百分比（10 至 100，默认 `20`）。
- `allow_biting=True` 保留负侧边距，让斜体字母排得更紧凑（默认 `False`）。

完成字格测量后，`Track` 会检查相邻硬描边（包含正文以及同一注音内的相邻假名）：

- `min_outline_gap=0`（默认）允许相邻硬描边相切，仅在发生重叠时插入间距。
- 设为 `min_outline_gap=4` 可在描边之间留出至少 4 脚本像素的空隙；设为 `None` 则跳过描边避让。
- 如果自定义图层在样式描边之外又加了更粗的硬边，请用 `reserved_border` 声明最外层硬边半径。辉光、阴影与临时动画描边不计入间距预留。

横排日语假名的比例间距请见[选择与注册字体](fonts.md#启用假名比例间距)。需要从右向左排布字符或反向走字时，可设置 `Track(right_to_left=True)`，或设置 `Track(reverse_timing=True)`（也接受按行判断的谓词函数）将计时窗口按相反空间顺序分配。

## 竖排日语歌词

在 `Track` 上设置 `vertical=True`，即可生成从上到下走字、从右向左换列的竖排歌词：

```python
from kara_templater import Document, KaraokeEffects, KaraokeRows, Line, Style, Track, build_lyric_scene

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=52, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3500, text=r"{\k80}風|かぜ{\k80}の{\k90}歌|うた")
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            vertical=True,
            layout=KaraokeRows(rows=3, anchor="top"),
            effects=(KaraokeEffects(),),
        ),
    ),
)
scene.export("vertical.hook")
```

竖排模式的几个要点：

- 省略 `layout` 时默认两列从右向左轮转；传入 `KaraokeRows(rows=1)` 或 `rows=3` 可切换为单列或三列。`anchor` 控制整列在纵向的对齐位置，不满一页时始终从最右侧起排。`break_before` 与分页时间设置与横排一致。
- 长音符（`ー`）与括号会自动绕字格中心旋转。注音排在正文右侧，间距由 `ruby_gap`（脚本像素）控制。
- `highlight="no_wipe"` 会在每个音节结束时整字变色，不做向下走字。
- 整列过渡（`fade`、`rise`、`slide_in`、`slide_out`）会连同注音一起动画化。逐字过渡、计时粒子与描边闪烁在竖排模式下不生效，但自定义 `LyricRule` 动画依然可用。
- 内置 `SignalCue` 信号灯与 `VolumeCue` 音量条仅支持横排。竖排需要节奏引导符号时，请为占位字符加上 `\k` 计时并通过 `Track.guide_symbols` 映射矢量图形，详见[编排注音与倒数提示](text-and-cues.md#用矢量图形替换行内计时符号)。

## 仅渲染局部预览区间

调试长歌曲中的某一段时，可向 `build_lyric_scene` 传入绝对秒数范围 `preview_interval=(start, end)`：

```python
from kara_templater import Document, KaraokeEffects, Line, Style, Track, build_lyric_scene

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=54, shadow=0),)
)
document.records.extend(
    (
        Line(start_time=1000, end_time=3000, text=r"{\k200}First"),
        Line(start_time=12000, end_time=15000, text=r"{\k300}Chorus"),
    )
)

scene = build_lyric_scene(
    document,
    tracks=(Track(id="main", effects=(KaraokeEffects(),)),),
    preview_interval=(10.0, 16.0),
)
scene.export("preview.hook", start=10.0, duration=6.0)
```

请依然把整首歌的歌词留在 `document`（与 `inputs`）中。排布阶段会保留完整的行轮转顺序、相邻行交接与并行行高，只返回与预览窗口相交的歌词行和独立提示。最终整曲导出，或模板代码需要访问窗口外对象时，省略 `preview_interval`（或传 `None`）。

## 下一步

- [编排注音与倒数提示](text-and-cues.md)
- [内置卡拉 OK 特效](karaoke-effects.md)
- [设计整曲布局](../tutorials/karaoke-design.md)
- [Track API 参考（英文）](../../reference/tracks.md)
