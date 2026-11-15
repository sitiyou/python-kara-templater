# 标准 ASS 动画引擎 TODO

设计与验收依据见 [计划](ass-animation-engine-plan.md)。P0–P5 首版工作已完成，逐项证据和明确边界见 [验收索引](ass-animation-engine-acceptance.md)。[进度记录](ass-animation-engine-progress.md)、[案例卡](ass-animation-engine-cases.md)及下方各批次备注保留历史状态；旧备注的“仍待验证”不替代最终索引。

## P0 需求与基线

- [x] 为 E01–E12 建立案例卡：画面、参数、对象、时间关系、关键时刻和边界。（第四十四批核对；[案例卡](ass-animation-engine-cases.md)逐例规定画面、时序、预算与限制；原型和验收状态分开记录。）
- [x] 准备自有测试歌词与可分发字体、路径资产；记录参考出处及依赖。（第五十八批；案例卡“固定资产清单”、tools.validate_engine_assets 与 engine-assets-validation.json，核对六份字体、许可、子集覆盖、MANIFEST.in 和十二例源码哈希；外部机制出处保留在计划中。播放端字体选择和最终视觉验收单独处理。）
- [x] 核对扩展 templater 与非标准渲染标签，记录可迁移到标准 ASS 的算法。（第一百零三批；[源码核对](template-standard-ass-audit.md)读取七份固定提交模板，区分 Lua/ILL/word/mixin 生成扩展与播放标签，记录曲线/分片/轮廓/书写的标准输出替代；十二例实际标签清单归档，不扩大为任意 Lua 兼容。）
- [x] 为每例准备可播放参考或人工明确的预期；标明无法复现的部分。（第一百零一批；[全案例核对](case-interface-audit.md)连接十二例明确目标及独立参考，区分自有机制夹具与外部作品复刻，保留截图时序、笔顺、连续采样和边缘差异的限制。）
- [x] 固定分辨率、帧率或时间戳、字体、背景和渲染器版本。（第一百零二批；[当前基线](engine-baseline.md)汇总画布、采样/播放时钟、字体与背景哈希及实际渲染器版本。十二例当前保存文件与四背景/整曲片段报告哈希一致，字体字节一致。）
- [x] 测量参考输出成本，确定每例及整曲的质量和成本预算。（第一百零二批；[当前基线](engine-baseline.md)汇总十二例和 180 秒整曲成本、原定质量/预算及耗时口径；当前整曲重编译与既有播放报告文件哈希一致，120104/556/62539000，未调高预算。）
- [x] 审计已有模块，记录复用、适配与替换范围，以及旧 API 的行为基线。（第六十一批；计划“当前模块复用与适配审计”与 track-migration.md，逐入口核对原生事件/可编辑对象/覆盖率输出，明确 render_karaoke 的旧插入路径和保留的 Effect 能力；旧基线为 v0.1.0 恢复测试及差分报告。）
- [x] 固定首版能力范围、高成本可选能力和明确不支持的语义。（第六十七批；ass-engine-capabilities.md 对照公共接口与出口诊断，分清普通 Scene、整组 RGBA 和覆盖率语义，列明原生/采样策略及预算。能力范围不替代全例视觉与发行验收。）

退出证据：案例卡、参考资源清单、基线报告、能力矩阵与迁移审计表。

- [x] 为 E11 明确填充、描边、辉光的交界目标，建立连续播放和不同背景参考。（第九十二批；[E11 验收](e11-acceptance.md)给出独立宽度、颜色、透明度和整字恒定辉光语义，四背景完整参考及连续播放通过；前沿向辉光扩散属于策略比较的单独模式。）
- [x] 为 E04 增加樱花飘散变体，确定数量、漂移、旋转和发射时机。（第六十三批完成可见扫色接入，第六十四批校正实际过渡中心与出生位置；scene_sakura.py 固定 18 曲线+6 直线独立花瓣和 12 前沿触发花瓣，三秒寿命；既有几何、发射捕获及合成参考与更新后的四背景报告。）
- [x] 为 E12 建立行内与独立导唱符案例，覆盖文本和矢量图形内容。（第六十五批核对；scene_lyric_cues.py 展示行内条形/数字与独立文字，scene_cues.py 展示用户矢量工厂；cues-validation.json 验证独立文字和组移动隔离，custom-cue-validation.json 补充独立矢量的 218 项几何/透明度检查。此项完成案例建立，所有行内元素的绝对像素参考仍由 P2 视觉验收追踪。）

- [x] 以 v0.1.0 建立模板、code、变量、修饰符与 helper 的兼容矩阵和输出基线。（第七批，见[兼容矩阵与证据](legacy-templates.md)。）

## P1 公共接口与契约

- [x] 用候选接口编写 E01–E12 的作者侧原型，先验证表达能力。（第四十四批核对；examples/scene_whole_song.py 的 CASES 明确映射十二例；新增文件往返测试逐例编译，不以表达能力代替视觉达标。）
- [x] 确定文字、路径、组的身份、复制、所有权、寿命与来源契约。（第四十四批核对；scene.py、scenes.md 的几何/组/来源与编译保留章节；test_scene.py 验证重复身份、复制、寿命交集和 owner 保留。）
- [x] 确定字符范围、塑形簇、词、音节、片段和注音的选择语义。（第五十三批；scenes.md 的“歌词选择与来源范围”逐项映射到 DocumentLyrics、DocumentLayout、LyricLayout，明确 code point/簇、续唱、注音来源及单行限制；对应三组回归测试。此项是语义契约，不代表全例视觉验收。）
- [x] 确定统一时间单位、绝对与局部时间、时间锚点和旧接口适配。（第四十四批核对；scenes.md 时间契约与 animation-timelines.md；Scene 使用秒，Line 保留毫秒，旧前端通过明确适配进入 Scene。）
- [x] 定义局部与全局坐标、变换中心、矩阵顺序、跟随和循环依赖诊断。（第五十七批；scenes.md“坐标与变换中心速查”及世界引用契约，scene_evaluation.py 与仿射/遮罩/引用回归；世界状态覆盖次序、组原点、显式 pivot、寿命端点和延迟闭环规则均已核对。）
- [x] 支持带符号缩放、镜像、零面积状态、局部遮罩与测量缩放独立保存。（第十五批；`tests/test_scene_affine.py`、`tests/test_group_masks.py` 与 [标准 ASS 验证](scene-mirror-validation.json)。）
- [x] 实现保持方向的非等比组缩放、子旋转与剪切矩阵组合，以及文字/路径/局部遮罩的仿射降级。（第十三批；`tests/test_scene_affine.py` 和 [实际渲染](scene-affine-validation.json)。镜像/退化状态在第十五批补充，共享组遮罩的已实现范围见第十四批。）
- [x] 定义属性能力、关键帧、回调、顺序、并行、错峰及重复协议。（第五十七批核对；scene_animation.py 的 StateAnimation/StatePatch、SceneTimeline、StateKeyframe，与 scenes.md“时间和属性”；test_scene.py/test_scene_keyframes.py/test_writing_example.py 验证声明通道、冲突、接续、局部断点和重复。旧 Track 时间线保持明确独立适配。）
- [x] 明确属性冲突、接续、叠加、保持与释放，以及透明度组合语义。（第四十四批核对；scenes.md 明确逐子对象透明度与显式整组 RGBA 的区别；test_scene.py 验证冲突、接续、释放和声明写集合。）
- [x] 定义对象生成、随机种子、历史状态引用和可跳转求值契约。（第四十四批核对；particles.py、object_references.py；test_particles.py/test_scene_references.py 验证键控随机、历史、复制与乱序求值。）
- [x] 实现显式对象引用图、跨父组世界状态跟随、延迟取样、复制重定向与回调前循环检查。（第十一批，见 [场景契约](scenes.md#对象引用与世界坐标跟随)、引用回归与 [libass 报告](scene-follow-validation.json)；仿射组合已在第十三、十五批补充，第五十七批核对状态。）
- [x] 编写类型正反用例，验证公开接口不泄漏 Any/Unknown。（第四十四批核对；tests/typing 的 assert_type 正例与 tools.check_scene_types 的 24 个错误扩展反例均通过；全仓库 ty 通过。）
- [x] 对照全部案例审查原型缺口，确定实现接口与模块依赖。（第一百零一批；[全案例核对](case-interface-audit.md)逐例对应作者接口、模块、验收和保留边界。十二例当前公开接口编译及源码快照一致，13 项文件/Document 等价回归、24 个类型反例、Ruff、ty 通过。）

退出证据：作者侧原型、契约说明、类型检查结果和能力覆盖表。

- [x] 定义导唱符内容工厂、布局占位、时间锚点、倒计时和自定义动画接口。（第四十四批核对；cues.py 的 CueFactory/CueContent/CuePreset；scene_cues.py 自定义图形与 test_scene_text.py、test_lyric_cues.py。）
- [x] 比较输入标记载体，确定命名空间、版本、作用域、转义及类型化参数。（第五十四批；scenes.md“输入标记载体与 v1 契约”比较注释块、标准 override、事件字段和 Python 配置；tests/test_document_text.py 补充引用/Unicode/跨行作用域/原始偏移回归。v1 只引用类型化 CuePreset，不执行表达式。）
- [x] 定义代码构造与标记导入的等价性，以及保存和再次生成规则。（第四十四批核对；test_scene_text.py/test_lyric_cues.py 验证标记与直接构造相同，test_scene.py 验证 owner 再生成，新增文件往返回归。）

- [x] 定义统一 Document 的标准数据、文本标签作用域、扩展元数据和来源接口。（第四十四批核对；ass.py、document_text.py、document_lyrics.py 及 scenes.md；标准记录保留，扩展标记为类型化数据，来源由 EventOrigin/SourceRef 记录。）
- [x] 定义行样式、内联颜色、样式重置、Python 配置和动画的覆盖优先级。（第四十四批核对；scenes.md 明确 style → 标签/重置 → 作者对象 → 动画/材质；test_document_text.py/test_document_lyrics.py 的作用域回归。）
- [x] 设计旧模板兼容前端、类型化原生 ASS 事件节点及新旧混用规则。（第七批，见[兼容矩阵与证据](legacy-templates.md)。）

## P2 最小端到端核心

- [x] 将 PreparedTrack 覆盖率适配接入公开 Document 前端，保留选择、来源、owner 再生成及可编辑对象。（第三十三批；`prepare_track_coverage`、`tests/test_track_coverage_frontend.py` 与 [固定注音示例报告](scene-coverage-tracks-validation.json)。不同透明度降级的舍入边界见迁移说明，全案例与最终发行验收另行继续。）

- [x] 公开 Document + ObjectGroup 的覆盖率材质出口，统一声明断点、采样、事件合并与最终预算；增加固定示例和真实 libass 连播/跳转验证。（第三十二批；`compile_coverage`、`examples/scene_coverage.py`、[报告](scene-coverage-validation.json)。PreparedTrack 公共适配与全案例验收另行继续。）

- [x] 实现对象与组、歌词绑定、布局和几何查询。（第七十批；scene.py、scene_text.py、scene_lyrics.py 及布局/簇/注音回归，详见 [P2 核心核对](ass-engine-core-audit.md)。完整案例视觉验收仍独立保留。）
- [x] 实现类型化属性、动画编排与任意时刻求值。（第七十批；scene_animation.py、scene_evaluation.py 及关键帧/引用/乱序访问回归，详见 [P2 核心核对](ass-engine-core-audit.md)。完整案例视觉验收仍独立保留。）
- [x] 建立共享场景计划及来源追踪，贯穿生成对象与输出事件。（第七十批；EventOrigin/SourceRef、ObjectReport、owner 事件标记及旧模板/文件往返回归，详见 [P2 核心核对](ass-engine-core-audit.md)。完整案例视觉验收仍独立保留。）
- [x] 实现标准 ASS 原生表达与能力检查，明确不支持组合的诊断。（第七十批；静态/move/可选原生 Tween 与采样策略、能力拒绝及手写 ASS 对照；复杂优化仍列 P3，详见 [P2 核心核对](ass-engine-core-audit.md)。完整案例视觉验收仍独立保留。）
- [x] 在展开前预检预算，并在生成过程中执行实际预算限制。（第四十四批核对；test_scene.py 的回调前预算、实际字节/峰值/路径限制，以及 compile_coverage 的独立预算回归；超限不自动降质。）
- [x] 打通导出、实际 ASS 预览、关键帧检查和诊断流程。（第七十批；示例 CLI、validate_scene_core 实际 libass 预览/连播/跳转/策略预算报告与错误来源回归，详见 [P2 核心核对](ass-engine-core-audit.md)。完整案例视觉验收仍独立保留。）
- [x] 按案例卡完成 E01、E02、E06、E12，记录质量与成本。（第七十九批；[E01](e01-acceptance.md)、[E02](e02-acceptance.md)、[E06](e06-acceptance.md)、[E12](e12-acceptance.md)分别汇总独立参考、全部输出状态、四背景播放与预设预算；范围为案例卡固定 libass 首版。）
- [x] E01 正文/注音、扫色、描边与两层辉光达到约定门槛。（第七十九批；124 输出区间、四背景 516 帧完整 RGB 差 0，详见 [逐项验收](e01-acceptance.md)。）
- [x] E02 固定错峰动画达到约定 libass 门槛。（第七十六批；[逐项验收](e02-acceptance.md)覆盖全部输出区间、文字/描边及装饰参考、含淡出透明度的四背景合成、播放与预算；P2 的 E01 和 P5 仍继续。）
- [x] E06 固定词背景与导唱组合达到约定 libass 门槛。（第七十五批；[逐项验收](e06-acceptance.md)对应全部状态的几何/颜色/采样/四背景/预算；P2 其余案例与 P5 发行继续。）
- [x] E12 固定导唱案例达到约定的 libass 质量与成本门槛。（第七十三批；[逐项验收](e12-acceptance.md)汇总布局/颜色/时间/四背景/预算/自定义工厂证据；其他三例仍未整体验收，跨播放器与最终发行仍列 P5。）
- [x] 通过相关测试、Ruff 与 ty。（第七十九批；核心、文件往返、原生 Tween、旧模板和导唱相关 108 项回归通过；全仓库 Ruff、ty 通过。）

退出证据：四个可运行示例、导出 ASS、视觉报告、预算报告与检查结果。

- [x] 实现标记解析和来源诊断，验证导唱符不改变原始歌词时间与注音。（第九批：`bind_lyric_cues`、`tests/test_lyric_cues.py` 与实际 libass 示例；原始输入标记保留于源 Comment。）
- [x] 验证自定义标记被编译消费，输出播放不依赖扩展标签。（第九批：`bind_lyric_cues`、`tests/test_lyric_cues.py` 与实际 libass 示例；原始输入标记保留于源 Comment。）

- [x] 打通 ASS 文件 → Document → 框架 → ASS，验证直接构造 Document 的等价性。（第四十四批核对；tests/test_scene_document_roundtrip.py：十二例源 Document 文件往返输出字节相同；另在布局绑定前加载含颜色/重置/注音/导唱的文件并比较输出。）
- [x] 接入旧模板最小兼容路径，保留模板/code 记录与未匹配事件。（第七批，见[兼容矩阵与证据](legacy-templates.md)。）
- [x] 支持逐字颜色和重置标签，验证作用域、文本范围和注音关联。（第八批：DocumentLyrics、scene_lyrics 与 13 项语义/布局回归；当前为单行绑定，组合限制见场景文档。）

## P3 路径 遮罩与对象生成

- [x] 核对通用 Tween/fade 的原生 ASS 优化范围。（第八十三批；[范围核对](ass-engine-native-tween-audit.md)逐项列明顺序/并行/保持的原生 t、复杂组合采样及默认语义；49 项相关回归和当前固定示例 300 帧/8 次跳转通过。显式 native_tweens 不冒充默认采样的逐像素等价优化。）

- [x] 实现共享组遮罩的世界坐标、组出生时钟、复制、动态采样及正向矩形/凸边界求交，保留来源与预算。（第十四批；`tests/test_group_masks.py`、[实际渲染](scene-group-masks-validation.json)。一般闭合非凸交集和反向差集在第十六批补充。）

- [x] 实现路径采样、路径布局、曲线运动、旋转与倾斜。（第八十二批；[逐项核对](ass-engine-path-sampling-audit.md)对应 Contour/Polyline、layout_path、MoveAlong、仿射降级与组合回归；明确参数进度、近似弧长及切线限制。）
- [x] 实现矩形和矢量遮罩，验证移动、旋转与缩放时的坐标关系。（第十批：screen/local 坐标、动态 GeometryAnimation、颜色场求交；测试与真实 ASS 报告见场景文档，skew 与共享组遮罩分别在第十三、十四批扩展，通用布尔组合在第十六批补充，曲线仍使用显式细分近似。）
- [x] 实现对象复制、碎片、残影和粒子，明确出生与持续跟随行为。（第五批：`particles.py` 与 `tests/test_particles.py`；显式区分出生快照、本地历史和纯函数持续跟随，通用引用图在第十一批接入，见 `tests/test_scene_references.py`。）
- [x] 实现空间渐变和逐字属性分布。（第六批：`paint_fields.py`、`scene_gradient.py`，当前为屏幕坐标颜色场；像素、预算与类型证据见进度记录。）
- [x] 实现确定性采样、边界切分、等价事件合并与复杂度报告。（第八十二批；[逐项核对](ass-engine-path-sampling-audit.md)对应变化区间、全部断点来源、厘秒中点、同对象相邻事件合并与预算报告；相关 110 项回归、Ruff、ty 通过。）
- [x] 验证跳转、重复构建和采样顺序变化的一致性。（第四十四批核对；四背景全案例报告、E08 修复后重验、当前整曲报告，以及 test_scene.py/test_scene_references.py/test_particles.py；纯回调契约仍要求作者遵守。）
- [x] 完成 E03、E04、E05、E09、E11，以及遮罩与组变换组合用例。（第九十五批；五例逐项验收与 [组合核对](ass-engine-mask-combinations.md)齐备，44 项仿射/遮罩/布尔回归、三个示例当前连播/跳转和预算通过；多策略比较仍单列。）
- [x] E04 固定樱花发射与完整合成达到约定 libass 门槛。（第九十四批；[逐项验收](e04-acceptance.md)汇总独立歌词/游标、36 片花瓣、出生捕获、重叠合成、播放与预算；P3 组合及策略比较继续。）
- [x] E11 固定柔和扫色达到约定 libass 门槛。（第九十二批；[逐项验收](e11-acceptance.md)明确 24/36 px 填充/描边及恒定整字辉光，全部状态四背景完整 RGB 差 0，播放和预算通过。）
- [x] E09 固定渐变与残影达到约定 libass 门槛。（第九十一批；[逐项验收](e09-acceptance.md)汇总上下行独立/完整 RGB 对照、四背景播放、时间语义与预算。）
- [x] E03 固定圆弧与两轮高亮达到约定 libass 门槛。（第八十四批；[逐项验收](e03-acceptance.md)汇总 198 时刻/138 状态、独立解析位置与注音变换、四背景颜色/播放和预算；其他案例继续。）
- [x] E05 固定碎片聚合达到约定 libass 门槛。（第八十一批；[逐项验收](e05-acceptance.md)汇总全部局部状态几何/alpha、四背景重叠合成、完成态原生文字、播放和成本；P3 其他案例继续。）
- [x] 通过视觉、预算、相关测试、Ruff 与 ty。（第九十七批；五例与组合证据见本节逐项链接，扫色策略比较完成；当前全套 1094 项测试、19 项子测试以及全仓库 Ruff、ty 通过。其他播放器及发行验证仍在 P5。）

退出证据：五个示例及樱花变体、组合用例、确定性检查和质量成本报告。

- [x] 比较柔和扫色的分条、图层和显式栅格策略，验证色差、接缝与成本。（第九十七批；[四背景比较](sweep-strategies-comparison.md)含 320 帧、240 项相对比较和 60 项覆盖检查。默认分条；叠层边缘增加、显式栅格成本及着色后模糊的不同语义已说明。）
- [x] 实现樱花矢量粒子示例，验证独立与扫色触发、原生与采样输出成本。（第六十四批；test_sakura_example.py 验证可见颜色变化与游标轨迹对应实际过渡中心，包含边界外的半宽延伸；sakura-validation.json 分项记录直线 6 条 native-move、环境曲线 2718 条、触发曲线 1812 条 sampled 事件；完整示例 14805 条，仍在案例预算内。）

## P4 高级几何

- [x] 提供保持来源与布局对应关系的文字转路径接口。（第四批实现与定向验证，见[进度记录](ass-animation-engine-progress.md)。）
- [x] 实现路径细分、必要的布尔操作和轮廓扰动。（第四批凸边界求交；第十六批补充闭合填充路径的交集/并集/差集/异或及非零绕向验证，见[进度记录](ass-animation-engine-progress.md)。）
- [x] 支持用户提供的有序书写路径、路径显露与笔尖跟随。（第四批实现与定向验证，见[进度记录](ass-animation-engine-progress.md)。）
- [x] 定义形状插值的轮廓匹配、孔洞及不匹配处理。（第四批实现与定向验证，见[进度记录](ass-animation-engine-progress.md)。）
- [x] 对高复杂度几何执行预算检查，标明采样近似与失败原因。（第四批实现与定向验证，见[进度记录](ass-animation-engine-progress.md)。）
- [x] 完成 E07、E08、E10，核验参考资产和标准 ASS 输出。（第八十九批；[E07](e07-acceptance.md)、[E08](e08-acceptance.md)、[E10](e10-acceptance.md)各自具备独立几何/颜色、全部输出状态、四背景播放和预算证据。）
- [x] E08 固定书写及笔尖合成达到约定 libass 门槛。（第八十九批；[逐项验收](e08-acceptance.md)保留连续轨迹与采样目标的误差区别。）
- [x] E10 固定孔洞/字形插值达到约定 libass 门槛。（第八十七批；[逐项验收](e10-acceptance.md)汇总全部状态几何、连续误差界、四背景颜色/播放、拓扑失败与预算；E08 继续。）
- [x] E07 固定轮廓扰动达到约定 libass 门槛。（第八十五批；[逐项验收](e07-acceptance.md)汇总全部状态的孔洞/变形几何、连续公式界、四背景颜色/播放、预算与整曲一致性；E08/E10 继续。）
- [x] 通过视觉、预算、相关测试、Ruff 与 ty。（第八十九批；三例独立验收、书写/路径/文件往返 34 项、布尔/整组栅格 21 项回归及全仓库 Ruff/ty 通过；其他播放器与发行仍在 P5。）

退出证据：三个示例、几何边界用例、限制说明和质量成本报告。

- [x] 提供显式整组 RGBA 合成、合成后模糊及根透明度的标准 ASS 烘焙接口。（第二十四批；`scene_raster.py`、11 项定向回归和 `scene-composite-validation.json`。Track 覆盖率材质迁移仍待完成。）

## P5 集成 迁移与发布验收

- [x] 将 Track 常用配置适配到统一场景计划，复用公共能力。（第九十八批；[迁移核对](track-scene-migration-audit.md)覆盖 NativeEvent、可编辑对象和覆盖率材质三种出口，共享准备/排版/动画/材质及来源规则；明确采样与不支持的样式边界，相关 93 项测试、16 项子测试通过。）
- [x] 提供 prepare_track_scene 公共入口，迁移正文/注音、布局、属性动画和硬边扫色为可编辑对象，保留诊断与来源。（第二十一批；tests/test_track_scene.py、tests/test_track_preparation.py 与 scene-editable-tracks-validation.json。覆盖率合成及昂贵材质模式仍待迁移。）
- [x] 拆出共享准备阶段，将原生/采样/栅格 Track 输出以带来源 NativeEvent 接入 Scene，并验证新旧入口与混合归属。（第十二批；[迁移范围](track-migration.md#迁移到混合场景)、`tests/test_track_scene.py`；可编辑对象及公共属性/合成迁移仍待完成。）
- [x] 更新 layered_glow 与其他示例，说明有意的视觉变化。（第九十九批；[作者指南](scene-authoring.md)列出 E01–E12 固定入口与修改点，说明 Track Blur、旧 Halo 和独立恒定辉光的差别；layered_glow 补齐入口类型。19 项 CLI/文档回归通过，含实例与子类版本字节相等。）
- [x] 验证跨行对象、双语与注音、多次高亮和独立装饰的组合。（第五十五批；examples/scene_bilingual.py、tests/test_bilingual_example.py 与 [实际播放报告](scene-bilingual-validation.json)。两条源记录、续唱共用正文/注音、世界坐标双目标装饰及独立提示；不扩展为自动多行布局。）
- [x] 验证短音节、零时长、连字、空格、字体回退及错误来源定位。（第五十六批；test_document_lyrics.py 验证 k0/k1/kt 与来源定位，test_scene_text.py/test_characters.py 验证簇、空格及隔离 Fontconfig 下的 Document 回退/缺字；绑定层补充记录/范围/样式并保留异常链。Windows 字体提供器另归发行矩阵，不以 Linux 结果代替。）
- [x] 建立 libass 基线，并记录其他目标播放器的标准 ASS 差异。（第一百零六批；[播放器矩阵](player-compatibility.md)连接当前实测 libass 基线，依据 libass/mpv 官方文档记录字体、描边、颜色矩阵及样式差异；明确 VSFilter/mpv 未做本项目像素验收，不将文档核对冒充实测。Windows 发行仍归发行门槛。）
- [x] 测量整曲事件数、峰值活动事件数、文件大小、生成与播放成本。（第二十二批；固定 180 秒、12 类案例重复组合，见 [机器可读报告](whole-song-validation.json)。该项不替代各效果视觉验收。）
- [x] 将 E06 测量背景框/贝塞尔装饰加入整曲夹具并重新验证。（第三十五批；明确 E01–E12 id/工厂映射，新增十二例单独导出与整曲首轮 3600 帧比较，[新报告](whole-song-validation.json)与[实际预览](images/whole-song-e06.png)。该检查证明组合/播放一致性，独立视觉参考仍待完成。）
- [x] 检查预览与实际导出一致，超预算行为可解释且不静默降质。（第一百批；[核对说明](preview-budget-audit.md)列明落盘 ASS 预览路径和预算失败证据。工具新增导出/预览 SHA-256 与渲染前后字节检查；E11 实测 300 帧/跳转通过，82 项相关回归、Ruff、ty 通过。）
- [x] 完成自定义对象、动画、生成器、采样和预算的使用文档。（第九十九批；[作者指南](scene-authoring.md)提供可执行的类型化对象工厂/纯动画脚本，连接完整契约并说明生成身份、随机通道、时间、断点、报告、预算及昂贵出口；脚本实际生成 400 事件、峰值 4、231226 字节的 ASS。）
- [x] 完成旧接口迁移表与兼容测试，决定弃用范围和时间。（第九十八批；[迁移核对与保留决定](track-scene-migration-audit.md)与旧模板矩阵齐备；当前 23 组 v0.1.0 差分一致。本次保留旧入口，不设移除版本/日期；显式 --templates 的 CLI 变化单独说明。）
- [x] 运行完整测试、Ruff、ty 与发行包验证。（第一百一十一批；当前 Linux 1094 项测试/19 子测试、Ruff、ty 通过；[Linux 修复矩阵](distribution-validation-final-linux.json)与[Windows ABI 矩阵](distribution-validation-final-windows.json)覆盖三个 Python ABI、类型正反例、32+3 示例及两种 CLI。Windows 每 ABI 1093 项/19 子测试通过，1 项 Linux 专用测试跳过；实际宿主为 Wine，范围不扩大为真实 Windows 测试。）
- [x] 从源码包重建 Python 3.12 本地 Linux wheel，在无源码包目录的独立测试工作目录运行 928 项测试、24 个固定 Scene 示例和旧 CLI。（第二十三批；distribution-validation-py312.json。修复后的 manylinux/Windows 矩阵及干净发布产物仍未验收。）
- [x] 使用排除本机缓存及无关许可证的暂存源码包，重建 Python 3.12/3.13/3.14 本地 wheel；每个 ABI 通过 1027 项测试、公开类型和 24 个反例、27 个固定 Scene 示例及旧 CLI，跨 ABI 示例 ASS 哈希相同。（第三十四批；[当前矩阵](distribution-validation-current.json)。本机 wheel 的符号下限为 manylinux_2_38，manylinux_2_28/Windows 修复包仍待验证，不以本地结果替代。）
- [x] 为 E01–E12 逐项附验收证据，汇总剩余限制后完成计划。（第一百一十一批；[总验收索引](ass-animation-engine-acceptance.md)对应公共契约、十二例、整曲、预览、预算、迁移和发行。35 个固定示例在 Windows 三 ABI 字节一致，统一换行后与 Linux 一致；系统字体旧模板位置差异单列。保留采样/边缘覆盖率、昂贵出口、字体、Wine 及播放器验证限制。）

- [x] 完成 v0.1.0 模板兼容矩阵，核对执行顺序、重复应用、保留策略和文件入口。（第七批，见[兼容矩阵与证据](legacy-templates.md)。）

- [x] E01–E12 在黑、白、棋盘和 RGB 渐变背景上各验证 600 帧连续播放与乱序访问一致。（第三十六批；[报告](engine-backgrounds-validation.json)。不替代独立视觉参考。）
- [x] E09/E11 不透明填充与描边内部通过独立 RGB 公式对照。（第三十六批；[报告](case-colors-validation.json)。边缘、辉光及连续时间误差仍待验收。）

- [x] E05 完成态、E07 未变形/恢复态与独立原生文字参考核对 1 像素几何容差，检查 5000 ms 精确结束边界。（第三十七批；[报告](case-geometry-validation.json)。边缘差单独报告；动画中间形状及其他案例仍待验收。）

- [x] E08 笔尖开闭区间与独立曲线弧长参考核对，修复回调遗漏书写断点。（第三十八批；[报告](writing-validation.json)、tests/test_writing_example.py。墨迹覆盖率参考仍待完成。）

- [x] E10 圆环/孔洞和字形 B 的动态几何与独立参考比较，两对象各 55 时刻满足 1 像素容差。（第三十九批；[报告](morph-validation.json)。抗锯齿差单独报告，连续时间误差和其他播放器不在此项结论内。）

- [x] E12 独立标签与手写 ASS 比较，验证歌词组平移时正文、注音、行内提示一起移动且独立提示不动。（第四十批；[报告](cues-validation.json)，29 个边界时刻。绝对布局及所有行内图形参考仍待验收。）

- [x] E02 各字入退场位置/透明度及轨道菱形与独立公式参考核对，共 166 个时刻。（第四十一批；[报告](staggered-validation.json)。边缘和连续时间误差分开报告。）

- [x] E03 圆弧、注音与两轮缩放/高亮对照独立解析参考，核对 98 个时刻并检出重复缩放。（第四十二批；[报告](round-validation.json)。边缘与连续时间限制单独记录。）

- [x] E04 发射表、寿命、出生捕获及实际游标/残影历史位置、直线花瓣位移核对。（第四十三批；[报告](sakura-validation.json)。曲线飘动和重叠合成参考仍待完成。）

- [x] E06 词背景、正文与贝塞尔装饰对照原生测量/手写 ASS 参考，检查保留占位及 padding。（第四十五批；[报告](word-backgrounds-validation.json)。28 项几何检查通过；1 秒前自定义导唱和最终合成不在此结论内。）

- [x] E01 正文/注音前景与独立测量、共享缩放公式对照，覆盖两段演唱及边界共 59 时刻。（第四十六批；[报告](lyric-geometry-validation.json)。辉光/描边/颜色仍需单独验收。）

- [x] 从包含字体修复和容器许可证的新源码包重建 manylinux 2.28 环境的 Python 3.12/3.13/3.14 修复 wheel，逐 ABI 验证 1042 项测试、19 子测试、类型正反例、27 示例与旧 CLI，跨 ABI 哈希相同。（第四十八批；[矩阵](distribution-validation-manylinux.json)。遵守现有 Linux 宿主动态库策略；Windows 修复包仍待验证。）

- [x] E07 演唱中间的轮廓扰动和孔洞与独立公式对照，55 时刻通过，并给出固定公式的连续几何采样界 0.627479 px。（第四十九批；[报告](outline-motion-validation.json)。字体/光栅误差与该时间误差界分开。）

- [x] E08 四笔墨迹的宽度、前缀与曲线形状对照独立密集采样参考，66 时刻通过并检出笔宽翻倍。（第五十批；[报告](writing-ink-validation.json)。边缘、连续曲线界与最终合成分开记录。）

- [x] 为 SceneTimeline.play 开放局部采样断点，验证等待、对象出生和重复排程叠加后的实际显隐边界。（第五十一批；tests/test_writing_example.py，书写示例改用该入口且输出 ASS 哈希不变。该项不替代完整编排协议验收。）

- [x] 提供 Scene 多属性秒制关键帧入口，复用 Tween、冲突检查、断点和重复排程；添加固定 ASS 示例及实际播放报告。（第五十二批；tests/test_scene_keyframes.py、examples/scene_keyframes.py、[报告](scene-keyframes-validation.json)。完整 P1 契约审查仍独立进行。）

- [x] E04 全部 30 片曲线花瓣的位移、收缩、旋转、淡出与独立公式/手写 ASS 对照，覆盖非整厘秒出生。（第五十九批；[报告](sakura-flutter-validation.json)，480 项填充几何与透明度检查；描边及重叠合成另行验收。）

- [x] E04 曲线花瓣补充 480 项描边外轮廓参考与加粗反例。（第六十批；sakura-flutter-validation.json 的 outline_checks，1 像素几何容差；细环抗锯齿覆盖率差另报，不声称像素一致。）

- [x] E04 完整场景与逐对象 source-over 参考比较四背景 24 帧，包含实际重叠和反转顺序反例。（第六十二批；[报告](particle-composite-validation.json)，全帧 RGB 差最多 2/255；几何、连续时间和跨播放器范围分开。）

- [x] E05 运动中全部 12 片的几何与 alpha 对照独立密集轮廓/矩形裁切和标量动画参考。（第八十批；[报告](fragments-validation.json)，全部局部输出区间及出生/结束边界，逐片漂移反例；重叠合成和完整 E05 验收仍待完成。）

- [x] E10 两对象的几何参考扩展到全部输出状态，并计算固定 smoothstep 插值的连续位置误差界。（第八十六批；[报告](morph-validation.json)，各 175 时刻、静态区间证明及带前提检查的控制点位移界；完整颜色与案例验收仍待完成。）

- [x] E08 墨迹参考扩展到全部有内容状态，补充独立解析圆笔尖形状与停笔检查。（第八十八批；[墨迹/笔尖几何](writing-ink-validation.json)与 [518 时刻位置/显隐](writing-validation.json)；连续理想轨迹观察误差单独保留，最终合成仍待验收。）

- [x] E09 逐字配色和三层延迟残影与手写原生 ASS 完整合成对照。（第九十批；[报告](gradient-echoes-validation.json)，四背景 112 帧 RGB 差 0，删除残影反例被检出；上方渐变整层与 E09 最终验收仍继续。）

- [x] E04 歌词绝对布局与填充/描边扫色对照独立原生字形测量和标量颜色公式。（第九十三批；[报告](sakura-lyrics-validation.json)，全部歌词输出状态四背景完整 RGB 差 0；整例验收仍继续。）

## 更新规则

- 勾选任务时记录实现文件、验证命令及证据位置。
- 原型能表达、功能已实现、视觉正确、成本达标分别核验。
- 新需求先进入案例卡与能力矩阵，再评估影响和安排阶段。
- 发现失败保留最小复现，修正实现或明确修订目标后重新验收。
- 只修改文档时检查链接与清单一致性；代码改动执行对应检查。
