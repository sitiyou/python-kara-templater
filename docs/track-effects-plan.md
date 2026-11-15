# Track 声明式特效重构计划与 TODO

状态：P0–P5 已完成实现与验收；工作树和安装后的发行包均通过 664 项测试、严格 Ruff 与 ty 检查。当前接口见 [Track 使用说明](tracks.md)，逐项证据和能力边界见 [验收记录](track-effects-acceptance.md)，历史过程见 [实施记录](track-effects-progress.md)。本文替代上一版以 Lyrics + variants 为中心的方案。下文示例使用显式构造函数。

## 目标与配置方式

本库为已有歌词动画添加特效，输入可以是解析 ASS 得到的 Document，也可以是直接构造的 Document。配置不依赖 ASS 私有协议或新增的逐行样式字段。

直接构造是完整的一等用法：Body(style=...)、Overlay(style=..., reveal=...)、Track(...) 和 SingingPulseAnimation(peak=...) 均可直接使用，不要求用户先定义子类。子类用于命名、复用默认配置或编写自定义行为，不是配置的前置条件。

两种方式使用普通 Python 构造与继承。内置组件显式声明参数，自定义子类显式编写 __init__，通过 super().__init__ 传递公共参数。不要收集类属性、自动生成构造签名或引入 CONFIG/digest_config；不得通过无类型的 **kwargs、字符串属性路径或 Any/Unknown 实现扩展。普通实例配置不需要 compose/configure。

## 职责与依赖

| 对象 | 职责 | 不承担的职责 |
| --- | --- | --- |
| Track | 选择输入歌词，组合 layout、body、overlay、ruby、animations | 字形测量、动画逐帧计算 |
| Lead 等用户子类 | 为一种歌词角色提供可复用配置 | 库内部的角色特判 |
| Layout | 单个 Track 的行位置分配、单行或双行排版 | 文字颜色、扫色、演唱时钟 |
| Body | 正文基础文字样式 | 输入筛选、覆盖层进度 |
| Ruby | 注音样式、对齐和跟随关系 | 复制正文布局或擅自修改注音时钟 |
| Overlay | 将部分绘制样式绑定到已有文字，通过 reveal 控制显露 | 独立文字内容、字体、字号、字距和布局 |
| Sweep | 根据演唱进度生成显露规则 | 用户可见的测量/blur 补偿参数 |
| Animation | 类型化参数、事件响应和属性动画描述 | 直接调用 ASS 后端、依赖具体 Track 子类 |

依赖方向为输入选择 → 排版/文字目标 → 覆盖与动画绑定 → 统一中间表示 → 后端输出。样式和动画声明可复用；绑定后的目标、时钟、布局和动画状态逐 Track、逐行独立。

## 直接配置示例

省略导入。时间参数以毫秒计。内置颜色常量沿用现有颜色系统。

```python
SUNG = PaintStyle(
    fill=Color.hex("#01829d"),
    stroke=WHITE,
    blur=Blur(color=Color.hex("#67e5ff")),
)

result = render_karaoke(
    document,
    tracks=(
        Track(
            source=LineMatch(style="K1"),
            layout=DoubleLine(),
            body=Body(
                style=TextStyle(
                    fill=WHITE,
                    stroke=BLACK,
                    stroke_width=5,
                    blur=Blur(
                        color=Color.hex("#9e6d64"),
                        radius=10,
                        width=10,
                    ),
                ),
            ),
            ruby=Ruby(
                style=TextStyle(
                    fill=WHITE,
                    stroke=BLACK,
                    stroke_width=3,
                    blur=Blur(
                        color=Color.hex("#9e6d64"),
                        radius=10,
                        width=6,
                    ),
                ),
                offset_y=10,
                follow="syllable",
            ),
            overlay=Overlay(
                targets=(Body, Ruby),
                style=SUNG,
                reveal=Sweep(curve=linear),
            ),
            animations=(
                FadeInAnimation(duration=800),
                FadeOutAnimation(duration=200),
                SingingPulseAnimation(peak=1.1, attack=80, release=160),
            ),
        ),
        Track(
            source=LineMatch(style="K2"),
            layout=SingleLine(),
            body=Body(style=TextStyle(fill=WHITE)),
            ruby=None,
            overlay=Overlay(
                targets=(Body,),
                style=SUNG,
                reveal=Sweep(curve=linear),
            ),
            animations=(SingingPulseAnimation(peak=1.05, release=240),),
        ),
    ),
)
```

K1 与 K2 是输入 style 的例子，不是库预设的角色。Track 不必与某个固定 style 名绑定；source 使用现有类型化来源选择器。未匹配输入沿用现有输出保留策略，并以测试固定行为；多个 Track 匹配同一行默认报告歧义，不悄悄重复输出。

SingleLine/DoubleLine 管理一个 Track 的连续歌词行；DoubleLine 表示在两个行位间分配，不代表自动文本折行。默认保持输入排版；显式指定布局策略才重排。行位占用依据显示窗口，不仅依据 singing 区间；延长显示窗口也必须进入占用计算。超出容量明确诊断，不静默覆盖。

多个 Track 的内部双行布局不能自动协调彼此的位置。K1 固定上行、K2 固定下行属于跨 Track 布局，应通过明确的位置配置或独立布局容器表达。不增加隐式跨 Track 调度；显式 TrackGroup(*tracks, layout=DoubleLine(position=...)) 共享行位，子 Track 不再单独声明 layout。

## 子类复用与构造覆盖

```python
class Lead(Track):
    def __init__(
        self,
        *,
        source: SourceMatch,
        animations: tuple[Animation, ...] | None = None,
    ) -> None:
        super().__init__(
            source=source,
            layout=SingleLine(),
            body=Body(style=TextStyle(fill=WHITE, stroke=BLACK)),
            overlay=Overlay(style=SUNG, targets=(Body,)),
            animations=(FadeInAnimation(duration=400),) if animations is None else animations,
        )


lead = Lead(
    source=LineMatch(style="LEAD"),
    animations=(FadeInAnimation(duration=600), FadeOutAnimation(duration=200)),
)
```

同样允许继承 Body、Ruby、Overlay、Animation，但默认值和参数传递都由显式构造函数表达。上例中 animations 序列整体替换，不自动追加。只复用配置时可以使用普通工厂函数。框架不执行不透明的任意对象深合并。

TextStyle/PaintStyle 内部的部分字段级联遵循显式契约：UNSET 表示该层未提供值；None 仅在允许禁用的字段上表示禁用，例如 ruby=None、overlay=None、blur=None。PaintStyle 的 INHERIT 表示使用所属目标当前的基础绘制值。嵌套 Blur 的样式级联按字段处理，与组件替换、dataclasses.replace 的字段替换语义区分。

共享样式值不可变，可通过 dataclasses.replace 派生变体；类默认组件不得携带共享的运行状态。组件和动画使用显式 __init__；样式值使用普通不可变 dataclass。子类公开构造签名由真实 Python 参数定义，使用 ty 正反用例验证，不引入签名生成机制。

## Overlay 与文字的关系

Overlay 配置独立，运行时绑定 Body/Ruby 的文字目标。targets 中的 Body/Ruby 是当前 Track 内的类型化角色引用，不是全局查询；默认覆盖当前 Track 中存在的文字角色。显式引用不存在的角色应诊断。

公共 PaintStyle 分别覆盖每个目标自己的基础外观。正文描边宽度 5、辉光宽度 10，注音描边宽度 3、辉光宽度 6，不会因共享 SUNG 被统一成正文数值。逐角色局部覆盖使用 Overlay(body=PaintStyle(...), ruby=PaintStyle(...))，None 表示禁用对应角色；不使用字符串字典。

Overlay 与文字共享塑形、布局和当前几何变换；只允许覆盖绘制属性。Body/Ruby 的 blur 保留为普通字体绘制属性，不要求额外 Halo。Sweep 决定显露进度，Overlay.style 决定覆盖后的外观。共享 reveal 声明不共享时钟，Ruby 默认使用自己的 segment 时间；follow 仅控制变换跟随。

扫色仍是按字形区域选择基础/覆盖外观，再处理描边与模糊；不是两个完整文字图层直接 alpha 相加。整体透明度应用一次，光晕自然扩散到扫色前沿之外。分开布局 advance、glyph ink 和绘制边界；公共接口不暴露为修复测量误差而存在的 padding/lead/tail。后端能力、误差容限及成本必须验证，不能用隐藏时间常量替换旧补偿。

## 独立动画类与时间模型

所有内置动画都是普通 Animation 实现，支持带参数直接构造，例如 SingingPulseAnimation(peak=1.2, attack=60, release=240)。自定义类显式声明构造参数，通过事件方法返回统一动画描述：

```python
class AccentAnimation(Animation):
    def __init__(
        self,
        *,
        peak: float = 1.1,
        attack: Milliseconds = 80,
        release: Milliseconds = 160,
    ) -> None:
        super().__init__()
        self.peak = peak
        self.attack = attack
        self.release = release

    @on(Syllable.Singing)
    def accent(self, event: Syllable.Singing) -> Animate:
        return Animate(
            event.target,
            scale=Envelope(
                peak=self.peak + 0.02 * (event.index % 3),
                attack=self.attack,
                release=self.release,
            ),
        )


accent = AccentAnimation(peak=1.08, release=240)
```

上述参数绑定使用普通 Python 构造函数。ty 正反用例验证参数类型、未知参数报错、事件参数与方法返回类型；@on 保留具体返回类型，不将 Animate 降为 Any/Unknown。

- Animation 不依赖 K1、Lead 或 ASS 输出实现；绑定时提供类型化目标和时间上下文，编译时展开事件，不引入实时事件队列。
- FadeInAnimation 锚定 Display.Start；FadeOutAnimation 默认从 Display.End-duration 开始。淡入淡出只是透明度动画，无专用 fade 字段。
- Singing 事件区间与动画寿命分离；Envelope 可在 singing.end 后 release。支持独立关键帧、内置缓动和 Callable[[float], float]，上升/下降曲线可分别设置。
- 支持序列/并行动画，多个 animations 进入同一冲突分析；不得按声明顺序静默覆盖同属性写入。显式组合策略与互斥目标可消除冲突。
- 组动画只作用一次；音节变换跟随规则决定 Ruby 的关联，Overlay 复用已求值几何，不重复运行缩放/透明度动画。
- 默认输出裁至原显示窗口且不重定时；显式 extend_display 扩展目标与附属绘制窗口，重新检查布局占用。组可见性仍可能限制实际可见时间。
- 短音节、零时长、尾段重叠、重复事件及目标能力不匹配均有明确校验规则。

## 实施 TODO

### P0：契约与类型原型

- [x] 审计现有 effect、sources、layout、animation、compiler 的职责，形成模块依赖图与迁移范围。
- [x] 验证 Track/Body/Ruby/Overlay/Animation 的显式构造参数及普通子类继承。
- [x] 验证自定义 Animation 的显式 __init__、参数错误诊断与 @on 返回类型；不泄漏 Any/Unknown。
- [x] 固定组件替换、样式级联、禁用、不可变共享与运行状态隔离契约。
- [x] 固定 Overlay 目标引用、逐角色局部覆盖/禁用的类型化接口。
- [x] 固定 SingleLine/DoubleLine 行位分配、输入布局保留、容量冲突与跨 Track 位置配置。
- [x] 审计 Sweep 合成、测量误差与 libass 能力，建立最小视觉复现和成本基线；见 [后端审计](track-backend-audit.md)。

### P1：Track 与配置绑定

- [x] 实现 render_karaoke(document, tracks=...) 及现有输入选择器绑定。
- [x] 实现直接配置和子类复用的共同解析路径，普通效果不依赖 compose/configure。
- [x] 实现逐 Track、逐行绑定隔离，以及未匹配/重复匹配输入的输出策略与诊断。
- [x] 以现有 Document 时间和文本为输入，兼容 parsed ASS、直接构造 Document 和显式 KaraokeItem。
- [x] 明确旧 effect 入口迁移方式；同时提供互斥入口时，拒绝冲突参数。

### P2：文字、覆盖与布局解耦

- [x] 拆分 Body/Ruby 配置和运行目标，接入基础样式与代码范围分色级联。
- [x] 实现独立 Overlay + Sweep，复用文字塑形、布局和变换。
- [x] 实现公共覆盖样式、角色局部覆盖/禁用、独立时钟与不可变样式复用。
- [x] 实现基础 blur、透明合成、动态绘制边界，移除用户侧测量/blur 补偿需求；自然合成由显式栅格路径实现，原生路径限制明确诊断。
- [x] 对 ASS 表达能力不足提供受预算限制的方案或明确诊断；保留必要的独立装饰能力。
- [x] 实现 SingleLine/DoubleLine，测试显示窗口、动画延长、占位冲突和输入布局保留。

### P3：通用动画

- [x] 实现独立 Animation 类的参数绑定、类型化事件上下文与统一编译。
- [x] 实现 FadeInAnimation、FadeOutAnimation、SingingPulseAnimation 作为普通可配置预设。
- [x] 支持自定义返回值、关键帧、Envelope、lambda 缓动、序列和并行组合。
- [x] 实现动画属性冲突、目标能力检查、组/局部动画及跟随关系的统一校验。
- [x] 验证 release 超出 singing、显示裁切/延长、短音节、零时长及重复触发。

### P4：示例与验收

- [x] 用直接 Body/Overlay/Animation 构造改写 layered_glow；另给出等价的子类复用版本。
- [x] 验证 Lead、K1、K2 的输入绑定，以及单行/双行排版，不添加角色名称特判。
- [x] 验证相同配置用于多个 Track 时互不影响；验证构造参数覆盖类默认配置。
- [x] 验证正文/注音共享扫色颜色、保留不同描边/blur 宽度，以及局部覆盖/禁用。
- [x] 用 parsed ASS 和直接构造 Document 分别验证一行三种颜色交替，无需输入携带自定义样式字段。
- [x] 视觉验证斜体、空格、字体回退、连写、较大 blur、动态缩放、音节边界、注音和透明边缘；RGB 与 YUV420 分别记录，后者的色度混合限制见后端审计。
- [x] 记录与旧 layered_glow 的有意视觉差异、事件数量、采样误差及渲染成本；见完整夹具的成本/采样报告与验收记录。

### P5：迁移与质量

- [x] 更新公开导出、配置参考、迁移文档与示例；所有预期语法经实际执行后再标为可用。
- [x] 添加有意义的运行时/视觉测试与正反类型用例，覆盖直接构造和子类自定义。
- [x] 通过项目严格 ruff、ty 检查及相关测试；不放宽规则规避问题。
- [x] 生成本轮独立验收记录，不引用历史通过结果作为新实现完成证据。

## 验收范围与后端能力边界

- Track、Body、Ruby、Overlay、Animation 均使用显式构造和普通继承。两类 Document 输入、范围分色、CSS 级联、TrackGroup、动画生命周期及类型契约均经实际测试。
- 原生文字路径保留低成本输出，对不同材质的描边/辉光硬裁剪及按绘制层应用 alpha 明确诊断。自然前沿和合成后组 alpha 使用 `RasterSettings` 栅格路径；两者均从 libass 查询有限核边界，不提供用户侧测量补偿。
- 栅格支持预模糊材质分配、不同半径/宽度、正文/注音、分层几何与材质动画。不同材质、范围和动画层级的透明度通过覆盖率与权重分离实现，独立高斯参考及层级像素测试覆盖；非零样式旋转、非普通描边模式和超出原生半径范围仍明确报错。
- 默认栅格无损；显式颜色误差预算只影响空间精度。像素、采样、缓存、事件及字符预算均限制输出。完整 layered_glow 在显式启用 4/255 空间量化并提高事件预算后，使用默认字符预算成功输出；约 100 MB 的成本、旧示例差异及采样误差均已实际记录。
- 九类 RGB 矩阵、独立动态/中间帧参考和完整示例的 13 帧验证分别覆盖几何、材质与时间采样。RGB 的端点一致不能掩盖 YUV420 色边或帧间保持误差，详见验收记录中的分项数据。
- 旧 Effect/Halo、独立装饰及尚未提供等价 Track 语义的逐字事件继续保留；迁移说明明确入口和差异，没有删除兼容能力。

## 后续：可采样动画与时间轴组合（已实现）

原 P0–P5 的验收数字是当时的快照。本轮动画接口与语义见
[动画时间轴](animation-timelines.md)，示例见 `examples/syllable_pulse.py`。

- [x] `Animation.sample(t, context) -> Transform`，支持直接传函数和普通子类。
- [x] `Composition.compose(timeline, context)` 与函数式 builder，支持嵌套。
- [x] `play` 的并行、顺序、明确开始时间、时长覆盖和歌词区间绑定。
- [x] 按时间接续属性快照，后开始者接管，同开始同属性明确报错。
- [x] `ScaleTo`、`MoveTo`、`OpacityTo`、`TransformTo` 及用户自定义曲线。
- [x] 当前音节放大、下一音节缩小；间隔、直接后继无时间、零时长和末尾收尾。
- [x] 显示窗口扩展保持源歌词时钟，原生线性关键帧与任意函数采样接入。
- [x] 调度边界切分采样区间，覆盖原生与 raster 后端。
- [x] 类型正反例、文档示例、真实 Document/解析 ASS 与命令行验证。
- [x] 本轮工作树 Ruff、ty、完整测试通过：692 passed。历史 wheel 验收不代表本轮新代码已重新打包验证。
