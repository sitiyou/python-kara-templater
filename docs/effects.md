# 特效指南

本库给已有歌词添加特效。输入提供正文、演唱时间、ASS 样式和显示窗口，效果配置颜色、扫色、强调及装饰，不重新编排歌曲时间线。

本文说明如何通过组件、样式和动画行为为已有歌词添加特效。范围见[实现计划](effect-system-plan.md)，逐项证据见[交付审计](effect-system-audit.md)，运行结果见[最终验证报告](effect-system-final-validation.json)。

## 一个完整的效果

```python
from kara_templater import (
    BLACK, CYAN, WHITE, Body, Effect, Halo, Lyrics, Ruby,
)

class Glow(Effect):
    def compose(self):
        yield Lyrics(
            Body(fill=WHITE, stroke=BLACK, stroke_width=3),
            Ruby(stroke_width=2, follow="syllable"),
            Halo(id="light", color=CYAN, width=6, blur=8, opacity=0.2),
        )

    def configure(self):
        self.text.sweep(fill=CYAN)
        self.syllables.on_singing(pulse=1.1)
        self.query_one("#light", Halo).on_singing(opacity=(0.2, 0.8), keep=True)
```

`compose()` 必须返回一个 Lyrics，包含一个 Body、至多一个 Ruby，以及任意多个 Halo。每行创建独立的绑定实例，随后调用 `configure()`，完成样式解析后才测量布局和编译输出。不要把绑定后的组件或目标保存到全局变量。

来源与来源集合在 compose 前已经绑定；组件查询在 configure 中可用。组件查询按声明树的遍历顺序返回，多个 Halo 按声明顺序叠放在正文后方，后声明的 Halo 位于先声明的 Halo 上方。非法根结构、Body/Ruby 数量或重复 ID 在 configure 前报错。

Body 未设置的外观继承来源 ASS 样式；ruby 默认继承对应正文的颜色，保留自己的布局尺寸。Halo 默认白色、不透明、宽度和模糊为零，颜色独立于正文。字号用 `style.font_size` 在布局前设置；当前不支持单个字符或读音的混合字号布局，会报能力错误。

将类或实例传给 `render_karaoke`：

```python
from kara_templater import Document, render_karaoke

source = Document.load("input.ass")
result = render_karaoke(source, effect=Glow)
result.document.save("output.ass")
```

直接构造的 Document 也走同一入口，不需要先序列化再 parse。显式传入 `KaraokeItem` 集合是第三种入口：`render_karaoke(document, items, effect=Glow)`。输入对象保持不变；解析导入时，输出文档将已处理原歌词保留为带所有权标记的注释。相同 owner 重跑替换自身输出，不删除其他 owner 的事件。

CLI 脚本导出 `effect = Glow`，然后执行 `kara-templater input.ass output.ass --effect song_effect.py`。脚本是普通 Python，歌词内容不作为代码执行。

不传 --effect 时，CLI 的颜色、淡入淡出和强调选项也通过同一套 Effect 组件与行为组合；其预设显式保留历史命令行的 ruby 描边和透明度。来源诊断中的 effect 名称对应实际作者类，正文与装饰不再借内部编译类名称区分。

## 代码层分色

不要求修改 ASS、加入私有标签、拆分 Dialogue 或填写 Actor/Effect 字段。可以根据已有正文、样式、来源顺序或时间在代码中选择目标。

```python
from kara_templater import RED, GREEN, BLUE, StyleSheet, rule

class Alternating(Effect):
    styles = StyleSheet(
        rule("body", fill=WHITE, stroke=BLACK, stroke_width=3),
        rule(".red:sung", fill=RED),
        rule(".green:sung", fill=GREEN),
        rule(".blue:sung", fill=BLUE),
    )

    def compose(self):
        yield Lyrics(Body())

    def configure(self):
        if self.syllables.text == "星月风星月风":
            for text, role in zip("星月风", ("red", "green", "blue"), strict=True):
                self.characters.query(f'[text="{text}"]').add_class(role)
        self.text.sweep()
```

输入只需普通 `{\k300}星月风星月风`。唱前白色，扫过区域依次显现红绿蓝红绿蓝；六种颜色范围仍共享原 3000 ms 演唱段。[可运行版本](../examples/alternating_colors.py)包含 Document 构造与命令行入口。

直接覆盖也可用于单个目标或集合：

```python
self.characters[0].style.sung.fill = RED
self.rubies[0].style.fill = BLUE
self.body.text_range(0, 2).style.sung.fill = GREEN
```

`text_range` 使用整行纯正文的 Unicode 码点，左闭右开，不包含 ASS 标签和 ruby。字符集合使用保守的字形簇候选；最终布局会拒绝切开连字或不可独立绘制的字形。不要假定一个码点就一定可单独绘制。

层叠顺序为来源外观、StyleSheet、组件显式参数及 `.style`。规则按 `(ID 数, 类/属性/状态数, 类型数)` 比较，同级后声明者优先。目标继承组件已解析外观，再应用目标新增规则和覆盖。`INHERIT` 读取对应继承值；`UNSET` 删除本级覆盖，重新使用较低层值。`None` 不是继承关键字。

`:sung` 表示唱后外观，由扫色覆盖混合，不是整对象同时变色。`sweep(fill=..., stroke=...)` 直接写入正文和 ruby 的 `.style.sung`；后续赋值可覆盖，`UNSET` 可撤销颜色覆盖而保留扫色行为。范围类标记合并，显式覆盖优先于类规则；较窄范围不会自动获得更高优先级。

集合赋值广播到各目标；读取返回共同的显式声明，声明不同时报错。空集合读取 UNSET，写入仍校验参数。单个 ruby 对应多种正文颜色时，需要明确指定自身配色，避免猜测。

## 选择来源与组件

| 入口 | 含义 |
| --- | --- |
| `self.source` | 当前 KaraokeItem，含来源 ID、ASS 样式、显示窗口和结构化歌词 |
| `self.body` / `self.ruby` | 声明组件；后者要求已声明 Ruby |
| `self.query(Halo)` / `query_one("#light", Halo)` | 查询声明组件；query_one 要求恰好一个匹配 |
| `self.syllables` | 原歌词单元，可能有多个演唱段 |
| `self.characters` | 全行字符候选，实际可独立绘制性由布局验证 |
| `self.segments` | 所有原演唱段，保留停顿、重复与零时长 |
| `self.rubies` | 有非空读音的来源段，正文不在此集合中 |

组件查询支持类型推断：`self.query(Body)` 返回 `tuple[Body, ...]`，
`self.query_one(Ruby)` 返回 `Ruby`，子类查询保留子类类型。
字符串选择器的结果是 `Component`；需要调用特定组件的方法时，写成
`self.query_one("#light", Halo)`。它会先要求恰好一个匹配，再检查实际组件类型，
不匹配时报 `TypeError`。`self.body` 和 `self.ruby` 分别是 `Body`、`Ruby`。

集合支持索引、切片、迭代和 `.query()` / `.query_one()`，筛选后仍可调用样式及行为方法。例如 `self.syllables[0].segments[1]`、`self.rubies.query('[text="きょ"]')`。属性等值、类型、类标记、局部 ID 和后代关系共用有限选择器语法；不支持 `>`、逗号组合或运行时伪状态查询。

来源层级为 syllable → character，或 syllable → segment → ruby。来源属性包括 `unit`、`text`、`style`；字符有单元内 `start/end`，segment/ruby 有 `segment`、`start_ms/end_ms`，segment 还有 `reading`。可用 `self.rubies.query('syllable.lead segment[segment=1] ruby')` 查询某类单元下的第二读音。类型名称用于来源集合查询；样式表仍匹配视觉组件及正文/ruby 样式节点，可先查询目标再添加样式类。

`.source_refs` 提供原 SourceRef，`.intervals` 提供原时间区间，segment/ruby 的 `.readings` 返回读音。`.text` 返回正文或 ruby 文本；segment 集合按所属单元去重正文，时间与读音仍逐段保留。重复文本不会被视为唯一身份，query_one 会报告多匹配。

静态单元没有 segment；空正文没有字符候选，但可以有演唱段。segment 是时间目标，不能直接设置静态样式，应选择正文或 `.rubies`。组件与来源实例不跨行共享可变状态。地址在来源结构不变时稳定，不是编辑歌词后仍永久有效的 ID。

空行或空正文不生成文字及关联装饰，也不执行这些目标的动画函数；静态正文仍正常显示，但 on_singing 没有可绑定的时钟。空正文附带非空 ruby 时，当前后端会报告零宽正文映射错误，包含单元和段地址。ruby_continuation 只影响读音排版分组，不合并来源选择：组内每段读音仍可分别查询、设样式和绑定行为。

字符查询发生在布局前，候选字符可能在实际字体中形成连字。动画选择覆盖完整连字时绑定到实际字形，例如 DejaVu Sans 中 `office` 的 `self.characters[1:4]` 选中整个 `ffi`；只选其中一个 `f` 会报字形簇边界错误，不会静默忽略动画或拆开连字。相邻范围只在同一条行为内合并，分别声明的单字动画不会自动合成。

## 时间、曲线与组合

`on_singing()` 默认绑定首段开始到末段结束的包络，停顿期间继续变化。`progress="singing"` 按累计实际演唱进度求值，停顿时保持。选择 `.segments` 后调用行为会逐段绑定独立时钟；选择 `.rubies` 则只作用于相应读音，缩放绕其自身中心。

`progress="singing"` 必须使用 `(singing.start, singing.end)`，不接受另行偏移的绑定区间。已知线性/分段曲线会映射到各段的实际时钟，停顿两端具有相同属性值；关键帧可以落在段内，也可以通过绝对时间引用落在停顿处。零总演唱时长、量化后无法保留节点或未知函数继续采样。普通函数接收累计演唱进度，原生优化不执行或推断函数内容。

支持 `scale`、`offset_x`、`offset_y`、`opacity`。常量表示固定值，二元组等价于线性 Transition，函数接收归一化时间并返回实际属性值。rate 函数则返回插值进度：

```python
from kara_templater import Transition, there_and_back, smooth, singing

self.syllables.on_singing(scale=Transition(
    1, 1.2,
    rate=there_and_back(peak_at=0.2, return_at=0.65, rise=smooth),
))
self.syllables.animate(
    offset_y=lambda p: -20 * p,
    during=(singing.start - 100, singing.end + 200),
)
```

内置 rates 为 linear、smooth、ease_in、ease_out、ease_in_out、there_and_back。`pulse=1.1` 是往返缩放快捷写法；不可同时传 scale。需要多段精确变化时可传 `Keyframes(Keyframe(0, 1), Keyframe(0.3, 1.2), Keyframe(1, 1))`。关键帧比例相对于绑定区间，也可使用时间引用；倒序不会自动重排。

`during` 接受绝对整数毫秒或 `singing.start/end`、`display.start/end` 加减毫秒。默认区间外恢复基础属性；`keep=True` 保持函数实际终值 `f(1)`。显示窗口裁剪输出，不重启演唱时钟。静态文字可用 display 绑定动画。

`self.characters.on_highlight(duration_ms=400, offset_y=...)` 在扫色到达时启动；threshold 可选 enter/center/complete，duration_ms 也可为 traversal。轨道选择支持 first/each/named，命名轨道传 track_id，retrigger 控制是否跨轮再触发。

需要绝对时间或目标信息时，显式使用 Contextual；普通 lambda 仍只接收进度：

```python
from math import sin, tau
from kara_templater import Contextual, display

self.characters.animate(
    offset_y=Contextual(
        lambda ctx: 4 * sin(
            ctx.time_ms / 1000 * tau + ctx.noise("phase", animated=False) * tau
        ),
        seed=42,
    ),
    during=(display.start, display.end),
)
```

PropertyContext 提供 time_ms、progress、绑定 interval、显示 window 和只读 target；target 包含正文或读音文本、kind、sources 以及稳定身份。可直接按文本或来源判断，无需解析输出 ID。noise 按显式种子和原目标身份产生确定性值，animated=False 不随时间变化。跟随的 Halo 复用原动画目标的上下文；Halo 自己声明的属性使用其自身目标。函数只在采样预检通过后执行，返回实际属性值，继续受属性校验、冲突和来源诊断约束。

独立的 Halo 属性需要与正文或读音共享随机相位时，可用 `ctx.noise("phase", animated=False, scope="source")`；默认 scope="target" 则保留每个装饰自己的噪声身份。这通过原始目标绑定实现，不依赖解析 ID 字符串。[dynamic_effect.py](../examples/dynamic_effect.py) 展示文字位移和辉光模糊共享来源相位。

keep=True 在绑定结束后传入终点时间和终点进度，保持终值；time_ms 不会随着显示窗口继续前进。progress="singing" 时，time_ms 仍是实际绝对时间，progress 才是扣除停顿后的演唱进度。函数应保持纯粹，不依赖求值次数。

不同属性可重叠；同属性默认 replace 要求时间不重叠。显式 compose 支持位移 add、缩放/透明度 multiply，以及按声明顺序取最后活动规则的 override。重叠规则必须选择相同的显式模式；不同中心的重叠缩放不能自动合成。冲突报告目标、属性与时间。

## Ruby、辉光与跟随

Ruby 默认不跟随正文的位移、缩放和透明度动画，但跟随整行淡入淡出；`follow="syllable"` 开启全部跟随。也可传 `Follow(position=..., scale=..., opacity=..., fade=...)` 独立控制，各开关在 Follow 构造器中默认 True。Halo 默认跟随所附目标的全部变换；附着在默认 Ruby 上的 Halo 不会额外继承正文强调。position 指显式位移，围绕中心缩放产生的几何位移仍由 scale 决定。`self.ruby.hide()` 同时隐藏相关装饰，跳过隐藏目标的属性求值。关闭跟随不禁用 `self.rubies[i]` 自己声明的动画。

`Halo(color=INHERIT)` 显式继承所附正文或读音的唱前/唱后填色；也可以仅设置 `halo.style.sung.fill = INHERIT`。每个目标独立读取已解析样式，支持一行多色和读音自身覆写。未声明继承的 Halo 仍使用独立配色；UNSET 移除覆盖后回到规则或默认白色。继承的是目标样式，不把轨道的完整 Paint 栈复制成另一组辉光。

Halo 按声明顺序由后向前叠放，文字在上方。width、ruby_width、blur、opacity 独立配置，targets 可为 text/body/ruby。默认 clip="none" 为完整目标辉光；clip="sung" 裁剪到已唱覆盖，重叠轨道取覆盖并集，避免重复增亮。

在 compose 中也可以传来源选择集合，例如 `Halo(targets=self.characters[:1])` 只装饰首个字符，`Halo(targets=self.rubies[1:])` 只装饰后续读音。`self.syllables[:1]` 同时选择首个音节的正文及关联读音；空集合不生成辉光。选择在声明时固定，不改变文字、布局或演唱区间。字符范围必须覆盖完整可绘制字形簇，切开连字会报告来源错误；`self.segments` 是时间片段，不能直接作为 Halo 的视觉目标。

Halo 默认跟随目标全部变换；使用 Follow 关闭对应属性。`window=(display.start, display.end + 300)` 可延长装饰显示，演唱时钟不变；fade 跟随仍使用来源淡入淡出窗口，因此希望在来源退场后继续显示时需要显式关闭 fade 跟随。`self.text.fade(in_ms=..., out_ms=...)` 配置来源窗口内淡入淡出。

Halo 自身支持 opacity 和 blur 的 on_singing/animate，组透明度与装饰自身透明度相乘。可用 `rule("halo:sung", fill=BLUE, opacity=0.8)` 或 `halo.style.sung.fill = BLUE` 配置唱后外观。唱后状态根据实际扫色覆盖解释，单纯经过演唱结束时间不会触发整对象换色。

动态模糊必须在构造时声明上界，例如 `Halo(id="light", blur=10, max_blur=30)`，再调用 `self.query_one("#light", Halo).on_singing(blur=(10, 30))`。blur 支持常量、曲线、关键帧、函数和 Contextual，当前统一采样，可与原生 opacity 同时使用。区间外恢复基础 blur，keep=True 保持终值。上界必须覆盖基础模糊，并用于裁剪域预留；实际采样值超出该 Halo 的上界会报告来源和时间，不因另一个 Halo 声明了更大上界而放行。动画不修改原布局或正文扫色进度。

`clip="none"` 保持唱前和唱后两侧均可见；外观不同时需要空间裁剪来区分两侧，外观相同则保持完整无裁剪辉光。`clip="sung"` 始终隐藏未唱区域。自身 opacity 动画在活动区间覆盖两侧的状态透明度，结束后恢复各状态值；keep=True 则保持终值。改变状态颜色会保留 ASS 硬裁剪接缝诊断，不承诺统一模糊的无缝混色。

## 颜色

以下常量均为不可变 Color，可与 `Color.hex("#RRGGBB")` 或六位颜色字符串互换。透明度单独设置，不包含在颜色中。字符串颜色不接受简写或英文颜色名。

| 常量 | RGB 十六进制 |
| --- | --- |
| WHITE | `#FFFFFF` |
| BLACK | `#000000` |
| RED | `#FF0000` |
| GREEN | `#00FF00` |
| BLUE | `#0000FF` |
| YELLOW | `#FFFF00` |
| CYAN | `#00FFFF` |
| MAGENTA | `#FF00FF` |
| ORANGE | `#FFA500` |
| PURPLE | `#800080` |
| PINK | `#FFC0CB` |
| GRAY | `#808080` |

可用 `SUNG_FILL = Color.hex("#01829d")` 定义歌曲专用配色。[layered_glow.py](../examples/layered_glow.py)同时使用 WHITE/BLACK 和命名自定义颜色，保留原画面的准确值。

## 输出与当前边界

普通扫色、淡入淡出及可识别的线性/分段缩放使用原生 ASS。组透明度与 Halo 自身透明度也会自动尝试原生输出；缩放及透明度支持已知曲线的 override 和线性 multiply：常量相乘或一个变化因子乘常量可原生输出；多个同时变化的因子乘积非线性时保持采样。与 fade 相乘后非线性、过短的分段或未知函数也保持采样。横纵位移的已知线性/分段曲线自动输出为原生 `\move`，包括显式 add/override；各轴独立选择输出路径，可以与另一轴或缩放的函数采样共存。位移在缩放后施加，正文、关联装饰与扫色裁剪只平移一次。不能把 lambda 自动识别为原生曲线。`SamplingSettings(step_ms=40)` 默认每 40 ms 保持一个值，步长须为 10 ms 正整数倍，不承诺任意函数的空间误差。可在 configure 设置 `self.sampling`。

底层 TextLayer 已支持 `opacity_animations=(OpacityAnimation(points, keep=..., component="group"),)`；component="glow" 则覆盖辉光自身透明度。它要求已知分段线性点，保留原始透明度时钟；同时变化的淡入/组透明度/辉光透明度相乘若产生非线性曲线，会报告需要采样。作者层在属性函数执行前检查已知点与组合曲线，按稳定目标统一选择原生或采样路径。普通脚本继续使用 on_singing/animate，无需直接构造底层动画。原生 alpha 在节点间连续插值，可能与旧的 40 ms 保持采样有轻微亮度差异；这是输出精度改善，不应继续要求与旧采样逐像素相同。

渲染在属性回调前预检预算，`render_karaoke(..., on_estimate=callback)` 提供成本预览；最终输出仍受事件上限约束。`result.diagnostics`、`event_origins` 保留能力提示与来源。ASS 时间使用 10 ms 网格，矩形裁剪还有整数像素取整误差。

预算预检覆盖整份文档，后续歌词超预算也不会先执行前面歌词的属性函数；on_estimate 可以抛出异常取消渲染。估算统计采样曝光和视觉通道，不是最终事件数的上界：原生裁剪细分可能增加事件，合并相同采样状态也可能减少事件。最终编译仍执行 max_events 限制；无法在 ASS 时间网格内达到 clip_error_px 时明确报错。该容差只约束裁剪曲线近似，不包含整数裁剪坐标取整，也不约束任意函数在两个采样点之间的变化。属性函数异常保留原异常原因、来源、目标与绝对采样时间。

本库不提供自动换行、碰撞避让或通用场景图。字体缺失、不可独立绘制的字形及不支持的 ASS override 明确报错。局部辉光采用 ASS 硬裁剪，不等于先裁剪字形再统一模糊；增加时间采样不能消除空间接缝。多层、并行轨道与动画组合需在实际字体和播放器环境中验证。

组合验证命令为 `python -m tools.validate_composed_glow /tmp/composed-glow-review`。固定场景覆盖双层辉光、并行扫色、ruby 跟随/退出跟随、整组/逐字缩放和已唱区域辉光。原生往返曲线与等价关键帧要求画面完全相等；等价函数按 10 ms 采样，对比时单独验证扫色坐标，并为边界附近的整数裁剪与色度重建留出明确容差。详见 [composed-glow-validation.json](composed-glow-validation.json)，不将局部高对比边界宣称为逐像素等价。

追加 `--offsets` 可在同一矩阵中验证横纵位移，并将两条已知位移相加的写法与单条等价位移逐像素比较。已保存 [composed-offset-validation.json](composed-offset-validation.json)，覆盖原生、关键帧、函数及 add 合成四种写法。函数对照仍使用上述裁剪坐标与边界像素容差。

旧作者类 KaraokeEffect 已删除，不提供兼容包装。作者脚本使用 Effect；EffectPlan/build、TextLayer、底层 Pulse 和 DynamicEffect 保留用于自定义输出与后端验证，共用内部编译器。最终交付复验结果见 effect-system-final-validation.json。

已知属性合成的渲染对照见 [composed-product-validation.json](composed-product-validation.json)：五组场景分别比较原生、关键帧、函数、等价乘法和位移加法，乘法写法同时覆盖缩放与 Halo 透明度，要求与原生画面逐像素相同。
