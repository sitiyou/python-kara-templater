# 导入带时间轴的歌词

在布置声部轨道之前，先载入带时间轴的 ASS 脚本，或直接在 Python 中构建歌词文档。本页介绍支持的卡拉 OK 计时标签、注音写法、歌词行筛选方式，以及如何定位报错中的源码位置。

## 载入或创建 Document

`Document`（歌词文档）保存脚本分辨率（PlayRes）、命名样式与按顺序排列的 ASS 记录。你可以用 `Document.load(path)` 读取磁盘上的带时间轴的 ASS 文件，用 `Document.parse(text)` 解析 ASS 字符串，或用 `Document.create(...)` 在 Python 中新建脚本。

```python
from kara_templater import (
    Document,
    KaraokeEffects,
    Track,
    build_lyric_scene,
)

ass_text = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,54,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\k50}Ka|ka{\\k50}ra|ra{\\k50}o|o{\\k50}ke|ke
"""

document = Document.parse(ass_text)
scene = build_lyric_scene(
    document,
    tracks=(Track(id="main", effects=(KaraokeEffects(),)),),
)
scene.export("output.hook")
```

如果歌词保存在文件中，把 `Document.parse(ass_text)` 换成 `Document.load("song.ass")` 即可。需要写出标准 ASS 时，调用 `document.save(path)`（UTF-8 带 BOM）或 `document.dumps()` 获取文本。

`Document` 内部提供三个常用属性：

- `document.records` 按原始顺序保存 Script Info 行、`Style` 对象、`Line` 事件以及未识别的区块。`record_index` 指的是 `document.records` 中的列表索引，不是文本文件的物理行号。
- `document.styles` 返回样式名到 `Style` 对象的字典。
- `document.lines` 按源码顺序返回全部 `Line` 事件（包含 Dialogue 与 Comment）。

> [!NOTE]
> `Line.start_time` 与 `Line.end_time` 遵循 ASS 记录习惯，单位为**毫秒**。`Track`、`Scene` 以及歌词计时区间一律使用**秒**。

如果 Python 里已经有结构化歌词数据，不必伪造 ASS 对白行。直接把 `LyricSource.from_lyrics(...)` 传给 `Document.create(..., lyric_sources=..., bpm=...)` 或 `build_lyric_scene(..., inputs=...)`。`build_lyric_scene` 会读取这些歌词源，并用 `bpm` 计算倒数提示的自动时长；`save()` 与 `dumps()` 只会序列化 ASS 记录本身。

## 卡拉 OK 计时标签

导入的歌词同等识别 `\k`、`\K`、`\kf` 与 `\ko`。每个标签以百分之一秒为单位，从该行事件的 `start_time` 起依次推进计时指针。

- **休止**：不含文字的计时块同样推进时间。例如 `{\k30}{\kf20}春|>はる` 表示该音节在歌词行开始后 300 ms 处起唱，持续 200 ms。
- **忽略 `\kt`**：歌词时钟会忽略 `\kt` 标签。需要休止时，请改用空 `\k` 标签。
- **零时长分段**：类似 `{\k0}` 的分段会保留在源码数据中。编写自定义动画时请跳过这类分段，或为 `AnimationClip` 指定正数时长。
- **自动跳过的事件**：`Track`（声部轨道）导入 ASS 文件时，会自动跳过没有计时标签的对白行、注释行以及 `\p1` 矢量绘图区间。歌词行的入场与退场时间由你的模板决定。

## 注音与分段计时写法

在任意计时块中，用竖线 `|`（或全角 `｜`）标注行内注音（振假名）。`body|reading` 与 `body|>reading` 解析出相同的正文与读音。

当同一个正文单元需要跨越多个计时分段时（例如一个汉字对应两个假名，中间还隔着休止），在后续计时块里用 `#`（或全角 `＃`）承接上一个正文单元：

```text
{\k40}影|か{\k20}{\k40}#|げ
```

在这句里，`影` 会在 `か` 期间走字（扫色）到一半，在 200 ms 的休止期间保持当前进度，再到 `げ` 期间完成剩余走字；两个读音各自保持独立时钟。如果你用 Python 构建 `DocumentLyrics` 并希望每个分段都重新扫过整个正文，请设置 `LyricUnit(..., repeat=True)`。

在通过 `Document.create(...)` 编写的文档中，还支持两个用于控制横排注音分组的前缀：

- `|!` 强制开启新的注音组，不与相邻带注音音节合并。
- `|<` 允许较宽的读音向正文左右两侧等量溢出。

全角 `！` 与 `＜` 同样有效。通过 `Document.load` 或 `Document.parse` 导入的 ASS 文件会把 `|!`、`|<`、` |>` 一律当作普通注音分隔符处理。注音间距与分组规则详见[编排注音与倒数提示](text-and-cues.md)。

## 导入 ASS 与代码构建文档的区别

`Document.load` 和 `Document.parse` 将文件视为“纯歌词输入”，外观完全交给模板决定；`Document.create` 则视为代码构建的文档，保留文档自带的样式和行内变色标签。

| 行为 | 导入的 ASS（`load` / `parse`） | 代码构建（`create`） |
| --- | --- | --- |
| 正文、`\k` 计时、注音、提示标记 | 正常读取 | 正常读取 |
| 行内变色（`\c`、`\1c`–`\4c`）与 `\r` 重置 | 忽略（由模板提供外观） | 保留为外观分段 |
| 排版使用的样式 | `Default` 与 `Default-furigana`（通过 `Track.styles` 覆盖） | 使用文档自身的命名样式 |
| `source.style`、`source.actor`、`source.effect` | 保留，可用于 `Track(source=...)` 筛选 | 保留，可用于 `Track(source=...)` 筛选 |
| `\|!` 与 `\|<` 注音前缀 | 视为普通 `\|` 分隔符 | 控制注音分组断开与左右溢出 |
| `\p1` 矢量绘图区间 | 自动跳过 | 绑定文本时作为不支持的标签报错 |

多数模板直接通过 `build_lyric_scene` 处理歌词。如果需要更底层的文本解码或字符测量结果，可选用以下接口：

| 目标 | 函数或方法 | 返回结果 |
| --- | --- | --- |
| 为多个声部轨道排版并添加特效 | `build_lyric_scene` | 包含排好版的歌词行与提示的 `LyricScene`（时间单位为秒） |
| 测量单行正文、注音与 `#` 续接 | `layout_document_lyrics`、`document.lyrics_at(record_index)` | 测量后的 `LyricLayout` 或解码后的 `DocumentLyrics` |
| 读取单行纯文本、静态行内变色与提示 | `layout_document_text`、`document.text_at(record_index)`、`read_document_text` | 测量后的 `TextLayout` 或解码后的 `DocumentText` |

直接用 `TextObject` 创建独立文本节点时，`text` 字段按字面 Unicode 显示：花括号与反斜杠会直接画成字符，不会当作 ASS 标签解析；换行符 `\n` 转为硬换行；回车 `\r` 与空字符 `\0` 会报错。只有在必须原样透传已编码的 ASS 对白时，才使用 `AssDialogue`。

## 筛选歌词行并保留源码记录

通过 `Track(source=...)` 指定哪些歌词行归入某个声部轨道。筛选函数接收一个 `LyricSource`，可读取它的 `style`、`actor`、`effect`、`text` 和 `display` 属性：

```python
from kara_templater import Track

lead = Track(id="lead", source=lambda s: s.style == "Lead")
harmony = Track(id="harmony", source=lambda s: s.actor == "harmony")
```

多个 `Track` 可以同时选中同一行源码而互不干扰，各自生成独立的视觉对象。未被任何轨道选中的歌词行会原样保留。

导出标准 ASS 或手动构建场景时，`build_lyric_scene(..., owner="karaoke")` 与 `scene.replace_source(record_index)` 会把原对白行转为带标记的 Comment 记录保留下来。后续重新生成时只要沿用相同的 `owner` 名称，库就会只替换该 `owner` 产出的事件，并自动恢复不再选中的源码行。请勿手动修改生成 ASS 中的归属标记，否则重新生成时可能无法匹配旧结果。

> [!TIP]
> 请确保 `Document` 的 `PlayResX` 与 `PlayResY` 与目标视频的宽高比一致。字号、描边、边距与坐标全部以脚本像素为单位。

## 源码区间与错误排查

`DocumentText` 和 `DocumentLyrics` 中的字符偏移按解码后的 Unicode 码点计数，既不是 UTF-8 字节数，也不是塑形后的字形索引。一个可见字符可能包含多个码点（例如基字符加上组合变音符），空格虽无墨迹但仍占步进宽度。用于排版或着色的区间不能从塑形后的字符簇中间切开。

载入或绑定失败时，可以按异常类型定位问题：

- **ASS 文件格式错误**：`Document.load` 与 `Document.parse` 遇到无效语法（例如旧版 SSA v4 样式、缺少 `Format:` 行或非法时间戳）会抛出 `ValueError`；读取文件失败会抛出 `OSError`。
- **正文、计时或提示语法错误**：`read_document_text`、`parse_document_lyrics`、`document.text_at` 与 `document.lyrics_at` 会在 `ValueError` 消息中给出 `record_index` 和原始字符偏移（若 `record_index` 指向的不是 `Line`，则抛出 `TypeError`）。不支持的 ASS 覆写标签会记录在 `DocumentText.unsupported` 中，每条为 `TextIssue(record_index, raw_offset, raw, reason)`。
- **文字塑形或字符簇切分错误**：当文字所属书写系统无法拆分为独立字形，或边界切开了字符簇时，`layout_document_text` 与 `layout_document_lyrics` 会抛出 `LayoutCapabilityError`。

如果需要将生成结果追踪回原始歌词，`SourceRef(source_id, unit_index, segment_index)` 能在排版变化时稳定标识某行及可选的单元或分段（修改源码结构后索引会指向新位置）。`EventOrigin` 将这些引用与轨道 ID 附着在生成对象上；导出标准 ASS 时，`AssResult.event_origins` 会把每条输出对白与其 `EventOrigin` 对应起来。常见报错处理见[故障排查](../output/troubleshooting.md)。

## 下一步

- [布置声部轨道](tracks.md)
- [编排注音与倒数提示](text-and-cues.md)
- [选择与注册字体](fonts.md)
- [Documents API 参考（英文）](../../reference/documents.md)
