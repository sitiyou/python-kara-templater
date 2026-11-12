# 声明式文字特效修改计划

状态：待实现。本轮仅更新设计与 TODO，以下语法尚未实现。本文替代前一版将 Sweep、Fade 作为 Effect 专用平级字段的方案。第一轮历史记录见 [原计划](effect-system-plan.md)。

## 核心模型

文字对象持有样式、可选 sweep 和通用 animations。Sweep 是所属文字的局部外观覆盖，不拥有独立文本、排版或变换树。普通辉光属于文字样式的 blur，不要求作者维护 base/sung 两个 Halo。动画使用统一的触发与属性轨道模型，淡入淡出是透明度动画，不增加专用 fade 生命周期字段。

Lyrics 是正文与注音的文字组，可声明公共 style、sweep 和 animations。Body/Ruby 可以局部覆盖或禁用 sweep。公共 sweep 配置复用，不等于共享时钟或绘制状态：每个目标独立绑定自身来源、布局与演唱时间。

## 预期写法

省略导入。颜色沿用现有示例。PaintStyle 是不可变的部分绘制样式，可以跨对象与效果共享。

```python
SUNG = PaintStyle(
    fill=Color.hex("#01829d"),
    stroke=WHITE,
    blur=Blur(color=Color.hex("#67e5ff")),
)


class LayeredGlow(Effect):
    lyrics = Lyrics(
        style=TextStyle(
            fill=WHITE,
            stroke=BLACK,
            stroke_width=5,
            blur=Blur(
                color=Color.hex("#9e6d64"),
                radius=10,
                width=10,
                opacity=0.8,
            ),
        ),
        body=Body(),
        ruby=Ruby(
            style=TextStyle(stroke_width=3, blur=Blur(width=6)),
            offset_y=10,
            follow="syllable",
        ),
        sweep=Sweep(
            style=SUNG,
            curve=ProgressCurve.two_stage(
                time_fraction=3 / 17,
                progress_fraction=0.3,
            ),
        ),
        animations=(
            On(Display.Start, Animate(opacity=(0, 1), duration=800)),
            On(
                Display.End,
                Animate(opacity=(1, 0), duration=200),
                offset=-200,
            ),
            On(
                Syllable.Singing,
                Animate(scale=Envelope(peak=1.1, attack=80, release=160)),
                where=~LineMatch(style="LEAD"),
            ),
        ),
    )

    variants = (
        When(
            LineMatch(style="LEAD"),
            lyrics.ruby.override(visible=False),
            lyrics.sweep.override(curve=linear),
        ),
    )


result = render_karaoke(document, effect=LayeredGlow)
```

公共 Sweep 把正文与注音各自的填充、描边和辉光颜色扫成 SUNG 中的颜色。它没有重设正文的描边宽度 5、辉光宽度 10，也没有重设注音的描边宽度 3、辉光宽度 6。曲线声明共用，注音绑定自身 segment 的演唱进度。follow 影响变换跟随，不隐式改变扫色时钟。

本示例有意将辉光改为随扫色覆盖区域变色；它与旧例两层辉光按音节时间叠加、以及上一版草案的整音节辉光渐变均不同。独立的整音节颜色动画仍可由通用动画机制表达，但不得默默与 Sweep 同属性写入混合。

## 样式复用与覆盖

第一种复用是所属文字组的公共默认值：Lyrics.sweep 被 Body/Ruby 继承。第二种复用是不可变的 PaintStyle 常量，供不同 Sweep 使用。需要常量变体时可使用标准 dataclasses.replace，不修改原对象：

```python
RUBY_SUNG = replace(SUNG, fill=PINK)

# 只覆盖该注音的扫色填充；曲线等仍继承 Lyrics.sweep。
ruby = Ruby(sweep=Sweep(style=PaintStyle(fill=PINK)))

# 在另一个效果中显式复用完整公共覆盖样式。
other_sweep = Sweep(style=SUNG)
```

replace 是字段替换；替换嵌套 Blur 时不会暗中深合并旧 Blur。声明继承中的部分字段合并则有明确契约，两者不可混淆。

解析顺序：先确定文字组与目标的普通样式，应用现有来源范围级联；然后以每个目标自己的已解析样式作为覆盖层基底，应用公共 sweep.style、局部 sweep.style 以及来源范围的 sung 覆盖。每一级仅覆盖显式字段，嵌套 Blur 按字段处理。

- 未指定字段使用 UNSET，构造时不能提前填默认值。
- sweep 未指定表示继承，sweep=None 表示禁用；blur=None 表示禁用辉光。
- 覆盖样式中的 INHERIT 表示使用所属目标的对应基础绘制属性，UNSET 表示不贡献当前层覆盖。继承的含义必须在类型与文档中明确。
- PaintStyle 仅允许绘制属性；字体、字号、字距等属于 TextStyle，不能被 Sweep 覆盖。避免用宽泛 **kwargs 或字符串属性路径绕过类型检查。
- 共享声明不可变；每行、每个目标的解析结果和动画状态独立。
- 原有代码分色能力接入同一套普通/sung 样式级联，不增加 ASS 私有协议或要求导入数据携带自定义角色字段。

## Sweep 的领域语义

Sweep 表示沿既有歌词进度逐渐显露另一套绘制外观。用户声明覆盖什么颜色或绘制属性；后端负责掩膜、字形边界与图层展开。

| 内容 | 归属与继承规则 |
| --- | --- |
| 文本、字形塑形、字体、字号、字距、基线、排版 | 唯一归属底层文字，Sweep 直接复用；不允许覆盖导致重新排版 |
| 位置、缩放、旋转、变换中心 | 复用目标在当前时刻的几何变换，不复制动画再执行一次 |
| 填充、描边颜色 | 默认使用所属文字当前绘制值，可局部覆盖 |
| 描边宽度、blur 的颜色/宽度/半径/透明度 | 默认继承目标，允许显式绘制覆盖；扩张只影响绘制边界，不改变排版或演唱进度 |
| 文字组整体透明度、可见性、显示窗口 | 作用于最终合成结果一次；覆盖层局部透明度是额外合成参数，不能重复乘继承值 |
| 扫色曲线、方向、时钟、重复策略 | 属于 Sweep 的语义，可显式控制，与底层几何补偿分离 |

所有继承都基于每个目标，而不是先从 Body 解析出一套固定样式后复制给 Ruby。继承已求值的属性，不克隆并重复执行底层动画。

Sweep 不应默认生成两个完整文字图层直接 alpha 叠加。默认语义是由扫色掩膜在基础外观与覆盖外观之间选择，保持区域外基础样式，区域内采用覆盖样式；透明覆盖值参与区域内的外观合成。透明颜色与边缘抗锯齿不得因重复绘制变深。特殊多轨叠加使用显式合成策略。

绘制语义应先按字形覆盖与进度分配绘制外观，再处理描边和模糊；光晕可以自然扩散到扫色前沿之外。不能默认在全部模糊完成后用硬矩形裁掉光晕。ASS/libass 是否能原生表达此合成顺序必须验证；必要时使用受预算约束的分层/采样方案，并明确后端能力限制。

## 底层边界与时间补偿

现有代码证据：timeline.EdgeSweep 持有 padding_px/lead_ms/tail_ms，masks.track_spans 为外侧边界展开装饰余量；_compiler 使用 border + 4*blur 估算辉光边界并提示用户增加 padding。新的公共 Sweep 不携带这些补偿参数。

- 分开维护布局 advance 区域、实际 glyph ink 区域、描边/模糊后的绘制区域。使用与输出一致的字体选择、塑形与坐标变换，检查 metrics 与 libass 的差异。
- 原始演唱进度和触发时钟不因描边、模糊或裁剪误差而改变。padding 不能承担时间修正职责，也不能自动把原来的 24 ms 换成另一个隐藏常量。
- 明确进度为 0 和 1 时的完整未覆盖/已覆盖语义；装饰外扩不能导致开头残色、结尾残边或内部音节边界串色。
- 动态 scale、stroke_width、blur 需要当前时刻的有效绘制边界。模糊核无有限的数学外边界时，按后端误差容限估算并验证，不能宣称存在绝对精确的有限边框。
- 后端误差控制使用统一的渲染精度配置及诊断。真实的艺术性提前/延后仍可显式修改时间锚点，但不得作为修复 metrics/blur 的必填项。
- 不承诺只改 libass：先定位测量、塑形、裁剪及合成哪个环节产生差异，再决定编译器、metrics 或渲染适配层的修复。

## 通用动画与生命周期

animations 是同一种声明序列，支持透明度、缩放、位移、颜色等；On 负责事件匹配与时间偏移，Animate 负责类型化属性轨道。常用 FadeIn/FadeOut 将来可以作为普通动画预设，但不引入专用 fade 字段。

Display.Start/End 是显示窗口的时间锚点。示例离场动画从 End-200 开始，在 End 完成；不能等 End 才启动一段在默认窗口之外不可见的动画。Syllable.Singing 提供完整演唱包络，Segment.Singing 提供单段区间，Highlight 按选定扫色轨道产生区间。作用目标由事件上下文确定，可通过类型化目标引用明确指定。

事件与行匹配在构建阶段展开，不依赖实时事件队列。声明、普通动画预设和 @on 方法返回值编译为同一种动画轨道。

```python
@on(Syllable.Singing, where=LineMatch(style="K1"))
def accent(self, event: Syllable.Singing) -> Animate:
    return Animate(
        event.target,
        scale=Envelope(peak=1.08 + 0.02 * (event.index % 3), attack=80, release=160),
    )
```

该动态规则用于替代对应固定缩放，不应与其悄悄叠加。

- 动画寿命独立于事件区间。Envelope 从基础值在 attack 内升至 peak，保持到演唱结束，再经 release 回到基础值；短音节压缩 attack，零时长按明确定义处理。
- 关键帧允许 event.end+160 等独立时间锚点，缓动支持内置函数及 Callable[[float], float]。分别控制上升/回落曲线，保留序列/并行组合能力。
- 默认输出裁至原显示窗口，不重新缩放动画进度；显式 extend_display 扩展相关目标及附属绘制的窗口。组透明度可能使延长部分不可见，文档必须说明。
- 同属性冲突、尾动画与下一次演唱重叠、keep、组动画和局部动画进入统一校验；不能依赖回调执行顺序。
- 根组动画作用于文字及其 sweep/blur 的合成结果一次；音节动画绑定音节及依照 follow 关联的注音。自定义动画不需要新增 Effect 字段种类。

## 实施 TODO

### P0：语义与类型原型

- [ ] 审计当前扫色、字形测量、EdgeSweep、透明合成与 Halo 行为，建立最小复现图。
- [ ] 固定基础文字/覆盖绘制/组变换的属性边界，确认 alpha、描边、blur 的合成顺序。
- [ ] 为 TextStyle/PaintStyle/Blur、Lyrics.sweep、局部覆盖、不可变复用和嵌套引用编写类型原型；不泄漏 Any/Unknown。
- [ ] 固定 On/Animate 的目标、时间锚点、Envelope 和冲突语义。

### P1：声明、继承与样式复用

- [ ] 实现声明绑定及逐行隔离，普通效果不再依赖 compose/configure。
- [ ] 实现公共 Lyrics 样式与 sweep、Body/Ruby 部分覆盖和显式禁用。
- [ ] 支持不可变 PaintStyle 常量及 dataclasses.replace，确保复用不串状态。
- [ ] 将 When、LineMatch 及其否定匹配接入声明解析，保留代码范围分色的既有级联契约。

### P2：扫色与后端边界

- [ ] 测量并对比 advance、ink、描边和 blur 的边界；定位 metrics/libass 差异。
- [ ] 公共 Sweep 移除 padding/lead/tail 补偿；后端按精度契约自动处理绘制边界。
- [ ] 实现覆盖层与文字共用塑形、布局和动态变换；禁止独立排版及重复透明度应用。
- [ ] 实现 blur 样式及基础/覆盖外观合成，验证彩色光晕自然扩散与透明边缘。
- [ ] 对原生 ASS 表达不了的情况提供受预算控制的实现或明确诊断，不要求用户补魔法数字。
- [ ] 独立多层装饰与普通 blur 分开审计；在能力被覆盖前不直接删除必要的底层支持。

### P3：统一动画

- [ ] 实现 animations/On/Animate 及 @on 返回值的统一编译。
- [ ] 以透明度轨道实现入场/离场，删除专用 fade 配置依赖。
- [ ] 支持 scale、offset、颜色、Envelope、关键帧、自定义曲线与序列/并行组合。
- [ ] 验证超过 singing 的寿命、显示范围、重复演唱、多段时钟、跟随和重叠冲突。

### P4：示例与验收

- [ ] 按本文重写 layered_glow，移除 base/sung Halo、compose/configure、专用 fade 与补偿参数。
- [ ] 验证 Body/Ruby 共享扫色颜色同时保留不同描边及辉光宽度；验证局部颜色覆盖、禁用 sweep 和声明复用隔离。
- [ ] 验证 parsed ASS 与直接构造 Document 的一行三色交替，覆盖正文与 blur 的 sung 样式；兼容显式 KaraokeItem。
- [ ] 覆盖斜体外伸、空格、字体回退、字形连写、较大描边/blur、缩放、零时长和多段演唱。
- [ ] 检查扫色起止及中间边缘、音节交界、注音、透明叠加、release 尾段；保留新旧视觉对照并区分有意变化。
- [ ] 记录事件数量、采样误差与成本，不能以无限拆层掩盖错误。

### P5：文档与质量

- [ ] 更新效果文档与迁移说明，解释样式继承、覆盖合成和通用动画。
- [ ] 扩充正反类型用例与有意义的运行时/视觉测试，通过严格 ruff、ty 检查。
- [ ] 生成独立验收报告，未完成前不得引用历史验收作为本轮完成证据。
