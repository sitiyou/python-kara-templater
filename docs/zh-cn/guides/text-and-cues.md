# 编排注音与倒数提示

调整注音相对正文的对齐与间距，在起唱前添加动画倒数提示，并将带时间轴的占位符号替换为矢量图形。本页涵盖内置提示工厂、按 BPM 自动计时、自定义提示工厂以及底层文本排版接口。

## 定位与分组注音读音

在横排轨道上，同一行内的全部注音（振假名）默认共享一条基线（`ruby_alignment="line"`），最低的注音描边会比整行最高正文描边高出 `ruby_gap` 脚本像素（默认 `6`）。

如果想让每组读音仅根据各自对应的正文墨迹确定高度，设置 `ruby_alignment="group"`：

```python
from kara_templater import Track

track = Track(id="main", ruby_alignment="group", ruby_gap=4)
```

调小 `ruby_gap` 会让注音贴近正文，负值允许重叠。间距基于动画前的塑形墨迹与静态硬描边（及 `reserved_border`）计算，阴影、辉光和缩放脉冲仍可能伸入这段空隙。`ruby_gap` 以 `PlayRes` 脚本像素计，随视频分辨率等比缩放。

横排注音遵循 Aegisub 的分组规则：

- 相邻带注音的音节合并为同一个注音组。
- 较短的读音按自然间距居中排在正文上方。斜体字会沿墨迹倾斜方向计算视觉中心，同时用描边避让防止相邻读音相撞。
- 较宽的读音从所在组的左边缘起排。紧邻的无注音音节会先吸收溢出宽度；空间仍不足时，后续组连同正文一起右移。
- 在代码构建的文档（`Document.create`）中，`|!` 强制另起一组，`|>` 视为普通分隔符，`|<` 允许较宽的读音向左右等量溢出。规则背景可参考 [Aegisub 振假名教程](https://aegisub.org/docs/latest/furigana_karaoke)。

## 为 Track 添加倒数提示

在带时间轴的歌词行中插入提示标记，并在 `Track.cues` 中注册同名的 `CuePreset`：

```python
from kara_templater import (
    CueMarker,
    CuePreset,
    Document,
    KaraokeEffects,
    Line,
    Style,
    Track,
    VolumeCue,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(
        start_time=3000,
        end_time=5500,
        text=CueMarker("intro", "count").markup() + r"{\k120}Ready {\k130}now",
    )
)

scene = build_lyric_scene(
    document,
    bpm=120,
    tracks=(
        Track(
            id="main",
            cues={"count": CuePreset(factory=VolumeCue())},
            effects=(KaraokeEffects(),),
        ),
    ),
)
scene.export("count_in.hook")
```

按视觉形式选择合适的内置提示工厂：

| 工厂 | 起唱前的表现 | 提示结束时 |
| --- | --- | --- |
| `VolumeCue` | 递减音量柱整体闪烁脉冲（默认 `flashes=3`），随后从左到右依次填满高亮色（默认 `count=4`）。 | 全部音量柱消失。 |
| `SignalCue` | 一排矢量信号灯（`circle`、`square`、`rounded`、`star`、`note8`、`note16`、`notepair`，或单位正方形内的自定义 `VectorPath`）按步依次熄灭。 | 最后一盏灯消失。 |
| `BarsCue` | 递减条状倒数按步依次减少一条。 | 最后一条消失。 |
| `TextCue` | 每步显示对应的文字标签（默认 `("3", "2", "1")`）。 | 最后一个标签消失。 |

### 尺寸、造型与配色继承

- **默认尺寸**：`VolumeCue` 与 `SignalCue` 默认为标记处正文字号的一半（`size_ratio=0.5`，例如 80 px 字体对应 40 px 信号灯）。`BarsCue` 与 `TextCue` 默认跟随完整正文字号（无宿主字符时为 48 px；`BarsCue` 宽度为高度的 1.5 倍）。也可以直接设置 `VolumeCue(height=...)`、`SignalCue(size=...)` 或 `TextCue(font_size=...)` 指定固定脚本像素。
- **音量柱外观**：`column_width_ratio` 控制单柱宽度与整体高度之比（默认 `0.25`）；`align` 控制较矮音量柱的对齐方式，可选 `"center"`（默认）、`"top"` 或 `"bottom"`；`transition` 控制闪烁柔和度，从 `0`（硬切闪烁）到 `1`（默认 `0.67`）。
- **信号灯细节**：内置信号灯自带随灯淡出的边缘高光（`edge_brightness=0` 可关闭）。`spacing` 增加相邻灯间距，`slide=Vec2(...)` 让每盏灯在熄灭淡出时产生位移。
- **颜色与特效联动**：轨道使用 `KaraokeEffects` 时，`SignalCue` 在整个倒数期间继承高亮填充、描边、`SecondaryOutline` 与 `glow`；`VolumeCue` 则在每根柱子填充时从唱前着色（`before_fill`、`before_outline`、`secondary_outline`、`base_glow`、`base_material`）切换到唱后着色（`after_fill`、`after_outline`、`after_secondary_outline`、`glow`、`material`）。行首的行内音量柱会共享第一位非空声部的横向 `LyricGradient` 渐变。启用 `zoom_pulse` 或 `zoom_pulse_scanline` 时，信号灯与音量柱会按相同曲线级别脉冲放大。
- **固定配色**：传入 `CuePreset(colors=PaintPair(...))` 可覆盖自动继承，在多条轨道间复用固定配色。

### 选择信号灯熄灭方向

使用 `SignalCue` 时，可以决定起唱前最后一拍保留哪一侧的信号灯：

| 工厂 | 全亮 | 第 1 步后 | 第 2 步后 | 开始走字 |
| --- | --- | --- | --- | --- |
| `SignalCue(direction="left_to_right")` | ● ● ● lyric | · ● ● lyric | · · ● lyric | · · · lyric |
| `SignalCue()`（默认 `right_to_left`） | ● ● ● lyric | ● ● · lyric | ● · · lyric | · · · lyric |

表中 `·` 表示熄灭后保留的占位空隙。`slide` 偏移独立于熄灭方向。

## 计时、BPM 与提示放置方式

倒数提示默认在触发时刻结束，触发点取该行第一个带文字的计时音节（跳过行首空 `\k` 休止）。需要绝对触发时刻时，传入 `CuePreset(trigger=...)`（秒）。

### 显式秒数与按 BPM 自动计时

- **显式秒数**：在 `CuePreset` 上设置 `lead` 与 `duration`。令 `lead=duration` 即可在起唱瞬间刚好结束。如果希望全部信号灯或音量柱先静止亮起一段时间再开始倒数，可在 `SignalCue` 或 `VolumeCue` 上设置 `countdown`（秒）——例如 `CuePreset(factory=SignalCue(countdown=2), lead=5, duration=5)` 会先全亮 3 秒，再用最后 2 秒完成倒数。`steps` 必须从 `0` 严格递增至 `1`。
- **按 BPM 自动计时**：向 `build_lyric_scene(..., bpm=180)`（或 `Document.create(..., bpm=...)`、`bind_cues`、`bind_lyric_cues`）传入固定曲速。省略的 `lead` 会自动等于 `duration`：
  - `VolumeCue` 为最终填充预留 1 拍，每次闪烁预留 `flash_ratio` 拍（默认 3 次闪烁在 120 BPM 下共 2.0 s）。
  - 其余提示每步预算 4 拍（四舍五入至毫秒），若单步达到或超过 1800 ms 则减半（例如 180 BPM 下 3 步共 3.999 s）。非均匀 `steps` 按声明比例划分总时长。
- **未传 BPM 时**：省略的 `lead` 与 `duration` 各自默认为 `1.0` s。添加标记前可调用 `preset.resolve_timing(bpm=bpm)` 查看精确的 `(lead, duration)`。

### 行内放置与独立放置

- **行内放置（`placement="inline"`，默认）**：以标记处正文字形的可见墨迹中心做纵向对齐（行尾标记对齐最后一个字形），同步移动关联注音，并默认留出正文字号八分之一的间距（可用 `CuePreset(gap=...)` 覆盖，包括 `0`）。保持 `keep_space=True`（默认）可防止提示结束后歌词跳位。竖排轨道上，行内提示会顺着列向下推开正文与注音。
- **独立放置（`placement="independent"`）**：默认按 `CuePreset(position=Vec2(...))` 放在画布绝对坐标上。在 `Track` 中，更推荐设置 `CuePreset(line_edge="above")` 或 `"below"`，让提示自动避开轮转歌词行与注音（底部行上方或顶部行下方），行排布会自动为组合高度留出空间。

完整双轨道对比（行内 `VolumeCue` 与独立 `SignalCue`）见 [karaoke_signals.py](../../../examples/karaoke_signals.py)。

## 提示标记语法

在 ASS 歌词行中，提示标记写作带 `kara:v1` 前缀的注释块：

```text
{kara:v1 cue id=count-in preset=bars placement=inline}
```

- `id` 与 `preset` 为必填非空字符串；同一行内 `id` 不可重复。
- `placement` 可选，取值 `inline`（默认）或 `independent`。
- 参数值采用 POSIX `shlex` 引号规则，支持 Unicode、空格、引号与等号，禁止花括号、反斜杠与换行符。推荐调用 `CueMarker(id, preset, placement=...).markup()` 生成规范标记，或直接把 Python `CueMarker` 传给 `bind_cues` / `bind_lyric_cues` 而无需修改原 ASS。
- 标记在解码正文中的位置决定其锚点偏移。锚点必须落在正文的字符簇边界上，不能插在注音或 `#` 续接语法内部。

> [!NOTE]
> 提示标记解析报错时，诊断信息中的偏移是原始 ASS `Text` 字段里的字符偏移（包含前面的标签），与解码后的正文偏移不同。

## 用矢量图形替换行内计时符号

如果希望某些符号随歌词一起走字并在唱过后留在屏幕上（例如换气符号或竖排节奏引导符），先在正文中给每个符号分配普通 `\k` 计时（如 `{\k30}◆{\k30}◆{\k50}歌`），再通过 `Track.guide_symbols` 将它映射到矢量路径：

```python
from kara_templater import (
    Document,
    KaraokeEffects,
    Line,
    Style,
    Track,
    Vec2,
    VectorGuide,
    VectorPath,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=2500, text=r"{\k30}◆{\k30}◆{\k90}Sing")
)

triangle = VectorPath.polygon(Vec2(0.1, -0.75), Vec2(0.7, -0.4), Vec2(0.1, -0.05))
scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            guide_symbols={"◆": VectorGuide(triangle, advance=0.8)},
            effects=(KaraokeEffects(highlight="utopia_scanline"),),
        ),
    ),
)
scene.export("guide_symbols.hook")
```

路径坐标与 `advance` 默认以标记处的正文字号为单位（也可通过 `VectorGuide(..., size=...)` 指定脚本像素）。`y=0` 为基线，负 `y` 向上延伸。替换后的图形同样参与注音对齐、描边避让以及横排或竖排走字。

若要将两个符号锚定在第一个音节起点，可给两个符号都写 `\k0` 紧接首字；在内置走字下，它们在起唱帧保持唱前颜色，并在下一个百分之一秒切换。

## 编写自定义提示与底层文本排版

任何满足 `(context: CueContext) -> CueContent` 签名的函数或可调用对象都能作为 `CueFactory`。返回局部场景对象与预留的 `width`、`height` 即可（行内对齐可指定 `ink_center_y`，或用 `CueContent.from_line(line)` 自动对齐测好的 `LyricLine`）。自定义工厂与运动跟随示例见 [scene_cues.py](../../../examples/scene_cues.py)、[scene_lyric_cues.py](../../../examples/scene_lyric_cues.py) 和 [scene_cue_follow.py](../../../examples/scene_cue_follow.py)。

如果不经过 `Track` 而直接组装 `Scene`，可用底层排版函数绑定单行歌词：

- `layout_document_text(document, record_index, ...)` + `bind_cues(layout, presets)`：适合纯文本、静态行内变色与提示。
- `layout_document_lyrics(document, record_index, ...)` + `bind_lyric_cues(layout, presets)`：适合正文、注音与 `#` 续接。`LyricLayout.unit_group(index)` 会以正文中心为枢轴把正文和注音打组，便于同步缩放脉冲。完整示例见 [scene_bilingual.py](../../../examples/scene_bilingual.py)。
- `TextLayout.characters` 提供每个字符簇的源码范围、字格边界、墨迹边界与实际命中的 `FontFace`。`range_bounds(start, end)` 可测量任意字符区间，`background(start, end, ..., follow=True)` 会创建跟随局部文字动画的背景框（放在同一父组中，或跨组时使用引用）。

> [!WARNING]
> 独立字符排版支持拉丁、希腊、西里尔、中日韩汉字、假名、现代韩文音节、数字、标点及常见歌词符号（组合变音符会随基字符保留在同一簇内）。连写文字、双向控制符、Emoji 序列与古韩文字母会抛出 `LayoutCapabilityError`。

## 下一步

- [布置声部轨道](tracks.md)
- [选择与注册字体](fonts.md)
- [内置卡拉 OK 特效](karaoke-effects.md)
- [Lyric cues API 参考（英文）](../../reference/cues.md)
