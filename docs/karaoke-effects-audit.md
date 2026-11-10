# Karaoke 特效计划交付核查

核查日期：2026-11-09。范围为实施计划的六个阶段、测试验收项及 A～D 交付；不扩展为通用渲染器、自动排轨或任意脚本文字支持。以下 105 项按原清单顺序逐项对应证据，未以复选框本身作为证明。

最终状态：各项要求在计划声明的支持范围内完成。单元/集成测试 241 项通过；相同库代码的隔离安装测试也为 241 项。83 个公开导出均存在且无重复，旧入口不存在。11 条示例/CLI 命令通过；README 的 8 个 Python 代码块在提供其注明的 document/items/result 上下文后通过。

画面证据的有效范围以各报告为准：固定字体、分辨率和渲染器；纯填色、硬裁剪装饰、不同区域与时钟、缩放及淡入淡出分别验证。不同辉光之间的硬边界是明确诊断的能力限制，不能解释成支持平滑空间换色。字体回退、未支持文字、事件预算和冲突均有诊断，不静默替换语义。

代码/测试链接指向实际实现及断言；报告键位于 [验证基线](effects-validation-baseline.json)，配套命令、误差和限制见 [验证说明](effects-validation.md)。历史失败报告 `scaled_clip_clock_probe` 保留用于追溯，当前成功证据是 `clip_clock_final_validation`。

## 阶段一 确定需求样例与验收目标

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 1.1 | 提炼 `ass_builder.py` 的最小样例，覆盖 K1、K2、H1、H2 和 LEAD 的配置差异。 | [examples/recipes.py](../examples/recipes.py)、[docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |
| 1.2 | 固定字体文件、分辨率、渲染器版本和关键采样时刻，建立可复现的画面对比方法。 | [tools/validate_effects.py](../tools/validate_effects.py)、[docs/effects-validation.md](../docs/effects-validation.md) |
| 1.3 | 从应用模板与当前 `render_sweep()` 提取有效需求和已知问题；将参考画面与新设计的目标画面区分，不要求逐帧复现旧行为。 | [docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |
| 1.4 | 明确填色、描边、辉光、ruby 偏移、扫色节奏和缩放回落的目标表现；内部层数由生成器决定。 | [examples/recipes.py](../examples/recipes.py)、[tools/validate_glow_strategies.py](../tools/validate_glow_strategies.py) |
| 1.5 | 建立旧功能到新能力的替代清单，确认目标需求覆盖后删除对应旧入口、参数、分支和专用测试。 | [docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md)、[kara_templater/__init__.py](../kara_templater/__init__.py) |
| 1.6 | 检查参考代码与拟复用内容的许可证要求，优先独立实现领域接口。 | [THIRD_PARTY.md](../THIRD_PARTY.md) |

## 阶段二 定义领域模型

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 2.1 | 定义 `DisplayWindow`，统一校验开始、结束时间和空窗口。 | [tests/test_timeline.py](../tests/test_timeline.py) |
| 2.2 | 定义高亮轨道和时间到空间的映射；支持按 ruby 宽度分区，并依据实际需求确定默认策略。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tests/test_ruby_timing.py](../tests/test_ruby_timing.py) |
| 2.3 | 支持显式正文分区；约定无 ruby、静态文本、空读音、零时长与间隙的行为。 | [tests/test_mixed_layout.py](../tests/test_mixed_layout.py) |
| 2.4 | 区分分区演唱与同一区域重复演唱；定义重复时的保持和重置策略。 | [tests/test_timeline.py](../tests/test_timeline.py) |
| 2.5 | 定义正文与 ruby 的关联，不通过重复布局推导两者关系。 | [tests/test_structured.py](../tests/test_structured.py)、[tests/test_ruby_timing.py](../tests/test_ruby_timing.py) |
| 2.6 | 定义独立的触发器、目标选择器与变换中心，覆盖三种缩放模式；区分音节和 segment 的时间锚点。 | [tests/test_animation.py](../tests/test_animation.py) |
| 2.7 | 根据高亮轨道求出逐字进入、中心和完成时间，处理变速、停顿、零时长与重复演唱；避免强调变换影响触发计算。 | [tests/test_animation.py](../tests/test_animation.py)、[tests/test_ruby_timing.py](../tests/test_ruby_timing.py) |
| 2.8 | 定义固定时长和逐字扫过时长，以及重复触发与已有动画的冲突规则。 | [tests/test_animation.py](../tests/test_animation.py) |
| 2.9 | 定义首版可独立绘制的字符单元及来源映射，明确字素、shaping cluster、空白和不支持拆分的处理。 | [tests/test_characters.py](../tests/test_characters.py) |
| 2.10 | 定义唱前、唱后外观和主题配置，对外使用 RGB 颜色与直观透明度，输出时统一转换为 ASS 格式。 | [tests/test_composition.py](../tests/test_composition.py)、[tests/test_ass_output.py](../tests/test_ass_output.py) |
| 2.11 | 定义与 segment 解耦的文本外观范围，明确行默认、范围覆盖、轨道覆盖及 ruby 继承的解析顺序。 | [tests/test_appearance.py](../tests/test_appearance.py) |
| 2.12 | 定义带稳定标识和独立目标区域的多轨模型，保留不连续的已唱区域及各轨道的生命周期。 | [tests/test_timeline.py](../tests/test_timeline.py) |
| 2.13 | 定义重叠区域的合并、优先级覆盖和独立叠加策略，校验冲突优先级及不兼容外观。 | [tests/test_composition.py](../tests/test_composition.py) |
| 2.14 | 定义强调触发的轨道选择、首次到达去重、演唱轮次重置和同时触发规则。 | [tests/test_animation.py](../tests/test_animation.py)、[tests/test_render.py](../tests/test_render.py) |
| 2.15 | 将环境变量解析留在应用层，库配置使用显式参数。 | [kara_templater/recipe.py](../kara_templater/recipe.py)、[examples/recipes.py](../examples/recipes.py) |
| 2.16 | 定义独立的 `padding_px`、`lead_ms`、`tail_ms`，分别确定单位、语义与合理默认值。 | [tests/test_timeline.py](../tests/test_timeline.py) |
| 2.17 | 定义独立于绘制范围的 `timing_region`，支持文字主体默认策略、布局近似和显式边界调整。 | [tests/test_mixed_layout.py](../tests/test_mixed_layout.py) |
| 2.18 | 分离主体进度曲线与预扫、收尾过渡；约定动态 blur 不改变主体时间映射，多个视觉层或轨道可共享该映射。 | [tests/test_render.py](../tests/test_render.py)、[tools/validate_parallel_paints.py](../tools/validate_parallel_paints.py) |
| 2.19 | 约定动画回落超出显示窗口的处理策略；首版默认截断并提供诊断，显式配置可扩展窗口。 | [tests/test_animation.py](../tests/test_animation.py) |
| 2.20 | 对同一目标、同一属性的重叠动画默认报错；只对明确支持的组合提供叠加规则。 | [tests/test_animation.py](../tests/test_animation.py) |

## 阶段三 实现 ASS 事件生成

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 3.1 | 建立有限的效果计划，包含目标、时间区间、外观、变换和高亮区域。 | [kara_templater/recipe.py](../kara_templater/recipe.py)、[tests/test_render.py](../tests/test_render.py) |
| 3.2 | 统一处理标签数值、文本转义、颜色、透明度和时间换算。 | [tests/test_ass_output.py](../tests/test_ass_output.py) |
| 3.3 | 实现固定位置、淡入淡出、缩放和矩形扫色的原生标签输出。 | [tests/test_ass_output.py](../tests/test_ass_output.py) |
| 3.4 | 按外观与动画需求展开视觉层，将共享变换同步到正文各层；ruby 是否跟随强调由策略指定，不固定为旧实现的四层。 | [tests/test_render.py](../tests/test_render.py)、[tests/test_ruby_timing.py](../tests/test_ruby_timing.py) |
| 3.5 | 实现独立逐字绘制并复用原布局位置；实现整体缩放时各字位置围绕组中心变化，避免将整体缩放错误实现为各字原地缩放。 | [tests/test_characters.py](../tests/test_characters.py)、[tools/validate_pulse_geometry.py](../tools/validate_pulse_geometry.py) |
| 3.6 | 将逐字触发结果编译到各自事件的局部时间，保持填色、描边和辉光同步。 | [tests/test_ass_output.py](../tests/test_ass_output.py)、[tools/validate_clip_seams.py](../tools/validate_clip_seams.py) |
| 3.7 | 定义跨行、跨效果的图层分配顺序，避免每个配方都独立占用固定的 0 至 3 层。 | [tools/validate_effects.py](../tools/validate_effects.py) |
| 3.8 | 按颜色范围与轨道区域交集展开事件，复用原布局和基础未唱层，避免重复绘制整行。 | [tests/test_appearance.py](../tests/test_appearance.py)、[tools/validate_parallel_paints.py](../tools/validate_parallel_paints.py) |
| 3.9 | 实现受支持区域的并集去重、优先级遮挡与显式层序叠加，验证不连续区域、轨道退出及裁剪接缝；不支持的组合输出能力诊断。 | [tests/test_masks.py](../tests/test_masks.py)、[tools/validate_parallel_paints.py](../tools/validate_parallel_paints.py)、[tools/validate_clip_seams.py](../tools/validate_clip_seams.py) |
| 3.10 | 裁剪范围读取实际分辨率或目标几何，移除新路径中写死的 1080。 | [tools/validate_effects.py](../tools/validate_effects.py) |
| 3.11 | 明确裁剪坐标空间。缩放或移动时，保证扫色区域按配置跟随文字；无法原生精确表达的组合必须诊断或使用已验证的近似路径。 | [tests/test_ass_output.py](../tests/test_ass_output.py)、[tests/test_sampling.py](../tests/test_sampling.py) |
| 3.12 | 分开处理内部扫色前沿和外部装饰边界，防止扩大边距导致提前露出未唱区域。 | [tests/test_masks.py](../tests/test_masks.py)、[tests/test_render.py](../tests/test_render.py) |
| 3.13 | 实现统一的装饰边缘过渡和完成后释放外侧裁剪的策略。 | [tests/test_render.py](../tests/test_render.py)、[tools/validate_glow_strategies.py](../tools/validate_glow_strategies.py) |
| 3.14 | 将预扫、主扫和收尾分别编译，保证主扫在演唱区间内按指定曲线完成；处理显示窗口截断与相邻装饰过渡重叠。 | [tools/validate_adjacent_units.py](../tools/validate_adjacent_units.py)、[tools/validate_effects.py](../tools/validate_effects.py) |
| 3.15 | 根据装饰配置扩展裁剪安全范围，不把该范围纳入主体进度归一化；无法可靠估算时支持显式补偿并给出诊断。 | [tests/test_sampling.py](../tests/test_sampling.py)、[tests/test_render.py](../tests/test_render.py) |
| 3.16 | 统一 ASS 事件时间量化，处理短事件、量化后的零长度和相邻边界，避免空隙或重叠闪烁。 | [tests/test_ass_output.py](../tests/test_ass_output.py)、[tools/validate_clip_seams.py](../tools/validate_clip_seams.py) |
| 3.17 | 输出事件保留来源信息，错误能够定位原始歌词、单元、segment 和效果。 | [tests/test_sources.py](../tests/test_sources.py)、[tests/test_render.py](../tests/test_render.py)、[tests/test_import_ass.py](../tests/test_import_ass.py) |
| 3.18 | 接入事件数上限与统计，超限时给出具体效果和原因。 | [tests/test_ass_output.py](../tests/test_ass_output.py)、[tests/test_sampling.py](../tests/test_sampling.py)、[tests/test_render.py](../tests/test_render.py) |

## 阶段四 提供脚本化特效接口

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 4.1 | 实现 `KaraokeEffect` 配方，将外观、高亮、强调、ruby 策略分别配置。 | [kara_templater/recipe.py](../kara_templater/recipe.py)、[examples/recipes.py](../examples/recipes.py) |
| 4.2 | 提供 `Sweep`、两阶段扫色、`Pulse` 和淡入淡出组合。 | [examples/recipes.py](../examples/recipes.py)、[tests/test_timeline.py](../tests/test_timeline.py) |
| 4.3 | 提供三种缩放模式的快捷配置和完整参数接口，允许独立选择触发时机、目标、中心及持续时间。 | [tests/test_animation.py](../tests/test_animation.py)、[tools/validate_pulse_geometry.py](../tools/validate_pulse_geometry.py) |
| 4.4 | 定义进度曲线及分段衔接的数学语义，验证端点、速度与时长；ASS 加速参数由生成器处理，不暴露为旧行为兼容模式。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tools/validate_effects.py](../tools/validate_effects.py) |
| 4.5 | 暴露计时区间、主体曲线和装饰过渡的独立配置，以新能力替代旧 `clip_size` 和专用 sweep 参数。 | [tests/test_render.py](../tests/test_render.py)、[docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |
| 4.6 | 允许效果由普通函数或 `build(target, context)` 对象提供，配置与单次执行状态分离。 | [tests/test_render.py](../tests/test_render.py)、[examples/staggered_path.py](../examples/staggered_path.py) |
| 4.7 | 提供按行、歌词单元和 segment 的遍历接口，返回稳定的来源引用。 | [tests/test_sources.py](../tests/test_sources.py) |
| 4.8 | 支持主题复用和按 style 分派，避免为 K1、K2 等样式复制效果逻辑。 | [examples/recipes.py](../examples/recipes.py)、[tests/test_render.py](../tests/test_render.py) |
| 4.9 | 提供文本范围配色、多轨并行扫色和重叠策略的公开配置；强调接口支持选择轨道和去重方式。 | [tests/test_appearance.py](../tests/test_appearance.py)、[tests/test_animation.py](../tests/test_animation.py) |
| 4.10 | 提供同一 segment 内多配色、不同区域并行扫色、同一区域双轨覆盖与叠加的示例。 | [examples/parallel_tracks.py](../examples/parallel_tracks.py) |
| 4.11 | 实现导唱预设：共用外观与线性扫色，不默认附带正文缩放或 ruby。 | [tests/test_render.py](../tests/test_render.py)、[examples/recipes.py](../examples/recipes.py) |
| 4.12 | 提供一个自定义组合示例，证明用户无需修改库内部就能组合新的歌词特效。 | [examples/staggered_path.py](../examples/staggered_path.py)、[tests/test_staggered_path.py](../tests/test_staggered_path.py)、[examples/whole_glow.py](../examples/whole_glow.py) |

## 阶段五 统一入口与删除被替代功能

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 5.1 | 建立统一的 `render_karaoke()` 入口，接入文档与布局能力，并保持输入文档不变。 | [tests/test_render.py](../tests/test_render.py) |
| 5.2 | 逐项评估模板引擎能力：仍有独立价值的能力纳入明确范围，已被脚本接口完整替代的模板执行入口和实现直接删除。 | [docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |
| 5.3 | 在统一扫色能力完成后删除 `render_sweep()` 及其专用配置，更新仓库内调用点，不保留转发包装。 | [kara_templater/__init__.py](../kara_templater/__init__.py)、[docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |
| 5.4 | 统一生成事件的归属标记与清理规则，保护源歌词和无关事件，避免重复生成。 | [tests/test_render.py](../tests/test_render.py)、[tests/test_import_ass.py](../tests/test_import_ass.py) |
| 5.5 | 验证同一文档重复运行结果稳定，清理已删除路径遗留的仓库内引用。 | [tests/test_cli.py](../tests/test_cli.py)、[tests/test_render.py](../tests/test_render.py) |
| 5.6 | 增加独立示例文件，覆盖正文、ruby、多段读音、双配色和导唱符。 | [examples/recipes.py](../examples/recipes.py)、[examples/multi_reading.ass](../examples/multi_reading.ass) |
| 5.7 | 更新 README、公开导出、命令行和示例，使它们只指向当前有效接口；说明替代后的调用方式。 | [README.md](../README.md)、[kara_templater/__init__.py](../kara_templater/__init__.py)、[tests/test_cli.py](../tests/test_cli.py) |
| 5.8 | 记录外部应用的替换步骤；本库验收不自动修改外部 `ass_builder.py`。 | [docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md) |

## 阶段六 按需求扩展定制能力

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 6.1 | 扩展 native 测量接口，提供能够对应文字范围的墨迹边界，并验证字体回退、空白和组合字符。 | [tests/test_characters.py](../tests/test_characters.py)、[native/metrics.cpp](../native/metrics.cpp) |
| 6.2 | 扩展首版逐字绘制的文字支持范围，利用新增测量信息改善复杂 shaping cluster 的处理，保留阶段二确定的拆分契约。 | [tests/test_characters.py](../tests/test_characters.py) |
| 6.3 | 增加自定义属性时间函数，明确归一化进度、随机种子和执行上下文。 | [tests/test_sampling.py](../tests/test_sampling.py) |
| 6.4 | 实现必要的时间采样输出，提供精度、最大事件数和超限策略；评估前先报告预计输出规模。 | [tests/test_sampling.py](../tests/test_sampling.py)、[tests/test_render.py](../tests/test_render.py) |
| 6.5 | 对采样事件按全局时间求值，避免每个事件重新开始淡入或动画。 | [tests/test_sampling.py](../tests/test_sampling.py)、[tests/test_ass_output.py](../tests/test_ass_output.py)、[tools/validate_clip_seams.py](../tools/validate_clip_seams.py) |
| 6.6 | 固定字体下验证采样与整音节缩放、淡入、整数位移及动态 blur 的组合，保留原始插值和细分时刻。 | [tools/validate_effects.py](../tools/validate_effects.py) |
| 6.7 | 扩展局部错峰、路径位移或更复杂强调，每个能力以具体歌词样例驱动。 | [examples/staggered_path.py](../examples/staggered_path.py)、[tests/test_staggered_path.py](../tests/test_staggered_path.py) |
| 6.8 | 实验辉光跟随扫色的策略，分别验证整体增强、硬裁剪与完成后释放。 | [tools/validate_glow_strategies.py](../tools/validate_glow_strategies.py)、[examples/whole_glow.py](../examples/whole_glow.py) |
| 6.9 | 对无法用目标 ASS 路径达到的合成效果明确报告能力边界，不承诺时间采样可以解决空间合成问题。 | [tests/test_masks.py](../tests/test_masks.py)、[tests/test_render.py](../tests/test_render.py)、[README.md](../README.md) |

## 时间与映射

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 7.1 | 相邻 segment、中间停顿、零时长、乱序的不同单元、不同单元的重叠演唱。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tests/test_mixed_layout.py](../tests/test_mixed_layout.py) |
| 7.2 | 静态文本、空白、空读音、正文多读音和显式区域映射。 | [tests/test_mixed_layout.py](../tests/test_mixed_layout.py)、[tests/test_characters.py](../tests/test_characters.py) |
| 7.3 | 显示窗口早于零点、回落超出窗口、非常短的事件以及 ASS 时间量化。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tests/test_animation.py](../tests/test_animation.py)、[tests/test_ass_output.py](../tests/test_ass_output.py) |
| 7.4 | 同一区域重复演唱的保持与重置。 | [tests/test_timeline.py](../tests/test_timeline.py) |
| 7.5 | 不等宽多字音节的逐字触发，验证结果来自扫色轨道而非按字数均分。 | [tests/test_animation.py](../tests/test_animation.py)、[tools/validate_pulse_geometry.py](../tools/validate_pulse_geometry.py) |
| 7.6 | 变速扫色、字内停顿、ruby 映射和零时长对进入、中心、完成触发的影响。 | [tests/test_animation.py](../tests/test_animation.py)、[tests/test_ruby_timing.py](../tests/test_ruby_timing.py) |
| 7.7 | 多 segment 音节的开始触发与逐 segment 触发，重复触发期间的动画冲突与固定时长配置。 | [tests/test_animation.py](../tests/test_animation.py) |
| 7.8 | 同一 segment 跨多个颜色范围，颜色配置不改变演唱时间与扫色映射。 | [tests/test_appearance.py](../tests/test_appearance.py)、[tests/test_render.py](../tests/test_render.py) |
| 7.9 | 多轨独立开始、暂停、完成、保持及退出，验证不连续区域不会被错误连成一个扫色区间。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tests/test_masks.py](../tests/test_masks.py) |
| 7.10 | 指定轨道、任意轨道首次到达和分别到达的强调触发，覆盖同时到达、重复轮次及被遮挡轨道。 | [tests/test_animation.py](../tests/test_animation.py)、[tests/test_render.py](../tests/test_render.py) |
| 7.11 | 固定主体计时区间和曲线，仅改变 blur、描边与 padding，验证主体位置及逐字触发时刻不变。 | [tests/test_render.py](../tests/test_render.py) |
| 7.12 | 验证预扫和收尾不消耗主扫演唱时长、不改变已唱文字区域；覆盖零时长、短音节和显示窗口截断。 | [tests/test_timeline.py](../tests/test_timeline.py)、[tests/test_masks.py](../tests/test_masks.py)、[tools/validate_adjacent_units.py](../tools/validate_adjacent_units.py) |

## 画面

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 8.1 | 粗描边、强辉光、斜体、留白明显的字形与首尾装饰越界。 | `decoration_boundary_validation`、`completion_release_validation` |
| 8.2 | 小 blur、大范围 blur 和动态 blur 的对照画面，检查主体在相同演唱时刻的扫色位置与边缘完整性。 | `dynamic_validation`、`global_animation_clock_validation` |
| 8.3 | 对照线性主扫、分段变速主扫及手动计时区间，检查主体进度的视觉节奏，不以亮起像素面积比例作为判定标准。 | `speed_mapping_validation` |
| 8.4 | 同一主体映射搭配不同装饰范围的多轨扫色，以及相邻 segment 的预扫和收尾重叠。 | `parallel_decoration_validation`、`adjacent_unit_validation` |
| 8.5 | 扫色与缩放同时发生，正文和 ruby 的不同强调策略。 | `ruby_validation`、`global_animation_clock_validation` |
| 8.6 | 对同一多字音节分别验证逐字扫到缩放、所有字同时独立缩放和音节整体缩放；核对各字中心位置及字间距离。 | `pulse_geometry_validation` |
| 8.7 | 拆分绘制前后的静态排版一致性，覆盖字距、组合字符和不能安全拆分的 cluster 诊断。 | `positioned_cluster_validation`、`cluster_spacing_validation`、`oblique_validation`、`hangul_cluster_validation` |
| 8.8 | 行内唱前与唱后多配色、ruby 继承与覆盖，以及颜色边界的布局稳定性。 | `multicolor_ruby_validation` |
| 8.9 | 不同区域同时扫色，以及同一区域多轨合并、优先级覆盖和透明叠加的差异。 | `parallel_paint_validation` |
| 8.10 | 合并区域无重复加亮、覆盖轨道退出后下层正确显露，裁剪交界处无额外描边或辉光接缝。 | `clip_clock_final_validation`、`parallel_decoration_validation`、`glow_track_validation` |
| 8.11 | 固定强辉光样例的重复 union、priority 精确退出与同色相邻分区完成后的整帧对照；不同外观交界及缩放、淡入淡出时钟的接缝验证通过。 | `glow_track_validation`、`parallel_decoration_validation`、`clip_clock_final_validation` |
| 8.12 | 多行重叠期间的图层顺序、导唱符与正文同时显示。 | `overlapping_lines_validation` |
| 8.13 | 1920×1080 之外的分辨率与不同字号。 | `resolution_size_validation` |
| 8.14 | 在 segment 开始前、开始、内部阶段交界、结束、尾部补偿结束和回落结束采样。 | `phase_boundary_validation`、`global_animation_clock_validation` |

## 功能完整性与成本

| 项目 | 要求 | 实现与验证证据 |
| --- | --- | --- |
| 9.1 | 保留并更新验证有效需求的测试，删除仅锁定旧接口或旧行为的测试，运行新模型的语义与集成测试。 | `installed_package_validation` |
| 9.2 | 固定环境中比较关键帧，记录可接受像素误差；出现差异时保留差异图和原因。 | `clip_clock_final_validation`、`global_animation_clock_validation` |
| 9.3 | 统计代表性歌曲的事件数、生成耗时与输出大小，与记录的性能基线比较。 | `real_song_benchmark`、`romaji_excerpt_benchmark`、`final_song_benchmark`、`current_synthetic_benchmark` |
| 9.4 | 验证没有启用采样的常规扫色不会意外退化为逐帧事件。 | `current_synthetic_benchmark` |
| 9.5 | 统计颜色范围与轨道数量增加时的事件成本，验证公共未唱层不会随轨道数重复生成。 | `parallel_paint_validation`、`parallel_decoration_validation`、`real_song_benchmark` |
| 9.6 | 检查替代清单：每个删除项有对应的新能力或明确的范围取舍，仓库内没有遗留兼容分支和重复实现。 | [docs/ass-builder-replacement.md](../docs/ass-builder-replacement.md)、[kara_templater/__init__.py](../kara_templater/__init__.py) |

## 交付与剩余边界

| 交付 | 核查结果 |
| --- | --- |
| A 需求和契约 | 应用需求矩阵、独立 K1/K2/H1/H2/LEAD 样例、时间/映射/触发测试齐全。 |
| B ASS 生成和多轨动画 | 三种缩放、配色、区域组合、字幕层序和装饰时钟均有实现与画面证据。 |
| C 统一入口与替代 | render_karaoke、CLI、公开导出、归属清理、替代文档齐全；旧执行模块已删除，无转发包装。 |
| D 测量与自定义扩展 | 字形/字体元数据、采样回调、ArcWave 与 WholeGlow 样例及成本/精度记录齐全。 |

本地 sdist→wheel→隔离安装链已验证 Linux CPython 3.14，产物哈希见 `installed_package_validation` 和最终排序后的 `final_sorted_package_validation`；未将它当作 Windows 或 manylinux 修复产物的实测。相应 CI 配置已经补齐测试源与依赖，未触发远程发布。仓库变更未提交，外部 ass_builder.py 未修改。

验收不要求恢复旧模板执行、复刻旧像素或固定四层。原始数据结构保留静态/空白/零时长语义；明确不支持的 shaping、空间合成和自动布局能力保持公开边界，而非在完成核查时新缩减范围。
