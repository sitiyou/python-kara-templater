# 特效系统交付审计

此文件按实现计划逐阶段记录验收依据。P0～P5 的 47 个 TODO 及核心契约已逐项核对，最终测试与视觉复验通过。历史基线与视觉容差见 effect-system-progress.md。

## P0：特效定义方式契约

| 要求 | 已核对的实现与证据 |
| --- | --- |
| 生命周期、缺省样式、声明顺序、查询范围 | Effect._prepare 在 compose 前绑定来源，验证声明树后 configure，最后返回布局样式；render_karaoke 随后布局。test_effect_lifecycle.py 实际渲染两行，记录顺序、验证实例隔离与字号，并覆盖非法结构、默认跟随及 Halo 外观。test_effect.py 验证重复 ID 和组件复制；test_effect_halo.py 验证 Halo 顺序及正文前后关系。 |
| 选择器、时间、冲突与跟随的最小接口 | 指南“选择来源与组件”“时间、曲线与组合”固定入口。test_effect_queries.py 验证属性、后代、类和重复来源查询；test_effect_properties.py 验证默认/显式时间、停顿进度、冲突、并行触发；test_effect_follow.py 验证跟随开关、独立装饰窗口及裁剪。 |
| 样式表、范围类与直接覆盖，双 Document 入口 | stylesheet.py 按 specificity 稳定排序，属性级应用 INHERIT/UNSET；effect.py 将目标覆盖应用到组件解析结果之上。test_effect.py、test_effect_target_styles.py 验证层叠、状态、继承、范围和跨行隔离；effect-system-validation-baseline.json 记录六帧双输入与直接覆盖等价验证。 |

原接口草案已由当前指南及可执行示例具体化。layered_glow、whole_glow、staggered_path、parallel_tracks 和 alternating_colors 都使用组件/样式/领域行为定义效果；不要求作者处理拆分层或反查内部 ID。P4 的迁移和视觉验证证据沿用原计划已完成条目。

## P1：来源目标

验收详见实施记录“P1 来源选择与目标追踪验收”。test_effect_selection.py、test_effect_queries.py、test_effect_source_edges.py 以及 test_characters.py 覆盖遍历、来源稳定性、空/静态/多段/读音组、实际字体整形限制和展开后来源追踪。来源稳定性以未修改的歌词结构为边界，不承诺编辑或重排后的索引身份不变。

## P2：样式、行为与组合

| 剩余验收项 | 已核对的证据 |
| --- | --- |
| 样式层叠、状态、ruby 继承及动画边界 | test_effect.py 覆盖来源基础色、规则优先级、显式覆盖、INHERIT/UNSET、ruby 继承和多色歧义；test_effect_target_styles.py 覆盖集合广播、读声明及范围覆写；test_effect_halo_states.py 覆盖空间唱后状态、动画覆盖状态透明度及 keep/恢复。 |
| 字号先布局、共同中心/逐字中心、正文/ruby/Halo/裁剪跟随 | test_effect_lifecycle.py 和 test_effect.py 检查实际布局输入与输出字号；test_effect_scale.py 验证共同中心、逐字中心和读音退出跟随；test_effect_follow.py、test_native_offsets.py 验证分开控制、缩放后位移一次及裁剪时钟。composed-glow-validation.json 和 composed-product-validation.json 提供实际渲染组合矩阵。 |
| 属性冲突、显式合成及传播 | check_motion_conflicts 在求值前检查目标/属性/区间；test_effect_properties.py、test_effect_scale.py、test_effect_selection.py 覆盖默认冲突、keep 延伸冲突、不同缩放中心、正文/读音冲突及源信息；test_native_composition.py、test_native_offsets.py 验证 add/multiply/override、覆盖恢复和非线性采样；test_effect_follow.py 验证关联对象只跟随一次及装饰窗口的再次冲突检查。 |

声明的基础外观与动画属性不会产生两套互相竞争的时钟：组透明度乘基础外观，Halo 自身透明度在活动时覆盖其基础/状态值，结束遵守 keep。缩放是布局后的变换，基础 font_size 在布局前处理。各语义已由指南说明，并有以上行为与渲染测试覆盖。

P5 迁移复核补验：原计划的显式目标/时间上下文入口此前只存在于底层，现已通过 Contextual、PropertyContext 和 PropertyTarget 补齐作者属性接口。test_effect_context.py 验证推迟求值、来源、确定性噪声、跟随、keep 及异常边界。随后已补齐 Halo blur/max_blur，test_effect_blur.py 验证上界、空间预留及组合；dynamic-effect-migration.json 记录动态示例十帧与旧输出完全相同。此后的 P5 迁移已覆盖 recipes、验证工具、benchmark 和测试；旧作者类现已删除，最终复验已完成，见文末矩阵及 effect-system-final-validation.json。

## 最终验收范围

P5 已完成预设通用组合、旧作者类删除、CLI/文档迁移与最终复验。文末 47 项矩阵逐项连接计划要求和实现证据；核心契约以对应行为断言、来源断言与独立画面参考核对。最终验证报告记录实际命令结果与源码指纹，不以测试总数单独作为完成依据。

P0/P2 验收时测试记录：完整 pytest **442 项通过**。当轮新增生命周期测试 9 项，Ruff、Black 与 git diff --check 通过；没有改写已有视觉基线。

## P3：后端接入验收

| 要求 | 实现及验证证据 |
| --- | --- |
| 可表达曲线原生输出，其余受预算采样 | behaviors.bind_property 与 lowering.native_motions 只读取已知曲线节点；native_opacity_supported 核对透明度通道和 fade 乘积。test_native_composition.py、test_native_offsets.py、test_native_singing_progress.py 验证原生及回退路径、停顿、终值、量化及显式组合。零总时长仍可通过采样表达，不要求为所有特例增加原生优化。 |
| 任意函数不推断；采样预检和精度边界 | test_sampling.py 验证全局网格、缓存、预算拒绝、误差原因和不跨间隙合并。新增 test_effect_render_contract.py 从新 Effect 入口验证整文档预算、样本上限、估算取消与函数异常来源。render.py 先准备所有 SamplingPlan 再求值；估算不是最终事件数上界，最终编译再次限制事件数。 |
| 来源、字体及裁剪精度 | test_effect_source_edges.py 检查动画选择的实际字形边界与来源展开；test_characters.py 检查缺字及真实字体整形能力；test_ass_output.py 验证原始时钟、量化、排序后来源、裁剪误差及实际输出上限。新增作者入口精度测试确认过严容差报错仍包含段地址和绝对时间。 |
| 已知曲线、函数与关键帧结果 | composed-product-validation.json 的五组场景 × 五种写法 × 八帧，本轮重新运行且报告完全一致；关键帧、乘法和加法写法与原生逐像素相同，函数遵循已记录的裁剪分界容差。native-opacity-validation.json 的独立静态参考七帧也重新通过，最大通道差 2/255。test_native_singing_progress.py 对四个属性的实际演唱进度使用独立计算和函数对照。 |

P3 验收后完整 pytest **458 项通过**。不承诺任意函数采样的空间误差，也不把 clip_error_px 当作最终整数像素裁剪的总误差；指南明确这两项限制。后续 P5 全量复验已通过，见最终报告。

## P5 旧入口删除核对

KaraokeEffect 实现和顶层导出均已删除，Python 源码中的名称仅保留在 test_effect_lifecycle.py 的移除断言及禁止依赖回归桩中。作者示例、CLI 和 benchmark 使用 Effect；后端工具直接调用同一内部编译器，不另建兼容配方。test_render.py 保留完成释放、脉冲时钟、隐藏轨道触发、来源定位、预检预算与异常身份等断言；作者层读音分色歧义现在附有精确 segment 来源。删除后全量 481 项测试通过。随后完成最终综合审计、验收命令和显式 Halo 颜色继承补验，全量测试现为 485 项通过。

## 最终逐项追踪矩阵

下表编号按实现计划各阶段 TODO 的原始顺序。测试名称指实际断言内容；运行结果与视觉对照另存 effect-system-final-validation.json。核心契约由前文 P0～P3 的实现/测试说明及本表共同核对，未缩减原有范围。

| 编号 | 计划要求 | 验证依据 |
| --- | --- | --- |
| P0.1 | 提取 `layered_glow` 的完整行为清单：正文前后配色与边框、两层辉光、增强时钟、整音节缩放、ruby、LEAD 分支、两阶段扫色、边缘补偿和淡入淡出。 | examples/layered_glow.py；docs/layered-glow-before.json、docs/layered-glow-native.json；完整输入 tests/fixtures/layered_glow.ass |
| P0.2 | 保存自包含输入、当前关键帧及事件数量基线；记录现有异常，避免把错误画面作为要求。 | tests/fixtures/layered_glow.ass；tools/capture_layered_glow.py；历史与原生报告记录字体、帧哈希、事件数 |
| P0.3 | 以本文声明式草案为起点，补齐逐字位移、并行扫色用例，验证组件结构、选择器与领域行为可以复用。 | examples/staggered_path.py、examples/parallel_tracks.py；test_effect_properties.py 的 parallel_sweep 基线断言 |
| P0.4 | 固定 compose/configure 生命周期、组件默认样式、声明顺序、选择器范围和便捷访问接口；记录缺省时间及跟随语义。 | effect.Effect._prepare；test_effect_lifecycle.py 的顺序、字号、跨行副作用及缺省跟随断言 |
| P0.5 | 固定 Transition、内置曲线、直接函数和可选关键帧接口；用不对称放大/保持/缩小、提前放大和延后恢复用例检验定制能力。 | test_effect_scale.py 的 asymmetric_peak、explicit_offsets、configurable_linear_return、nonlinear_keyframe 测试 |
| P0.6 | 明确选择器、时间绑定、属性冲突和跟随关系的最小接口，不先固定类名或链式写法。 | docs/effects.md；test_effect_queries.py、test_effect_properties.py、test_effect_follow.py |
| P0.7 | 固定 Python StyleSheet/rule、状态样式、范围类标记及直接覆盖语义；明确两种 Document 输入均不要求额外 ASS 分色字段。 | stylesheet.py；test_effect.py 的 three_input_paths、cross_line_isolation；tools/validate_effect_system.py |
| P1.1 | 实现 Effect、Lyrics、Body、Ruby、Halo 的最小声明式生命周期，绑定已有歌词与布局，不复制源数据。 | effect.py 的 Effect/Component/Lyrics/Body/Ruby/Halo；test_effect_lifecycle.py |
| P1.2 | 实现类型、ID、类标记选择器及正文/ruby/音节便捷访问，验证重复 ID、单项查询失败及跨行状态隔离。 | stylesheet.Selector；test_effect.py 的 query_errors；test_effect_queries.py |
| P1.3 | 从现有 recipe 构建流程中抽出来源到布局目标的映射。 | _compiler._prepare_targets 与 targets.layout_targets；recipe.py 只保留来源/上下文/配置值 |
| P1.4 | 统一解析 ASS 与直接构造 Document 的来源入口；在布局前支持正文范围标记与样式配置，布局后验证字形簇边界。 | render.py 统一 import_karaoke 并在布局前 _prepare；test_effect.py 三入口、布局前配置和 cluster_split |
| P1.5 | 提供行、单元、segment、字形簇和 ruby 的遍历与选择，保留不可独立绘制字形的诊断。行通过每行绑定的 self.source 访问；字符候选在布局后按完整字形簇验证和绑定。 | behaviors.TargetSelection；test_effect_selection.py 与 test_effect_source_edges.py |
| P1.6 | 建立稳定目标身份、分组与装饰依附关系；来源追踪贯穿后续展开。已验证多段正文、两层装饰和 ruby 经扫色及采样后保留原始来源地址。 | targets.VisualTarget、properties.PropertyTarget；test_effect_context.py、test_render.py 的动态来源测试 |
| P1.7 | 明确空文本、静态单元、多 segment 单元及 ruby 组的选择结果。空正文不输出装饰，静态单元无演唱时钟，ruby 排版组不合并来源段；零宽正文附带读音明确诊断。 | test_effect_source_edges.py 的 empty/static/ruby_layout_group；test_effect_selection.py 的空集合与多段元数据 |
| P2.1 | 实现 Python 样式表、有限选择器优先级、唱后状态、属性级覆盖、INHERIT/UNSET 及直接 `.style` 设置；验证 ruby 继承和动画冲突边界。 | stylesheet.py；test_effect.py、test_effect_target_styles.py、test_effect_halo_states.py（含四种显式继承路径） |
| P2.2 | 定义并导出常用 `Color` 常量，固定其 RGB 值，统一特效系统颜色参数对 `Color` 和 `#RRGGBB` 的转换与校验。 | colors.py 与 __init__.py；docs/effects.md 的固定 RGB 表 |
| P2.3 | 验证内置常量、同值字符串和 `Color.hex()` 的结果一致；无效颜色在输入边界报错，透明度仍独立配置。 | test_effect.py 的颜色类型、同值输入、非法输入；stylesheet._value 和 Halo 边界校验 |
| P2.4 | 实现 sweep()、on_singing()、fade() 的领域入口，自动解析目标时间与关联装饰；保留显式时间、轨道和曲线配置。 | effect._Text.sweep/fade、behaviors.TargetSelection.on_singing；test_effect_properties.py |
| P2.5 | 统一显示窗口、演唱包络、演唱进度和扫色到达触发的绑定入口。 | properties.resolve_interval、behaviors.bind_property；test_effect_scale.py、test_effect_properties.py |
| P2.6 | 验证属性初值、keep 终值保持、pulse 恢复、ruby 隐藏连带装饰以及配置冲突的确定性。 | test_effect_scale.py 的 reset/keep/zero_duration；test_effect_selection.py 的 hidden_ruby；test_effect_halo_states.py |
| P2.7 | 复用已有 pulse 规划，支持整体缩放、逐字独立缩放及扫到触发。 | behaviors 的到达时间规划与统一属性规则；test_effect_scale.py、test_effect_properties.py 的 arrival/repeated_round |
| P2.8 | 实现常量、线性、分段曲线和自定义函数的属性描述。 | properties.py；test_effect_scale.py、test_native_composition.py、test_effect_context.py |
| P2.9 | 实现线性、平滑、缓入/缓出及可配置往返曲线，区分 rate 返回插值进度与属性函数返回实际值；允许直接传入 lambda。 | properties 的 rate/Transition/there_and_back；test_effect_scale.py 的函数等价与时间参数校验 |
| P2.10 | 实现 animate() 的显式相对时间区间，以及可选关键帧；pulse 等快捷效果统一展开到同一属性模型。 | behaviors.animate；test_effect_scale.py 的相对时间、关键帧、pulse；test_effect_properties.py 的 Halo 关键帧 |
| P2.11 | 验证往返峰值与保持时长、不同上升/下降曲线、函数端点、区间外保持、超调约束、短音节时间倒序和函数异常来源。 | 上述 scale 测试覆盖保持段、f(1)、倒序、超调报错；test_effect_render_contract.py 覆盖异常源和 cause |
| P2.12 | 明确基础字号在布局前生效，验证共同中心/逐字中心缩放，以及正文、ruby、辉光、裁剪的跟随与退出跟随。 | Effect._prepare 字号处理；test_effect_lifecycle.py；test_effect_scale.py 与 test_effect_follow.py |
| P2.13 | 实现属性冲突检测、显式合成规则和关联对象的变换传播。 | behaviors.check_motion_conflicts、follow.py、lowering.py；test_native_composition.py、test_native_offsets.py |
| P2.14 | 覆盖停顿、零时长、重复演唱、并行轨道与窗口截断的行为测试。 | 多段间隙/零时长/重复演唱/并行/窗口：test_effect_selection.py、test_effect_properties.py、test_native_singing_progress.py |
| P3.1 | 支持多层辉光、稳定叠放顺序、独立属性及正文/ruby 的不同参数。 | effect.py 的 Halo 展开；test_effect_halo.py 的双层顺序和 ruby_width；test_effect_blur.py |
| P3.2 | 实现整目标装饰与随扫色裁剪装饰的明确选择；`Halo(clip="none" / "sung")` 复用来源目标与遮罩编译，重叠轨道取覆盖并集。 | Halo.clip 与共用 _compile_targets；test_effect_follow.py；tools/validate_halo_clip.py |
| P3.3 | 将特效定义统一展开为输出计划，移除作者侧去重与裁剪修补需求。 | examples/layered_glow.py、whole_glow.py、staggered_path.py、dynamic_effect.py、recipes.py 均以组件/行为创作 |
| P3.4 | 为可表达属性变化生成原生变换，为其余变化接入采样预算与诊断。 | lowering.py；test_native_offsets.py、test_native_composition.py、test_native_singing_progress.py；原生透明度静态参考 |
| P3.5 | 任意 lambda 不假定可解析为原生变换；通过统一求值入口采样，复用成本预检与精度说明。验证内置曲线、等价函数及关键帧在约定容差内结果一致。 | 任意函数延后求值：test_effect_native_opacity.py、test_effect_render_contract.py；composed-product-validation.json |
| P3.6 | 保留已有来源元数据、输出上限、字体能力检查和裁剪精度契约。 | render.py/sampling.py/ass_output.py；test_render.py、test_sampling.py、test_characters.py、test_ass_output.py |
| P4.1 | 按 compose/configure 的声明式组件方式重写 `layered_glow.py`，保留全部已确认行为；LEAD 分支直接选择配置，不先添加再撤销行为。 | LayeredGlow.compose/configure；LEAD 分支不创建 pulse；13 帧 capture 与 native 基线一致 |
| P4.2 | 特效定义部分以不超过 40 行有效 Python 代码为可用性目标，排除导入、CLI 和输入样式配置；不得靠塞入专用隐藏 helper 达标。 | LayeredGlow 整类 34 个非空物理行（含类/方法声明、文档字符串及括号），无专用隐藏 helper |
| P4.3 | 迁移 `whole_glow.py` 与 `staggered_path.py`，验证装饰和自定义运动可复用同一机制。 | WholeGlow 与 ArcWave；capture_composed_examples 对照事件哈希及帧；作者脚本不访问输出层 |
| P4.4 | 验证双层辉光、ruby 跟随、逐字与整组缩放、并行扫色的交叉组合；五组场景对照原生/关键帧/等价函数，记录裁剪坐标与像素容差，见 composed-glow-validation.json。 | composed_glow.py 五个场景 × native/keyframes/function/product/additive × 八帧；test_effect_combinations.py |
| P4.5 | 实现本文一行三色交替示例，以单 segment 六字验证解析 ASS、直接构造 Document 和显式 items 三种入口；增加直接覆盖等价性与跨行隔离检查。 | alternating_colors.py；test_effect.py 的 3 输入、直接覆盖与跨行隔离；三色视觉工具 |
| P4.6 | 保存三色示例起唱、颜色交界及唱后关键帧，核对预期颜色、原始演唱区间和无分色基线布局；记录实际验证结果。 | 三色工具六个关键帧逐字颜色断言、无分色布局对照及 segment 不变断言；四输入逐像素一致 |
| P4.7 | 对比起唱、变速节点、音节中间、结束及退场关键帧，检查事件数和求值成本；解释可接受的差异。 | layered/whole/arc/song/dynamic/recipes 迁移报告；benchmark-migration.json 记录成本及事件增长 |
| P5.1 | 让 `render_karaoke` 和 CLI 的 Python 效果入口支持新特效系统，保持输入处理与特效定义分离。 | render_karaoke 与 __main__.py；test_cli.py 的 Python 脚本、默认命令、错误、读音与重复 owner 集成 |
| P5.2 | 将仍有价值的预设实现为通用组合，不保留第二套独立效果引擎。 | examples 的 LayeredGlow/WholeGlow/ArcWave/DynamicGlow/SongEffect/RecipeEffect 与 CLI 预设均使用 Effect |
| P5.3 | 功能完整替代后移除旧的作者侧实现，按原计划不增加兼容包装；保留有明确用途的底层扩展入口。 | recipe.py 旧类删除；__init__.py 无旧导出；test_effect_lifecycle.py 的不存在断言和禁止依赖桩 |
| P5.4 | 更新 README、示例和[特效指南](effects.md)，说明组件结构、代码层样式表、层叠覆盖、范围分色、两种 Document 输入、选择器、默认样式、领域行为、进阶时间配置、跟随、合成和后端边界；指南明确区分当前能力与剩余迁移任务。 | README.md、docs/effects.md、docs/ass-builder-replacement.md 当前入口；相对链接存在性检查 |
| P5.5 | 补充内置颜色及其 RGB 值对照表；示例展示常用颜色常量与命名自定义配色，同时保持原画面的准确颜色。 | colors.py 12 个固定 RGB 常量；指南颜色表；layered_glow.py 保留三个精确自定义色值 |
| P5.6 | 运行相关单元测试、集成测试及视觉验证，更新交付审计与验证记录。 | effect-system-final-validation.json；全套 pytest、Ruff、Black、diff 检查与记录的视觉验收命令 |

## 最终运行结果与边界

最终报告：[effect-system-final-validation.json](effect-system-final-validation.json)。485 项 pytest 通过，覆盖 CLI 子进程和重复 owner；Ruff、Black 与 git diff --check 通过。LayeredGlow 全类仅 34 个非空物理行（包括文档字符串、声明和括号）。

删除旧入口后的关键视觉复验命令（输出目录可替换）：

```sh
python -m tools.capture_layered_glow /tmp/final-layered-glow-inherit --compare docs/layered-glow-native.json
python -m tools.capture_composed_examples /tmp/final-composed-examples-inherit --compare docs/composed-examples-native.json
python -m tools.capture_migrated_examples /tmp/final-migrated-examples
python -m tools.validate_effect_system /tmp/final-authoring-colors-inherit --font /usr/share/fonts/sarasa-gothic/Sarasa-Regular.ttc
python -m tools.validate_composed_glow /tmp/final-composed-glow-inherit --offsets
python -m tools.validate_native_opacity /tmp/final-native-opacity
python -m tools.validate_halo_clip /tmp/final-halo-clip
python -m tools.validate_effects /tmp/final-effects
python -m tools.validate_adjacent_units /tmp/final-adjacent
python -m tools.validate_glow_strategies /tmp/final-glow-strategies
python -m tools.validate_parallel_paints /tmp/final-parallel --decorated
```

layered 的 13 帧及 whole/arc 的事件和画面基线一致；song/dynamic/recipes 的 36 帧与迁移基线逐像素一致；三色四入口六帧一致。组合矩阵、独立原生透明度和 Halo clip 报告与已有基线完全一致。后端综合、相邻单元、辉光策略和装饰并行配色分别通过 1063、44、32、57 项检查。

审计发现并修复的最后缺口：Halo 显式 INHERIT 原来读取白色默认值，现按其正文/读音目标分别读取对应状态填色；四条测试覆盖构造声明、样式规则、仅唱后继承及 UNSET。修改后重新运行全量测试、核心示例和组合基线。

保留的边界均为计划明确允许的能力限制：不解析 ASS 私有分色协议；不支持任意混合字号整形；不承诺编辑来源后的永久 ID；任意函数按离散样本求值，不承诺样本间空间误差；ASS 不同模糊色的硬裁剪接缝仍诊断。复杂轨道的完整 paint 栈使用显式 TrackStyle；Halo 的 INHERIT 读取目标样式，不复制轨道 paint 栈。当前视觉结果针对已记录字体和本机 libass，不宣称跨字体或跨平台逐像素一致。事件数变化已在各迁移报告及 benchmark 中记录，不将层数减少当作设计正确性的条件。
