# 从 Effect 迁移到 Track

当前可编辑场景、覆盖率材质及旧模板的入口选择、测试证据与保留限制见 [统一场景迁移核对](track-scene-migration-audit.md)。本次版本保留旧入口，不设弃用日期。本文后半的内部实现记录按历史阶段书写；其中“尚未公开/待接入”不代表当前公共接口状态，当前入口以该核对表及下方“公开覆盖率出口”“可编辑 Track 覆盖率前端”为准。

普通歌词样式和动画使用 `render_karaoke(document, tracks=(...))`。旧 `effect=` 仍可运行；一个调用只能选择一个入口。Track 不实例化 Effect，也不执行 compose/configure；不需要把旧查询树包装成另一层配置。

## 配置与选择

| 旧写法 | Track 写法 | 语义 |
| --- | --- | --- |
| compose 中的 Lyrics(Body(), Ruby()) | Track(body=Body(...), ruby=Ruby(...)) | 角色独立配置，省略 ruby 表示禁用 |
| configure 根据 self.source.style 分支 | 多个 Track(source=LineMatch(style=...)) | 同一来源只匹配一个 Track，重复匹配报错 |
| self.body.style.fill = WHITE | Body(style=TextStyle(fill=WHITE)) | 基础文字外观 |
| self.body.style.sung.fill = CYAN | Overlay(style=PaintStyle(fill=CYAN)) | 覆盖外观，不复制文字几何 |
| self.body.text_range(a, b).style.sung.fill | Body(spans=(TextSpan(a, b, overlay=...),)) | 完整正文中的 codepoint 范围 |
| text_range(...).add_class("accent") | TextSpan(..., classes=("accent",)) | 用 Track.styles 的选择器提供基础/sung 样式 |
| Ruby 上的局部样式查询 | Ruby(spans=(RubySpan(unit, segment, ...),)) | reading 内的独立范围，不使用正文索引 |
| self.text.fade(...) | FadeInAnimation、FadeOutAnimation | 普通透明度动画，遵守显示窗口和属性冲突 |
| self.syllables.on_singing(pulse=...) | SingingPulseAnimation 或 On(Syllable.Singing, Animate(...)) | Envelope 可越过演唱结束时间 release |
| self.text.animate(...) | On(Display.Start, Animate(...)) | 组变换，Ruby 不开启 syllable follow 也会跟随 |
| self.rubies.on_singing(...) | SegmentSinging 事件，目标 kind="ruby" | 事件与目标显式分开，保留 reading 的 segment 时间 |
| 修改 sampling.step_ms | Track(sampling=SamplingSettings(step_ms=...)) | 采样配置独立于事件类 |

TextStyle/PaintStyle 是不可变值。通过 `dataclasses.replace` 派生变体；构造覆盖由普通 Python 参数表达。没有任意对象深合并：一个新的 Body 替换整个 Body 配置，一组 animations 替换整组动画。Overlay 的部分绘制字段才参与样式级联。

旧 `.style` 可写入口保留给 Effect；新 Track 的不可变声明从 `.text_style` 读取。不要用 `body.style.fill = ...` 修改已传入的 TextStyle；直接构造所需样式或替换声明。Track.styles 保留 CSS 选择器规则，但运行时没有 query/configure 阶段。

来源过滤用 LineMatch 或 SourceMatch。回调接受一个 KaraokeItem，参数名不受限制；不需要给解析 ASS 增加逐行样式字段。范围索引切断不可独立绘制的字形簇时会报错，不能通过逐 codepoint 颜色强行拆开连写。

## 读取源数据的动画

只依赖事件时间或索引时使用 @on。需要文本或完整来源时，实现 Animation.actions，从类型化 AnimationContext 读取原输入，再返回同一种 Animate 描述：

```python
from collections.abc import Iterable
from kara_templater import (
    Animate, Animation, AnimationContext, AnimationEvent,
    Envelope, Syllable,
)

class TextAccent(Animation):
    def __init__(self, *, peak: float = 1.1) -> None:
        super().__init__()
        self.peak = peak

    def actions(
        self, context: AnimationContext,
    ) -> Iterable[tuple[AnimationEvent, Animate]]:
        for event in context.events(Syllable.Singing):
            unit = context.item.source.units[event.target.units[0]]
            if not unit.text.strip():
                continue
            yield event, Animate(
                event.target,
                scale=Envelope(peak=self.peak, release=160),
            )

accent = TextAccent(peak=1.08)
```

若覆盖 actions 后还希望使用基类的 @on 处理器，可显式 `yield from super().actions(context)`；自行声明返回类型时也要包含这些处理器允许的组合类型。不要重写 bind 绕过目标校验、时间锚点解析和冲突分析。

## 排版与动画时钟

省略 layout 保留输入位置。SingleLine/DoubleLine 管理一个 Track；TrackGroup 使用一个明确的绝对位置，为多个 Track 统一分配行位，子 Track 省略 layout。占用按显示窗口计算，extend_display 的尾段也计入容量。

Display.Start/End 和关键帧引用保持原始显示时钟。默认裁至原显示窗口；需要延长时显式设置 extend_display。组、音节、Ruby 的几何按层级组合，同层同属性写入仍须解决冲突。材质动画与 Sweep 同时修改一个绘制属性时，需要显式 compose="override"。

## 示例迁移与保留能力

| 示例或能力 | 当前入口与处理 |
| --- | --- |
| layered_glow | layered_glow.py 使用实例；layered_glow_classes.py 使用子类，两者输出逐字节一致 |
| alternating_colors | track_colors.py 演示 TextSpan；测试覆盖解析 ASS、直接 Document 和 RubySpan |
| source.style 条件配置 | 按 LineMatch 拆成多个 Track；通过 TrackGroup 显式共享行位 |
| 动态颜色、描边与文字 blur | Animate 的绘制属性；未知几何函数使用 PaintBounds 声明值域 |
| 独立 Halo、whole_glow | 保留旧 Effect/Halo；独立装饰并不等同于基础文字的 Blur |
| staggered_path 的逐字 on_highlight | 保留旧 Effect；Track 尚无逐字扫过事件，不用 Syllable.Singing 冒充等价语义 |
| parallel_tracks、recipes 的优先级覆盖 | 保留旧 HighlightTrack/TrackStyle 编译路径；新的 Track 是输入配置单元，与 HighlightTrack 不是同一个概念 |
| composed_glow 的多套独立光晕 | 保留旧 Effect 的装饰配置；不要把多个装饰强行合并成一个 Blur |

新接口覆盖普通文字效果的配置路径，兼容入口继续提供独立装饰、逐字扫过事件及并行区域等能力。对旧 Effect 传入其不支持的新 TextSpan/RubySpan、TextStyle blur/font_name/spacing 会明确报错；不会静默丢弃声明。

文字 Blur 随 sweep 变色与旧双 Halo 混合并非像素等价；扫色使用原时间轴，不迁移 padding/lead/tail 等测量补偿。默认原生文字后端仍在绘制后裁剪，并按绘制层应用透明度；需要“先选材质再模糊”和合成后的组 alpha 时，显式使用 `OutputSettings(raster=RasterSettings())`。栅格路径有预算、时间采样及视频混合格式限制，空间量化也必须显式启用。诊断、完整示例成本与实测误差见 [后端审计](track-backend-audit.md) 和 [验收记录](track-effects-acceptance.md)。


## 迁移到混合场景

仅导出已有 Track 时继续使用 render_karaoke。需要独立路径、粒子、残影或其他 Scene 对象时，改用 prepare_karaoke，向返回的 scene 添加对象，再 compile。二者共享准备阶段和事件插入；原生与栅格 Track 输出均有逐像素等价回归。

| 能力 | 当前迁移状态 |
| --- | --- |
| Track/TrackGroup 配置与属性回调 | 沿用已有绑定/降级；准备时执行一次 |
| 原生、动态采样、栅格事件 | 带 EventOrigin 进入 NativeEvent，共享场景排序和最终预算 |
| 再次生成、改变选择、切回旧入口 | 移除同 owner 的来源标记与生成事件，保留未匹配字幕和其他 owner |
| 给 Track 歌词直接套 Scene 组变换或对象引用 | 使用 prepare_track_scene 返回的可编辑 ObjectGroup；prepare_karaoke 仍返回已降级事件 |
| 整词覆盖率材质与合成后透明度 | 使用 prepare_track_coverage → compile_coverage；显式像素预算与材质作用域，限制见下文 |

参见 [Track 文档](tracks.md#与-scene-特效组合)及固定的 [scene_tracks.py](../examples/scene_tracks.py)。

### 可编辑场景迁移的准备阶段

内部 `BoundTrack` 已拆为 `prepare` 与 `lower`：`PreparedTrack` 保存正文/注音视觉目标、演唱轨道、来源、解析后的样式、属性绑定、材质绑定及布局上下文。`prepare(lower_native=False)` 保留缩放等属性绑定，不提前变成原生 ASS 动画；不会采样动态属性回调。`lower` 可以消费修改后的准备结果，不重新布局或绑定。旧 `build` 组合两步，保持既有输出。

PreparedTrack/BoundTrack 的准备结果仍属内部接口；公开可编辑入口为 prepare_track_scene 和 prepare_track_coverage。特别是修改文字长度后需由调用方重新测量布局；不能把替换目标内容视为自动重新排版。准备结果可转换为可编辑文字对象并返回诊断；覆盖率材质通过下文的 prepare_track_coverage 显式接入。`prepare_karaoke` 的公开行为仍是带来源的 NativeEvent 适配；`prepare_track_scene` 显式选择可编辑对象，两者共享前端与来源所有权。

内部 `_track_scene.track_objects` 现可将 PreparedTrack 转为普通 ObjectGroup/TextObject，保留正文与注音的字体、布局、来源、寿命、几何属性、颜色与宽度动画，并将辉光拆为可编辑的独立文字层。Track 缩放同时缩放描边和辉光半径，适配层显式写入这些通道；其他未被动画控制的属性仍可直接修改。几何属性按原有层级与 pivot 求值，回调在 Scene 编译预算预检之后执行。

该转换已接入公开 prepare_track_scene 入口。扫色复用旧后端分区，转换为动态矩形遮罩与文字层；release 阶段通过寿命组移除遮罩，保留原动画时钟。静止边界保留原生整数端点插值规则；带几何运动的边界在变换前使用连续坐标。已提前降级的原生动画、下划线、删除线、样式角度及非普通描边 BorderStyle 也明确拒绝。Scene 动态转换采用采样保持，旧原生动画可连续插值；已有夹具验证采样中心的像素等价，不能据此宣称区间内所有时刻等价。整组透明度仍遵循每绘制层 alpha，不提供离屏合成。分区诊断通过准备结果返回；高级覆盖率合成由独立的 prepare_track_coverage 入口提供，不改变该入口的原生分层语义。入口与固定示例见 [Track 文档](tracks.md#将-track-转为可编辑-scene)。


### 共享覆盖率材质核心

Track 栅格后端现将几何遮罩与颜色分区交给内部 `_material_composition.MaterialLayer` / `compose_material_layers`。共享核心只处理覆盖率、完整颜色分区、模糊半径和透明度权重，不依赖歌词、字体、Track 配置或时间。按半径合并辉光后模糊，再按辉光、描边、填充的顺序遮挡；各角色内部的相加饱和由未加权覆盖率归一化。Track 继续负责来源组件、音节与整行作用域的分组和关闭，不用数值相等代替对象归属。

这一拆分是 Scene 材质迁移的内部基础，尚未将它公开为作者 API，也没有将普通 ObjectGroup 的 RGBA 合成冒充加权覆盖率合成。现有 Track 独立像素参考继续通过；程序化遮罩另覆盖多层遮挡、着色后模糊、不同透明度作用域、预算和标准 ASS 回读。可编辑 Track 场景仍使用前述逐层透明度与硬边扫色。


内部 `_scene_coverage.SceneCoverageSampler` 现可从 ObjectGroup 直接求值文字/路径覆盖率，复用 SceneEvaluator、ClipResolver 和标准几何降级，再调用共享材质核心。填充/描边沿用对象 PaintField，显式辉光可使用独立颜色场；横纵颜色分区都在模糊前着色。每个叶对象暂为一个材质组件，组按原子子树合成后施加本地透明度。它尚未表达 Track 一个来源组件包含多个材质片段及不同透明度权重的全部映射，因此未替换 prepare_track_scene，也未新增公共接口。

此内部求值器现按每帧实际模糊核在视口外扩展采样，合成后裁回画面；原生 blur/shadow 与写入 opacity 的对象引用拒绝；辉光外观可由固定 Glow 或有边界的 GlowFunction 声明，颜色场可随时间变化。源对象可继续使用已有几何动画、路径变形、遮罩和几何引用。采样时刻由调用者提供，帧网格/输出预算仍需由后续场景编译入口负责。它不承诺与普通 Scene 的全局图层交错等价，组在这里是合成边界。


内部采样器的 `components` 现可显式指定互不嵌套的 ObjectGroup，将其后代作为同一个材质组件。中间组织组保留变换、遮罩、寿命和贡献透明度，不再在组件内部形成独立的合成边界；同角色片段按覆盖率相加归一化，等半径辉光合并后模糊，再由描边/填充遮挡。贡献透明度不同则使用加权覆盖率平面，相同时只在已确定的组件内选择单平面快速路径。普通组及兄弟组件仍按组图层和独立透明度合成。

组件按身份指定，不按颜色/alpha 数值推测。互补裁剪片段可共享一个辉光，独立栅格化的相邻路径仍可能有不同的抗锯齿边缘；材质组合不代替几何并集。复制对象后需要按复制身份提供组件选择，当前内部配置不自动重定向。Track 中按目标变化的上级作用域权重和动态辉光外观仍待适配；本步未改变公开 prepare_track_scene 行为。

内部 `GlowFunction` 接收视觉叶对象的世界 VisualState 和出生后的秒数，返回 Glow 或 None。颜色、描边宽度、模糊半径及辉光透明度可任意纯函数变化；None 仅关闭辉光。函数须声明 max_blur、max_border 和局部断点，采样器在回调前按视口加最大空间扩展预检像素预算，并在每次求值后核验返回类型和实际边界。这个预检是保守上限，不是精确绘制面积；声明过松会提前超预算。

宽度与半径使用脚本像素，是否随几何缩放由回调显式决定；独立辉光颜色场在回调返回外观之后着色。复制后继续使用叶对象出生时钟，仍需为复制身份重建外部映射。该类型暂未公开导出，公共帧网格与 Track 材质适配仍待接入。


内部 `ScopeOpacity(owner, function, breakpoints)` 现可为每个视觉叶贡献声明所属叶/祖先作用域的额外 alpha。函数使用该 owner 出生后的秒数，返回 0–1 因子，并与 owner 原有状态透明度相乘。它不改变几何求值及辉光回调收到的 VisualState。每个叶/owner 最多一条规则，owner 必须位于该叶的真实归属链，断点必须在 owner 寿命内；这些关系在任何回调前验证。

带规则的路径保留多层覆盖率平面：组件内部使用未加权覆盖率遮挡，已完成组件的局部覆盖率参与上一级遮挡，音节/整行等上级权重逐层保留并关闭。因此对两个目标施加不同整行权重，不会错误地把它们当作两个独立的透明绘制层。组件内组织组折入贡献权重，组件外普通组保留各自合成边界。没有有效规则时继续走原有快速路径，空规则不改变输出。

空间预检额外计入最深归属链所需平面数量，过深或过大的工作区会在回调前触发像素预算。运行时越界保留实际叶身份与来源。规则复制需显式重定向 owner 和目标身份；函数的局部时钟无需平移。该段记录早期内部实现；当前作者可通过 compile_coverage 与 prepare_track_coverage 使用这些规则，见后文公共入口。


### PreparedTrack 覆盖率适配原型

内部 `track_coverage(item_id, prepared, max_glow_blur=..., max_glow_border=...)` 返回 CoverageTrack：普通可编辑组/文字对象、来源组件选择、动态辉光、分区和作用域规则。结构为整行 → 来源单元 → 正文/具体读音组件 → 唱前/唱后材质片段；只保留一个来源组件的填充/描边/辉光所有权。它消费未提前降级的 PreparedTrack，不重新排版或执行回调。现有 editable Track 的文字能力检查提取为共享验证，旧入口保持原行为。

CoveragePartition 用小数屏幕 x 区间表达模糊前的材质所有权，按像素交叠比例分配覆盖率；互补分区不会退化成整数 clip。它有区域数量、断点及组合色带预算，运行时也校验声明上界。分区前沿随正向轴对齐、等比的 Track 几何移动；旋转、剪切或不等比的动态前沿明确拒绝，二维覆盖率分区尚未实现。填充/描边动画复用已有适配，透明度从几何回调分离并映射到局部、来源单元和整行作用域；辉光复用解析后的材质绑定，通过 GlowFunction 输出缩放后的外观。

tests/test_track_coverage.py 对照原栅格后端的采样覆盖率，覆盖非整数前沿、起止释放、正文/注音、缩放位移、不同透明度及动态辉光颜色/宽度/半径，并在相同采样网格比较旧标准 ASS 的实际像素。当前夹具逐像素相同，不宣称任意时间与旧原生透明度插值等价。

第三十批边界复现曾显示最大 alpha 差 41/255：字形左边界 -12、辉光半径 8 时，新采样器过早裁掉了画面外覆盖率。第三十一批已补齐 overscan 并移除 strict xfail；18 个边缘/半径组合与旧 Track 栅格结果逐像素一致。该底层适配函数仍属内部；公共 Document 入口已在第三十三批接入，下文说明其配置与限制。


覆盖率采样的空间预算使用声明的最大半径/宽度，并计入扩展画布及模糊输出。真正求值时先在查询局部快照中解析活动辉光，只执行一次外观回调，再按当前帧最大实际模糊核扩展采样；不能直接用声明上限代替实际核，否则小半径可能因有限核对齐产生取整差。遮罩先在原始世界坐标解析，再连同几何平移到扩展画布；覆盖率结果移回原坐标，颜色场可查询负坐标及画面外区间，所有组件合成后再裁剪。此改动针对 SceneCoverageSampler，不改变 rasterize_group 的已声明视口内 RGBA 烘焙语义。

### 公开覆盖率出口（第三十二批）

`compile_coverage(document, group, ...)` 现已公开，连同 GlowFunction、CoveragePartition、ScopeOpacity 和 CoverageResult；作者可直接编写普通 Scene 对象，通过统一帧网格输出标准 ASS，见[完整契约](scenes.md#覆盖率材质编译)。它保留 Document、来源替换和 owner 再生成行为，并校验最终预算。上文的“内部语义”描述对应各批实现当时的状态；PreparedTrack 转换函数仍属内部，公共适配已由下文 prepare_track_coverage 提供。prepare_track_scene 保持原有输出语义；高级组合的最终图像与发行验收继续进行。

### 可编辑 Track 覆盖率前端（第三十三批）

`prepare_track_coverage(document, items=None, tracks=(...), max_glow_blur=..., max_glow_border=..., owner="default")` 现在将上述适配接入公共 Document 流程。返回 `PreparedTrackCoverage`，保留 document、普通 ObjectGroup 根节点、components 身份、glows/glow_materials、partitions、scope_opacities 与 diagnostics。`prepared.compile(settings=RasterSettings(...), budget=SceneBudget(...))` 调用同一个 compile_coverage，返回 CoverageResult；保存 `result.document` 即为标准 ASS。

```python
from dataclasses import replace
from kara_templater import (
    WHITE, Body, Document, Line, LineMatch, Style, TextStyle,
    Track, Vec2, VisualState, prepare_track_coverage,
)

source_doc = Document.create(
    width=160, height=90,
    styles=(Style(fontname="DejaVu Sans", fontsize=24, align=5, shadow=0),),
)
source_doc.records.append(Line(text=r"{\k20}Hi", start_time=0, end_time=400))
track = Track(source=LineMatch(), body=Body(style=TextStyle(fill=WHITE)))
prepared = prepare_track_coverage(
    source_doc, tracks=(track,), max_glow_blur=8, max_glow_border=4,
)
prepared = replace(
    prepared,
    group=replace(prepared.group, state=VisualState(position=Vec2(0, -10))),
)
result = prepared.compile()
result.document.save("output.ass")
```

原来的 `prepare_track_scene` 保持原生分层透明度与硬裁剪语义；新的覆盖率前端显式选择像素输出成本和材质作用域。两者共用 ASS 导入、Track 选择、布局、来源注释、owner 清理和恢复流程。省略 items 会将匹配的原 ASS 行保留为源注释；显式 items 不改变已有对白。改为空选择会恢复本 owner 原来的源行，其他 owner 输出保留。同 owner 可从三种 karaoke 输出入口重新生成，不叠加旧生成事件。

准备阶段不采样属性函数；`max_objects` 限制生成文字节点，编译阶段再执行像素、帧数与输出预算。动画绑定本身仍可运行作者的声明构造逻辑，不能把“不采样”解释为不调用任何用户代码。Track.sampling 不用于此出口，时间网格由 SceneBudget 和显式断点控制；Track 既有动画声明仍使用毫秒，新 Scene 动画使用秒。仅辉光动画也独立携带其断点，不依赖填充是否生成了状态动画。

可用 dataclasses.replace 改组、追加文字/路径和自定义动画；可编辑返回的材质字典。根组覆盖所有选中行的显示窗口，子对象仍在各自寿命内显示。更名/复制仍须显式重定向字典键、组件身份和透明度 owner。当前 Track 自动前沿支持平移和正向轴对齐等比缩放；旋转、剪切、非等比前沿拒绝，需作者显式改写材质分区。最终辉光像素上界必须包含后加缩放。空选择保留 Document，根节点使用空的 0–0.01 秒占位寿命，不生成可见事件。

固定 [scene_coverage_tracks.py](../examples/scene_coverage_tracks.py) 从写死的 ASS 歌词构建正文/注音/扫色和辉光颜色动画，然后增加纯函数漂移与下划线路径。240×135、10 Hz、8/255 空间量化容差下输出 72,722 条可见事件、峰值 2,610 条、21,745,391 字节；300 帧实际 libass 连播与八次独立跳转一致，两次生成字节相同，见[报告](scene-coverage-tracks-validation.json)与[预览](images/scene-coverage-tracks.png)。

透明度参考测试另记录了舍入边界：旧 Track 在各作用域权重相同时选择单平面并在合成后施加透明度；新覆盖率作用域使用带权平面。新增显式 items 夹具在 1.85 秒出现最大 1/255 的 RGBA 差异，黑白背景上的显示 RGB 差异也最多 1/255，其余检查点相同。这是该夹具的实测范围，不是任意输入的误差承诺，也不由空间量化参数产生。原生透明度插值与新出口的区间保持仍是不同的时间策略。高级组合的全案例参考误差与发行验收继续推进。
