# 核心概念

了解 kara-templater 共用的数据模型、时间单位、坐标空间、生命周期和输出格式。先读一遍这一页，后面的指南和教程就能串成一个整体。

## 流程：Document、Track 与 Scene

在导出之前，每个项目都会依次经过三个核心对象：`Document` → `Track` → `Scene`。

### Document 与记录

`Document`（歌词文档）保存画布尺寸（`meta.res_x`、`meta.res_y`，对应 ASS 的 `PlayResX` 与 `PlayResY`）、具名样式 `Style`（`document.styles`），以及按原顺序排列的 `records`（包含 `Script Info`、样式和可通过 `document.lines` 访问的 `Line` 事件）。

- 用 `Document.load(path)` 读取 ASS 文件，用 `Document.parse(text)` 解析 ASS 字符串，或用 `Document.create(width=..., height=...)` 新建脚本（默认 1280 × 720，并写入 `YCbCr Matrix: None`，避免播放器重映射你编写的 RGB 颜色）。
- 用 `document.save(path)` 或 `document.dumps()` 将记录序列化为标准 ASS。
- Python 导入器也可以直接把结构化的 `lyric_sources` 和 `bpm` 传给 `Document.create(...)`，无需先拼装临时 ASS 事件。

当 `build_lyric_scene` 或 `scene.replace_source(record_index)` 替换原始歌词事件时，原行会被保留为带归属标记的 ASS `Comment`。使用相同的 `owner` 重新生成时，只会替换该归属者的输出，其他记录保持不变。

### Track（声部轨道）

`Track`（声部轨道）代表一条独立的声部流，例如主唱、和声或翻译。每条 `Track` 负责声明：

- **来源筛选**（`source`）：基于 `LyricSource` 元数据（`style`、`actor`、`effect`、`chapter`）的筛选函数，默认选中全部歌词。
- **排版布局**（`layout`、`region`）：默认使用 `KaraokeRows()`（底部两行交替排列；开启 `vertical=True` 时为从右到左两列交替）。需要固定坐标或自定义行数时，可传入 `Layout(...)`。
- **显示留白**（`preview`、`tail`）：默认 `preview=5.0` 秒，唱后留白 `tail=None` 为自动模式（目标为最后一个计时单元结束后 1.0 秒，包含退场动画，并在退场前尽量保留至少 0.2 秒停留）。同一行空间紧张时，系统会先压缩多余的唱前预览和停留，最后才按比例压缩退场动画。
- **视觉特效**（`effects`、`theme`、`cues`、`styles`）：由 `KaraokeEffects`、`LyricRule` 规则或自定义函数组成的元组，依次装饰完成测量后的每句 `LyricLine`。

调用 `build_lyric_scene(document, tracks=...)` 后，库会按真实字形轮廓测量歌词、排布不重叠的行、绑定动画，并返回 `LyricScene`（`Scene` 的子类）。

### Scene 与视觉对象

`Scene`（场景）将 `Document` 与待求值或导出的视觉对象组合在一起：

- `TextObject` — 纯字面 Unicode 文本（`{`、`}` 和 `\` 会按字符直接显示，不会被当作 ASS 标签；换行符产生硬换行）。
- `PathObject` — 基于 `VectorPath` 的矢量图形，支持填充、描边、模糊、阴影、渐变和自定义材质着色器。
- `ObjectGroup` — 层级容器，其变换会叠加到所有子对象上。每个准备好的 `LyricLine` 本质上都是一个 `ObjectGroup`。
- `AssDialogue` — 原样透传给 ASS 导出的原生 ASS 事件。

所有视觉对象都是不可变的 dataclass，且整个 `Scene`（包含所有嵌套子对象）内的 `id` 必须唯一。修改对象时请使用 `dataclasses.replace(...)`、`.animate(...)` 或 `.copy(...)`，并用 `scene.add(...)` 将额外对象加入场景。

## 时间单位

不同层级沿用了各自数据格式的习惯，请牢记这三种单位：

| 使用位置 | 单位 | 示例 |
| --- | --- | --- |
| 原始 `Line.start_time`、`Line.end_time`、`DisplayWindow` | 毫秒（ms） | `Line(start_time=1000, end_time=3000, ...)` |
| `Line.text` 中的 `\k`、`\K`、`\kf`、`\ko` 标签 | 厘秒（10 ms） | `{\k50}` 持续 0.5 秒 |
| `Lifetime`、`TimeSpan`、`AnimationClip`、`Timeline`、`StateKeyframe`、`Track`、`LyricRule`、`KaraokeEffects`、`SceneEvaluator` 及几何/遮罩/材质回调 | 秒（s） | `Lifetime(1.0, 4.0)` |
| 序列化后的 ASS 事件起止时间 | 厘秒（10 ms 网格） | `0:00:01.00` |

在以秒为单位的 `Scene` 中，还要区分两个时钟：

- **绝对歌曲秒数**：从整首歌的 `0` 秒起算。`Lifetime(start, end)`、`TimeSpan`、`SceneEvaluator.at(id, time)` 以及 `StateReference` 查找（`StateLookup`）均使用绝对秒数。
- **对象局部秒数**：从对象的 `time_origin`（默认即 `lifetime.start`）起算。`AnimationClip`、`Timeline`、`StateKeyframe` 以及对象自身的几何、裁剪和材质回调均使用局部秒数。

> [!TIP]
> 最常见的笔误是把秒写进 `Line(start_time=...)`，或把毫秒写进 `Lifetime(...)`。记住一条口诀：原始 ASS `Line` 用毫秒，`\k` 标签用厘秒，`Track` 和 `Scene` 里一律用秒。

## 坐标与对齐锚点

所有距离、字号、位置、描边宽度和偏移量都使用由 `Document` 画布（`PlayResX` × `PlayResY`）定义的**脚本像素**。原点 `(0, 0)` 位于左上角，`x` 向右递增，`y` 向下递增。旋转角度使用度数，不透明度范围是 `0`（完全透明）到 `1`（完全不透明）。

### 对齐锚点

`TextObject.alignment`（默认 `7`，左上）和 `Style.align`（默认 `2`，底部居中）沿用 ASS 小键盘 1–9 对齐编号：

| 垂直 \ 水平 | 左对齐 | 居中 | 右对齐 |
| --- | --- | --- | --- |
| 顶部 | `7` | `8` | `9` |
| 居中 | `4` | `5` | `6` |
| 底部 | `1` | `2` | `3` |

文本对象的 `position` 决定的是该对齐锚点的位置。描边、辉光和阴影不会改变文字排版的步进宽度和布局包围盒——需要匹配文字宽度时，请调用 `range_bounds(...)` 或 `path_bounds(...)` 等实测接口，不要按字符个数估算。

### 局部坐标与世界坐标

`ObjectGroup` 的子对象使用相对于父级 `(0, 0)` 原点的局部坐标。父级的位置、缩放、旋转和斜切会与子对象的变换叠加，且分组的 `(0, 0)` 原点就是其变换枢轴——放进分组并不会自动把子对象重新居中。注意 `VectorPath.rectangle` 的左上角位于 `(0, 0)`，而 `VectorPath.circle` 以 `(0, 0)` 为圆心。

每个视觉节点都在 `VisualState` 中保存状态（`position`、`scale`、`rotation`、`skew`、`opacity`、`face_opacity`、`fill`、`outline`、`border`、`blur`、`shadow`、`shadow_opacity`）：

- 变换会沿父子层级传递；`opacity` 会按每个子对象分别相乘（而非先离屏合成整组再调透明度）。
- `fill` 和 `outline` 颜色不会从 `ObjectGroup` 继承，需在子对象或歌词特效上直接设置。
- `node.at(time)` 只计算节点自身的局部动画；若要获取叠加了父级变换和引用关系的世界空间状态，请调用 `scene.evaluator().at(node.id, time)`。

## 生命周期与时钟

`Lifetime(start, end)` 表示以秒为单位的绝对左闭右开区间 `[start, end)`，满足 `0 <= start < end`。当 `start <= time < end` 时对象可见。

- **父级裁剪**：子对象的实际可见时间会与所有祖先的 `lifetime` 取交集，但不会重置子对象自身的局部动画时钟。
- **动画片段与保持**：每个 `AnimationClip` 从 `time_origin` 后的局部偏移开始，持续正数秒 `duration`。默认 `hold=True`，片段结束后会保持最终通道值；设为 `hold=False` 则在结束后恢复原有值。同一对象上不能有两个片段同时写入同一个通道，冲突会直接报错。
- **保留时钟原点（`clock_start`）**：设置 `clock_start` 后，即使可见区间 `lifetime` 被裁剪或延展（例如轨道换行交接时缩短唱前预览），局部动画、遮罩和材质时钟仍锚定在原起点，不会重新从头播放。若可见开始早于 `clock_start`，回调会收到负数局部秒数，而普通动画片段会等到各自起始点才开始。
- **复制对象**：`node.copy(id=..., offset=..., delay=...)` 会克隆单个节点或整棵分组，为所有后代生成唯一 `id`、重映射内部引用，并将生命周期和 `clock_start` 平移 `delay` 秒，同时保留局部动画时钟。

## 歌词目标与计时

`build_lyric_scene` 会把每句带时间轴的歌词构造成 `LyricLine`，其层级暴露六种可查询角色（`LyricRole`）：

| 角色 | 选中范围 |
| --- | --- |
| `line` | 整句 `LyricLine` 分组（正文、注音和行内提示一起运动）。 |
| `syllable` | 每个计时单元及其附带的注音读音。 |
| `segment` | 音节中的单个计时分段（适用于重复计时或 `#` 续接）。 |
| `character` | 仅正文成形字形（不会把注音从所属音节中拆离）。 |
| `ruby` | 仅注音成形字形。 |
| `cue` | 附带的倒数或引导提示。 |

`LyricRule` 可以把任意 `StateAnimation`（如 `FadeIn`、`ScalePulse`、`DriftOut`、`Transform`）绑定到某个角色或查询结果，并锚定到 `enter`、`exit`、`timing`、`after_timing` 或自定义锚点（如 `HighlightArrival`）。即便布局阶段缩短了唱前或唱后留白，原始 `\k` 计时时钟也始终保持不变。

## 实时预览与导出

同一个 `Scene` 可以生成着色器预览与播放文件，也可以编译为标准 ASS。着色器管线先用 Naga 将 WGSL 材质转译为 GLSL，再生成对应的预览资源或播放文件。

| 用途 | 入口方法 | 结果 |
| --- | --- | --- |
| 浏览器实时预览 | `scene.preview()` | 在浏览器中打开 WebGL 2 播放器，查看羽化走字、柔光扫描线、渐变、粒子和自定义 WGSL 材质等效果。 |
| 视频播放与渲染 | `scene.export("song.hook")` | 为 mpv 或 FFmpeg 打包着色器及纹理。 |
| 标准 ASS 兼容导出 | `scene.ass.compile().document.save("song.ass")` | 生成普通字幕播放器可读的 `.ass` 文件，支持硬边走字和符合 ASS 规则的变换。 |

## 下一步

- [导入带时间轴的歌词](guides/documents.md) — 查看所有受支持的 `\k` 标签、注音分隔符与结构化输入方式。
- [布置声部轨道](guides/tracks.md) — 配置多行轮换、字距、竖排歌词与多声部轨道。
- [动画与计时](guides/animation.md) — 使用时间线、规则、时长感知工厂和缓动曲线。
- [预览与导出](output/README.md) — 查看着色器与字幕输出的能力和限制。
