# 特效系统实施记录

## 三色示例与两种 Document 输入复核

重跑 `tools.validate_effect_system`：普通 `{\k300}星月风星月风` 在唱前保持白色，唱后依次为红、绿、蓝、红、绿、蓝。解析 ASS、直接构造 Document、显式 items 及直接 style 覆盖四种路径均输出 18 个事件，六个关键帧逐像素一致；原始单 segment 时钟和布局保持不变。结果与 [effect-system-validation-baseline.json](effect-system-validation-baseline.json) 一致。

跨行隔离测试现同时覆盖解析和直接构造输入，以及 class 规则和直接覆盖两种写法；断言未标记的第二行仍为白色、来源 segment 映射保持不变、输入文档序列化内容完全不变。`tests/test_effect.py` 的 35 项测试通过，Ruff 与 `git diff --check` 通过。分色标记始终属于代码侧效果实例，不要求解析器提供歌词样式字段。

## 2026-11-11：来源配置与三色分色链路

已实现 `Effect.compose/configure`、`Lyrics/Body/Ruby`、组件查询、正文范围标记、Python 样式表、直接覆盖、唱后状态及正文扫色。`render_karaoke(effect=MyEffect)` 与传入实例都可用，每行复制独立配置。`configure()` 在布局前执行；ASS 导入与直接构造 Document 仍经过同一 `import_karaoke` 入口，不增加歌词分色字段。

当前 `self.source` 是 `KaraokeItem`，可读取 `.id`、`.style`、`.window`、`.source.units`。范围使用整行纯正文码点，允许跨单元，编译时用现有字形映射校验边界。范围不会拆分原始 segment，也不为文字重新分配演唱时长。

样式支持 `fill`、`stroke`、`stroke_width`、`opacity`、组件 `font_size`；颜色接受 `Color` 或 `#RRGGBB`。基础配色取 ASS Secondary/Primary/Outline，基础规则作用于唱前唱后，`:sung` 表达差异。组件显式值覆盖该组件规则；子范围继承组件结果，再应用范围规则及直接覆盖。同属性的重叠范围直接覆盖按范围首次声明顺序解析。`UNSET` 移除当前显式声明，`INHERIT` 读取对应来源/父级值。

选择器支持类型、ID、类、`[属性=值]`、后代关系及样式中的 `:sung`。查询目前返回声明组件；范围保存代码标记，还没有单元、segment、字形等便捷查询。支持的属性包括组件的 `style`（来源 ASS 样式名），范围匹配时的 `start/end/style`。不提供 CSS 文本解析。

ruby 默认继承关联正文颜色，保持独立字号和描边宽度；正文分色使颜色无法唯一确定时，需要明确 ruby 颜色。改变组件基础字号会先重新测量，再通过 ASS `\fs` 输出；范围字号和唱后字号变化暂时明确报错。

### 内置颜色

| 名称 | RGB | 名称 | RGB |
| --- | --- | --- | --- |
| WHITE | `#FFFFFF` | BLACK | `#000000` |
| RED | `#FF0000` | GREEN | `#00FF00` |
| BLUE | `#0000FF` | YELLOW | `#FFFF00` |
| CYAN | `#00FFFF` | MAGENTA | `#FF00FF` |
| ORANGE | `#FFA500` | PURPLE | `#800080` |
| PINK | `#FFC0CB` | GRAY | `#808080` |

### 验证

运行示例：

```sh
python -m examples.alternating_colors /tmp/alternating-colors.ass
python -m pytest tests/test_effect.py -q
python -m tools.validate_effect_system /tmp/kara-authoring-review \
  --font /usr/share/fonts/sarasa-gothic/Sarasa-Regular.ttc
```

视觉验证需要 Pillow、带 libass 的 ffmpeg 和覆盖示例文字的字体，不是库的新增运行依赖。验证脚本保存 ASS、各时间点 PNG、ffmpeg 日志及 `report.json`。本次输出保存在 `/tmp/kara-authoring-review`；该路径是本次环境的产物，可使用上述命令重新生成。

- 正文：`星月风星月风`，输入只有一个 `\k300`，显示窗口 0～4000 ms。
- 解析 ASS、直接构造 Document、显式 items、直接 `.style.sung.fill` 四组均生成 18 个事件，无诊断。
- 在 0、490、510、1490、1510、3500 ms 的四组画面逐像素一致；自动断言起始白色和结束红绿蓝红绿蓝，并检查布局和演唱时间未改变。
- 实际检查起始、中间及结束帧；增加所有时刻每字可见、扫色前方保持白色及后方保持目标颜色的像素断言。
- 固定字体：Sarasa Gothic CL；文件 SHA256：`96ba7681369bc162f23df2b97e6ecaf8b9df84f05c073e6c75e4acc56da9607b`。
- 单元测试覆盖层叠优先级、状态、继承/移除覆盖、错误输入、三入口等价、两种分色写法、跨行隔离、跨单元范围、字形边界、原始 segment 来源、ruby 继承及歧义、布局前字号与输出字号一致。

完整单元测试 **271 项通过**，其中新特效系统测试 28 项。视觉结果摘要保存于 [effect-system-validation-baseline.json](effect-system-validation-baseline.json)。

本次中间帧检查还发现环境差异：ffmpeg n9.0.2 / libass 0.17.5 在默认滤镜线程设置下，会丢失重复文字的部分未唱白色字形；相同 ASS 使用 `-filter_threads 1` 时恢复，静态裁剪参考也正常。验证脚本固定为单线程并检查中间帧。该对照定位到渲染环境相关行为，尚未证明底层根因；没有为此改变输出颜色或扫色时钟，也不宣称默认多线程路径已经修复。复现时去掉脚本的 `-filter_threads 1` 即可检查本环境的差异。

### 后续工作

这只是首个可运行链路。仍需提取 layered glow 的完整输入与视觉基线、抽出 recipe 的目标映射、完成 Halo、音节/segment/字形查询、属性动画与曲线、时间绑定和冲突检测，随后迁移 layered_glow/whole_glow/staggered_path，验证组合并更新默认文档与 CLI。现阶段保留旧 `KaraokeEffect` 作为后端复用入口；不声称已经完成统一引擎或旧入口移除。

## 2026-11-11：完整目标映射、Halo 与迁移基线

`targets.py` 从原 recipe 提取了 `VisualTarget` / `PreparedLyrics`。正文目标保留原单元的所有 segment，ruby 目标保留对应 segment；二者保存几何、绘制样式、轨道、缩放和来源。recipe 先准备这些目标，再展开空间扫色，旧入口与特效系统共用这份映射。装饰直接使用完整目标，没有遍历扫色碎片去重或清理裁剪。

新增 `Halo(color=..., opacity=..., blur=..., width=..., ruby_width=...)`，默认绑定正文和 ruby；`targets="body"/"ruby"` 可限制种类。按声明顺序从后向前叠放，正文在上方。隐藏 Ruby 后不会创建对应装饰。Halo 当前覆盖完整对象；随扫色裁剪装饰仍待实现。

`self.text.fade(in_ms=..., out_ms=...)` 绑定显示窗口，同时作用于正文、ruby 和 Halo。`halo.on_singing(opacity=..., keep=...)` 绑定演唱时间：正文使用单元首段至末段包络，跨停顿连续变化；ruby 使用自己的 segment。静态目标保留基础透明度，零时长目标按瞬时切换处理，`keep=True` 保持函数实际终值。重复声明同一 Halo 的透明度行为会报错，不静默覆盖。

透明度支持常量、`(a, b)`、`Transition(a, b, rate=...)` 和直接 lambda。内置 `linear/smooth/ease_in/ease_out/ease_in_out/there_and_back`；往返曲线支持 `peak_at/return_at/rise/fall`。rate 返回插值进度，直接函数返回实际属性值。函数暂时通过已有 40 ms 采样入口输出，执行前仍检查采样预算；不把任意函数推断成原生 ASS 变换。后续需将这些表达接入缩放、位移、显式时间和原生变换优化，尚不能将整个属性动画条目标为完成。

### Layered glow 行为基线

自包含输入：[tests/fixtures/layered_glow.ass](../tests/fixtures/layered_glow.ass)。其字体使用仓库 DejaVuSans.ttf，三个样式分别覆盖普通两个单元、含停顿的同单元多读音、LEAD 无 ruby 分支。该输入保留演唱时间，不依赖外部歌曲文件或样式约定。

已提取原示例行为：

| 行为 | 精确参数与时钟 |
| --- | --- |
| 正文 | 白字黑边 5 → `#01829d` 字、白边 5 |
| Ruby | 描边 3、向下 10 px、随整单元缩放；LEAD 隐藏 |
| 底层 Halo | `#9e6d64`，透明度 0.8，blur 10，正文宽 10 / ruby 宽 6 |
| 上层 Halo | `#67e5ff`，透明度 0.2 → 0.8；正文按单元包络、ruby 按对应 segment |
| 缩放 | 非 LEAD 整单元 1 → 1.1 → 1，共同中心；LEAD 不缩放 |
| 扫色 | 非 LEAD 两阶段：时间 3/17 到进度 0.3；LEAD 线性 |
| 边缘 | padding 24 px，lead/tail 各 24 ms，不改变主体时间 |
| 淡入淡出 | 显示窗口内淡入 800 ms、淡出 200 ms，关联装饰同步 |

复现命令：

```sh
python -m tools.capture_layered_glow /tmp/kara-layered-before
```

旧实现基线生成 728 个事件，535 个采样/静态输出层，13 个帧（起始、淡入、演唱开始、变速节点、音节中间、停顿、完成和退场）。摘要、逐样式事件数、像素哈希和诊断存于 [layered-glow-before.json](layered-glow-before.json)。原始 ASS、PNG 和 ffmpeg 日志保存在 `/tmp/kara-layered-before`。迁移后同一工具仍用于生成新结果，应保存到新目录并与固定 JSON 基线比较。

基线检查发现原有后端在不同前后描边的空间交界仍报告 `ASS hard-clips`；K2 多读音映射也保留相应提示。这是待明确比较的后端限制，不以“没有诊断”为迁移条件，也不把可能错误的接缝画面当作不可更改的需求。实际检查了 1850 ms 的普通、停顿后多读音与 LEAD 画面。

Halo 测试验证一次绑定、稳定顺序、完整窗口、ruby 隐藏、两类时钟、静态/零时长、宽度不改变扫色、函数预算检查、异常来源，以及与旧 `WholeGlow` 相同输入的最终 ASS 事件等价。当前仍保留旧示例；完整缩放表达和目标选择接入后再迁移。

本阶段完整测试 **282 项通过**（新增 Halo 测试 11 项），相关 Ruff、Black 与 `git diff --check` 检查通过。

## 2026-11-11：缩放表达、显式时间与 layered glow 迁移

`self.syllables` 可按原单元遍历、索引或切片；`self.characters` 可按源码字形候选遍历、索引或切片，最终布局仍必须验证它们能独立绘制，不能通过分色或动画切开实际整形簇。空白可以被选择但不产生可见绘制目标。选择保存来源范围，不使用输出图层编号。

已接通以下实际可运行写法：

```python
self.syllables.on_singing(pulse=1.1)
self.characters[1].on_singing(scale=Transition(1, 1.2, rate=there_and_back))
self.syllables.on_singing(scale=lambda p: 1 + 0.2 * sin(pi * p))
self.syllables.animate(
    scale=Transition(1, 1.4),
    during=(singing.start - 100, singing.end + 300),
    keep=True,
)
self.syllables.on_singing(scale=Keyframes(
    Keyframe(0, 1), Keyframe(0.2, 1.3),
    Keyframe(0.65, 1.3), Keyframe(1, 1),
))
```

`singing.start/end` 取每个目标所属单元的演唱包络；`display.start/end` 取显示窗口。`during` 也可使用绝对整数毫秒。关键帧位置使用区间比例或这些时间引用，`Keyframe(..., rate=...)` 指定到下一帧的缓动；绑定后必须严格递增，首尾与绑定区间一致。固定毫秒造成短音节倒序时报告冲突时间，不自动重排。显式时间窗口裁剪不重启进度。

`pulse` 展开为普通 `Transition(1, peak, rate=there_and_back)`。线性 Transition、线性关键帧、线性往返（含不对称峰值和保持段）复用扩展后的 ScaleAnimation 与 ASS 几何编译，生成原生缩放/位移变换；任意 lambda、平滑缓动和带非线性段的关键帧走采样预算入口。没有通过执行用户函数来猜测其是否线性。

整单元缩放使用共同中心；逐字缩放使用各字中心。ruby 在 `follow="syllable"` 时使用同一缩放及中心，`follow="none"` 时不跟随；Halo 从所属完整目标继承一次缩放。采样缩放也通过同一几何编译器变换中心、字形、描边、模糊和扫色裁剪，避免父子重复缩放。区间外回到基础倍率；`keep=True` 保持实际终值，静态目标不调用属性函数，零时长变化只在 keep 时保留瞬时终值。

同一目标的缩放区间重叠会报告目标及绝对毫秒；keep 占用至显示结束，不能用后续声明静默覆盖。非重叠原生/采样缩放混合时统一在目标的采样求值器中计算，避免两次应用。当前显式合成策略、按实际演唱进度暂停、扫到触发仍待实现。

### 迁移结果

[layered_glow.py](../examples/layered_glow.py) 已使用 `Effect`、`Lyrics/Body/Ruby/Halo` 和领域行为，特效定义为 **33 行有效 Python**（不含空行、docstring、导入与 CLI/输入配置）。示例不再访问 `EffectPlan.layers`、`animation_id`、`origin.sources`、clips 或内部 component 字段。CLI 可直接载入文件导出的 `effect = LayeredGlow`。

```sh
python -m tools.capture_layered_glow /tmp/kara-layered-after \
  --compare docs/layered-glow-before.json
python -m kara_templater tests/fixtures/layered_glow.ass /tmp/layered-cli.ass \
  --effect examples/layered_glow.py
```

对照固定输入与字体，**13 帧逐像素一致**；728 个事件、535 个最终计划层均不变。K1、K2 与 LEAD 的预检样本数仍为 1800、1200、1200，原有硬裁剪提示保留。详细报告见 [layered-glow-after.json](layered-glow-after.json)，其中 comparison 记录零帧差异、零事件差异。CLI 的重复生成字节一致性也有自动回归。

新增缩放测试覆盖共同/各字中心、ruby 与 Halo 跟随、自定义函数延迟执行、预算拒绝、采样异常来源、提前/延后区间、区间外复位、不对称保持、短音节倒序、keep 冲突、静态和零时长目标，以及原生/采样混合。仍需验证更广泛的曲线与函数视觉误差、并行轨道交叉组合，并迁移 whole_glow、staggered_path；完整目标尚未完成。

本阶段完整测试 **306 项通过**；相关 Ruff 与 `git diff --check` 通过。零时长关键帧也按瞬时切换处理，保留最终值时不会被误判为分段时间倒序。

## 2026-11-11：通用属性、扫色到达触发与其他示例迁移

`behaviors.py` 现在统一解析缩放、水平/垂直位移和组透明度。Halo 的透明度也使用同一个声明、绑定、关键帧求值与冲突检测流程，已移除先前单独的 SingingMotion 实现。

实际入口：

```python
self.characters.on_highlight(
    duration_ms=400, threshold="enter", tracks="first",
    offset_x=lambda p: 8 * sin(2 * pi * p),
    offset_y=lambda p: -24 * sin(pi * p),
)
self.syllables.on_singing(opacity=lambda p: 1 - 0.2 * p)
self.syllables.on_singing(offset_x=Transition(0, 20), progress="singing")
self.query_one("halo").animate(
    opacity=Transition(0.2, 0.8),
    during=(singing.start - 200, singing.end + 200), keep=True,
)
```

`on_highlight` 使用已有 Pulse 到达规划，只在内部产生时钟，不向作者暴露输出 ID。支持 enter/center/complete 阈值、固定毫秒或 traversal 持续时间、first/each/named 轨道和重复演唱；命名轨道用 `track_id`，是否跨轮再次触发用 `retrigger`。阈值来自原始字形计时区域，不使用辉光宽度、padding 或已变换后的坐标。底层 Pulse 规划允许将冲突检查交给属性层，以便区分位移、透明度和缩放的冲突与显式合成。

默认 `progress="envelope"` 在演唱停顿中继续推进；`progress="singing"` 按累计实际演唱时长推进并在停顿保持。实际演唱进度目前绑定来源演唱区间，不能同时填写另一段任意 during。比例关键帧按此进度解释，时间引用关键帧也映射到累计演唱进度，避免在停顿中漂移。

不同属性可重叠；同属性默认 `compose="replace"` 要求区间互不重叠。显式模式：

- offset_x/offset_y 支持 `compose="add"`。
- scale/opacity 支持 `compose="multiply"`。
- 所有已实现属性支持 `compose="override"`，按声明顺序取最后一个活动规则；结束后恢复仍活动的其他规则。
- 重叠规则须选择同一种显式合成方式，不能混用默认覆盖与叠加来猜测意图；重叠缩放还要求相同中心。

组透明度与文字自身透明度、Halo 自身透明度独立相乘。原生缩放可同时搭配采样位移，采样只平移其中心，不再次缩放。位移与透明度目前仍通过采样输出，原生优化属于剩余任务。

`self.text.sweep()` 已支持显式 tracks、track_styles 和 overlap；tracks 可以是既有轨道元组，或布局完成后接收 LaidOutLine 的工厂函数。轨道工厂在构建阶段运行，属性函数仍等采样预算检查后才执行。自定义轨道拥有自己的进度曲线，不再同时给 sweep 设置另一条曲线。

### 示例和验证

- [whole_glow.py](../examples/whole_glow.py) 已改为 Body + Halo + on_singing，不再去重图层或反查来源。
- [staggered_path.py](../examples/staggered_path.py) 已改为 characters.on_highlight 的两条位移函数，不再建立 ID 到时间的字典。
- [parallel_tracks.py](../examples/parallel_tracks.py) 使用同一 Effect 生命周期、代码范围配色和轨道工厂，展示分区、优先级及透明叠层。

迁移前后的固定场景对照：whole_glow 仍为 210 个事件，staggered_path 仍为 166 个事件；按时间、层级、样式和内容归一化后的全部事件哈希一致，**18 个关键帧逐像素一致**。并行扫色的全部 266 个事件也保持一致。已查看逐字路径的中段画面和整体辉光的演唱中画面。layered_glow 的 13 帧对照同时再次通过。

报告：[迁移前](composed-examples-before.json)、[迁移后](composed-examples-after.json)、[并行扫色事件基线](parallel-effect-system-baseline.json)。可重跑：

```sh
python -m tools.capture_composed_examples /tmp/kara-composed-after \
  --compare docs/composed-examples-before.json
python -m tools.capture_layered_glow /tmp/kara-layered-after \
  --compare docs/layered-glow-before.json
```

新增测试覆盖同目标多属性、实际进度停顿、静态文字的显示窗口绑定、显式合成、来源诊断、命名轨道阈值、并行与重复到达、窗口截断，以及 Halo 与组透明度的相乘。完整测试 **323 项通过**，相关 Ruff 和 `git diff --check` 通过。

后续仍需补齐 segment/ruby 等来源目标查询、跟随配置、随扫色裁剪装饰、原生属性输出优化、更多组合视觉误差验证，以及默认文档和旧作者入口的整理。当前迁移成功不等于全部计划已完成。

## 独立跟随、装饰窗口与扫色裁剪

`Follow` 已导出，支持分别控制位移、缩放、动画透明度及淡入淡出的跟随。示例：

```python
yield Lyrics(
    Body(),
    Ruby(follow=Follow(scale=False, fade=False)),
    Halo(
        color=RED,
        clip="sung",
        follow=Follow(position=True, scale=True, opacity=False, fade=True),
        window=(display.start, display.end + 300),
    ),
)
```

`position` 控制 offset_x/offset_y 位移；缩放围绕其中心产生的几何位移仍由 `scale` 控制。Ruby 保留 `"none"`/`"syllable"` 快捷配置，传入 Follow 时按属性过滤跟随规则；隐藏 ruby 仍连带隐藏其装饰。这里的 opacity 开关控制动画属性传播，不改变静态样式的层叠规则。

Halo 默认为整目标辉光（`clip="none"`），`clip="sung"` 则把同一装饰颜色裁剪到已唱覆盖区域。重叠轨道取覆盖并集，不重复增加辉光亮度。裁剪沿用共享遮罩编译器，在未拆分的来源目标上生成，不修改已生成图层；唱前遮罩的基础透明度保持为零，自身透明度动画不能让未唱区域显形。

自定义 window 只改变装饰的输出窗口。演唱时钟仍来自歌词；跟随淡入淡出时也保留原显示窗口的淡入淡出时钟。修复了扩展窗口遗漏原淡入起点、淡出终点的问题，避免把原来的短淡入拉长到扩展窗口。关闭 fade 跟随时，装饰可在扩展区间内持续显示。扩展窗口重新检查被跟随动画的冲突，最终所有装饰合计仍受图层预算约束；预算失败前不执行用户属性函数。

验证：完整测试 **331 项通过**，其中新增 8 项覆盖独立跟随、Ruby、覆盖并集、透明度隔离、扩展窗口时钟与冲突、预算。layered_glow 的 13 帧及 whole_glow/staggered_path 的 18 帧仍逐像素匹配迁移前基线。

新增独立像素验证工具：

```sh
python -m tools.validate_halo_clip /tmp/halo-clip-review
```

固定 DejaVu 字体，分别渲染无辉光、整目标辉光和已唱裁剪辉光。6 个采样时刻中，起唱前与无辉光画面完全一致，唱后与整目标辉光完全一致；扫色中已唱侧匹配完整辉光，未唱侧匹配无辉光。仅排除裁剪线左右各 2 像素，以容纳原生整数裁剪和 YUV420 色度重建边缘；未宣称边缘逐像素相等。已查看扫色中画面，报告见 [halo-clip-validation.json](halo-clip-validation.json)。

边界仍为 ASS 的硬裁剪：扫色前沿从字形计时框起点出发，在起唱瞬间，前沿左侧的模糊外溢可见；结束时解除裁剪。该行为与既有遮罩后端一致，不表示在模糊前裁剪字形。多字、多层、并行轨道加缩放的完整组合视觉验收仍待完成，来源查询、原生属性优化及默认文档整理也仍属后续任务。

## 扫色快捷颜色统一进入样式覆盖

修复 `sweep(fill=..., stroke=...)` 的独立颜色缓存：此前 build 阶段把缓存再次覆盖到样式解析结果上，使调用后对 `.style.sung` 的修改或 `UNSET` 失效。现在快捷参数直接写入 Body 和 Ruby 的 `.style.sung`，保留统一的颜色校验，后续直接赋值、移除覆盖及 `INHERIT` 均走同一层叠路径。无颜色参数的 sweep 不改样式，范围分色仍保持原有语义。

新增 5 个回归用例检查先后赋值、正文与 ruby 独立覆盖、UNSET 恢复样式表与 ruby 继承、INHERIT，以及 sweep 本身传 UNSET；断言最终 ASS 事件而非只检查声明对象。单 segment 带 ruby 的输入使唱后事件可直接逐项比较；多 segment 场景中的裁剪片段可能保留未覆盖区域的唱前 paint，不能把每个事件的 paint 都当作完整字形最终配色。

原有 layered_glow、whole_glow、staggered_path 的 31 个关键帧及事件基线再次通过。完整样式功能仍需继续审计，尤其是装饰状态样式及来源查询，不据此勾选整个 P2 样式任务。

本阶段完整测试 **336 项通过**，三色示例四种输入/覆盖写法的 6 帧比较再次通过，布局与时间未变；相关 Ruff 与 `git diff --check` 通过。

## 来源集合与逐段行为

补齐 `self.segments`、`self.syllables[i].segments` 和 `.characters`；无需通过 `self.source.source.units` 读取普通正文，三色示例已使用 `self.syllables.text`。集合可以切片、倒序和迭代，并提供原始 `source_refs`、`intervals`，segment 集合还提供 `readings`。同文单元和同音读音保持不同地址，地址可通过既有 SourceRef.resolve 回到原对象；不会根据文本或时间去重。

逐段行为仍进入共享 MotionRule / BoundProperty 求值流程。对多个 segment 调用 on_singing 会分别绑定各段，而不是合并成包络。选择第二读音可以仅在该段驱动所属正文单元，ruby 及其辉光按来源地址匹配跟随；缩放仍使用正文单元共同中心。显式相对时间、keep、原生缩放、采样位移和属性冲突检查复用原有实现。段内时间错误的诊断精确指向所选 segment。

静态、空文本与零时长来源保留明确区别：静态单元没有段，空文本没有字符候选，但可有时间段；零时长段仍可读取和选择。空选择不添加行为，但仍校验参数。字符只提供布局前的保守候选，实际字形边界仍由布局校验；不尝试在配置阶段推断某个 segment 覆盖哪些字符。

新增 9 项测试覆盖来源地址、重复正文、顺序和切片、空与静态来源、分段时钟与停顿、ruby/辉光传播、共同中心、与单元行为的冲突、错误定位和实例隔离。完整测试 **345 项通过**；layered_glow 的 13 帧仍与迁移前基线逐像素一致。

P1 尚未全部完成：来源 CSS 查询、独立 ruby 目标配置与更完整的分组契约仍需补齐，因此保留相关未完成项。

## 独立 ruby 行为

新增 `self.rubies`、`self.syllables[i].rubies`、`self.segments[i].rubies`，支持既有索引、切片和来源元数据。集合只包含非空读音，文本为读音本身，来源地址仍是原 segment；`.segments` 可返回所属演唱段。`self.ruby` 仍是声明组件，没有改变已有样式、隐藏及 Follow 配置的含义。

读音可直接调用 on_singing/animate，沿用共享属性模型。独立缩放绕读音自己的中心（包含 ruby 的布局偏移），时间来自对应 segment；独立位移不影响正文和其他读音。对应 Halo 按自己的 Follow 设置继承动画。ruby 的正文跟随开关只过滤继承行为，不影响自身行为；自身与跟随行为共同参与属性冲突检测及显式合成。隐藏读音或不声明 Ruby 组件时，不生成其视觉目标，也不运行它的属性函数。

新增 6 项测试覆盖选择映射、空读音过滤、自身中心与时间、正文及兄弟目标隔离、辉光传播、默认关闭跟随时的自身动画、冲突与显式相加、隐藏后的函数隔离。完整测试 **351 项通过**；三个迁移示例的 **31 个关键帧**及事件基线保持一致，相关 Ruff 与 `git diff --check` 通过。

独立行为已接通；来源选择器与逐目标样式仍未完成，不提前勾选整体来源查询任务。

## 来源目标样式

已接通歌词单元、字符候选及 ruby 集合的 `.style`、`.style.sung` 和 `.add_class()`。正文目标复用既有 TextRange 样式节点，ruby 使用原单元/segment 地址保存声明；索引、切片及派生集合保持同一节点身份。集合样式通过广播写入原节点，不另设隐藏覆盖层。读属性返回共同的显式声明，异值时报错，空集合读取 UNSET 且仍校验写入值。

同时修复来源子目标重新套用通用规则的问题：组件已解析的规则不在目标层重复应用，以免读取 `.style` 或移除目标覆盖时反而丢失组件的显式颜色。新增目标类/属性/后代规则仍参与层叠。重叠正文范围保留原语义：类标记合并，显式覆盖优先；范围更窄并不自动增加 CSS 优先级。segment 作为时间目标不接受静态样式，作者应选择正文或该段 rubies。

7 项新增测试覆盖类标记与直接覆盖、正文/ruby 独立配色、属性广播与读取、UNSET/INHERIT、空集合校验、访问样式不改变外观，以及逐目标字号能力诊断。完整测试 **358 项通过**；三项迁移示例的 **31 帧**及事件基线一致，三色示例仍通过各输入入口的关键帧比较。

来源选择器和多层组合的完整验收仍待继续，未将 P1/P2 整体标为完成。

## 来源集合查询

集合现在支持 `.query()` / `.query_one()`，共用现有选择器解析器，返回仍可配置样式与行为的同类来源集合。支持类型、属性等值、局部 ID、类标记与后代关系；可按正文筛选字符，或按单元/演唱段层级筛选读音。查询只读来源与已有类标记，不创建样式范围，也不会因为查看字符候选而提前触发布局边界校验。查询保持集合当前顺序；同文、同音和同时刻来源不会合并。

组件查询入口不变，来源查询限定在明确的集合上，避免 `query("ruby")` 的含义混杂。来源类型选择器不自动成为新的视觉样式层；先查询并添加类标记，再由既有 StyleSheet 解析外观。segment 仍是时间目标，类标记来自祖先单元，不能直接设置静态样式。

三色示例已改为查询“星”“月”“风”字符后添加 red/green/blue 类，输入仍是单 segment 的普通 ASS 或 Document。解析/直接构造/显式 items 的画面，以及直接范围覆盖参考，6 个关键帧完全一致，布局与时间不变。

新增 7 项测试覆盖重复文本与来源身份、后代选择、读音时间属性、局部 ID、只读性、匹配数量错误、切片顺序、筛选后的行为与样式、实例隔离和两种 Document 入口。修复缺失属性意外匹配字符串 None，以及空单元在相邻范围边界继承类标记的问题。完整测试 **365 项通过**；原三项特效示例 **31 帧**与事件基线仍一致。P1 的选择器条目已勾选，其余身份/分组、完整边界和组合验收继续保留待办。

## 默认文档与颜色参考

README 的首个完整效果和 CLI 脚本示例已切换为 Effect.compose/configure，修正 ArcWave 仍被描述为 build + DynamicEffect 的过时说明。旧配方、底层时序与来源追踪文档保留在明确的底层接口章节，旧后端审计不再被当作整个新作者层的交付证明。

新增 [effects.md](effects.md)，覆盖当前可用的声明周期、两种 Document 与显式 items、代码分色、样式层叠、来源查询、默认时间、曲线/函数/关键帧、冲突合成、ruby/Halo 独立行为与跟随、采样与 ASS 边界。明确标注尚未接通的 Halo 状态颜色、原生属性优化和旧作者实现整理，未以文档替代这些实现任务。

指南列出全部 12 个内置 Color 的准确 RGB 值。layered_glow 用 BASE_GLOW、SUNG_GLOW、SUNG_FILL 为原精确颜色命名，同时保留 WHITE/BLACK 常量；没有用近似内置颜色替换原配色。

验证：实际执行 README 入门效果和指南的 Glow/Alternating 类，验证直接构造与 parse 后 Document 都能渲染；逐项比较颜色表与代码常量。layered_glow 仍为 728 个事件、535 个图层，13 帧匹配迁移前基线。完整测试 **365 项通过**；相关 Ruff 与 `git diff --check` 通过。P5 文档及颜色表两项已勾选，核心实现和完整交付审计继续推进。

## Halo 唱后状态外观

修复 Halo 忽略 `:sung` 及 `.style.sung` 的缺口：分别解析唱前/唱后颜色与透明度，在来源目标上复用共享覆盖编译。相同状态保持原有完整无裁剪 Halo；不同状态保留两侧装饰并按扫色分区。clip="sung" 继续将唱前 paint 置为完全透明，避免 opacity 动画暴露未唱区域。重叠轨道仍取覆盖并集，不叠加相同装饰。

opacity 动画活动期间显式覆盖两侧状态值；区间外没有活动规则时保留每个状态自己的透明度，修复若统一回退到唱前透明度会覆盖唱后样式的问题。keep=True 保持动画终值。仅有演唱时间而无 sweep 覆盖时，Halo 保持唱前外观，不将状态解释为整对象瞬时变色。正文输出保持不变。

新增 9 项测试覆盖空间颜色/透明度、稳定动画身份、唱前隐藏、层叠与 UNSET、相同状态快速路径、动态透明度恢复及 keep、重叠轨道、无 sweep 和正文隔离。完整测试 **374 项通过**；三个原有示例的 **31 帧**及事件基线不变。

像素验证可执行 `python -m tools.validate_halo_clip /tmp/halo-state-review --states`：独立渲染红色完整辉光、蓝色完整辉光及红转蓝状态辉光，比较 6 个时刻。唱前/唱后完整画面精确匹配，中途两侧分别匹配各自参考，仅排除裁剪线左右各 2 像素。已查看中段图像；报告见 [halo-state-validation.json](halo-state-validation.json)。这仍是硬裁剪后的颜色分区，不宣称模糊融合无缝。特效指南已同步移除该能力未实现的旧说明。

## 原生透明度后端

新增底层 OpacityAnimation 与 TextLayer.opacity_animations，支持已知分段线性点、保持段、结束恢复、keep、零时长终值，以及 group 乘到绘制层、glow 覆盖辉光自身透明度两种语义。辉光基础透明度为零也能正确变亮，不使用除以基础值的换算。

透明度使用自己的原始节点和淡入淡出边界，裁剪细分与采样位移暴露窗口不会重新量化透明度端点。保留起点右极限、终点左极限，避免动画之外出现提前变色或恢复段变成反向淡出。分段节点在 ASS 时间网格上坍缩时报告能力错误；同通道重叠行为明确拒绝。来源元数据与最终事件预算贯穿输出。

组透明度、辉光透明度和 fade 的乘积可能不是线性的。后端检查每个原始区间内的乘积，拒绝不能准确使用线性 ASS 变换表达的组合，不偷偷把二次/三次曲线改成直线。此时错误明确要求采样。作者层的自动路径选择和回退尚未接入，所以 P3 原生属性输出条目仍未完成；当前普通作者行为保持已有输出。

11 项新增测试覆盖关键帧保持、边界跳变、辉光与正文隔离、零基础透明度、clip/采样窗口原时钟、fade 合成、非线性拒绝、时间精度、来源与预算，以及实际采样位移组合。完整测试 **385 项通过**；原有三项示例 **31 帧**和事件基线保持一致，相关 Ruff 与 `git diff --check` 通过。

新增 `python -m tools.validate_native_opacity /tmp/native-opacity-review`，用独立计算的静态透明度参考检查 7 帧：端点及区间外完全一致，中途最大 RGB 通道误差为 2/255，低于预设 3/255 容差（原生插值整数 alpha 与静态单次舍入的差异）。原生示例使用 3 个事件；7 个参考事件只用于离散取样对照，不作为性能基线。报告见 [native-opacity-validation.json](native-opacity-validation.json)。下一步将该后端接到已有作者属性描述，保留任意函数及非线性组合的采样路径。

## 作者层自动选择原生透明度

已将 OpacityAnimation 接到现有 BoundProperty。按稳定 animation_id 收集正文、ruby 与 Halo 的所有输出区域，检查已知分段曲线、fade 和组/辉光透明度乘积，统一决定该目标的输出路径。没有执行用户函数，也没有通过解析 lambda 来猜测线性关系。原生通道从采样属性集合中移除，避免重复施加；仍需采样的位移等属性与原生透明度共存。

未知函数、显式多规则合成、时间量化后坍缩的分段，以及同时变化的组/辉光/fade 造成的非线性乘积，保留原有采样。不同目标可以选择不同路径，例如正文原生、辉光采样。此处只实现透明度自动选择，位移原生输出仍未完成。

新增 6 项作者层测试覆盖原生无回调、函数预检、fade 回退、非线性乘积按目标回退、过短时间段及采样位移/原生缩放组合。已有语义测试改为检查原生与采样合成后的属性；原采样 WholeGlow 的固定事件哈希通过显式 lambda 路径继续保留验证，不用新实现自己生成的哈希替代旧证据。完整测试 **391 项通过**，相关 Ruff 与 `git diff --check` 通过。

实际输出变化：layered_glow 从 **728 事件/535 图层降至 389 事件/180 图层**；whole_glow 从 **210 事件降至 49 事件/35 图层**；staggered_path 仍为 166 事件。旧迁移基线保留，新原生基线分别保存为 [layered-glow-native.json](layered-glow-native.json) 和 [composed-examples-native.json](composed-examples-native.json)。CLI 重跑所有权测试仍通过。

原生 alpha 连续变化，旧路径每 40 ms 保持一次，不再要求二者所有中间帧逐像素相同。31 帧比较中，layered_glow 最大通道差为 5/255，whole_glow 为 4/255，staggered_path 全部一致；比较容差设为 8/255，覆盖本例 0.6/s 斜率下一个 40 ms 桶的约 6.12/255 差异及舍入。报告见 [opacity-migration-validation.json](opacity-migration-validation.json)。独立静态参考工具再次通过，仍为端点完全一致、中间最大 2/255；已查看 whole_glow 中段画面。

可重复验证新的原生基线：

```sh
python -m tools.capture_layered_glow /tmp/kara-layered-native --compare docs/layered-glow-native.json
python -m tools.capture_composed_examples /tmp/kara-composed-native --compare docs/composed-examples-native.json
```

## 双层辉光、并行轨道与缩放组合验收

新增 [composed_glow.py](../examples/composed_glow.py) 固定组合场景及 `tools.validate_composed_glow`。五组配置覆盖整组缩放且 ruby 跟随、整组缩放但 ruby 不跟随、整组加已唱裁剪辉光、逐字缩放加独立 ruby 缩放，以及逐字缩放加已唱裁剪辉光。每组都包含两个 Halo、主/回声并行扫色及辉光透明度变化。每组分别使用原生往返 Transition、等价 Keyframes 和直接函数，后者显式采用 10 ms 采样。

共渲染 **15 个变体 × 8 个时刻**。原生曲线与关键帧的画面完全一致，单元测试同时确认最终 ASS 一致。函数采样的起唱前、起唱点、结束点及唱后画面完全一致；中间帧在扫色分界处可能存在明显的局部颜色差异，未经容差处理的单通道差最高达 229/255，不能称为全画面近乎逐像素相同。

最初的邻域像素比较失败后，对输出事件和像素逐项定位，确认不是字形丢失：差异出现在白色未唱条带与青色已唱区域的分界。根据独立的源轨道进度、字形中心和缩放公式，解析实际 ASS 的 clip/transform 求出分界坐标，最大误差 **0.538 px**，低于预先采用的 **0.75 px**（0.25 px 曲线近似 + 0.5 px 端点取整）预算。像素比较排除这些独立计算的分界左右各 2 px，以包含整数裁剪和 YUV420 色度重建；其余位置采用 1 px 几何邻域和 3/255 通道容差，五组全部通过，实际邻域残差为零。这是有明确排除区域的几何验收，不掩盖边界处高对比差异。

新增 11 项测试验证原生/关键帧相同输出、并行扫色分界坐标、来源/轨道身份、显示窗口、各目标存在性与唱后颜色，以及逐字缩放不能隐式驱动整音节 ruby 跟随。完整测试 **402 项通过**。报告保存为 [composed-glow-validation.json](composed-glow-validation.json)，包含每个变体的事件数、画面哈希、诊断、坐标误差及每帧排除带。已查看组合的中段原生与函数画面，并放大检查边界差异。

P4 的交叉组合验收已勾选；这不替代尚未完成的原生位移、其余契约审计与旧作者实现整理。

## 原生位移与显式位移合成

横纵位移已接入作者层自动输出选择。已知线性/分段曲线生成 OffsetAnimation，并按原始曲线时钟输出 `\move`。位移在缩放之后施加；文字位置和水平扫色裁剪各平移一次，缩放中心不随原生位移重复移动。纵向位移不重新锚定水平扫色时钟。横纵轴分别决定原生或采样路径，可与采样缩放共存；ruby 和 Halo 使用既有跟随配置。

显式 add/override 的已知位移也已支持原生输出：在规则激活、结束和曲线节点处分段，按声明顺序选择活动规则，再合并线性端点。保留跳变、恢复底层规则、keep 终值及零时长保持行为。未知函数不在规划阶段执行；无法保持时间节点的量化情况回退采样。缩放和透明度的显式组合优化仍待完成，P3 总项保持未勾选。

`tests/test_native_offsets.py` 的 12 项测试覆盖横纵独立时钟、缩放/裁剪几何、采样曝光窗口、量化诊断、作者层自动输出、混合原生与采样轴、短时间回退，以及新增的 add/override 边界、未知函数预检和采样缩放组合。完整测试 **416 项通过**；相关 Black、Ruff 检查通过。

执行 `python -m tools.validate_composed_glow /tmp/composed-offset-review --offsets`，五组场景 × 四种写法 × 八个时刻，共验证 **160 帧**。原生与关键帧、两条位移相加的画面完全一致；等价函数端点完全一致。函数中段扫色坐标最大误差 **0.538 px**，低于 0.75 px 预算；排除独立计算的分界左右各 2 px 后，1 px 邻域像素残差为零。原始整帧单通道差最高 231/255，集中在裁剪边界，不宣称函数与原生整帧逐像素等价。报告见 [composed-offset-validation.json](composed-offset-validation.json)。

重新对照现有原生示例基线：layered_glow 保持 389 事件/180 图层、13 帧一致；whole_glow 保持 49 事件/35 图层，staggered_path 保持 166 事件，事件哈希与基线一致。特效指南和计划已更新原生位移能力，完整接口审计和旧作者实现移除仍未完成。

## 缩放与透明度的已知曲线合成

将位移曲线分段逻辑提取为共用的 `native_motions`，接入缩放、组透明度和 Halo 自身透明度。已知 override 在覆盖结束后恢复底层曲线的当前值，不重启时钟；multiply 在每段至多一个因子变化时生成原生曲线。多个变化因子相乘产生高次曲线时继续采样；透明度的常量零因子可将整个乘积化为零。整个判定只读取已知端点，不执行用户函数。与 fade 或其他透明度通道合成后仍由原有能力检查决定是否回退。

同时修复已知缩放节点在厘秒量化下坍缩时的路径选择：作者层提前回退采样，不再将不可表达的节点交给 ASS 编译器。新增 8 项测试覆盖缩放/透明度的线性乘积、非线性回退、覆盖恢复、终值保持、透明度零因子和短区间缩放。测试辅助读取器现在同时读取原生缩放与采样缩放，避免将原生输出误认为属性未生效。完整测试 **424 项通过**，相关 Black、Ruff 检查通过。

组合视觉工具新增 product 变体：缩放曲线乘 0.5、Halo 透明度曲线乘 0.8，得到与原生基线相同的表达式。五组场景 × 五种写法 × 八帧，共 **200 帧**通过验证；product 和 additive 均与原生逐像素一致，事件数也一致。函数变体继续执行既定裁剪坐标和像素容差检查。报告保存为 [composed-product-validation.json](composed-product-validation.json)。三项迁移示例的现有原生基线再次通过。

P3 仍需审计演唱进度映射及完整后端能力契约；P0/P1/P2 的契约收口和 P5 的旧实现移除仍未完成。

## P1 来源选择与目标追踪验收

完成 P1 剩余三项验收，证据范围如下：

| 要求 | 当前实现与验证 |
| --- | --- |
| 行、单元、段、字符、读音选择 | 每行绑定的 self.source 保留原 KaraokeItem；TargetSelection 支持遍历、切片、查询及来源地址。test_effect_selection.py 和 test_effect_queries.py 验证顺序、重复文本、时间、只读查询、空集合、跨实例隔离和段/读音独立行为。 |
| 字形可绘制性 | layout_characters 保留实际字体整形，select_characters 验证完整字形簇。既有 test_characters.py 覆盖连字、组合符号、缺字和不支持的整形；新增来源边界测试验证动画选择也遵循该限制。 |
| 稳定身份与展开追踪 | VisualTarget 保存来源、正文组区域和读音依附；动画身份贯穿 Halo、扫色及采样。新增集成测试把含多段正文、ruby_continuation 和两层 Halo 的输出实际采样及编译，逐层检查身份与来源映射，逐事件检查来源集合，并将每个引用解析回原 Segment 对象。 |
| 空文本、静态正文、多段及 ruby 组 | 新增测试检查空行、空静态单元、空演唱单元不输出装饰或执行回调；静态正文保留字符及单元来源，无演唱动画；ruby 排版组保留逐段读音选择。空正文附带读音明确报告带来源地址的零宽映射错误。 |

验收发现并修复字符动画的静默丢失：来源候选 `f` 与实际 `ffi` 连字的范围不相等，旧代码因此跳过规则。现在在行为解析前合并同一规则的相邻来源范围，用实际整形结果校验边界，再绑定到实际字形簇。选择完整连字可动画，切开连字则抛出 LayoutCapabilityError 并携带 SourceRef；倒序选择也保持同样的覆盖语义。不同声明之间不合并，不能以此绕过各自的字形边界约束。

另将零宽正文附带读音的检查提前到颜色继承之前，避免将无正文可映射误报为分色歧义。新增 `tests/test_effect_source_edges.py` 共 9 项测试，完整测试 **433 项通过**；相关 Ruff、Black 与 `git diff --check` 通过。特效指南补充这些边界，计划 P1 全部勾选；P0、P2、P3 和 P5 仍按各自要求继续审计及实现。

## P0/P2 契约收口

逐项核对生命周期、样式解析、时间绑定、冲突检测和变换传播的当前实现及已有测试，新增 [交付审计](effect-system-audit.md) 保存要求与证据映射。新增 `test_effect_lifecycle.py` 的 9 项测试：实际渲染两行，记录来源绑定后的 compose/configure/layout 顺序，核对字号在测量前生效、声明查询顺序和实例隔离；七种非法声明树均在 configure 前拒绝；默认 ruby/Halo 跟随及外观有明确断言。

指南现明确 Ruby 默认关闭 position/scale/opacity 跟随，但保留整行 fade；Follow 构造器各开关默认开启，Halo 跟随其直接附着目标。并补充组件声明顺序和 Halo 叠放关系。P0 和 P2 剩余条目已有对应实现、行为测试或组合视觉证据，均已勾选；本轮没有改写视觉基线。

完整测试 **442 项通过**；新增测试 Ruff、Black 与 `git diff --check` 通过。整体任务仍未完成，后续集中在 P3 演唱进度及后端能力审计、P5 旧预设/特效定义方式整理及最终交付复验。

## 实际演唱进度的原生映射

已知线性曲线和关键帧不再因为 progress="singing" 一律采样。新增 singing_points 将累计演唱进度映射到原段时间，补入每段起止和段内曲线节点；停顿两端保持同值，零时长段不贡献进度。映射点继续经过已有厘秒能力检查，并复用缩放、位移和透明度的原生合成。未知函数不执行或推断，零总演唱时长保持采样。

核对输入契约确认 singing 进度仅允许绑定完整来源演唱区间，不能与自定义 during 偏移并用；指南补充这一限制。新增 11 项测试，将四种属性的线性/分段写法与独立进度计算和函数路径对照，覆盖停顿、段内转折、keep、绝对关键帧及零时长回退。既有 Halo 透明度测试改为同时接受原生图层窗口和采样曝光窗口，仍检查组合后的实际透明度。

完整测试 **453 项通过**，相关 Ruff、Black 检查通过。P3 剩余工作为预算、来源诊断与后端精度的综合核对；P5 迁移整理仍未完成。

## P3 预算、诊断与精度验收

已核对 render.py 的完整调用顺序：所有歌词完成来源绑定、布局和输出计划后，先编译静态部分，再为全部动态组建立 SamplingPlan，全部预检通过才调用 on_estimate 和属性函数。估算不是事件数上界，原生裁剪细分和状态合并会改变最终数量，编译器继续执行实际上限；指南补充这一契约。

新增 test_effect_render_contract.py 的 5 项集成测试，从新 Effect 入口验证第二行超预算不会先执行第一行函数、样本数量预算、估算阶段取消不修改输入、函数异常保留 cause/来源/目标/绝对时间，以及严格裁剪误差无法满足时的来源诊断。完整测试 **458 项通过**；相关 Ruff、Black 和 git diff --check 通过。

重新运行 200 帧组合矩阵和 7 帧独立透明度参考，报告与已保存 JSON 完全一致，无需重写基线。交付审计新增 P3 的实现、测试及渲染证据映射，计划 P3 三项剩余任务已勾选。整体目标尚未完成，余下为 P5 的旧预设/特效定义方式整理及迁移后的最终复验。

## P5：CLI 内置预设迁移

CLI 的无脚本入口改为普通 Effect 组合：Body/Ruby 声明、sweep/fade 和三种强调行为均走新特效编写方式，不再构造 KaraokeEffect。为保持命令行已有行为，预设显式设置 ruby 的正文描边宽度和透明度；新 Ruby 的通用默认值不变。仅传 --before 时仍保留来源唱后色，新增回归测试覆盖这一点。

迁移前后分别运行 karaoke.ass、multi_reading.ass 与 none/char/chars/syllable 四种模式，共八组；同时配置前后色和淡入淡出。所有生成事件序列完全相同，报告 [cli-migration.json](cli-migration.json) 保存事件数与迁移前后 SHA-256。CLI 脚本测试也已改用新 Effect 类，继续验证错误不写半成品、估算先于函数执行、颜色与 owner 重跑行为。

迁移检查还发现正文事件来源的 effect 字段仍使用内部 KaraokeEffect 名称，现由作者层传入实际 Effect 类名。Glow 和正文因此都指向真实作者效果；原先用旧名称区分视觉通道的测试已改为检查通道身份，跨效果类的视觉比较仅归一化 effect 名称，保留来源地址和轨道信息断言。完整测试 **459 项通过**，相关 Ruff、Black 与 git diff --check 通过。

P5 尚未完成：旧作者类仍被编译流程、部分示例和验证工具使用，需要继续抽出内部编译职责，迁移其余调用后删除公开作者入口，不能以 CLI 迁移代替整项完成。

## P5：歌曲脚本预设迁移

examples/song_effect.py 已改为 SongEffect，导出 effect = SongEffect。正文与 ruby 外观、已唱区域 Halo、两阶段扫色、边缘补偿、整音节 pulse 及淡入淡出均通过 compose/configure 表达，无旧作者对象或输出层操作。

迁移前先保存固定 scene 的 ASS，再用同一 DejaVuSans 字体和 ffmpeg 单滤镜线程渲染 500、900、1000、1200、1400、1600、1800、2000、2200、2800 ms 十帧。迁移后十帧均逐像素一致；事件数由 294 变为 392，计划图层由 70 变为 140，原因是辉光由原 Paint 的视觉通道改为独立 Halo 目标。此处以明确的独立装饰语义换取更多事件，不把它报告为性能优化。报告 [song-effect-migration.json](song-effect-migration.json) 保存字体、前后事件哈希与逐帧证据。

新增 CLI 集成测试确认脚本导出新 Effect 类，实际渲染及同 owner 重跑字节一致。完整测试 **460 项通过**，相关 Ruff、Black 和 git diff --check 通过。

剩余调用已分为三类：effect.py 对 prepare/compile 的内部编译依赖；examples/recipes.py 和其余工具的旧配置对象；dynamic_effect.py 及部分后端测试的 SampleContext/noise/动态模糊扩展。后续迁移必须保留这些明确用途，尤其不能把带上下文和模糊上界的扩展简单替换成只接受进度的 lambda；普通预设迁移后再删除旧作者类。

## P5：特效系统与旧作者对象解耦

将目标准备和遮罩编译提取到内部 `_compiler.py` 的两个函数。参数明确传入扫色、外观、轨道、窗口、来源名称和模糊上界；它们不持有作者实例，也不决定作者应如何组织效果。Effect.build 的正文与 Halo 编译直接调用这两个函数，effect.py 已无 KaraokeEffect 引用或实例化。旧类的 prepare/compile 方法已移除，尚待迁移的 build 调用复用同一个内部编译后端，不保留第二份遮罩实现。

重构中测试捕获到提取函数后的 fade 参数遮蔽，已将目标淡入淡出与默认淡入淡出分开。修复后完整测试 **460 项通过**。随后新增解耦回归测试：将旧 KaraokeEffect 构造器替换为必失败函数，正文、ruby、裁剪 Halo、缩放、位移和 fade 仍可通过新 Effect 构建并编译；生命周期测试共 **10 项通过**。相关 Ruff、Black 与 git diff --check 通过。

三项主要示例重新对照现有原生基线：layered_glow 保持 389 事件/180 图层及 13 帧一致，whole_glow 保持 49 事件/35 图层，staggered_path 保持 166 事件；后两者事件哈希与关键帧基线一致。普通特效入口已不依赖旧作者对象，但旧类的公开导出和其他调用仍在，P5 删除任务保持未完成。

## P5：补齐带上下文的属性入口

迁移动态示例时，逐项核对原计划“需要目标及时间上下文时通过显式进阶入口提供”，发现只有底层 SampleContext，新作者属性尚缺对应入口。现增加 Contextual(function, seed=0)，接入现有属性声明、时间绑定、冲突检测和采样路径，普通函数仍接收归一化进度。

PropertyContext 提供绝对 time_ms、progress、interval、window 和只读 PropertyTarget；目标携带文本、种类与原始 SourceRef，脚本无需反查输出层。noise 使用显式种子和原目标身份，跟随的装饰使用原属性绑定的目标，避免拆分或新增装饰改变相位。keep 期间上下文的时间和进度冻结在绑定终点；singing 进度只改变 progress，不将绝对时间改成虚拟时间。Halo 自身属性也支持 Contextual。

新增 5 项测试，覆盖无提前执行、预算拒绝、停顿中的时间/进度、终值保持、来源和只读目标、跟随噪声一致、重复输出、Halo 自身上下文与非法结果诊断、输入校验。完整测试 **466 项通过**，相关 Ruff、Black 检查通过。指南已给出显示窗口内的确定性波动示例。动态模糊及其上界的作者入口仍需迁移，旧动态示例尚未替换，P5 保持未完成。

## P5：动态模糊与动态示例迁移

Halo.on_singing/animate 新增 blur 属性，支持普通表达式及 Contextual，使用统一绑定、冲突及采样规则。构造器要求动态模糊显式声明 max_blur，上界覆盖基础值；有裁剪的装饰在执行函数前按上界预留空间。每个目标分别校验自己的上界，不能借其他 Halo 的较大上界放行。原生透明度降低过程只消费 opacity 规则，保留 blur 规则继续采样，避免组合时丢失模糊动画。

新增 noise(scope="source")，独立 Halo 属性可与其所依附正文/读音共享确定性相位。默认 target 作用域仍保持装饰独立。examples/dynamic_effect.py 已改用 DynamicGlow、Contextual 和 Halo(max_blur=18)，在显示窗口内分别配置文字位移与模糊，不再构造旧 KaraokeEffect 或修改输出计划。

迁移前后使用固定 scene、DejaVuSans 和单滤镜线程，十个时刻逐像素相同；输出事件从 **1232 降至 1057**，计划图层从 **616 增至 1057**，原因是原双视觉通道输出改为各自单通道的正文/Halo 目标。报告 [dynamic-effect-migration.json](dynamic-effect-migration.json) 保存字体、事件与帧哈希。CLI 实际运行并同 owner 重跑字节一致。

新增六项模糊测试、一项独立属性噪声共享测试及一项 CLI 测试，覆盖模糊与原生透明度共存、终值/恢复、各 Halo 独立上界、Contextual 预算前不求值、裁剪空间预留、无效参数及稳定输出。完整测试 **474 项通过**，相关 Ruff、Black 和 git diff --check 通过。P5 余下主要为 recipes 示例与旧验证工具/测试调用迁移、旧作者类删除及最终复验。

### P5：来源测试与局部 Halo 迁移（进行中）

导入 ASS、混合静态歌词和多段读音测试已改用 Effect/Body/Ruby，继续验证原来源、owner、演唱时钟和每轮强调。保留有明确用途的底层 pulse planner 测试。

Halo 的 targets 现支持字符、读音及音节来源选择集合，包含空集合；字符选择不能切开字形簇，错误带具体来源。新增七项测试覆盖选择范围、完整及部分 ffi 连字和时间片段拒绝。完整测试 **481 项通过**。

recipes 已改为 RecipeEffect；H2 用字符/读音选择分别声明辉光，K2 保留优先轨道的完整 Paint 替换语义。迁移对比记录在 [recipes-migration.json](recipes-migration.json)：首次对比发现 H2 重叠区域最大 4/255 的差异，定位为两层 Halo 的声明顺序改变。将读音辉光声明在正文辉光之前，保持原合成顺序后，16 个关键帧全部逐像素一致。事件数由 674 增至 841，分别声明装饰和正文导致拆分增加；没有减少原有视觉行为。旧作者类及工具/测试调用尚未完全删除，P5 保持未完成。

相邻音节验证工具已移除旧作者类，直接调用内部目标准备和遮罩编译入口；它需要隔离各单元的固定布局以验证跨单元遮罩、显示窗口及前后缘扩展，属于明确的后端测试。六种场景的 216 条输出事件在只归一化诊断效果名后与旧版本一致；120 帧、44 项检查全部通过，见 [adjacent-migration.json](adjacent-migration.json)。

### P5：辉光/并行配色工具与渲染用例迁移

`validate_glow_strategies` 和 `validate_parallel_paints` 已移除 KaraokeEffect。完整 paint 栈的硬裁剪、完成释放、union/priority/layer 直接测试内部编译器；并行配色继续与独立生成的静态 ASS 矩形比较。辉光工具的整对象分支改为绑定后的 WholeGlow 子类，显式使用函数曲线来保持原 40 ms 采样验证目的，避免新版 WholeGlow 自动原生化后误用旧的 held-value 期望。

实际执行结果：辉光策略 **81 帧、32 项检查**，普通并行配色 **80 帧、47 项检查**，带装饰并行配色 **100 帧、57 项检查**全部通过。报告分别为 [glow-tool-migration.json](glow-tool-migration.json)、[parallel-tool-migration.json](parallel-tool-migration.json)、[parallel-decorated-tool-migration.json](parallel-decorated-tool-migration.json)。

`test_render.py` 的默认正文/读音、红色扫色、分色与独立读音覆盖、guide、owner 清理、重复渲染、来源回退、原始事件验证和预检取消用例已使用 compose/configure；需要故意修改输出计划的测试通过绑定后的新 Effect 获取计划。该文件 **33 项测试通过**。剩余旧接口仍用于部分特殊后端测试、综合验证工具和 benchmark，旧类尚未删除。

### P5：综合验证与新特效入口性能基线

`tools/validate_effects.py` 已移除旧作者类，直接验证内部目标准备、遮罩编译、底层 Pulse 和采样输出；静态参考仍独立构造 TextLayer 或原始 ASS，保留完整空间/时间断言。实际运行 **1063 项检查全部通过**，报告见 [effects-tool-migration.json](effects-tool-migration.json)。

`tools/benchmark_effects.py` 已改为真实的新 Effect 生命周期，普通配色通过 Body/Ruby/style，辉光通过 Halo，逐字强调通过 on_highlight，常量采样通过属性函数声明。四轨样式明确按来源单元绑定。分色选择为首个有正文的单元前三个来源字符，遵循特效系统字形簇边界校验；不像旧 benchmark 在布局后选择前三个已绘制簇，不能为跑分而改变整形或放宽范围诊断。

120 行、每场景 3 次的基线已保存至 [benchmark-migration.json](benchmark-migration.json)：普通/分色/union4/priority4/pulse_glow/常量采样的中位耗时分别约 280/294/339/798/1085/1513 ms，输出事件数分别为 3360/3360/3360/13440/21600/3360。四条相同轨道及常量函数最终事件数等于普通输出。8 行迁移前后冒烟数据中 pulse_glow 从每行 135 增至 180 个事件，因装饰单独声明产生额外拆分；其他场景事件数保持一致。性能数字仅是本机基线，不宣称迁移提速。

渲染测试中的部分区域轨道、冲突轨道和重复 union 也已改用新 Effect 的 sweep 配置；原最终裁剪、来源错误及无重复增亮断言保留。仍有部分底层诊断/采样/脉冲测试使用旧类，下一步继续迁移后删除旧作者实现。

### P5：旧作者实现删除

`test_render.py` 剩余用例已迁移。分色、辉光诊断和动态来源使用新作者入口；底层 Pulse 的遮挡轨道触发、字形边缘时钟、完成释放和非法范围直接检查内部准备/编译阶段，未增加兼容配方。所有原有断言保留；作者层分色歧义测试发现读音颜色错误缺少 segment 来源，现已在读音样式解析阶段附加精确 EventOrigin，错误类型与异常身份不变。

KaraokeEffect 类及包导出已删除。源码搜索只剩移除断言和禁止旧依赖的回归桩；README、特效指南和应用接入说明已使用当前接口。EffectPlan/build、TextLayer、底层 Pulse/DynamicEffect 保留为明确的后端扩展，共用现有内部编译器。P5 前两个剩余 TODO 已勾选，最终综合复验仍未勾选。

删除后全量 **481 项测试通过**。全目录 Ruff 通过；全目录 Black 检查发现七个文件的格式差异，已统一格式（无行为修改），随后重跑全量测试。最终交付审计仍需逐项核对计划与视觉基线，不以旧类删除作为整体完成依据。

### 最终逐项审计与验收完成

逐项核对 P0～P5 共 47 个 TODO 及核心契约；审计矩阵已写入 effect-system-audit.md。最后补齐 Halo 的显式状态颜色继承，增加四项测试，默认独立色不变。新工具 capture_migrated_examples 可直接复验 song/dynamic/recipes 的 36 个历史关键帧，避免临时脚本成为唯一验证入口。

最终全量 485 项测试通过；全目录 Ruff、Black、diff 检查通过。layered/whole/arc/三色/组合矩阵、原生透明度、Halo clip 及后端验证全部通过，运行结果和当前源码指纹记录于 effect-system-final-validation.json。计划的最后验收项已勾选。实现与本机验证完成；历史记录中的“尚未完成”是当时状态，以本节和最终交付审计为准。未创建提交，也未修改外部应用。


## 命名整理：特效系统

统一使用“特效系统”称呼本次重构。实现模块改为 `kara_templater/effect.py`；指南、计划、实施记录和审计分别改为 `effects.md`、`effect-system-plan.md`、`effect-system-progress.md` 和 `effect-system-audit.md`。测试、辅助模块、验证工具及迁移报告同步改名，所有导入与文档链接已更新。

改名后全量 **485 项测试通过**，Ruff、Black 和 `git diff --check` 通过；README 与全部文档的相对链接检查通过。`tools.validate_effect_system` 重跑三色示例，四种输入路径的 18 条事件及六帧结果与现有基线一致；`tools.capture_migrated_examples` 重跑 song/dynamic/recipes 的 36 个历史关键帧，全部逐像素匹配。

[最终验证报告](effect-system-final-validation.json) 中的 `naming_update` 保存本次复验范围，`source_sha256` 更新为改名后的当前源码指纹。此前综合视觉验收记录与改名前指纹作为历史证据保留。
