# Document 场景 API

场景 API 支持文字、路径、组、注音绑定、柔和扫色、导唱组件、粒子和高级几何，并提供 Track 与旧模板前端。首次使用可从[作者指南与固定示例](scene-authoring.md)开始；本文提供详细契约与验证记录。完整计划仍有发行及跨播放器等验收事项，以 TODO 为准。

```python
from kara_templater import (
    Document, Lifetime, Scene, SceneTimeline, StatePatch,
    TextObject, Tween, Vec2, VisualState,
)

source = Document.parse("[Script Info]\nPlayResX: 1280\nPlayResY: 720\n")
timeline = SceneTimeline().play(
    Tween(StatePatch(position=Vec2(700, 300))), duration=2,
)
word = TextObject(
    id="title", text="Hello", lifetime=Lifetime(1, 4),
    state=VisualState(position=Vec2(100, 300)),
    animations=timeline.clips,
)
result = Scene(source).add(word).compile()
result.document.save("hello.ass")
```

该例生成一个原生 move 事件。`examples/scene_staggered.py` 演示逐字错峰、回弹、多属性并行、组位置和自定义曲线。运行 `uv run python -m examples.scene_staggered output.ass`。

## 时间和属性

新接口的公开时间单位为秒；底层 ASS `Line` 仍使用毫秒。`Lifetime` 是场景绝对时间，动画 clip.start 是相对于对象出生的时间。寿命半开，动画结束可保持或释放。释放恢复下层既有状态；保持值在后续动画开始时接续。同一属性在时间区间上冲突直接报错，不按调用顺序静默覆盖。

`SceneTimeline.play` 中的动画并行；连续调用默认顺序排程；`at` 指定错峰起点，`wait` 插入间隔，`repeat` 重复已记录的时间表。重复是时间表复制，保持值会接续，不自动回到初态；需要每次回到初态的动画可显式设置 `hold=False` 或安排返回动画。

`play(..., breakpoints=(0.35, 0.75))` 声明本次动画内部需要切分采样的时刻，单位为相对于本次 play 起点的秒，不是归一化进度或场景绝对时间。断点必须有限且位于 `[0, duration]`；同次并行动画共享这些断点，`repeat` 保留每个副本中的局部断点。自定义回调存在显隐切换或分段拐点时应显式声明，避免采样区间跨过边界。`examples/scene_writing.py` 将书写路径的断点传给笔尖时间线，保持两者开闭同步。

`StatePatch` 提供 position、scale、rotation、skew、opacity、fill、outline、border、blur、shadow。`Tween` 接受用户缓动函数。`StateFunction` 接受 `(VisualState, progress) -> VisualState`，声明它写入哪些属性；未声明的属性变化不传播。自定义函数必须是纯函数，不能依赖求值顺序或可变 RNG。

`SceneTimeline.keyframes(*frames, at=None)` 将一组 `StateKeyframe(time, target, rate=linear_rate)` 展开为相邻的 Tween。time 是本次关键帧序列起点后的秒数，必须为正且严格递增；第一段从当前状态开始，初始值直接写入对象的 VisualState。每帧的 rate 控制进入该帧的缓动。各段只写该帧 target 声明的属性，未声明属性继续保留已有状态或并行动画；各段终值保持。相同时间的多属性目标写在一个 StatePatch 中。需要释放、显式跳变或任意函数时仍可使用 play/AnimationClip/StateFunction。

```python
motion = SceneTimeline().keyframes(
    StateKeyframe(0.4, StatePatch(position=Vec2(450, 360)), smooth_rate),
    StateKeyframe(1.2, StatePatch(position=Vec2(830, 360), fill=PINK)),
)
motion.play(Tween(StatePatch(rotation=360)), duration=1.2, at=0)
```

每段起止自动成为采样边界，不必另列 breakpoints。插入前检查完整序列，冲突或非递增时间不会部分修改时间线。`uv run python -m examples.scene_keyframes output.ass` 导出固定的回弹移动、旋转、变色和淡出示例；[实际预览](images/scene-keyframes.png)与[播放报告](scene-keyframes-validation.json)可用 `tools.validate_scene_core --scene keyframes` 重现。旧 Track 的 Keyframe/Keyframes（归一化标量属性）保持原有语义，StateKeyframe 专用于 Scene 的多属性秒制编排。

求值与编译分离：`object.at(absolute_seconds)` 返回确定时刻的本地状态，不推进全局时钟。超出寿命的 at 仍可计算保持态，实际可见区间由编译器控制。当前实现不为任意函数声称空间误差上界。

## 几何、组与来源

`Vec2` 使用屏幕坐标，正旋转为顺时针；编译为 ASS 时取相反的 frz。`VectorPath` 保留多个轮廓、直线和三次贝塞尔控制点。`Contour.point` 为参数均匀采样，尚不是弧长均匀采样。`map` 可自行变换控制点，`rectangle` 和 `polygon` 构造基本图形。

`ObjectGroup` 的孩子使用本地坐标，但寿命仍是绝对时间；孩子可见性与所有祖先寿命取交集。位置、缩放和旋转从内向外各组合一次，layer 相加。组 opacity 乘入每个孩子，并非先合成整组再统一透明。组不隐式继承填充、描边或模糊。非均匀组缩放与子对象旋转/倾斜现通过二维矩阵组合和路径降级支持，具体范围见下文。

`copy(id=..., offset=..., delay=...)` 平移完整动画轨迹并推迟寿命；组复制递归重命名和推迟孩子。与原对象一同放入场景不会共享身份。普通场景复用同一身份会报错。

### 坐标与变换中心速查

| 数据/接口 | 坐标或时间含义 |
| --- | --- |
| PathObject.path | 对象原点周围的几何坐标；rectangle 从 `(0,0)` 起，circle 以原点为中心 |
| TextObject 的 position | 由 alignment 选择的文字锚点在父坐标中的位置；文字测量的左上角不总是这个锚点 |
| VisualState.position | 本对象原点在父坐标中的位置；根对象使用脚本坐标 |
| VisualState.transform | `T(position) × R(rotation) × S(scale) × H(skew)`，点先经 H；skew 分量是剪切系数，不是角度 |
| ObjectGroup | 以组原点作缩放/旋转中心；后代坐标只经各级矩阵一次，不自动按包围框居中 |
| object.at(t) | 用场景绝对秒查询本地动画，clip.start 相对对象出生；不组合父变换或世界引用 |
| scene.evaluator().at(id,t) | 父矩阵组合后应用声明的世界通道引用；查询时刻夹到对象寿命端点，显隐另由编译器决定 |
| FollowObject.offset | 屏幕/脚本坐标偏移，不随目标旋转；自定义局部偏移需使用目标 transform.apply |
| RectangleClip/VectorClip | screen 固定脚本坐标；local 相对遮罩所属对象原点，组遮罩不跟各孩子重置原点 |

任意变换中心通过局部坐标和组显式构造。例如将一个 80×40 矩形绕中心旋转，把它的子对象 position 设为 `Vec2(-40, -20)`，父组 position 设为所需的画面中心，再旋转父组。已有对象若带动画，要同步平移其整个局部轨迹，可使用 copy(offset=...)；不能仅改基础 position 而期待所有绝对目标值一起移动。`LyricLayout.unit_group` 已完成正文/注音围绕正文中心的重定位。

矩阵次序、镜像/退化、局部遮罩及文字降级由 `tests/test_scene_affine.py`、`tests/test_group_masks.py`、`tests/test_scene_masks.py` 验证；跨父组跟随、历史、复制重定向、缺失目标和循环诊断由 `tests/test_scene_references.py` 验证。依赖图同时包含父子边与显式引用边，循环在回调执行前拒绝；延迟不会让一个循环合法。以上是对象模型契约，完整组合图像的精度与成本仍按案例验收。

`RectangleClip` 与 `VectorClip` 可显式选择 screen/local 坐标；screen 遮罩保持画面位置，local 遮罩使用对象变换。动态与共享组遮罩的具体契约见下文，不能将两种坐标模式混用。文字对象只接受纯文本，不能借文字参数注入未审核标签；标准文本语义先由 `Document.text_at` 绑定。

对象可附 `EventOrigin`，编译报告和诊断保留它。`NativeEvent` 接入已降低为标准 ASS 的旧前端输出，保留原本 Effect/actor 等信息；其生成归属使用独立 Comment 元数据。

## 编译、保留与预算

Scene 接收 Document，输出新 Document，不原地修改源记录。默认保留源事件；`replace_source(record_index)` 将指定源事件保存为 Comment。新效果和旧模板的选择与归属仍由各前端明确决定，不自动对生成的事件再次套效果。

同一 owner 再次编译时只替换自己的输出。其他 owner 输出、原始注释、未匹配事件和未知段落保留。生成样式具有稳定名字；不同的源样式碰巧占用该名时报错。自定义事件列顺序保留；没有 Effect 列时为生成事件引入新的标准 Format。

静态对象使用单事件，单一线性位置动画使用 move；其余属性动画按预算采样。采样包含 clip 边界和对象寿命，合并相邻等价事件。采样使用区间中点；报告实际最大事件间隔，不能将标称帧率当作误差证明。ASS 时间量化为 centisecond，量化后寿命消失时报错。

`SceneBudget` 默认 50 Hz、25,000 输出记录、10 MiB、1,000 峰值活动事件和每个路径 4,096 控制点。原生兼容节点的来源注释也计入记录预检；最终 `SceneResult.event_count` 只统计生成的 Dialogue。输出体积和峰值活动数包含保留的源事件。展开前保守估算，过程中检查实际记录数与字节数，序列化后再次核对总字节和活动事件。预算超限失败，不自动降低质量。

## 当前验证

`uv run python -m tools.validate_scene_core /tmp/scene-core-validation` 导出 ASS，再使用系统 ffmpeg/libass 获取关键时刻预览。当前[预览](images/scene-core.png)和[报告](scene-core-validation.json)属于初步核心验证；后文已补充连续/跳转检查；全部背景和全部效果的完整验收仍待完成。

## Document 文字、按词背景与导唱组件

```python
from kara_templater import (
    BarsCue, CuePreset, Lifetime, Scene, Vec2,
    bind_cues, layout_document_text,
)

# record_index 是源 Dialogue 在 Document.records 中的位置。
layout = layout_document_text(document, record_index, display=Lifetime(0, 5))
bound = bind_cues(layout, {"bars": CuePreset(factory=BarsCue())})
scene = Scene(document).add(bound.group(position=Vec2(300, 320)), *bound.independent)
scene.replace_source(record_index)
scene.compile().document.save("output.ass")
```

输入可含 `{kara:v1 cue id=intro preset=bars placement=inline}`。也可以将 `CueMarker` 元组直接传给 `bind_cues(markers=...)`，两条路径产生相同对象模型。preset 是显式注册的 `CuePreset`，未知名称报错。原始标记留在源 Comment，生成 Dialogue 不含本库标记。

### 输入标记载体与 v1 契约

| 载体 | 适用范围与选择理由 |
| --- | --- |
| 行内 `{kara:v1 ...}` 注释块 | 当前导唱锚点入口；能精确插入解码正文位置，普通 ASS 播放端不会将注释作为可见歌词 |
| 标准 ASS override | 逐字颜色、颜色重置和原始 karaoke 时间继续使用标准标签；不发明播放端必须理解的导唱标签 |
| 事件 Effect/Actor 字段 | 保留用于事件选择与旧模板语义；不能单独表达一行内多个正文锚点 |
| Python 类型化配置 | 定义 CuePreset、内容工厂、位置、尺寸、触发时刻和动画；可直接提供 CueMarker，适合无需编辑输入 ASS 的作者 |

v1 的命名空间前缀必须紧跟左花括号，大小写固定为 `kara:`；格式为 `{kara:v1 cue id=... preset=... [placement=inline|independent]}`。当前只识别 cue，未知版本或 kind 明确报错，不作为普通注释忽略。没有该前缀的普通注释保持原样，不参与导唱绑定。

参数按 POSIX shlex 词法分词，但不执行 shell、变量替换或代码。id/preset 是非空字符串，可包含 Unicode、空格、单双引号和等号；使用 `CueMarker(...).markup()` 自动引用。不能包含 `{`、`}`、反斜杠或换行，否则无法可靠留在单个 ASS 注释块内。v1 不提供这些字符的反斜杠转义。placement 默认 inline；未知参数、重复参数、未闭合引用和非法 placement 均拒绝。不要向标记中嵌入 Python 表达式或任意效果配置；字符串只作为已注册 preset 的查找键。

id 在同一源记录内唯一，不同行可复用。标记 offset 由其插入位置决定，以解码正文的 Unicode code point 计数；它不是标记参数，`markup()` 不序列化 CueMarker.offset。直接构造标记时 offset 显式指定，绑定器检查范围和塑形簇边界。注音/续唱输入先投影为正文范围，注音内部或续唱语法内部的无效锚点会报错。

解析错误提供 `record N, text offset M`：N 是 Document.records 下标，M 是该源事件原始 Text 字符串的 code point 偏移，含此前 override/注释长度；它不同于解码后 CueMarker.offset。解析与绑定不改变原始歌词时间。编译时应替换选中的源事件为 Comment；再次生成使用 owner 归属移除旧生成事件，原始标记留作编辑来源，输出的生成 Dialogue 不依赖本库标签。

契约回归见 `tests/test_document_text.py`（引用/Unicode/非法参数/源偏移/跨行 id）、`tests/test_scene_text.py`（代码与标记绑定、簇边界和时序）、`tests/test_lyric_cues.py`（注音投影和生成标签消费）。

`layout_document_text` 保留原始 k/K/kf/ko/kt 时间为 `SingingSpan`，显示窗口独立配置。颜色按 style → 内联标签/重置 → 作者修改 TextObject → 动画声明的属性依次覆盖。文字范围使用 Unicode code point 索引，但选择边界必须对齐可独立绘制的塑形簇；例如 ffi 连字可作为一个对象，不允许颜色或导唱占位切在其内部。

当前绑定器支持单行普通文字以及静态颜色和字体样式重置。不同字号的 shaping runs 顶部对齐。未知 override、注音/续唱语法、带透明通道的样式、非标准边框模式等未接入语义明确报错，原 Document 不受影响。不要据此推断完整歌词绑定已完成。软换行遵守 Script Info 的 WrapStyle；产生实际换行时仍需后续多行布局。

`DocumentLayout.characters` 提供对象、文本范围、布局框、保守墨迹框和实际字体面。`range_bounds(start, end)` 是作者指定词范围的布局矩形，不做隐式分词；`range_bounds(..., time=t)` 可查询经过当前平移、缩放、旋转后的包围框。倾斜时使用同一二维矩阵变换布局框四角；这是本地文字布局框查询，不含父组、引用状态或描边/模糊。

### 歌词选择与来源范围

| 选择对象 | 范围与时间契约 | 入口或限制 |
| --- | --- | --- |
| 文本范围 | Python Unicode code point 的半开 `[start, end)`，不使用 UTF-8 字节或 glyph 编号 | `DocumentText.text`；歌词投影后的 body 索引与原文本索引通过 `LyricMapping` 对应 |
| 可绘制字符 | `DocumentLayout.characters` 每项是完整可独立绘制的塑形簇，可包含多个 code point | `PositionedText.start/end`；ffi 连字、组合音标不按 Python 字符数量强拆 |
| 词 | 作者指定的连续非空正文范围；分词策略可在作者代码中产生这些范围 | `range_bounds`、`background`；边界切入簇时抛出 LayoutCapabilityError，不隐式扩大或重塑 |
| 演唱单元 | `DocumentLyrics.units` 的 start/end 指向去除注音语法后的正文 | `LyricLayout.unit_group(index)` 联合正文及其所有注音，并以正文中心为组中心；跨簇拆分请求拒绝 |
| 演唱片段 | 每个 unit 的 segments 保留一次演唱区间，`#` 续唱追加片段而不复制正文 | `LyricSegment.singing` 使用绝对秒；零时长、kt 时间跳跃和重复高亮保留；source_start/end 指向原始解码文本 |
| 注音 | 单独的 RubyText.source 局部范围，通过 mapping 回到原文；显示关联与演唱关联分别保留 | `PositionedRuby.unit_index/segment_index`；颜色/样式重置作用域独立解析，整体选择用 unit_group |
| 空格与无时间文本 | 空格保留 advance，即使没有墨迹；无时间前缀/间隙有正文单元但 segments 为空 | 不凭空分配演唱时长；空格不能被转成非空字形路径 |

以上契约面向单行歌词绑定。多行/双语可以逐记录绑定后由作者组合对象组；这里没有自动跨行分词或自动拆分不可独立绘制的字形。正文颜色、注音、导唱标记使用同一来源投影，标记不能悄悄从注音内部移动到正文。

固定组合示例 `uv run python -m examples.scene_bilingual output.ass` 将两条源事件分别绑定：日文正文和注音按同一单元缩放/变色，`#` 续唱使第一字再次高亮，英文行以颜色高亮保留词间距。两行各自的组关键帧保持居中移动；不可见锚点提供测量后的行中心，画面上的青色装饰通过 ReferenceFunction 读取两个锚点的世界坐标。READY/SET/GO 独立倒计时不继承歌词组变换。源记录保存为 Comment，标记只存在于来源中。

该例的 [实际预览](images/scene-bilingual.png) 和 [播放报告](scene-bilingual-validation.json) 覆盖重复高亮、间隙、第二字、收尾；`tests/test_bilingual_example.py` 检查正文/注音共用脉冲、跨父组引用、独立提示与源记录保留。这验证逐记录组合能力，不声称自动多行排版或任意翻译时间对齐。

`background(..., follow=True)` 跟随所选字符的本地布局范围，采样继承字符动画的起止和内部 breakpoints；因此带显式断点的突变不会在背景上延迟或提前一帧。它不是世界坐标引用，若需父组变换应把背景与文字加入同一组。回归依据为 `tests/test_document_lyrics.py`、`tests/test_scene_text.py` 和 `tests/test_characters.py`，包括连字拒绝拆分、组合字符、空格、续唱与来源映射。

边界输入不会被自动延长：`\k0` 保留零时长演唱片段，`\k1` 保留 0.01 秒，`\kt` 保留显式间隙；零时长片段仍有来源，但不能直接作为要求正时长的 AnimationClip。作者可跳过它的动画或单独指定显示寿命，不能把显示窗口改写成演唱时间。向后移动演唱游标的 kt 被拒绝，并附源记录和解码文本位置。

字体回退通过 `PositionedText.fonts` 返回实际使用的字体面；请求字体与实际字体不一定相同。缺字或无法验证独立绘制的塑形簇明确报错，不用方框代替成功结果。Document 绑定会为底层 LayoutCapabilityError 补充源记录、解码文本范围与样式名，同时保留原异常链。这里的范围是当前正文/注音视图的范围，可用 LyricMapping 回查原文本；它不是原始 override 字符串的字节位置。`tests/test_characters.py` 的隔离 Fontconfig 测试同时检查 Document 前端的主字体/回退字体映射及缺字诊断；该隔离配置测试只适用于 Linux，Windows 字体提供器仍属发行矩阵验收范围。

`background(start, end, id=..., color=..., padding=...)` 按测量值生成普通 PathObject，描边和 blur 不计入文字布局框。`follow=True` 使背景在任意时刻跟随文本范围包围框，并加入文本动画的边界，适用于导唱释放占位或文字移动；它不是蒙版或自动字形轮廓。

`CuePreset` 明确指定提前量、持续时间、0–1 范围的步进时点、间隔、位置及是否保留占位。默认以首个唱段开始触发；也可用 `trigger=layout.singing[index].start` 或任何明确绝对时间。不从音节数量猜测节拍。`BarsCue` 每步减少一条，`TextCue` 按明确步进区间显示用户标签。

相对歌词定位也使用普通对象引用。将一个透明锚点作为歌词组的子对象，按选中唱段的 `start_offset/end_offset` 测量位置，再用 `replace(cued.independent[0], reference=FollowObject(anchor.id))` 让独立提示跟随锚点的世界位置。默认 FollowObject 只接管 position：歌词组旋转或缩放会改变锚点位置，提示本身保持正立和原字号，也不会继承透明锚点的 opacity。屏幕固定提示则保持原独立对象不加引用。若希望整体共同变换，可将提示加入共同父组；这些选择不会改变正文占位。

固定示例 [scene_cue_follow.py](../examples/scene_cue_follow.py) 读取第二唱段的开始时间，在 1.5–2.5 秒显示 READY/SET/GO，并跟随移动、旋转中的 ME 下方锚点。`CuePreset.trigger=layout.singing[1].start` 明确指定第二唱段，不推断节拍。运行 `uv run python -m examples.scene_cue_follow output.ass`；[预览](images/scene-cue-follow.png)与[验证报告](scene-cue-follow-validation.json)覆盖实际标准 ASS、300 帧连播和 11 个乱序跳转时刻。


自定义 factory 接收 `CueContext`（id、绝对寿命、绝对步进时点、来源），返回 `CueContent`（普通对象元组、占位宽高）。可在其中组合文字、路径、组与任意动画。对象寿命必须位于组件声明的寿命内。组件宽高是作者声明的排版空间，允许图形有艺术性的外溢。

行内组件加入歌词组，参与前后文字间距和变换。默认消失后保留占位；`keep_space=False` 会在结束时释放该宽度，后续文字和行内导唱一起重排，并支持乱序求值。背景需要 `follow=True` 才跟随重排。`bound.independent` 是独立画面坐标的对象元组，单独加入 Scene，不继承歌词组变换；若希望跟随歌词，也可以由作者将其放入共同父组。

完整固定场景见 `examples/scene_cues.py`：两个测量背景、曲线装饰、行内短条、独立文字倒计时和自定义旋转图形。运行 `uv run python -m examples.scene_cues output.ass`。实际输出的[关键帧](images/scene-cues.png)与[报告](scene-cues-validation.json)可复现：`uv run python -m tools.validate_scene_core --scene cues /tmp/scene-cues-validation`。

## 高级路径、文字轮廓与书写

`Document.create(width=1280, height=720)` 为直接构造场景提供标准 Script Info、样式和事件段；不再需要示例手写 ASS 文件头。

```python
from dataclasses import replace
from kara_templater import MorphPath, Vec2, text_to_path

shape = text_to_path(text_object)
target = shape.path.map(lambda p: Vec2(p.x * 1.5, p.y * 0.8))
shape = replace(shape, deform=MorphPath(target, start=1, duration=2))
```

`outline_text(TextObject)` 返回 `TextOutline`：真实塑形后的路径、原始 advance 布局框和实际字体面。字体回退与连字使用相同原生测量器。轮廓中二次曲线被精确转换为三次曲线；`text_to_path` 保留对象来源、寿命、变换、动画、图层和遮罩。纯空格没有墨迹路径，需保留布局空间；转为空绘图会明确报错。

文字与 drawing 的栅格提示和量化可能不同，文字转路径不承诺像素完全相同。测试在三个对齐方式下比较实际导出结果，归一化 alpha 差低于 5%；这只是当前测试字体和内容的验收范围。

`PathObject.deform` 接受 `GeometryAnimation`。`MorphPath` 处理确定目标路径；`PathFunction` 接收 `(base_path, local_seconds) -> VectorPath | None`，适合轮廓扰动和程序生成。None 表示这一时刻没有绘图。回调需声明 `max_points` 和几何时间边界 `breakpoints`；编译前执行上限预检，生成时验证声明和全局点数预算，错误携带对象、时间和来源。

`PathObject.path_at(absolute_seconds)` 可直接求值，不依赖访问顺序。`copy(delay=...)` 同样推迟变形时钟。编译报告给出实际最大绘图点数和采样间隔；不把任意回调的帧率说成严格几何误差上界。

`flatten` 用自适应 de Casteljau 细分，tolerance 指局部坐标中控制多边形到弦的距离约束，不是弧长精度承诺；后续缩放会放大空间误差。`Polyline` 提供累计长度、按近似弧长取点、前缀和重采样。递归深度、输入/输出点数均受限制。`stroke` 将折线变成带 bevel 接缝和 butt 端点的填充路径；零长度不可见。`VectorPath.circle` 使用四段三次曲线近似圆。

`resample_path` 是显式的对应准备，不自动识别字形或重排轮廓。`morph`/`MorphPath` 要求成对轮廓的封闭状态、段数、段类型和绕向相符；孔洞必须对应孔洞，外环对应外环，退化轮廓和不匹配会报错。轮廓顺序和起点由作者控制。即使端点匹配，中间仍可能自交；库不会隐式改变拓扑，必须预览作者指定的映射。

`intersect_convex(path, boundary, tolerance=..., max_points=...)` 保留为简单凸裁剪器的有界求交接口；非凸裁剪器仍不应传入此接口。一般闭合填充路径的交集、并集、差集与异或使用后文的 `path_boolean`。两者都显式细分曲线，空结果返回 None。

`WritePath` 由作者提供 `WritingStroke` 序列，每笔有明确起点、时长和开放路径。它不从字体轮廓猜笔顺。`full_path` 提供完整图形，`sample` 显露已写部分，`tip` 在同一条近似弧长路径上给出笔尖，`pen_down` 区分落笔与抬笔。无长度笔画和时间重叠被拒绝。暂停时笔尖停在上一笔末尾。

普通状态动画也可给 `AnimationClip(..., breakpoints=(...))`，值是相对该 clip 起点的秒数，用于明确切分自定义函数的不连续点。书写示例将笔画边界传给笔尖动画，因此笔尖与墨迹在相同时间区间采样。

新增固定示例：

| 示例 | 能力 | 实际 ASS 预览与报告 |
| --- | --- | --- |
| `examples/scene_outlines.py` | E07：确定性轮廓扰动、时间包络 | [预览](images/scene-outlines.png)、[报告](scene-outlines-validation.json) |
| `examples/scene_writing.py` | E08：自有笔顺、路径显露、笔尖跟随 | [预览](images/scene-writing.png)、[报告](scene-writing-validation.json) |
| `examples/scene_morph.py` | E10：孔洞对应、圆环到方环、字形变形 | [预览](images/scene-morph.png)、[报告](scene-morph-validation.json) |

运行形式为 `uv run python -m examples.scene_writing output.ass`。验证形式为 `uv run python -m tools.validate_scene_core --scene writing /tmp/writing-validation`，scene 也可选 outlines 或 morph。

验证工具现在除了关键帧，还连续渲染 300 帧，再以相反顺序创建全新的 libass filter、直接设置到各关键时间戳，比较帧哈希。这验证了当前背景、字体和 libass 环境中的跳转一致性；黑白背景、其他渲染器及整曲成本仍是后续完整验收内容。四个公共扩展类型反例可运行 `uv run python -m tools.check_scene_types`，验证错误状态、路径、导唱工厂返回值和错误向量类型会被 ty 拒绝。

## 曲线路径、粒子、残影和碎片

`MoveAlong(path, rate=..., orient=...)` 是普通 StateAnimation。路径坐标相对于动画开始时捕获的位置；Contour 使用曲线参数，Polyline 使用近似弧长。orient 开启时同时写入旋转，使对象沿切线朝向；同一时间再写 rotation 会按原有规则报告属性冲突。闭合 Contour 的采样包含隐式闭合边。以原点开始、线性缓动、不开启切线朝向的单直线运动可输出一个原生 move；复杂曲线和缓动继续使用共享采样器。

`layout_path(PathItem(...), path, ...)` 根据每个 item 明确给出的 advance 分配路径上的中心位置，anchor 指出对象本地哪个点贴到曲线上。返回普通 ObjectGroup，正文和注音可以先组合为一个 item，因此旋转和局部缩放只组合一次。对象来源和身份保留；多个不同排版副本同时加入同一场景时，调用 copy 为副本分配新身份。路径区间可反向，orient=False 可让字保持直立。max_items 在生成锚点组之前限制输入数量。

```python
from kara_templater import Emission, emit_particles

particles = emit_particles(
    (Emission(f"petal:{i}", i * 0.1) for i in range(24)),
    particle_factory,
    id="sakura",
    seed=17,
    emitter=emitter_position,
    max_particles=100,
)
scene.add(*particles)
```

factory 接收 ParticleContext，返回普通 TextObject、PathObject 或 ObjectGroup，必须保留上下文给出的 id 和出生时间，其余几何、动画和寿命由作者定义。发射列表和重复身份在任何工厂调用之前检查；无限或过长输入会在数量预算处停止。max_particles 限制根粒子数量，嵌套对象和最终输出事件仍由场景预算检查。

`context.uniform(key, low, high)` 和 `choose` 根据 seed、完整粒子身份和参数名计算稳定值。没有需要推进的 RNG 状态；改变生成顺序、先读取其他随机参数或添加不相关粒子，不改变已有粒子的随机参数。若作者让工厂依赖外部可变状态，则不属于该确定性保证。

`context.position` 是发射器在出生时刻的位置快照。`context.position_at(age)` 则重新求发射器在 birth+age 的位置，允许作者明确选择持续跟随；发射器必须是纯时间函数。函数返回的坐标空间由作者决定，同一份父组变换不能同时烘入发射器坐标并再由父组施加。

`echoes(object, count=..., spacing=..., opacity=..., decay=...)` 是历史副本，默认放在源对象后面的图层。每个副本独立延迟出生和结束，评估原对象的过去状态和几何；透明度乘在动态求值结果上，不会被后续 Tween 覆盖。复制完整组会同时延迟父组和子对象；只复制一个子对象则得到它的本地历史，不会自动捕获未传入的祖先历史。通过 ID 跟随其他对象使用下文的 FollowObject；引用图检查显式依赖与父子关系，不分析任意 Python 闭包。

`split_path(path_object, columns=..., rows=...)` 将静态填充轮廓按本地网格求交，输出普通 PathObject。新路径本身就是碎片，因此移动、旋转时不依赖固定在画面上的 clip。保留源状态和来源，新增切口也会继承 border；这是刻意的每片描边语义。细分和片数有预算。独立抗锯齿边缘可能出现细缝，示例在拼合完成后切回原始完整三次曲线，避免永久切缝。动态变形源需要先明确采样时刻，当前 split_path 不隐式处理它。

新增固定示例：

| 示例 | 内容 | 实际输出证据 |
| --- | --- | --- |
| `examples/scene_round.py` | E03：圆弧正文/注音、重复高亮、共同缩放 | [预览](images/scene-round.png)、[报告](scene-round-validation.json) |
| `examples/scene_sakura.py` | E04：24 个独立花瓣、12 个游标触发花瓣、残影 | [预览](images/scene-sakura.png)、[报告](scene-sakura-validation.json) |
| `examples/scene_fragments.py` | E05：4×3 文字碎片聚合与完整字形收尾 | [预览](images/scene-fragments.png)、[报告](scene-fragments-validation.json) |

运行方式与其他场景一致，如 `uv run python -m examples.scene_sakura output.ass`。验证参数为 `--scene sakura`、`--scene fragments` 或 `--scene round`。圆弧示例使用仓库有许可的 KaraTestCJK.ttf（仅覆盖示例所需的「時」「々」）与 DejaVu Sans，验证报告记录两个字体的 SHA-256；播放器需要提供对应字体。花瓣和笔画路径均由示例直接构造。

樱花示例的正文 SoftSweep 与游标共用 1–2 秒时钟，填充/描边分别采用 24/32 px 过渡宽度。游标通过 `front_at` 获取过渡中心，从整行左边界外 16 px 移动到右边界外 16 px；花瓣在这个前沿出生并保存出生位置。颜色场使用采样保持，游标使用原生连续 move，因此采样区间内部不声称两者像素前沿完全重合。圆弧的正文与注音是直接构造的对象组，不用于验证 Document 注音绑定；文件输入的绑定由 layout_document_lyrics 及其独立示例覆盖。

## 屏幕颜色场与柔和扫色

TextObject/PathObject 的 `material` 接受类型化 PaintField。`LinearGradient` 使用 ColorRamp/ColorStop 定义绝对脚本坐标上的色标；填充与描边可以分别设置。`SoftSweep` 定义前沿跨度、局部开始时间、时长、缓动、填充宽度和描边宽度，颜色对的顺序为 `(未唱, 已唱)`。没有指定的通道保留当前动画状态的颜色；指定的通道由颜色场覆盖。因此颜色场的优先级高于该通道的 StateAnimation。

`SoftSweep.front_at(time)` 返回过渡中心的脚本坐标，`time` 与颜色场采样一样是对象出生后的局部秒数。中心在左右端点之外各延伸最大过渡宽度的一半，以确保唱前/唱后完全覆盖；区间外固定在对应端点。使用全局时刻驱动跟随对象时，先减去承载颜色场对象的出生时间。

```python
from kara_templater import PINK, WHITE, SoftSweep

material = SoftSweep(
    left=240, right=1040, start=1, duration=3,
    fill=(WHITE, PINK), width=24,
    outline=(PINK, WHITE), outline_width=36,
)
```

颜色场目前固定在屏幕脚本坐标中，不随对象或父组旋转；运动文字可以穿过静态渐变。复制会保留颜色场并延迟其局部时钟，但 offset 不移动色标。组不继承 material；需要对叶对象显式设置。文字转路径保留 material。支持与正向矩形或矢量 clip 相交；反向 clip 与颜色场组合目前会给出明确诊断，不静默忽略裁剪。矢量求交的近似与坐标规则见下文动态遮罩。

编译器将颜色场拆为共用整数边界的互斥条带，每条在中心采样 RGB，生成标准 `\clip` 与颜色标签。默认 step=1 个脚本像素；更大的 step 是作者明确选择的空间近似，并不自动保证 2/255 色差。相邻同色条带和相邻时间的相同事件会合并。静态渐变允许原生 move；动态颜色场使用共有的时间采样器。报告中的 `peak_bands` 与 `*-bands` 策略解释展开成本。SceneBudget.max_bands 限制单次展开，max_events 的预检包含时间×条带上限，生成时仍检查实际事件/字节/峰值。

自定义 PaintField 实现 `axis`、`max_bands`、`breakpoints` 和 `bands(start, end, local_seconds, base_state)`。返回 PaintBand 必须以整数边界完整、无重叠地分割请求区间；超出声明数量或出现空隙会报错。空 breakpoints 声明静态颜色场；动态场需要声明关键时间边界。函数须可任意顺序求值，不推进隐藏状态。

这里的 blur 处理整个文字轮廓，随后才进行裁剪；不会把 clip 羽化，也不等于先着色再让颜色渗入辉光。`scene_sweep` 用单独、未分条的恒定粉色底层辉光展示这一差别。彩色前沿向辉光渗透仍需不同的合成策略。

| 示例 | 内容 | 证据 |
| --- | --- | --- |
| `examples/scene_gradient.py` | E09：填充/描边渐变、原生移动、逐字配色和残影 | [预览](images/scene-gradient.png)、[报告](scene-gradient-validation.json) |
| `examples/scene_sweep.py` | E11：独立宽度的柔和扫色和整词辉光 | [预览](images/scene-sweep.png)、[报告](scene-sweep-validation.json) |

运行 `uv run python -m examples.scene_sweep output.ass`；真实播放验证使用 `uv run python -m tools.validate_scene_core --scene sweep /tmp/sweep-validation`（也可选 gradient）。

`uv run python -m tools.validate_paint_fields /tmp/paint-fields-validation` 对系统 libass 进行单独的像素比较。固定旋转/模糊/半透明文字在黑、白和彩色图案背景上分条前后最大通道差为 0；320×160、不缩放的灰度渐变在像素中心最大 RGB 误差为 0，见[报告](paint-fields-validation.json)。该直接 RGB 参考显式设置 `YCbCr Matrix: None`，避免历史 VSFilter 色彩转换；没有这个声明的输入文档仍保留其原始色彩语义。这些结果不覆盖输出分辨率缩放、所有彩色色标或任意时间函数的误差。

## Document 正文与注音绑定

`document.lyrics_at(record_index)` 返回不执行代码、不进行测量的 DocumentLyrics。它在原有 DocumentText 上解析 `正文|注音`、全角分隔符、`#` 延续、注音 `!` 断开/`<` 回溢标记，并保留全部原始 tokens、颜色作用域和绝对演唱时间。未唱的前缀、kt 后至下一时间标签之间的文本也会保留。无时间标签的注音、无前置单元的延续和一个片段内多个分隔符会报错。

`lyrics.body.text` 是去除注音和控制符后的正文。LyricMapping 将正文/注音中的范围映射回原始已解码文本的 Unicode 码点范围；LyricUnit 的 start/end 指正文范围，每个 LyricSegment 保留原始范围、SingingSpan 和可选 RubyText。`#` 为前一单元追加演唱片段，不复制正文、不合并或丢弃零时长高亮。原始 token 字符位置与解码文本码点范围是两种坐标，不能混用。

```python
from kara_templater import Lifetime, Scene, layout_document_lyrics

layout = layout_document_lyrics(document, record_index, display=Lifetime(0, 5), ruby_gap=8)
scene = Scene(document)
scene.replace_source(record_index)
scene.add(layout.group())
result = scene.compile()
```

`layout_document_lyrics` 先对完整正文的兼容字体 run 塑形，再为注音安排空间；颜色或时间边界不主动拆坏连字。连续、不带断开标记的注音单元共用一行；显式断开/回溢标记建立新的布局组。超宽注音按分组规则为后续注音保留空间，同一正文单元的多个注音片段保持在该单元上方。`ruby_gap` 是正文布局框与注音布局框之间的距离，不等于可见墨迹之间的距离。

`layout.body` 保留通用 DocumentLayout 的字符选择、范围测量和背景接口；`layout.ruby` 记录每份注音的 unit_index、segment_index 和独立 DocumentLayout。`layout.unit_group(index)` 将正文单元与其注音组织到以正文中心为轴的普通 ObjectGroup 中，便于共享缩放或旋转。若独立分组边界切入连字，会明确拒绝；不需要独立分组时，跨演唱单元的连字可以继续保留为一个绘制簇。

颜色优先级仍是样式 → 显式标签 → Python 对象配置 → 动画/材质。注音优先使用 `<正文样式名>-furigana`；没有时派生半字号、半描边、半阴影的样式，测量过程不修改源文档。TextAppearance.inline_colors 记录显式颜色来源，所以显式设置为与正文默认色相同的颜色，也能正确覆盖独立注音样式。空颜色标签解除该通道覆盖，r/rStyle 清除所有覆盖并切换样式。

正文与注音都保留 SourceRef，注音还包含片段索引。display 只改变显示寿命，singing 仍为原始绝对秒数；复制/动画继续使用普通场景对象契约。导唱标记在解析时映射到正文边界，位于注音内容或延续控制符内部的锚点会报错。带注音的绑定使用下文 `bind_lyric_cues(layout, presets)`，它将占位释放同时传递到正文与注音；单独调用 `bind_cues(layout.body)` 仍只处理正文。

固定 E01 示例为 [scene_lyrics.py](../examples/scene_lyrics.py)，使用仓库字体的「時々」及拉丁注音。正文与注音共用缩放轴，填充/描边采用独立扫色，多层恒定粉色辉光作为普通副本。见[预览](images/scene-lyrics.png)和[报告](scene-lyrics-validation.json)。该示例的辉光按绘制簇合成，不宣称等同于整词覆盖先合并再模糊；颜色场仍固定在屏幕脚本坐标中。更复杂的覆盖合成是独立后续验收项。

```sh
uv run python -m examples.scene_lyrics output.ass
uv run python -m tools.validate_scene_core --scene lyrics /tmp/lyrics-validation
```

编译器现在只在已知变化区间内密集采样：状态动画的 clip 区间与 SoftSweep 的扫描区间。区间外使用已确定的保持/释放状态，并保留边界。任意 GeometryAnimation 或自定义动态 PaintField 仍保守地按整个寿命采样；不会根据少数相同样本猜测函数恒定。事件预检使用同一变化区间上界，sample_interval 报告变化区间中的实际最大采样间隔，静止平台不计入该值。


## 导唱符与注音联动

```python
from kara_templater import BarsCue, CuePreset, bind_lyric_cues

cued = bind_lyric_cues(layout, {
    "bars": CuePreset(factory=BarsCue(), keep_space=False),
})
scene.add(cued.group(), *cued.independent)
```

`bind_lyric_cues` 接受 LyricLayout，默认读取已映射到正文范围的输入标记，也可传 `markers=(CueMarker(...), ...)`。它复用相同的内容工厂与时间规则，不增加播放器标签。返回 CuedLyrics，包含更新后的 `lyrics`、完整 cue 元数据、inline 和 independent 对象。

行内占位在显示窗口内预留；keep_space=False 时，在导唱符结束边界释放。单元前的占位让正文及其注音都移动整个占位宽度；单元内部的占位会扩大正文框，注音移动半个占位宽度，从而保留相对正文中心的原始偏移。单元末端的占位只影响后面的单元。多次占位和释放可叠加，注音的各个演唱片段应用同一正文锚点规则。

`cued.group(position=...)` 包含正文、注音和行内导唱符，寿命覆盖提前显示的导唱符；各个文字对象仍保留原显示寿命和原唱词时间。`cued.independent` 单独加入场景，因此不会随该歌词组平移或缩放。注音保留原来独立样式、来源和时间，不因占位重新拆分文字。

这项联动计算的是导唱符引入的平移，不是任意对象间的通用跟随图。先绑定导唱符，再对共同 ObjectGroup 应用缩放/旋转；若给同一文字的 position 通道再添加与释放区间重叠的动画，仍按普通属性冲突规则诊断。任意逐字变形后的注音重排属于后续布局/引用能力。

新增固定示例 [scene_lyric_cues.py](../examples/scene_lyric_cues.py) 同时演示句首条形导唱符、句中数字及屏幕独立 READY/SET/GO。正文/注音在 1s 和 2.5s 两次释放时一起调整，原始演唱时间不变。[预览](images/scene-lyric-cues.png)与[报告](scene-lyric-cues-validation.json)记录真实 ASS 输出、连续播放和边界前后跳转验证。

```sh
uv run python -m examples.scene_lyric_cues output.ass
uv run python -m tools.validate_scene_core --scene lyric-cues /tmp/lyric-cues-validation
```


## 局部与动态遮罩

RectangleClip 与 VectorClip 的 `space` 默认为 `"screen"`，保持固定屏幕脚本坐标；设置 `space="local"` 则相对对象的对齐锚点，随对象及父组的缩放、旋转、平移变换。对文字而言，局部零点是 alignment/pos 锚点，不自动改成字形左上角。局部矩形在输出时转换为矢量裁剪，保留旋转后的形状。

```python
from kara_templater import PathFunction, RectangleClip, VectorClip, VectorPath

crop = RectangleClip(0, 0, 300, 90, space="local")
spot = VectorClip(
    VectorPath.circle(85),
    deform=PathFunction(spotlight, max_points=13, breakpoints=(0.5, 4.5)),
)
```

VectorClip.deform 复用 GeometryAnimation/PathFunction，回调接收原始遮罩路径和对象出生后的局部秒数。None 表示空遮罩区域：普通裁剪隐藏整个对象，反向裁剪显示整个对象。回调需纯函数求值并声明点数上界/时间边界；复制 delay 推迟时钟，offset 只移动 local 遮罩，screen 遮罩保持屏幕位置。

局部裁剪的移动无法只靠文字的原生 move 完成，所以编译器采样对象和裁剪路径；固定屏幕裁剪仍允许原生 move。任意遮罩回调按整个显示寿命保守采样，并切开声明的时间边界。所有输出使用标准 clip/iclip，不使用可变矢量 t 或渲染器扩展。

正向矢量遮罩可以与 LinearGradient/SoftSweep 条带组合：每个条带矩形与遮罩求交，输出一个正向矢量 clip。求交保留孔洞绕向；曲线先按 0.25 脚本像素的细分容差变为多边形，因此这是显式近似，不是曲线布尔精确解。局部遮罩先转为屏幕坐标，再与固定屏幕颜色场求交。矩形屏幕裁剪仍使用原生整数矩形交集。

复杂度检查包括原始路径、回调声明点数、实际返回路径和求交中间/结果点数，超限失败。ObjectReport.peak_clip_points 记录采样得到的遮罩及求交结果的峰值点数，和文字/绘图本身的 peak_path_points 分开。回调异常携带对象 id、源信息与采样时刻。

local 遮罩现在与 skew、父组非均匀缩放和子旋转共享完整二维矩阵。反向遮罩可以通过差集与颜色场组合，矩形与通用矢量的边缘差异见后文。ObjectGroup 可直接声明共享遮罩，嵌套求交范围见下文；镜像与零面积状态也使用同一矩阵。

固定组合示例 [scene_masks.py](../examples/scene_masks.py) 展示随组移动/旋转/缩放的局部裁剪、独立屏幕聚光路径和带矢量裁剪的渐变。[预览](images/scene-masks.png)及[报告](scene-masks-validation.json)记录实际标准 ASS 的连续播放、跳转、复杂度和成本。

```sh
uv run python -m examples.scene_masks output.ass
uv run python -m tools.validate_scene_core --scene masks /tmp/masks-validation
```


## 对象引用与世界坐标跟随

`FollowObject` 按 ID 读取目标的世界状态，默认只接管 position。它能跨父组使用，不依赖 Scene.add 的插入顺序；目标也可以是 ObjectGroup。以下例子让标签始终位于 leader 下方，并延迟 0.2 秒：

```python
caption = TextObject(
    id="caption",
    text="following",
    lifetime=Lifetime(0, 5),
    reference=FollowObject("leader", offset=Vec2(0, 80), delay=0.2),
)
```

`offset` 是屏幕坐标偏移，不随目标旋转。`channels` 可选择 position、scale、rotation、opacity 等 VisualState 属性；`opacity_factor` 仅在选中 opacity 时乘到目标透明度上。引用在本对象局部动画与父组变换之后求值，接管的通道替换世界状态；例如显式跟随 opacity 会替换本对象已经继承的父组透明度。未接管的通道继续保持正常继承。同一对象的局部动画不能写入引用已接管的通道，构造时即报错。

`scene.evaluator().at(id, seconds)` 是世界状态查询接口；`object.at(seconds)` 仍只计算本地动画。查询时间超出目标寿命时取端点状态，目标是否正在显示不影响引用求值；跟随对象有自己的显示寿命。每次查询独立求值，因此倒序查询和跳转不会改变结果。正 delay 读取历史，负 delay 读取未来。

高级关系使用 `ReferenceFunction(function, dependencies, channels, breakpoints=...)` 或实现 StateReference 协议。回调接收 `(base_world_state, absolute_seconds, lookup)` 并返回 VisualState；`lookup(id, seconds)` 只能读取声明的依赖。必须声明输出通道，不允许修改其他通道。回调应为纯函数；对自定义时间映射产生的不连续点，作者提供绝对时间 breakpoints。FollowObject 会自动传递目标动画和祖先的边界，并加上 delay。

引用图在执行回调前检查缺失 ID、重复 ID 和循环依赖，父子变换依赖也参与检查。因此父组不能引用自己的子对象；带延迟的闭环也会被拒绝。NativeEvent 是已生成事件，不提供可引用的视觉状态。错误包含对象 ID 和可用的来源信息；该检查不承诺发现回调内部自行维护的隐藏依赖或副作用。

复制单个跟随对象时，delay 延迟其历史时钟，offset 平移其跟随结果。复制整组会将组内引用重定向到副本，并补偿内部目标的共同时间平移；外部引用仍读取原目标的历史。外部世界位置引用不会因为复制父组的位置而自动改为相对坐标。`echoes` 保留引用历史，并衰减动态透明度；这仍是对象状态组合，不是离屏组透明度合成。

固定示例 [scene_follow.py](../examples/scene_follow.py) 同时展示跨父组标签、五个延迟圆点和读取两个目标位置的中点回调：

```sh
uv run python -m examples.scene_follow output.ass
uv run python -m tools.validate_scene_core --scene follow /tmp/scene-follow-validation
```

[预览](images/scene-follow.png)与[验证报告](scene-follow-validation.json)记录实际 libass 播放和跳转结果。含引用的对象当前按时间网格采样，保留显式边界并合并相同输出；不推断任意回调可以原生表达。


## Track 与新对象共同输出

`prepare_karaoke(document, tracks=(track,)).scene` 将 Track 的标准 ASS 结果作为带来源的 NativeEvent 接入。可以向它添加普通场景对象，再调用 compile，对混合输出检查总成本。原 render_karaoke 也复用该准备阶段和事件插入器。详细预算时机、再次生成与可编辑性限制见 [Track 组合说明](tracks.md#与-scene-特效组合)；固定示例为 [scene_tracks.py](../examples/scene_tracks.py)。


## 仿射组合与轮廓降级

`Affine2D(a, b, c, d, tx, ty)` 将点映射为 `(a*x + c*y + tx, b*x + d*y + ty)`。`outer @ inner` 表示先应用 inner，再应用 outer；`matrix.apply(Vec2(...))` 可直接用于 VectorPath.map。VisualState.transform 给出同一矩阵，顺序为本地双轴剪切、轴向缩放、顺时针旋转、平移。组矩阵从内到外相乘，因此非等比父缩放与子旋转不再简单相加缩放/角度。

ObjectGroup 可声明和动画化 skew。世界状态对可分解的矩阵返回等价 scale/rotation/skew；产生剪切时的这些数值不一定等于局部属性的乘积/和，但 transform 映射相同。已有无剪切组合保留原分解形式。组矩阵分解支持带符号缩放、反射及退化情况；第一基向量归零时使用剩余基向量，避免除零。负缩放经路径降级表达，不直接输出负 fsc 标签。

libass 的文字剪切含基线相关处理，不能直接作为通用对象矩阵。因此需要仿射降级时，编译器先提取单行文字轮廓或已有路径，再变换控制点，输出标准 ASS 绘图；局部遮罩使用同一矩阵。文字对齐锚点保持，空白文字无可见轮廓则不生成绘图。填充、描边、模糊和阴影在变换后的路径上绘制：border/blur 仍是脚本空间参数，不是先画完整描边再对覆盖率做任意仿射。这不提供离屏图层合成。

已知需要轮廓的文字在属性回调前检查轮廓点预算；每次编译缓存一份原始轮廓。自定义函数造成的仿射需求按实际输出样本确定，实际点数继续受预算限制。动态对象的所有输出样本采用一致后端，避免剪切经过零点时在字体与轮廓之间来回切换；这不是对采样点之间任意函数的误差保证。普通等比缩放可继续输出原生文字。报告策略增加 `-affine-path`，并记录 peak_path_points。

轮廓文本目前要求单行；换行对象会明确报错，可拆为多个 TextObject 放入共同组。轮廓光栅与字体原生 hinting 不承诺逐像素等价；本功能的像素验收参考是独立计算的仿射路径。镜像与零面积行为见后文；共享组遮罩见下一节。

固定示例 [scene_affine.py](../examples/scene_affine.py) 组合非等比父缩放、父旋转/剪切动画、两个不同子旋转和局部遮罩。运行 `uv run python -m examples.scene_affine output.ass`，或用 `tools.validate_scene_core --scene affine` 重建[预览](images/scene-affine.png)与[验证报告](scene-affine-validation.json)。


## 共享组遮罩

ObjectGroup 与叶对象共用 RectangleClip/VectorClip 接口。组的 `space="local"` 相对该组坐标原点，先经过组及祖先的世界矩阵，再作为同一个世界遮罩应用到全部后代；它不再跟着各个孩子自己的位置、旋转或形变移动。`space="screen"` 始终是固定脚本坐标。

```python
group = ObjectGroup(
    id="window", lifetime=Lifetime(0, 5), children=(text, decoration),
    state=VisualState(position=Vec2(640, 360)),
    clip=RectangleClip(-200, -80, 200, 80, space="local"),
)
```

动态 VectorClip.deform 接收相对**遮罩所属对象出生**的秒数。孩子可以晚出生、早结束，但不重置组遮罩时钟；复制组时遮罩自然随出生时间延迟。组遮罩的边界参与后代的采样网格与量化报告。单次编译按遮罩 owner/time 缓存世界形状，缓存最多 128 项；作者回调仍必须为纯函数，不依赖调用次数。

父、子遮罩通过几何求交合成，每条 ASS 事件只输出一个有效 clip/iclip：

- 单一组遮罩可使用任意标准矢量路径，或反向遮罩；原有空动态遮罩与反向语义保留。
- 多个正向矩形取交集。正向矢量与矩形/凸多边形求交保留孔洞与轮廓方向；凸曲线边界按 0.25 脚本像素容差细分，点数受 SceneBudget 限制。
- 相同的重复遮罩去重。空交集隐藏后代，不输出无效矩形；屏幕矩形取整后变为空也遵循这一规则。
- 不同非凸遮罩通过一般路径交集组合；正向与反向组合转为差集，两个反向组合转为并集的反向。反向遮罩与颜色场也已接入，具体精度与预算见后文。

这是一份共享的几何裁剪规则，最终分配给每个后代事件；不是将整组先离屏合成再应用一次覆盖率蒙版，边界抗锯齿与组透明度仍遵循各事件的标准 ASS 绘制语义。

预检覆盖所有祖先遮罩的原始路径与回调声明点数，执行时检查实际返回和求交复杂度；错误定位到遮罩所属对象及来源。叶对象报告中的 peak_clip_points 包含继承遮罩与合成结果。嵌套组不改变原有子对象/祖先寿命交集规则。

固定示例 [scene_group_masks.py](../examples/scene_group_masks.py) 将移动聚光路径施加于文字与嵌套装饰条，装饰组另有一个局部矩形限制。运行 `uv run python -m examples.scene_group_masks output.ass`；[预览](images/scene-group-masks.png)与[报告](scene-group-masks-validation.json)可由 `tools.validate_scene_core --scene group-masks` 重建。


## 镜像、零缩放与退化状态

VisualState.scale 支持有限的正数、负数和零。负轴表示镜像，可以用普通 Tween 经过零点，或者将带符号缩放放在父组上与子旋转/剪切组合。`VisualState.singular` 标识线性变换是否将填充几何压为零面积。世界坐标和引用在这种状态下仍可查询；父子状态求值不会因为零缩放而除零。

反射对象输出变换后的标准绘图，所有实际 fsc 标签保持有效；同一动态对象的输出样本使用一致的几何后端。零面积文字或填充路径在对应输出样本不生成事件，包括其描边和阴影，不额外留下细线或点。近零但非零的状态不使用固定行列式阈值拒绝；最后仍受 ASS 坐标精度与采样间隔约束。

局部遮罩随同一带符号矩阵变换，孔洞与外轮廓的方向一起反转。所属对象处于奇异状态时，局部正向遮罩为空，反向遮罩不再限制后代；固定 screen 遮罩不受该变换影响。这与后代显式引用世界通道后的覆盖优先级保持一致。

PositionedText.layout_scale 保存布局时的正向测量缩放。之后即使通过 dataclasses.replace 把文字状态改为负缩放或零缩放，range_bounds(..., time=...) 也从原始测量尺寸计算，不从修改后的对象状态反推尺寸。源字体的测量比例仍要求正数；镜像应在布局后的对象或共同组上表达。

固定示例 [scene_mirror.py](../examples/scene_mirror.py) 使用 SceneTimeline 把一组旋转文字、箭头和局部遮罩依次从 1 缩至 0、翻至 −1、再恢复到 1。[预览](images/scene-mirror.png)与[验证报告](scene-mirror-validation.json)来自实际标准 ASS，可用 `uv run python -m examples.scene_mirror output.ass` 重建。


## 通用闭合路径布尔运算

`path_boolean(first, second, operation="intersection", tolerance=0.25, max_points=4096, max_work=1_000_000)` 支持 `intersection`、`union`、`difference` 与 `xor`。PathBooleanOperation 是公开 Literal 类型。结果是普通 VectorPath，空面积返回 None，可以用于路径对象、遮罩或 PathFunction 回调。

每个输入按非零绕向解释填充；孔洞、自交、重合边、分离轮廓和仅点接触均参与这一规则。算法先细分曲线，再按顶点与交点的 y 值划分线性区域；内部公共边消去，外边界重新连接为外轮廓/孔洞。结果加描边不会暴露扫描区域的内部网格线。开放轮廓明确拒绝。

这是多边形布尔运算加显式曲线近似，不是解析贝塞尔布尔求解器。tolerance 为输入路径的局部单位，之后放大路径也会放大近似误差；场景遮罩先变换到世界坐标再求交，因此容差为脚本像素。共享顶点统一到 1e-9 路径单位，清理共线点使用 1e-8 单位容差；不承诺比这些数值更细的拓扑。

max_points 同时约束两输入的合计原始/细分点数和最终输出，临时边界元素最多按 8 倍点数预算展开。max_work 计数候选边对检查、扫描边及边界处理，超限即诊断，不自动放宽容差。SceneBudget.max_boolean_work（默认 1,000,000）约束每次通用遮罩布尔操作；原有凸裁剪快速路径继续受点数预算限制。自定义 PathFunction 内直接调用时由作者传入自己的布尔预算，并声明返回路径点数。

嵌套遮罩只输出合成后的单一 clip/iclip，不依赖多标签覆盖。一个正向和一个反向遮罩使用差集，两个反向遮罩使用并集再反向；已有正向矩形和凸边界快速路径保留。

反向屏幕矩形与颜色场组合时，每条色带拆为最多四个互不重叠的原生矩形，预检事件估算也计入这个上限。通用反向矢量则从色带矩形减去遮罩，生成正向矢量裁剪。libass 的矢量边缘覆盖率与硬矩形裁剪不同，不能把数学几何等价说成像素完全相同；这也可能在矢量色带边缘带来小幅覆盖率差异。

[独立 RGB 对照报告](boolean-masks-validation.json) 固定 320×240、8px 色带和整数孔洞，使用系统 libass 在黑、白和彩色测试图背景验证：原生反向矩形与参考逐像素一致，矢量版本最大 RGB 差均为 3/255。该数值只适用于这份夹具，不是任意曲线、背景分辨率或 YUV420 合成的全局误差保证。几何正确性另以非零绕向点查询、独立手写矢量参考和无内部描边缝隙的实际光栅测试验证。

固定 [scene_boolean.py](../examples/scene_boolean.py) 用同一个移动圆形裁剪器展示四种操作；轮廓具有正常描边，形状回调不需要编写 ASS 标签。见[预览](images/scene-boolean.png)与[连续播放报告](scene-boolean-validation.json)。重建命令：

```sh
uv run python -m examples.scene_boolean output.ass
uv run python -m tools.validate_scene_core --scene boolean /tmp/scene-boolean-validation
uv run python -m tools.validate_boolean_masks /tmp/boolean-masks-validation
```

## 整组几何合并与共享辉光

`merge_geometry(group)` 将组中的文字轮廓和填充路径取并集，返回普通 `PathObject`。可以用 `dataclasses.replace` 指定填充、描边、模糊、颜色场与动画，并复制为多个外观层。重叠几何的内部边界被消去，适合整词统一描边和辉光；返回对象保留根组的变换、动画、透明度、遮罩、引用和来源。

子对象的几何变换、动画、路径变形及与祖先相交后的寿命参与合并。动态合并在编译采样时求值，支持任意顺序查询和延迟复制；静态几何只计算一次。子对象颜色、透明度、描边、模糊和图层不参与几何并集，因此透明度为零的子对象仍贡献形状。后代遮罩和世界引用目前明确拒绝；根组遮罩仍作用于合并结果。文字使用单行字形轮廓，其栅格化不承诺等同于原生文本 hinting。

`tolerance` 是根组局部坐标中的曲线细分容差，组放大会放大误差。`max_points` 限制每个来源及结果，单次布尔工作区允许两倍点数；`max_work` 限制每次布尔操作，而非整个组的累计工作量。动态回调在编译器预算预检之后运行，最近 128 组相同路径的并集结果可复用。

这是几何合并；需要保留子对象颜色并先合成后模糊时，使用下述显式整组 RGBA 合成。扫色覆盖率材质的完整迁移仍需独立验证。

固定 [scene_word_glow.py](../examples/scene_word_glow.py) 用四个重叠字形生成一个共享轮廓，再组合辉光与前景。见[预览](images/scene-word-glow.png)及[连续播放验证](scene-word-glow-validation.json)。

```sh
uv run python -m examples.scene_word_glow output.ass
uv run python -m tools.validate_scene_core --scene word-glow /tmp/scene-word-glow-validation
```

## 动态矩形遮罩

`RectangleClip(..., deform=RectangleFunction(callback, breakpoints))` 的回调接收所属对象出生后的秒数，返回 `(left, top, right, bottom)` 或 `None`。返回值必须有限且面积为正；`None` 表示空区域，正向遮罩隐藏对象，反向遮罩不限制对象。支持组遮罩、延迟复制和局部坐标，断点必须位于所属对象寿命内，编译预算预检先于回调。

屏幕坐标及轴对齐局部变换保留原生矩形裁剪，边界按 ASS 整数坐标量化；旋转/剪切后降为矢量多边形，因此边缘抗锯齿与原生硬矩形不同。现有静态局部 RectangleClip 的矢量降级行为保持不变。动态矩形按 Scene 采样区间取中心值，不自动编译为原生矩形 `\t`。

固定 [scene_rectangle.py](../examples/scene_rectangle.py) 用相同函数驱动正反向文字遮罩，输出标准 ASS；见[预览](images/scene-rectangle.png)和[验证报告](scene-rectangle-validation.json)。

```sh
uv run python -m examples.scene_rectangle output.ass
uv run python -m tools.validate_scene_core --scene rectangle /tmp/scene-rectangle-validation
```


## 长时间轴与复制的数值时钟

对象动画、路径、颜色场与动态遮罩在计算出生后的秒数时，将相减结果统一到 1e-10 秒。ASS 事件取整前将百分之一秒数统一到 1e-8，以稳定半格边界的 ties-to-even 取整。这是数值时间分辨率，远小于 ASS 的 10 ms 事件网格；不是自定义函数的平滑性或误差上界。避免复制到较晚时间后，浮点消减噪声把同一透明度或事件边界推到不同整数。

恒等组织组（无变换、动画、遮罩或引用）保留后代可用的原生 move，不因分组而强制采样。父组截断子对象出生时刻时仍使用采样，以免重置原生动画时钟。

## 180 秒组合压力夹具

固定 [scene_whole_song.py](../examples/scene_whole_song.py) 将 E01–E12 按 6 秒一段复制到 180 秒，检验完整组的时钟、内部引用和累计成本。案例表使用明确的 id、名称与工厂；E06 使用 scene_cues 的测量背景框和贝塞尔装饰。独立跟随能力继续由 scene_follow 验证。内容是机制压力夹具，不是新作歌曲，也不代表所有案例的视觉要求已经通过。

沿用事前预算：250,000 事件、100 MiB、峰值 2,000；帧率与单例相同，为 50 Hz。第六十四批修正樱花前沿后的当前输出为 120,104 事件、峰值 556、62,539,000 字节，预检估算 142,489。此次机器上生成约 4.64 秒，系统 libass 连续渲染 9000 帧约 15.39 秒。机器、字体、渲染器、测量范围与 RSS 限制均记录于[报告](whole-song-validation.json)，不据此承诺所有播放器实时运行。未包含 E06 的初版数据保存在[历史报告](whole-song-validation-initial.json)。

重复生成字节一致，150 个逆序新实例跳转与连续播放一致；后续重复片段的 5400 个帧与首轮对应帧一致。渲染验证明确采用毫秒时间基、每 20 ms 一帧、统一 +1 ms 偏移，避免 FFmpeg ASS 过滤器在事件边界将浮点时间截断到前一毫秒。此前发现的复制后事件半格和透明度差异已在编译器数值时钟中修复；精确整数毫秒对照另用于区分渲染时钟问题。

验证还独立导出十二个原示例，各渲染 300 帧，与整曲中首轮对应片段比较，共 3600 帧一致；这能发现包装成组时持续遗漏某个对象、却在每轮重复同一错误的情况。报告列出每例 id、实际工厂模块、独立 ASS 哈希与比较数量。E06 的[整曲预览](images/whole-song-e06.png)取自 30.001、30.501、31.501、33.001 秒，词背景框和曲线装饰均保留。独立导出仍使用同一引擎，因此该对照证明组合一致性，不替代独立视觉参考误差或四种背景验收。

```sh
uv run python -m examples.scene_whole_song output.ass
uv run python -m tools.validate_whole_song /tmp/whole-song-validation
```

## 显式整组 RGBA 合成

`rasterize_group(group, resolution=(width, height), blur_radius=0, settings=RasterSettings(...), budget=SceneBudget(...))` 返回 `RasterizedGroup`。其中 `scene` 是可继续添加普通文字、路径和其他装饰的独立场景，`sampled_frames`、`source_events` 与 `max_channel_error` 记录采样次数、输入降级事件数及显式空间量化容差。最终使用同一个 Scene 编译器输出标准 ASS；播放不需要位图附件或自定义标签。

执行顺序为：按现有 Scene 语义绘制子对象与遮罩 → 合成到给定视口的 RGBA → 可选的整组预乘颜色模糊 → 根组透明度 → 空间量化 → ASS 整数像素矩形。子对象的颜色、图层、透明度和自身模糊参与第一步，根组透明度只施加一次。`blur_radius` 为 0–100 ASS 像素，使用 libass 的有限模糊核。根组遮罩同样在整组模糊之前作用，不是模糊后的裁剪；视口外的内容不会贡献向视口内扩散的辉光。普通 `ObjectGroup` 的默认透明度语义不变。

组必须自包含；外部引用由 Scene 编译器诊断，根组自身的世界引用当前明确拒绝。返回的是已烘焙事件，不能再像原始文字对象一样编辑字形或重新安排子对象。可以修改原组后重新调用，或在返回的 scene 中添加其他对象。来源为空的纯图形保持无来源；有来源时汇总后代的歌词与轨道标识，显式根来源优先。

时间处理分两步：源图形先按 SceneBudget 降级，再在输出区间中心采样 RGBA。输出以 `budget.fps` 为基础，额外保留源事件起止及根透明度动画的显式断点，避免粗采样吞掉短寿命对象。区间内保持该帧，相邻完全相同帧合并。此策略不承诺连续时间误差界；`max_channel_error` 仅约束空间量化造成的背景合成颜色差，默认 0，也不覆盖缩放播放与 YUV 色度抽样产生的变化。

`RasterSettings` 限制单帧像素/覆盖面积、图像、矩形、事件、文本量、采样帧数与累计输出文本；`SceneBudget` 继续限制源场景和最终场景的事件、峰值与 UTF-8 字节。粗网格帧数和画布大小先于动画回调检查；源降级后加入边界可能进一步触发帧数限制。预算不足会报错，不自动降帧率或增大色差。`max_cached_masks` 不用于此接口。像素事件通常非常昂贵，必须测量实际输出，不能据此假定适合整曲。

固定 [scene_composite.py](../examples/scene_composite.py) 使用交叠彩色字母、整组模糊和透明度动画，明确选择 320×180、10 Hz、8/255 空间量化容差，并单独声明较大的事件预算。导出与真实 libass 验证：

```sh
uv run python -m examples.scene_composite output.ass
uv run python -m tools.validate_scene_core --scene composite /tmp/scene-composite-validation
```

本接口实现了通用 RGBA 烘焙，尚不等同于 Track 覆盖率材质的完整迁移；填充、描边和辉光在扫色前沿的独立材质语义仍需专门对照。

## 覆盖率材质编译

`compile_coverage(document, group, *, glows=..., glow_materials=..., components=..., scope_opacities=..., partitions=..., settings=..., budget=...)` 接受标准 Document 和可编辑 ObjectGroup，返回 `CoverageResult`。`result.document` 为标准 ASS，`result.output` 为包含事件数、峰值、字节数及来源报告的 SceneResult，`result.sample_times` 记录实际采样的绝对秒数。输入 Document 和对象均不修改。分辨率来自 Document；保留元信息、样式及未选中的字幕。`replace_records=(record_index, ...)` 将所选源事件转为注释，沿用 Scene 的来源保留约定；相同 `owner` 再次生成会替换该 owner 先前生成的事件。

对象自身的 PaintField 为填充与描边分配颜色。`glows` 按叶对象 id 指定静态 Glow 或 `GlowFunction(function, max_blur=..., max_border=..., breakpoints=...)`；函数接收世界 VisualState 与叶出生后的秒数，返回 Glow 或 None。None 只关闭辉光。模糊半径和宽度为脚本像素，随世界缩放变化需在函数中明确计算并声明足够大的最终上界。`glow_materials` 提供独立 PaintField，其 fill 着色辉光。辉光先着色再模糊，有限核采样包含视口外贡献，最后裁回视口。VisualState 的 blur/shadow 不能同时用于此出口；显式辉光有独立的覆盖率角色。

默认每个叶是一个材质组件。`components=(group_id, ...)` 将指定组的后代作为同一组件，按填充、描边、辉光的固有覆盖率完成遮挡；同角色按覆盖率相加并归一化。组件不得嵌套，组件内部 layer 不改变角色顺序；组件之外的普通组保留原子子树和图层顺序。`ScopeOpacity(owner, function, breakpoints=...)` 可为每个叶贡献指定额外的叶或祖先透明度因子；局部时钟属于 owner，因子与原 opacity 相乘，并在对应作用域关闭时应用。配置对象是纯函数契约，不能依赖前一帧。复制对象后需显式重定向配置键和 owner。

`CoveragePartition(function, max_regions=..., inside=True, breakpoints=...)` 返回小数屏幕 x 区间，按像素交叠比例分配模糊前的材质覆盖率。它不是整数 clip，目前只与横向颜色场组合；二维任意方向的覆盖率分区尚未实现。普通几何/遮罩仍支持现有 Scene 仿射和路径能力。组必须自包含，外部对象引用报错；写 opacity 的引用当前不支持。

输出以 `budget.fps` 建立网格，将对象寿命、状态/路径/遮罩动画、引用、颜色场、动态辉光、分区及透明度规则的显式断点加入网格，再量化为 ASS 厘秒。每个区间在中心求值，并将画面保持到区间末尾；例如首个 0–0.1 秒区间使用 0.05 秒的透明度，不能视为原生连续插值。连续相同的像素矩形合并时间区间，消失后的矩形不会跨空白区间合并。`max_time_quantization` 包含源断点的量化差；`max_channel_error` 仅为显式空间颜色量化容差，不覆盖时间保持、视频色度抽样或播放缩放误差。

帧数、几何和声明的空间上界在动画回调前预检；运行中继续检查单帧、累计事件/文本、峰值及含样式和来源注释的最终 UTF-8 字节预算。SceneBudget 的事件预算也计算每条生成事件配套的来源标记。超限报错，不自动降低质量。`max_cached_masks` 不用于此接口。原始对象仍可修改并重新编译；返回的 Document 已是像素事件。

固定示例 [scene_coverage.py](../examples/scene_coverage.py) 展示独立的填充、描边和辉光扫色、纯函数半径变化与整组淡入淡出：

```sh
uv run python -m examples.scene_coverage output.ass
uv run python -m tools.validate_scene_core --scene coverage /tmp/scene-coverage-validation
```

该例明确选择 320×180、10 Hz、8/255 空间量化容差，50 个样本输出 117,000 条可见事件、峰值 5,674 条、32,676,006 字节。实际 libass 的 300 帧连续播放与七次独立跳转一致，重复生成字节相同；见[报告](scene-coverage-validation.json)和[预览](images/scene-coverage.png)。这是高成本的标准 ASS 出口，尚不能由这一短例推出整曲成本可接受。底层 PreparedTrack 转换函数保留为内部，公开 Track 前端已由 prepare_track_coverage 提供；最终全案例验收继续推进。

第三十三批新增 `prepare_track_coverage`，可从 Document 与 Track 取得上述可编辑对象与材质绑定，再通过同一覆盖率出口编译；用法、与旧入口的透明度差异及固定注音示例见[迁移说明](track-migration.md#可编辑-track-覆盖率前端第三十三批)。全案例与发行验收仍未完成。


## 作者 RGB 与四背景验证

`Document.create()` 默认写入标准元信息 `YCbCr Matrix: None`，使代码指定的 RGB 在当前 libass RGB 输出中保持原色。解析已有 ASS 保留原声明或缺省状态，不自动改变历史视频颜色语义。缺少此声明曾使 E09 的目标 `(37, 246, 247)` 输出为 `(48, 227, 228)`；修复没有通过放宽色差阈值绕过问题。

运行 `uv run python -m tools.validate_engine_backgrounds /tmp/engine-backgrounds` 可复现[四背景报告](engine-backgrounds-validation.json)。E01–E12 各在黑、白、棋盘、自制 RGB 渐变上渲染六秒，100 Hz、600 帧；另一个 renderer 按置换顺序访问相同时刻，48 组逐帧相同。采样时刻为整数毫秒 `n*10+1`。这验证播放顺序一致性，不证明独立几何正确性；也不是每帧重建 renderer。实际预览为 `images/engine-backgrounds-E01.png` 至 `E12.png`。E03 无描边白字在白底上不可见，其他浅色内容也有低对比度，示例没有自适应背景配色。

运行 `uv run python -m tools.validate_case_colors /tmp/case-colors` 可复现[E09/E11 颜色对照](case-colors-validation.json)。独立手写 ASS 取得字形覆盖率，独立标量 RGB 公式检查 13 个时刻的完全不透明填充与描边内部；四背景共 1,562,376 个像素检查，最大通道差为 0。E11 公式显式采用既定 20 ms 中点保持语义。此结果不覆盖抗锯齿边缘、辉光、连续时间采样误差或其他案例的几何参考。


## 拼字完成与轮廓恢复的独立几何参考

`uv run python -m tools.validate_case_geometry /tmp/case-geometry` 使用手写原生文字 ASS，绕过 Scene、text_to_path 和路径降级，核对 E05 的完成态与 E07 的未变形/恢复态。E05 的参考位置由原生文字墨迹框独立居中；不是从被测路径读取位置。参考和输出使用相同固定字体和本机 libass，因此不代表不同字体或播放器间的等价性。

[报告](case-geometry-validation.json)逐项记录整数毫秒时刻；E05 从 1600 ms 起的五个时刻、E07 从 0 至 4999 ms 的九个未变形/恢复时刻，半覆盖率轮廓的双向 Chebyshev 距离均在 1 像素内。5000、5001、5010 ms 均为空白。故意移走三像素或删除全部墨迹的反例被拒绝。这里直接使用 native libass 整数时钟，未沿用视频验证的 +1 ms 偏移。

[参考、实际与覆盖率差图](images/case-geometry.png)显示边缘差异：E05 最大覆盖率差 54/255，L1 差除以参考覆盖率总量约 1.403%；E07 分别为 11/255 和 0.391%。这是原生文字与路径轮廓的抗锯齿差异报告，不将几何容差通过等同于逐像素相同。动画中间形状、其他案例独立几何和其他渲染器仍待检查。


## 书写笔尖的独立时间与轨迹参考

E08 的笔尖回调改变位置与可见性，因此 AnimationClip 显式传入 `breakpoints=writing.breakpoints`。只有 ink 的 WritePath 声明断点不足以约束独立 pen 对象：修复前 1.35/3.05 秒开笔会提前 10 ms，2.25 秒停笔也会提前。固定示例现保留每段笔画的开闭区间。

`uv run python -m tools.validate_writing /tmp/writing-reference` 使用独立标量三次 Bézier 求值和每段 10,000 步弧长积分，不调用 WritePath、flatten 或 tip。实际导出 ASS 在 518 个整数毫秒时刻检查，其中含每个断点前后 1 ms；383 个落笔位置和 135 个抬笔状态通过。[报告](writing-validation.json)中相对区间中点保持目标的最大位置误差为 0.213 像素以内；相对连续轨迹的最大观测误差约 3.312 像素，单独记录，不能当作全时间域误差上界。

更新后的 E08 为 387 事件、峰值 2、460,735 字节。[单例播放报告](scene-writing-validation.json)与[四背景重验](engine-backgrounds-writing-validation.json)覆盖修复后输出；第三十六批的全案例四背景报告中 E08 条目是修复前快照，其余案例不受此次修改影响。验证工具支持 `--case E08` 定向复验。完整墨迹覆盖率和动画中间的形状参考仍需继续。


## 带孔轮廓与字形变形参考

`uv run python -m tools.validate_morph /tmp/morph-reference` 独立构造 E10 参考：圆环由解析圆与方形周长等距采样的 64 个对应点插值，孔洞反向；不调用 VectorPath、resample_path 或 MorphPath。字母 B 使用手写原生文字 ASS 的覆盖率，再按作者指定的缩放、错切公式做逆仿射映射，不经过文字转路径或路径插值。参考采用明确的 20 ms 中点保持与独立 smoothstep 公式。

[报告](morph-validation.json)记录两对象各 55 个时刻，包括 1/4 秒断点前后 1 ms：半覆盖率轮廓均满足双向 1 像素 Chebyshev 容差；圆环孔洞保留，故意填孔会被拒绝；5000/5001/5010 ms 输出为空。该检验针对采样目标，不推导任意连续函数的误差上界。

[实际、参考和差图](images/morph-reference.png)已检查。圆环最大覆盖率差 53/255，归一化 L1 最大约 0.053%；字母 B 分别为 78/255、2.079%。B 参考的原生文字光栅化与双三次重采样不同于直接路径光栅化，边缘差单独报告，不声称像素一致。其他渲染器与连续时间采样误差仍需分别验证。


## 导唱符的实际输出隔离检查

`uv run python -m tools.validate_cues /tmp/cues-reference` 检查 E12 在 29 个整数毫秒时刻的实际输出，包含独立文本的 330/670/1000 ms 切换前后、第二个行内提示的时段以及歌词结束边界。[报告](cues-validation.json)中的 READY/SET/GO 参考是手写普通 ASS，直接使用固定字体测量居中，不经过 CueFactory 或场景布局；全部选定时刻的标签覆盖率差为 0。

验证另将作者提供的歌词根 ObjectGroup 平移 `(40,20)`：正文、注音和行内导唱的整体覆盖率与原图平移逐像素相同，独立标签区域保持不变。5 秒后整幅为空，生成 Dialogue 不含 cue 或 ruby 输入标记。这个检查证明两种放置方式的组合关系；第七十一批进一步用整段原生字体测量与标量位置公式，独立生成正文/注音、行内条形及数字 ASS；同一 29 时刻的填充和描边外包络均满足 1 px 半覆盖率轮廓容差。最大填充覆盖率差 34/255、描边外包络及细环差 69/255，不能解释为像素完全一致；原生整段文字和逐簇绘制的抗锯齿差单独保留。

已有 `tests/test_document_text.py`、`tests/test_scene_text.py`、`tests/test_lyric_cues.py` 的 32 项检查同时覆盖颜色作用域、输入标记与直接 Python 构造等价、源标记保留于注释、时序不变、自定义图形工厂、释放占位后的注音和背景跟随、错误来源定位。这些代码与实际输出验证共同支持导唱组件接口，不能把覆盖率平移检查单独当作所有布局行为的证明。


## 逐字入退场与轨道参考

`uv run python -m tools.validate_staggered /tmp/staggered-reference` 独立计算 E02 各字的 80 ms 入场错峰、650 ms 进入、40 ms 退出错峰与 500 ms 退出，直接写成静态原生 ASS 参考，不调用 SceneTimeline、Tween 或示例 bounce。空格保留字符索引与 59 px 步距，不生成可见字形。参考明确采用 20 ms 网格加各字动画断点的中点保持。

[报告](staggered-validation.json)检查 166 个整数毫秒时刻，含每字入退场起止前后 1 ms；填充及描边分别乘事件透明度后的覆盖率与参考逐像素相同。该比较验证几何和透明度，未将非重叠覆盖率平面比较冒充任意多层合成参考。

旁边的菱形另用独立三角函数计算位置、旋转，再直接写原生绘图 ASS。其半覆盖率轮廓满足双向 1 像素容差；最大覆盖率差 48/255、归一化 L1 最大约 3.477%，边缘差单独记录。出生与结束之外没有轨道对象残留。连续时间误差、其他播放器仍需分别检查。


## 圆弧排字、注音与重复高亮参考

`uv run python -m tools.validate_round /tmp/round-reference` 用解析圆的等距角位置、切线角度与手写原生文字 ASS 构造 E03 参考，不调用 layout_path、Polyline 或组变换。正文和注音共同按一次缩放变换，注音偏移为 52 px；两轮 250 ms 缩放/颜色变化由独立标量公式计算，并显式采用 20 ms 网格加动画断点的中点保持。

[报告](round-validation.json)包含 98 个整数毫秒时刻，覆盖两轮动画起止前后 1 ms；正文/注音半覆盖率轮廓满足双向 1 像素容差。故意将注音缩放两次的参考会被拒绝。实际实现采用一度步进的折线圆弧，参考采用解析圆，因此边缘不声称像素相同：最大覆盖率差 106/255，归一化 L1 最大约 3.707%。[实际、参考和差图](images/round-reference.png)已检查。

另外对实际与参考均完全不透明、内缩一像素后的共同内部检查颜色，共 37,215 个像素，最大 RGB 差为 0。边缘不纳入此颜色结论。5000/5001 ms 均为空白。连续时间采样误差与其他渲染器仍不在该参考的证明范围内。


## 樱花发射、出生捕获与游标残影

`uv run python -m tools.validate_sakura /tmp/sakura-reference` 核对 E04 的 18 片曲线环境花瓣、6 片直线花瓣、12 片游标触发花瓣，全部寿命为三秒。触发粒子的初始位置与出生时游标的线性位置一致。此参考以作者游标的起点、路程为输入，不把它当作歌词绝对排版的独立参考。

`uv run python -m tools.validate_sakura_flutter /tmp/sakura-flutter` 进一步检查全部 30 片曲线花瓣，各 16 个时刻（含 2.25 秒淡出断点前后），以及量化后寿命边界外不可见。参考独立计算带键随机参数、三次贝塞尔位移、smoothstep、横向余弦收缩、旋转和淡出，直接写标准 ASS 绘图，不调用 MoveAlong、StateFunction 或示例 PETAL 几何构造。游标触发花瓣的出生位置仍取作者对象，独立发射捕获依据上一份报告。

[报告](sakura-flutter-validation.json)的 480 项填充检查满足双向 1 像素半覆盖率轮廓容差，第六十四批前沿修正后最大抗锯齿覆盖率差为 72/255，透明度差最大 1/255；后者源于非整厘秒出生时钟在 alpha 半整数处的浮点舍入，单独记录，不声称逐像素相同。三个去掉旋转的反例被拒绝。[局部放大预览](images/sakura-flutter-reference.png)展示实际/参考/差图。

第六十批新增同样 480 项描边外轮廓检查：用未乘透明度的填充与描边覆盖率包络比较双向 1 像素几何容差，实际细环的透明度加权覆盖率差另报。原因是 0.5 px 细描边再淡出后，半覆盖率阈值可能只剩零星像素，不能把这些点的位置当作描边外轮廓。三个强制 8 px 描边的反例均被检出。此前只验证填充的快照保留为 [原报告](sakura-flutter-fill-validation.json)。多花瓣重叠合成、连续时间误差界和其他播放器仍未包含在这些检查中。

第六十二批另用 `uv run python -m tools.validate_particle_composite /tmp/particle-composite` 检查 E04 完整场景的层次合成：36 片花瓣、歌词组、游标和四个残影逐对象导出后，从原生覆盖率位图按声明图层/来源顺序独立做 RGB source-over（第六十四批改为浮点逐层合成，最终输出一次取整）；整组导出的 ASS 由 FFmpeg 实际渲染。黑、白、棋盘和 RGB 渐变背景各检查六个时刻，共 24 帧，所有像素的 RGB 通道差不超过 2/255。[报告](particle-composite-validation.json)保存字体、背景、各单独 ASS 和合并 ASS 的哈希及实际 renderer。

检查显式计数重叠像素；反转绘制顺序的错误参考被检出。[预览](images/particle-composite.png)展示棋盘背景的实际/参考/32 倍差图。该对照验证组合、顺序与透明度，独立几何仍由前述公式参考证明；它不证明任意时刻误差界或其他播放器的一致性。

第六十三批为正文加入 SoftSweep 后，当前合成报告已重新生成（四背景 24 帧最大差仍为 2/255），旧版保留为 particle-composite-validation-before-sweep.json。新 E04 的[四背景验证](engine-backgrounds-sakura-validation.json)每背景覆盖 600 帧连续与乱序访问。当前[整曲报告](whole-song-validation.json)也已更新为 120104 条事件、峰值 556、62539000 字节，包含 9000 帧连续播放、十二例单独导出对照和 150 次独立跳转；此前数字是历史快照，旧报告另存 whole-song-validation-before-sakura-sweep.json。

[报告](sakura-validation.json)另对实际独立导出的游标与四层残影检查出生前、出生、结束前及结束后的整数毫秒时刻：30 个可见位置检查的最大质心偏差约 0.086 px，透明度符合 `0.4 * 0.7**index`，残影各延迟 60 ms；原游标为连续原生运动，残影明确对照 20 ms 中点保持的历史位置。六片直线花瓣各保留一个 native-move 事件，18 次位移对照最大偏差约 0.104 px。

粒子测试还验证随机键不受调用/生成顺序影响、预算在工厂回调前检查、出生捕获与持续跟随区分、残影延迟与来源保持。本报告不覆盖曲线 flutter 的独立形状参考、重叠粒子的完整合成或任意连续时间误差。


## 文件入口与作者 Document 的等价性

`tests/test_scene_document_roundtrip.py` 对 E01–E12 逐例保存源 Document、通过 Document.load 重新加载，再使用同一作者对象计划编译，输出 ASS 字节相同，源 Document 保持不变。另一项回归在布局/导唱绑定之前加载包含颜色标签、样式重置、正文注音和 cue 标记的 ASS，并与直接构造 Document 的结果比较，避免仅验证已经准备好的对象。

这些检查支持文件入口与作者入口共享 Document/Scene 编译管线。旧 Python 模板的执行兼容范围仍以 legacy-templates.md 为准；没有因此承诺任意旧模板或任意 ASS 标签都能转换为可编辑场景对象。


## 按词背景框和装饰的独立参考

`uv run python -m tools.validate_word_backgrounds /tmp/word-backgrounds-reference` 使用原生整词测量与手写 ASS 构造 E06 参考，不调用 DocumentLayout、CuedLayout 或 range_bounds。参考明确保留 72 px 导唱条加 12 px 间距的占位；词框水平/垂直 padding 为 6/8 px，正文 64 px，装饰的两段三次曲线控制点直接按测得整行宽度计算。

[报告](word-backgrounds-validation.json)在导唱消失后的七个时刻，分别比较背景框、装饰、Hello 和 World 四种颜色的覆盖率，共 28 项。半覆盖率轮廓均满足双向 1 像素容差，最大边缘覆盖率差 34/255；整词测量与实际塑形簇布局存在亚像素差异，未将此结果称为像素相同。5000/5001 ms 各角色均为空。[逐角色差图](images/word-backgrounds-reference.png)已检查。1 秒前自定义导唱动画、描边及最终图层合成不由本参考证明。


## 正文/注音共享脉冲的前景参考

`uv run python -m tools.validate_lyric_geometry /tmp/lyric-geometry-reference` 使用原生整字、整段注音的测量结果和手写 ASS 构造 E01 参考，不调用歌词布局、unit_group 或 pulse。参考明确以正文中心为枢轴，注音顶部相对枢轴 -108 px；两段演唱为 1–2.2 秒、2.8–4 秒，缩放为 `1 + 0.08*sin(pi*p)**2`，按 20 ms 中点保持。

[报告](lyric-geometry-validation.json)记录 59 个整数毫秒时刻，包括演唱边界前后 1 ms。仅提取完全不透明的前景填充覆盖率，正文和注音均满足双向 1 像素轮廓容差；最大边缘差 51/255，未宣称像素相同。5000/5001 ms 前景为空。[实际、参考和差图](images/lyric-geometry-reference.png)已检查。辉光、描边、扫色颜色和连续时间误差仍需另行验收。


## 轮廓扰动的动态参考与时间误差界

`uv run python -m tools.validate_outline_motion /tmp/outline-motion-reference` 从固定字体的原生 WAVE 轮廓取得直线顶点，再用独立标量公式计算扰动，直接写绘图 ASS；不调用 text_to_path、VectorPath.map 或 PathFunction。工具断言该字体的 WAVE 是五个闭合多边形轮廓（含 A 的孔洞），不会把此简化假设扩展到其他字体或曲线字形。

[报告](outline-motion-validation.json)中的 55 个时刻满足双向 1 像素轮廓容差，最大抗锯齿覆盖率差为 3/255；故意去掉扰动的参考被拒绝。[实际、参考和差图](images/outline-motion-reference.png)已检查。

该固定公式还具有可证明的连续几何采样界。包络导数绝对值不超过 π/3，x/y 顶点速度分别不超过 `4*(π/3+11)` 与 `4*(π/3+9)` px/s；20 ms 中点保持的时间差至多 0.01 秒，因此顶点位置偏差不超过 0.627479 px。线段是对应顶点的凸组合，同一界也适用于线段上的对应点。工具检查采样间隔和零时间量化条件。此界不包含光栅化、原始字体轮廓误差或对象寿命之外的显隐，不是任意回调的通用承诺。


## 书写墨迹的独立参考

`uv run python -m tools.validate_writing_ink /tmp/writing-ink-reference` 为 E08 四段笔画单独计算弧长前缀和 6 px 线宽的平端/斜接轮廓，直接写入 ASS；不调用 WritePath、flatten、stroke 或场景几何降级。曲线每段固定 500 步，独立于实现中的自适应细分；时间参考使用 20 ms 中点保持并加入所有笔画断点。

[报告](writing-ink-validation.json)包含 66 个有墨迹时刻的几何对照，半覆盖率轮廓满足双向 1 像素容差。开笔前及 5000/5001 ms 没有墨迹，笔宽翻倍的反例被拒绝。最大抗锯齿覆盖率差 96/255，包含两种细分及笔画交叠边缘的差异，不声明像素一致。[实际、参考和差图](images/writing-ink-reference.png)已检查。笔尖历史检查见前文；连续曲线近似的严格全局界和最终笔尖/墨迹合成不由此参考证明。

## 显式连续 Tween 降级

`scene.compile(native_tweens=True)` 为符合条件的线性 Tween 选择标准 ASS `\t`，报告策略为 `native-tween`。默认 False 保留既有中点采样保持输出；原生连续插值与采样保持在区间内部本来就不同，因此这不是默认启用的逐像素等价优化。

当前支持一个或多个 hold=True、linear_rate 的 Tween，按开始时间排序输出；同属性顺序接续，不同属性可以并行，通道可组合 scale、rotation、opacity、fill、outline、border、blur、shadow。起始与目标缩放须为正；对象不含材质、遮罩、路径变形或引用，父组须为无动画、无遮罩的默认变换；有效出生时间须与对象出生一致并落在厘秒上。t 内开始/结束时间按毫秒输出，寿命仍受 ASS 厘秒量化。释放、自定义缓动、位置与其他通道混合、剪切及不满足条件的组合继续采样；纯匀速位置移动仍走原有 native-move。已支持多段 t 串接，包括带停留的关键帧；当前没有自定义缓动到 ASS 加速参数的自动识别。

透明度 Tween 由 `\t(...,\alpha...)` 连续完成，从完全透明开始的对象也保留原生事件。父组透明度乘法和复杂覆盖率语义不纳入本次优化。预检按原生事件计数，最终事件/字节/峰值检查仍执行。

固定示例 [scene_native_tween.py](../examples/scene_native_tween.py) 通过 SceneTimeline 编排入场、停留、并行退场，同时淡入淡出、缩放、旋转及变色：`uv run python -m examples.scene_native_tween output.ass`。测试以手写原生 ASS 对照 13 个起止/内部时刻的完整 RGBA，另检查回退条件和 1 事件预算；[预览](images/scene-native-tween.png)与[报告](scene-native-tween-validation.json)记录实际渲染。第六十九批另以反向声明的顺序/并行路径 Tween 核对 16 次乱序与重复访问，包含非零出生时间，手写 ASS 的完整 RGBA 一致；相对理想浮点透明度的 alpha 取整差至多 1/255。更复杂对象的原生降级仍需独立的语义与成本验证。


第七十一批 E12 [行内布局参考图](images/cues-reference.png) 左列为实际覆盖率，右列为独立参考，依次为 0/1000/1500/2500 ms，包含两次占位释放。参考不使用 CueFactory、LyricLayout 或 Scene 布局结果；正文/注音中心由整段字体测量计算，条形尺寸/数字时间表手写。5 px 布局漂移和 8 px 描边反例均被检出。旧标签/组平移报告保留为 cues-validation-before-inline.json；完整颜色合成、连续时间误差和其他播放器仍待验收。


第七十二批用 `uv run python -m tools.validate_cue_colors /tmp/cue-colors` 对 E12 进行四背景颜色检查。[报告](cue-colors-validation.json)记录 17 时刻 × 4 背景共 68 帧，实际值由 FFmpeg 渲染输出 ASS；参考由前述独立布局脚本产生覆盖率，再以浮点 source-over 合成。共同不透明、未被边缘覆盖的内部像素共 473,688 个，白色正文/注音、青色导唱和黑色描边的 RGB 差均为 0。选择共同内部只用于颜色，不代替独立几何检查；整帧最大差 69/255 另报，包含字形边缘差，不声称完整图像达到 2/255。

[三列预览](images/cue-colors.png)为实际、参考及 8 倍差图。此前独立标签参考只检查覆盖率，使用默认白色；本批将参考显式设为 TextCue 的青色，重跑 29 时刻几何检查并更新哈希。该修订不改生产示例或其输出。


第七十四批扩展 E06 的词背景参考到导唱出现期间。`tools.validate_word_backgrounds` 现在手写行内条形、独立数字，并接入独立标量旋转的 sparkle 参考；22 时刻、六类填充/描边角色共 125 项检查满足 1 px 轮廓容差，覆盖切换前后和旋转采样边界。旧仅检查导唱消失后画面的报告保留为 word-backgrounds-validation-after-cues-only.json。

`uv run python -m tools.validate_cue_colors --case E06 /tmp/word-colors` 使用相同完整参考检查四背景 68 帧。[颜色报告](word-colors-validation.json)的共同不透明内部像素共 1,496,488 个，六种预期颜色全部出现且 RGB 差 0；完整图像差最大 34/255 另报。[实际/参考/8 倍差图](images/word-colors.png)已检查。半透明 sparkle 的 alpha/独立几何仍由 custom-cue-validation.json 验证，内部颜色测试不把它误计为不透明像素。


`uv run python -m tools.validate_lyric_glow /tmp/lyric-glow` 验证 E01 的两层粉色辉光与共同缩放。实际仅选取示例的 wide/near 组导出；参考不调用 glow、layout_document_lyrics 或组变换，用原生整段/孤立字形轮廓差得到字形位置，以标量公式计算正文/注音中心和脉冲，直接手写 ASS。两者由同一 FFmpeg/libass 渲染，验证框架表达而非独立验证 libass 模糊算法。

[报告](lyric-glow-validation.json)覆盖 17 时刻、四背景共 68 帧，完整 RGB 差 0；故意降低 near 层透明度的错误参考被检出。[预览](images/lyric-glow.png)为实际、参考及差图。初始按前缀宽度定位字形并以浮点 source-over 合成的参考出现 18/255 差；原生轮廓定位与同渲染器手写 ASS 排除了字形定位及逐层取整差异，没有调整 2/255 阈值。前景扫色/描边和最终完整场景仍需分别验证。


`uv run python -m tools.validate_lyric_sweep /tmp/lyric-sweep` 将 E01 扩展到完整组合。参考复用已验证的独立原生字形定位，使用标量公式计算每个屏幕像素列的 RGB：填充白→粉、24 px，描边粉→白、16 px，前沿向两端各延伸 12 px。只有相邻列的两种颜色均相同时才合并，手写标准 clip 色带，不调用 SoftSweep、PaintField 或 Scene 编译器。前景与独立辉光参考按图层合成后，由同一 FFmpeg/libass 渲染。

[报告](lyric-sweep-validation.json)涵盖四背景 68 帧，包含两段唱词前后、脉冲中间时刻及结束，完整 RGB 差 0。故意把描边过渡改为 24 px 的参考被检出。[实际/参考/8 倍差图](images/lyric-sweep.png)已检查；所有输出状态和时间/预算的最终合并审查仍待完成，不把有限时刻比较说成连续理想函数误差证明。

路径采样、布局、MoveAlong、仿射降级与输出采样的实现证据见 [P3 路径与采样核对](ass-engine-path-sampling-audit.md)。该文档说明参数进度与近似弧长、量化后的实际采样间隔及事件合并条件。

## 固定扫色策略实验

`examples.scene_sweep_strategies` 提供相同 320×180、2 秒、10 Hz 输入的四种明确策略，均输出标准 ASS：

```sh
uv run python -m examples.scene_sweep_strategies bands.ass --strategy bands
uv run python -m examples.scene_sweep_strategies layers.ass --strategy layers
uv run python -m examples.scene_sweep_strategies raster.ass --strategy raster
uv run python -m examples.scene_sweep_strategies diffused.ass --strategy diffused
```

`bands` 是颜色条带，`layers` 是 16 层裁剪叠加，以 1/(N-i) 权重得到预期累计透明度；重复抗锯齿覆盖及 alpha 量化仍可能改变边缘。`raster` 将同一分条场景的整组 RGBA 烘焙为像素矩形，不额外模糊；`diffused` 在着色合成后再施加 2 px 整组模糊。后者的语义有意不同，不能当作分条的无损优化。

本实验明确使用 250000 事件、10000 活动事件、128 MiB 上限及零通道量化误差。第九十六批[生成测量](sweep-strategies-generation.json)分别为 419/290/51887/83979 事件；两个栅格输出超过普通单例预算，不自动提升普通 Scene 的限制。[四背景比较](sweep-strategies-comparison.md)确认分条作为默认：叠层使边缘覆盖增加，栅格误差最多 2/255 但体积约增百倍，着色后模糊保留为不同语义的显式选项。实验的低帧率与小画布不替换 E11 的验收配置。
