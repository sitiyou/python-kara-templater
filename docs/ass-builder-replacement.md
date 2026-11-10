# ass_builder 应用替换说明

应用继续负责读取环境变量、选择字体、排轨和确定每行显示窗口；本库负责时间映射、特效组合与 ASS 展开。本次没有修改外部 `/home/quy/dev/python/karaoke/ass_builder.py`。

## 应用接入

1. 将应用中的 ASS 样式及文档元信息构造成 `Document`。K1/K2/H1/H2/LEAD 可继续作为应用的样式名称，布局使用各自的对齐、字号和边距。
2. 将歌词数据构造成 `KaraokeItem(id, source, style, window)`。`source` 为 `KaraokeLine`，时间使用绝对整数毫秒；显示窗口独立于演唱时间。如果输入已经是带时间标签的 ASS，可省略 `items` 让 `render_karaoke()` 导入。
3. 将环境变量解析后的颜色转成 RGB `Color`，用 `PaintPair` 表达唱前/唱后外观，`Glow` 表达辉光。颜色派生算法属于主题配置，可保留在应用中的普通 Python 函数里。
4. 用共享 `KaraokeEffect` 配方及 `dataclasses.replace()` 配置正文/顶部样式差异，通过 `effect={"K1": ..., ...}` 分派。导唱使用 `KaraokeEffect.guide()`。
5. 调用 `render_karaoke(document, items, effect=effects, owner="song")`，检查 `RenderResult.diagnostics` 后保存 `.document`。保留稳定 owner 可重复生成；不要再创建模板注释或手动复制多个视觉层。

可运行例子为 [recipes.py](../examples/recipes.py)，另有可直接用于 CLI 的 [song_effect.py](../examples/song_effect.py)。两个例子均不读取外部应用目录。

## 需求核对与目标画面

2026-11-09 重新核对应用 `_effect_rows()`、`generate_ass_header()` 和配置项，以及本库提交 `7ff7d30` 中已删除的 `kara_templater/effects.py`。应用文件的 SHA-256 为 `7c0f12c5b6893671b3eb9a9596a0d754bdc971b8bc99b9badee2c69cda743b7c`。这些文件用于确认需求与问题，不作为新输出的逐帧参考。

| 原实现承担的需求或 workaround | 新目标与验收依据 | 当前情况 |
| --- | --- | --- |
| 正文/ruby 各复制四层，填色、实边、模糊边分别设色 | 唱前/唱后填色、描边、辉光显式配置，布局与变换共享；由配方按需要展开。`test_ass_output.py` 的共享变换、`multicolor_ruby_validation` 和 `overlapping_lines_validation` 验证颜色及层序 | 已实现；不维持四层数量 |
| `CLIP_SIZE` 同时用作像素外扩和毫秒提前/延后 | 空间补偿和预扫/收尾时间独立，主体按原演唱区间走完，blur 不占用主体进度。`test_timeline.py`、`adjacent_transition_validation`、`phase_boundary_validation` 验证 | 已实现 |
| 原生 metrics 无法预知后来添加的 blur/描边 | 字形墨迹与装饰安全范围分开；装饰估计须诊断并允许像素补偿，完成后真正解除外侧裁剪。`decoration_boundary_validation`、`completion_release_validation` 验证 | 已实现；估计不是任意 blur 的严格数学边界 |
| 扫色第一程使用加速参数、第二程匀速 | 使用明确的归一化时间/主体位置节点；曲线端点对应唱词时间，停顿保持位置。`speed_mapping_validation` 验证对应主体位置的线性/变速画面 | 已实现；不复刻旧加速常量 |
| `size_pop()` 在多个手写层重复，缩放与回落时间嵌在标签中 | 三种触发/目标/中心独立选择，回落按明确时长结束；默认 pulse 在区间中点到峰值、终点回原位，超窗明确截断或扩展。`test_animation.py` 和三模式渲染工具验证 | 已实现；三模式位置/间距的综合画面项继续单独验收 |
| ruby 单独偏移、描边和强调标签 | `RubyPolicy` 管位置/跟随，`RubyPaint` 管独立外观；ruby 继承对应正文，混合颜色须显式指定。`ruby_validation`、`multicolor_ruby_validation` 验证 | 已实现 |
| K1/K2 使用底部不同排轨，H1/H2 使用顶部主题，LEAD 关闭缩放/ruby/变速 | 样式控制排版，配方按 style 分派；导唱默认线性且无正文强调。独立的 `recipes.py` 覆盖五种样式，重叠导唱由手写 ASS 参考验证 | 已实现；应用继续负责排轨 |
| 所有裁剪上下界写死 0..1080 | 使用文档 PlayRes 和目标几何；96 px 文字放到 y>1080 仍完整显示。`resolution_size_validation` 验证 | 已实现 |
| 整段 overlay blur 从低不透明度逐渐增强，并不跟随局部硬裁剪前沿 | 提供可选择的整段辉光增强策略，保持主体扫色与强调独立；与局部硬裁剪、完成释放做同场景对照 | 已提供独立 `TextLayer.component`、`DynamicProperties.glow_opacity` 和正文示例 `whole_glow.py`；`glow_strategy_validation` 的 81 帧对照通过，示例关闭 ruby |

新目标画面以主体前沿、独立静态参考、显式手写图层参考和来源布局为依据。旧代码中的坐标常量、固定层数、时间/空间参数耦合及历史像素外观都不是必须保留的行为。不同外观交界的描边/辉光接缝仍需完成计划中的合成能力验收，不能用单轨画面通过代替它。

## 配置语义

| 应用需求 | 配置方式 |
| --- | --- |
| 填色、描边、辉光及透明度 | `Paint`、`Glow`，透明度使用 0～1 的不透明度 |
| 两阶段主体扫色节奏 | `ProgressCurve.two_stage(time_fraction=..., progress_fraction=...)` |
| 装饰外扩 | `EdgeSweep.padding_px`，单位仅为像素 |
| 装饰提前扫入、延后释放 | `EdgeSweep.lead_ms`、`tail_ms`，不消耗主体演唱时间 |
| 完成后的外侧裁剪 | `Sweep.completion="release"` 默认解除完整均匀区域的裁剪，`"clip"` 保留边界 |
| 手动主体计时边界 | 为 `HighlightTrack` 提供 `SingingPass.region`；变更辉光不修改该区域 |
| 扫到哪个字就缩放 | `Pulse.each_char()` |
| 音节开始时各字原地一起缩放 | `Pulse.simultaneous_chars()` |
| 音节整体缩放 | `Pulse.whole_syllable()` |
| ruby 位置与强调 | `RubyPolicy(offset_y=..., follow="none" / "syllable")` |
| 同一演唱段内部双色 | `ColorSpan(TextRange(...), ...)`，无需拆分时间 |
| 多扫色 | 独立 `HighlightTrack`，通过 `TrackStyle` 配置唱后覆盖及优先级 |

原先空间补偿同时参与时间补偿的参数应拆开重新配置，不提供旧参数转发或旧画面的逐帧复现。以主体扫色时刻、字形位置、装饰边缘和演唱节奏作为调节依据。

辉光范围当前使用带诊断的估计，复杂接缝仍需在应用字体与目标播放器上检查。ASS 时间量化、矩形裁剪精度和输出事件上限均由库统一处理。对于源 ASS 中本库未支持的内联布局标签，改用结构化数据和 Python 配方，避免导入时丢失含义。

相邻遮罩区域使用不同的可见描边/辉光时，输出 `ASS hard-clips` 能力诊断，包含来源、显示区间与相关轨道。当前路径分别绘制装饰再硬裁剪，不支持将换色后的区域作为一张图像统一模糊，也不保证不同装饰之间平滑衔接；增加时间采样不能解决这个空间边界。可以显式选择独立无裁剪辉光，但那是另一种画面语义。纯填色变化、相同装饰和只在时间上切换的整段外观不会触发此诊断。

## 已删除能力的替代清单

| 删除项 | 新能力或明确范围 |
| --- | --- |
| `Engine`、`apply_templates()`、`TemplateError` | `render_karaoke()`、函数或 `build()` 配方、带来源的模型/输出错误 |
| `$variables` 和内嵌 `!expression!` | `KaraokeItem`、`EffectContext.layout`、标准 Python 表达式 |
| 模板类型、循环、分组、记忆变量 | Python 函数、循环、对象及显式配置；不执行 ASS 中的代码 |
| `retime`、`relayer`、`restyle` 等模板辅助函数 | 显式时间对象、配方层序和样式；特殊事件通过 `EffectPlan.raw_lines` 提供 |
| `render_sweep()`、`SweepSettings`、五项 BGR 调色板 | `KaraokeEffect`、`Sweep`、`PaintPair`、`Glow` 和 RGB `Color` |
| 结构化布局到模板环境的桥接、空的第零音节 | 直接遍历结构化歌词和布局；没有人为插入的模板上下文 |
| 基于 Unicode 码点的拆字 | 经轮廓验证的字符单元及 `TextRange` 来源映射 |
| `--video-size` 的隐式比例修正 | 坐标统一为 ASS PlayRes 像素；应用提供一致的分辨率和位置 |

字幕读取、序列化、字体测量、ruby 布局与有效需求测试继续服务新流程。仅验证已删除模板语法的测试随旧实现移除。没有兼容包装或隐藏的旧执行入口。
