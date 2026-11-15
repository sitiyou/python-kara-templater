# 标准 ASS 引擎实施记录

目标保持为计划中的 P0–P5 和 E01–E12，并为全部效果提供直接构造场景、输出 ASS 的示例。当前尚未完成场景编译器与案例验收，不能把输入模型测试当作视觉验收。

## 第一批：Document 文本绑定

实现位于 `kara_templater/document_text.py`，通过 `Document.text_at(record_index)` 调用。文件级 Document 仍忠实保存原始事件；绑定结果保留完整 token、Unicode 文本范围、静态颜色、原始时间标签和导唱标记。范围不是字形簇，后续布局必须显式映射。新增 API 使用秒；旧 Line 时间仍用毫秒。

导唱输入协议为 `{kara:v1 cue id=intro preset=bars placement=inline}`，由 `CueMarker.markup()` 生成，支持带引号的标识符。placement 也可为 independent。作用域为所在事件，offset 为当前位置，id 在同一事件内唯一。未知版本、重复字段、未知参数或非法 placement 带记录索引与文本位置报错。preset 由后续效果注册表解析；此阶段不执行代码，也不消费输出标记。代码构造与解析返回同一种 CueMarker。

选择非反斜杠注释块是为了使源文件可直接保留在普通 ASS 文本内，不与标准 override 名称争用。此格式在本库内完成往返测试；尚未在 Aegisub 编辑器实测，不声称所有编辑器均保留它。

颜色目前支持标准 c/1c/2c/3c/4c 与 r/rStyle。空颜色标签回到当前重置样式。嵌套 t 中的标签整体保留，绝不误应用为静态颜色。其余 override 保留并列入 unsupported，效果绑定可调用 require_supported 拒绝误降级。完整透明度、布局和动画语义还需要接入。

### 检查与环境

- `uv sync --group checks` 安装仓库固定版本的 Ruff、ty 与测试依赖。
- 检查依赖补充 fonttools：现有字体构建工具导入它，原 checks 组遗漏导致全仓库 ty 失败。
- `uv run pytest tests/test_document_text.py tests/test_ass.py -q`：22 passed。
- `uv run ruff check .` 与 `uv run ty check`：全仓库通过。
- `uv run python -m pytest -q`：703 passed（21.31 秒）。直接执行 pytest 的入口未把仓库根目录放进模块搜索路径，导致 examples/tools 导入失败；采用项目发行检查同样的 python -m pytest 入口后全部通过。
- 公共类型正用例：`tests/typing/document_text.py`；负用例和整个新场景 API 的类型验证仍待后续实现。

### 复用审计初步结论

| 模块 | 后续处理 |
| --- | --- |
| ass.py | 保留标准记录、格式、注释、样式与文件 I/O；加入非破坏性类型绑定 |
| import_ass.py | 保留旧严格 timing-only 入口；新框架使用独立语义绑定，避免改变旧行为 |
| choreography.py / motion.py | 复用任意时刻求值、秒/毫秒边界经验；扩展对象属性与组关系 |
| Track 后端 | 保留当前工作树实现，待场景核心建立后适配，不能直接当成完整新引擎 |
| v0.1.0 engine.py | 当前分支无该模块；需从标签审计执行语义和布局依赖后恢复显式兼容前端 |

下一步先固定全部案例的验收卡和预算，再建立共享对象/场景/动画/编译层，并逐例实现和渲染。当前输入语义工作只构成 P1/P2 的部分基础，不勾选整项阶段验收。

## 第二批：共享对象场景与首个新示例

新增 `geometry.py`、`scene_animation.py`、`scene.py` 和 `scene_output.py`。公开入口为 `Scene(Document).add(...).compile()`，对象类型为 TextObject、PathObject、ObjectGroup 和兼容用途的 NativeEvent。状态、动画回调、路径几何、结果与预算均有明确类型；API 语义和暂时的能力限制见[场景文档](scenes.md)。

当前可用：顺序/并行/错峰/重复排程、同属性冲突检查、保持与释放、任意时刻求值、复制完整轨迹、组变换、固定画面遮罩、静态/原生 move/采样降级、相邻等价事件合并、预检和实际预算、源事件保留、同 owner 重编译、原生事件 Effect 保留。未完成的能力仍包括文档歌词到场景绑定、旧模板执行、导唱组件、局部动态遮罩、跟随关系、高级轮廓与完整 Track 接入。

首个例子为 `examples/scene_staggered.py`：直接构造固定场景，不读输入 ASS。逐字 80 ms 错峰回弹，多属性动画并行，单独矢量图形沿用户函数运动。导出的 ASS 已用系统 libass 0.17.5 渲染并人工检查 6 个关键时刻；809 个 Dialogue、峰值 11、332,120 字节，重复构建字节相同。它是 E02 的初步实现，尚未宣布 E02 完整验收。

证据：`tools/validate_scene_core.py`、[关键帧](images/scene-core.png)、[机器报告](scene-core-validation.json)、`tests/test_scene.py`（16 项语义/预算/保留测试）和 `tests/typing/scene.py`。预览直接使用导出的文件，不依赖修改后的播放端。当前报告明确保留连续/跳转、背景比较和误差测量等未完成项。

第二批检查结果：`uv run ruff check .`、`uv run ty check` 全仓库通过；`uv run python -m pytest -q` 为 719 passed（19.98 秒）；文档本地链接检查通过。全部基准的阶段退出条件尚未满足，TODO 整项保持未勾选。下一批优先补充文字测量/布局和 Document 绑定，使 E06 背景框与 E12 导唱符使用同一场景接口。

## 第三批：文字布局、背景与导唱

新增 `scene_text.py` 与 `cues.py`。Document 的静态颜色和字体重置进入经过塑形验证的独立绘制对象，保留原始演唱时间、布局框、墨迹框与字体来源。显式词范围可生成背景，动态包围框可跟随平移/缩放/旋转和导唱释放占位。文字范围不等于字形簇，连字内部的颜色、范围和 cue 边界明确拒绝。

CuePreset/CueFactory 接受明确时间和步进，不推断节拍。支持行内 BarsCue、独立 TextCue、自定义图形工厂、多个组件、保留或释放占位。导唱重排不改唱段时间。输入标记与直接 CueMarker 构造已通过等价性测试，旧源记录保存为 Comment，播放 Dialogue 不依赖本库标签。

新增 `examples/scene_cues.py`，固定演示 E06/E12 的初步版本。实际 ASS 经系统 libass 0.17.5 渲染，8 个关键时刻见[预览](images/scene-cues.png)，70 个 Dialogue、峰值 19、36,599 字节，重复生成一致，见[报告](scene-cues-validation.json)。文字输出补上标准 fe 字体编码标签，因此前一例最新体积更新为 334,556 字节，事件数和峰值未变。

验证：`tests/test_scene_text.py` 16 项覆盖颜色/重置、时间、零时长、连字、背景尺寸、输入与直接构造、工厂、释放占位、跟随背景、原文保留和栅格对照。栅格对照将包含 AV/ffi 的整段绘制与绑定后的簇绘制比较，允许既有 libass 1/64 像素定位误差，单通道差不超过 8/255，整帧平均差小于 .01/255。新增 `tests/typing/cues.py` 检查公共工厂和布局类型。新增软换行回归测试，WrapStyle 2 之外的软换行按空格处理。

全量回归为 734 passed（20.87 秒），随后新增的栅格对照已在布局测试中通过；Ruff、ty 全仓库通过。新增和修改的示例全部通过实际导出。这里仍不是 E06/E12 完整阶段验收：动画连续/跳转、所有背景和字幕边界组合尚待扩大验证，注音/续唱绑定、逐通道透明度和旧模板执行也仍在计划范围内。

补充验证：直接构造 Document 时 Script Info 记录是序列化事实来源，不要求在 metrics meta 缓存中重复 WrapStyle。新增软换行的直接构造/解析等价性测试；最后一次输入语义与布局定向回归为 28 passed。

## 第四批：高级几何与连续/跳转证据

新增 `path_geometry.py`、`path_animation.py`、`text_geometry.py`，扩展 PathObject 和现有场景编译器，未另建输出后端。

- 文字转路径来自原生真实塑形，保留连字、字体面、布局框、来源、寿命与状态；二次曲线精确转三次曲线。空白没有绘图，超复杂轮廓明确失败。
- 提供有界曲线细分、近似弧长查询、重采样、折线描画、凸多边形求交和显式轮廓匹配。求交保留孔洞绕向；当前不提供任意自交路径的通用 union/difference。
- MorphPath 检查闭合状态、段类型/数量、绕向和退化轮廓；作者决定轮廓/顶点对应，不自动猜测字形对应，中间自交仍需作者预览。
- WritePath 使用自有有序开放笔画和明确时间，显露和笔尖共用弧长表；零长度与时间重叠有诊断。
- PathFunction 是有类型的自定义几何回调，声明 max_points 与时间边界；场景在执行前及执行中检查预算。报告补充实际峰值绘图点数。
- AnimationClip 增加相对该 clip 的秒数 breakpoints，明确安排笔尖抬落等不连续点；Document.create 提供规范文件头，简化代码构造示例。

新增示例均写死内容并输出标准 ASS，路径和文字为自有示例，无外部模板运行依赖：

| 案例 | 源码 | 事件/峰值 | 字节数 | 实际峰值路径点数 |
| --- | --- | --- | --- | --- |
| E07 | `examples/scene_outlines.py` | 152 / 1 | 204,488 | 48 |
| E08 | `examples/scene_writing.py` | 386 / 2 | 460,149 | 墨迹 312、笔尖 13 |
| E10 | `examples/scene_morph.py` | 304 / 2 | 647,428 | 圆环 128、字形 60 |

关键帧与机器报告分别为 [E07](scene-outlines-validation.json)、[E08](scene-writing-validation.json)、[E10](scene-morph-validation.json)，预览链接见[场景文档](scenes.md)。实际输出另保存在忽略的 `build/ass-engine/scene-*.ass`，可由各示例和验证命令重新生成。

`tools/validate_scene_core.py` 新增连续渲染与跳转检查：每例用系统 ffmpeg/libass 连续渲染 300 帧，然后按逆序创建全新的 filter、将第一帧时间戳直接设置到目标时间，比较原始帧 md5。现有五个示例（staggered、cues、outlines、writing、morph）均通过。生成前向 metrics 注册仓库 DejaVu Sans，同一字体文件用于渲染，报告记录完整 SHA-256。所有例子重复生成的 ASS 字节一致。该结果覆盖当前深色背景和已记录的系统 libass 环境，不等于全部背景/全部播放器验收。

验证包括 `tests/test_path_geometry.py` 的 15 项几何、轮廓栅格、预算、动画边界测试，和 `tests/typing/path_geometry.py` 的公共类型正用例。文字路径在 an7/an5/an2 下与原文本实际渲染比较，归一化 alpha 差低于 5%；不声称两种 raster hinting 的逐像素等价。`uv run python -m tools.check_scene_types` 的四项错误扩展契约均被 ty 拒绝。

检查结果：Ruff、ty 全仓库通过，完整测试 751 passed（21.37 秒）；随后新增报告字段和来源断言通过 31 项路径/场景定向回归。TODO 中五项高级几何实现任务已有证据并勾选；P4 整体仍未退出，黑白背景误差测量及全部组合验收未完成。原目标不变，注音、柔和扫色、路径布局、粒子/碎片/残影、旧模板兼容和 Track 统一接入仍需继续。

## 第五批：路径布局、樱花生成、残影与碎片

新增 `path_motion.py`、`path_layout.py`、`particles.py`，所有功能继续返回普通对象和动画，使用同一 Scene 编译器。MoveAlong 支持参数路径/弧长折线、缓动、切线朝向，并将符合条件的直线运动降为原生 move。PathItem/LayoutPath 以显式 advance/anchor 沿曲线布置对象组；正文和注音共同旋转、缩放并保留来源。

Emission/ParticleContext/ParticleFactory 提供有界生成与稳定身份。随机值由 seed+id+key 决定，不推进共享 RNG；context.position 捕获出生位置，position_at(age) 显式持续跟随。echoes 延迟整个对象或组的状态、几何及寿命，透明度作用于求值结果。split_path 将静态字形切为局部几何，移动遮罩不固定在屏幕上；聚合后恢复完整字形以避免保留抗锯齿切缝。

本批检查发现并修复两项契约问题：ObjectGroup.copy 使用相同 id 进行局部变换时应保留子身份；Contour.point 对闭合轮廓应覆盖隐式闭合边。工厂协议改为位置参数，允许作者自由命名回调参数，不要求一定拼写为 context。

新增实际导出：

| 案例 | 示例 | 事件/峰值 | 字节数 | 编译策略 |
| --- | --- | --- | --- | --- |
| E03 | `examples/scene_round.py` | 348 / 12 | 143,611 | 12 个采样正文/注音对象 |
| E04 | `examples/scene_sakura.py` | 4,743 / 46 | 2,656,667 | 7 个原生 move、6 个静态对象、34 个采样对象 |
| E05 | `examples/scene_fragments.py` | 880 / 12 | 576,878 | 12 个采样碎片、1 个完整字形 |

分别见 [E03 报告](scene-round-validation.json)、[E04 报告](scene-sakura-validation.json)、[E05 报告](scene-fragments-validation.json)及[场景文档](scenes.md)中的预览。都通过重复生成字节一致、系统 libass 连续 300 帧和 8 个关键时间的新实例直接跳转哈希检查。生成与播放使用相同已记录 SHA-256 的字体；圆弧额外使用仓库 KaraTestCJK 字体及其既有许可。导出保存于 `build/ass-engine/scene-{round,sakura,fragments}.ass`，验证脚本可复现。

`tests/test_particles.py` 10 项覆盖稳定随机/生成顺序、工厂预检、出生捕获/持续跟随、原生直线、曲线切线、历史状态/几何、父子时钟、透明度/边界、局部碎片、沿路径注音组和闭合边。公共类型正用例见 `tests/typing/particles.py`，负例工具增加错误粒子工厂和错误路径参数，目前 6 项均被 ty 正确拒绝。

检查结果：Ruff、ty 全仓库通过；完整测试 761 passed（21.20 秒）；路径/粒子/场景定向回归 41 passed。示例生成预算未放宽。当前仅用游标模拟前沿触发，尚未把柔和扫色加到樱花正文；圆弧注音直接构造，尚不等于 Document 注音解析完成。通用引用图的环检测、动态遮罩、E01/E09/E11、旧模板前端、Track 接入及最终背景/整曲/发行验收仍需继续。

## 第六批：空间颜色场、柔和扫色与条带编译

新增 PaintField 协议、ColorRamp/ColorStop、LinearGradient 与 SoftSweep。填充和描边可以独立指定色标或扫色宽度，局部秒数时钟与动画一致。颜色场作用于 TextObject/PathObject，复制和文字转路径保留它；当前是固定屏幕坐标，不声称支持局部旋转渐变。组不隐式继承材质，与反向/矢量 clip 的组合明确拒绝。

统一编译器支持每个采样区间生成多个整数 clip 条带、跨区间合并相同事件，验证条带完整覆盖、声明数量与实际数量。全局 max_bands 与事件/字节/峰值预算共同约束；预检在调用自定义颜色场前完成。静态渐变可和原生 move 组合。报告新增 peak_bands，策略标记为 native-static-bands/native-move-bands/sampled-bands。

新增固定导出：

| 案例 | 示例 | 事件/峰值 | 字节数 | 内容 |
| --- | --- | --- | --- | --- |
| E09 | `examples/scene_gradient.py` | 3,196 / 556 | 1,364,810 | 填充/描边渐变、文字穿过固定颜色场、逐字配色与残影 |
| E11 | `examples/scene_sweep.py` | 5,667 / 39 | 2,455,343 | 填充 24px/描边 36px 的扫色、单独恒定粉色辉光 |

[渐变报告](scene-gradient-validation.json)、[扫色报告](scene-sweep-validation.json)包含固定字体 SHA、生成成本、策略、重复生成字节一致、系统 libass 连续 300 帧与关键时刻重新加载直接跳转的哈希比较。预览见[场景文档](scenes.md)，ASS 位于可重建的 `build/ass-engine/scene-{gradient,sweep}.ass`。

`tests/test_paint_fields.py` 的 9 项测试验证 RGB 插值、宽度独立、任意顺序求值、预算预检、条带覆盖、原生移动、矩形求交、材质复制/转路径、半透明模糊旋转文字的裁剪接缝和静态时段合并。公共类型用例见 `tests/typing/paint_fields.py`；错误扩展契约工具增加缓动返回类型和错误轴，总计 8 项由 ty 正确拒绝。

另用 `tools/validate_paint_fields.py` 验证系统 ffmpeg/libass 的 RGB24 实际输出。320×160、脚本和输出等比例的固定文字，在黑、白和彩色图案背景上条带版/完整版最大通道差均为 0；灰度渐变像素中心最大 RGB 误差为 0，见[机器报告](paint-fields-validation.json)。验证发现无显式色彩矩阵时历史 VSFilter 色彩转换会使 RGB 灰度落入 16..235；直接 RGB 参考因此显式声明 `YCbCr Matrix: None`，没有更改输入文档的默认色彩语义。此证据不覆盖缩放分辨率、所有彩色色标或任意时间函数的误差。

本批没有把 blur 当成 clip 羽化：颜色场给已形成的轮廓着色；扫色示例的完整辉光不随前沿变色。彩色前沿渗入模糊、局部颜色场、动态遮罩及其组合仍需后续实现/验收。完整测试在主要编译改动后为 768 passed（21.20 秒），随后材质转换保留及两项新测试通过 40 项场景/几何/颜色场回归；最终 Ruff、ty 全仓库通过。P3 整体仍未退出，旧模板前端、Document 注音、Track 统一接入与最终全案例/整曲/发行验收继续保留。

## 第七批：v0.1.0 兼容前端与统一场景输出

恢复 `engine.py` 的 Python 模板解释语义与 `_legacy_layout.py` 的旧歌词拆分/布局；新增 LegacyLine、LegacySyllable 类型化视图。公开 `Engine`、`apply_templates`、`preprocess`、`split_karaoke` 入口及旧 layout 模块导入均可用。Document 解析仍不执行代码。

`Engine.to_scene(document)` 在克隆文档上执行模板，保留源行与元数据，把生成结果放入 NativeEvent；`apply_templates` 调用同一 Scene 编译器。来源使用输入记录索引，并保留模板事件号诊断。新框架已有归属的事件不会因旧版宽松的 karaoke 匹配规则而被再次处理。模板毫秒时间和新场景秒时间明确区分。

集成修复：混合 NativeEvent 与普通对象时按加入顺序输出，不再按类型重排；原生归属注释与对应事件成对保留。空场景不再添加无用样式，纯原生输出也不插入未使用的场景样式。NativeEvent 保留旧版负起点/零时长/倒置区间，序列化沿用 Document 规则；新视觉对象仍要求正 Lifetime。

CLI 新增显式 `--templates` 与 `--video-size`。CLI/Python 默认 owner 都为 legacy-templates，文件入口与直接 Document 入口输出一致；新效果 CLI 仍用 default owner。旧版无选项模板命令需补 `--templates`，这是为显式执行制定的入口迁移规则，详见[兼容指南](legacy-templates.md)。旧模板与新预设参数不能混用；更复杂混合用 Engine.to_scene 后添加对象。

兼容证据：

- 恢复 v0.1.0 的 31 项测试到 `tests/test_legacy_v010.py`，保留原始输入夹具，仅调整格式/类型收窄/夹具路径；11 种 retime、变量、全部修饰符、helper、注音、多次高亮、宽高比和原地布局都有回归。
- `tests/test_legacy_scene.py` 的 9 项集成测试覆盖输入不变、文件/代码/CLI 等价、解析不执行、来源、未知字段和 Fonts、混合顺序、NativeEvent 边界、共享预算与反复生成。
- `tools/validate_legacy_templates.py` 在临时包中直接加载 git 标签原始 Python 源码，复用相同 native metrics，比较 23 组完整输出。仅去除新增归属 Comment 后全部相同，见[差分报告](legacy-template-validation.json)；没有把当前原生库结果宣称为旧版二进制环境。
- `tests/typing/legacy.py` 验证公共返回类型；负例工具增至 10 项，包含错误 Document 入参和宽高参数，全部由 ty 拒绝。

新增固定示例 `examples/scene_legacy.py`：旧 code/正文/注音模板与新淡入淡出文字共同编译。60 个事件、峰值 8、25,963 字节；重复生成字节相同，系统 libass 连续 300 帧与 6 个关键时刻重新加载跳转哈希一致。见[报告](scene-legacy-validation.json)及[预览](images/scene-legacy.png)。输出可由验证命令重建，当前位于 `build/ass-engine/scene-legacy.ass`。

检查结果：全仓库 Ruff、ty 通过；完整测试 810 passed、16 subtests passed（21.82 秒）。随后 CLI 默认 owner 对齐及入口等价断言通过 23 项 CLI/兼容集成回归。P0/P1/P2/P5 中旧模板对应条目按具体证据勾选，整体阶段仍未完成。Document 新歌词模型的注音绑定、E01 统一辉光、动态遮罩/引用图、Track 接入及最终全案例/整曲/发行验收仍需继续；旧模板的注音恢复不代替新模型的这项工作。

## 第八批：Document 注音、颜色来源与 E01 场景组合

新增 `document_lyrics.py` 的 DocumentLyrics/LyricUnit/LyricSegment/RubyText/LyricMapping，以及不执行代码和测量的 `Document.lyrics_at`。正文投影去除注音/控制符，保留原文 tokens、码点范围映射、颜色与 kt/k/K/kf/ko 时间；# 为原单元追加片段，零时长高亮不丢弃。untimed 前缀和 kt 与后续标签间的文本有回归保护。导唱锚点映射至正文，注音内容内的锚点明确拒绝。

TextAppearance 新增显式颜色来源信息。注音可使用独立 -furigana 样式或派生半字号样式；显式内联颜色（即使数值恰好等于正文默认色）覆盖注音默认值，空颜色标签和 r 重置正确解除覆盖。SingingSpan 和时间解析移至文本语义层，不让 Document 歌词解析依赖布局模块。

`scene_lyrics.py` 先整体塑形正文，再布局独立注音 run，保留 kerning/连字和来源。LyricLayout 提供 body、ruby、整体 group 与以正文中心为轴的 unit_group。分组会拒绝切开塑形簇；不分组时允许跨演唱单元保留一个连字。正文和注音共享显示寿命而保留原始演唱时间，修改 display 不重写唱词时间。

统一编译器补充已知变化区间分析，按状态动画 clip 和 SoftSweep 区间预检/采样，静止平台一次表达。任意几何回调和自定义动态颜色场仍按全寿命采样。该修复用于防止多层正文/注音被静止时段的虚高条带估算拒绝，未降低空间精度或放宽预算；两项回归分别证明短动画的长静止平台可在小预算下输出，以及未知几何回调不能享受这一优化。

新增固定 `examples/scene_lyrics.py`：由 Document 绑定「時々」与 toki/doki 注音，填充/描边扫色、两层恒定粉色辉光和共同唱时缩放。输出 16,614 个事件、峰值 155、7,567,332 字节；保持既定 25,000/1,000/10MiB 预算。系统 libass 连续 300 帧、11 个关键时刻的新实例跳转哈希及重复构建字节一致均通过。见[报告](scene-lyrics-validation.json)和[预览](images/scene-lyrics.png)，实际 ASS 位于 `build/ass-engine/scene-lyrics.ass`，验证工具可重建。

该例按绘制簇生成辉光副本，尚不等于先合并整词覆盖再模糊；颜色场仍为屏幕坐标。行内导唱符占位释放尚未自动传递到注音，跨行排版、per-channel alpha、动态遮罩/引用图、Track 统一接入和最终所有背景/整曲/发行验收仍需继续。E01–E12 都已有相应场景原型，不表示每张案例卡已完成全部验收。

`tests/test_document_lyrics.py` 的 13 项用例覆盖范围投影、颜色来源与重置、原始时间/延续/间隙、锚点、错误语法、超宽注音、字号派生、共同轴和连字边界。公共类型用例为 `tests/typing/document_lyrics.py`。完整回归发现 README 的 Track 测试依赖“第一个 Python 代码块”，在上一批新增兼容入口说明后定位错误，现改为定位 Configure tracks 章节，仍执行原示例并核验输出。

最终 Ruff、ty 全仓库通过；类型负例 10 项通过；完整测试 825 passed、16 subtests passed（29.37 秒）。TODO 中正文颜色与注音关联条目已按证据勾选，整体目标保持进行中。

## 第九批：行内导唱符与注音共同占位/释放

新增 `bind_lyric_cues` 与 CuedLyrics，复用原有 cue 内容工厂、预设时间和标记解析。正文单元前的占位给对应注音同样的平移；单元内部的占位给注音半宽平移，保留相对扩展正文框中心的偏移；单元尾部的占位只影响后续单元。多次释放沿用相同规则，独立导唱符保持屏幕定位。输出仍为普通 TextObject/PathObject/ObjectGroup 和标准 ASS。

CuedLyrics.group 包含正文、注音和 inline cue，父寿命扩展以容纳提前显示的导唱符，子文字自身寿命和 singing 不变。绑定保留注音来源和样式；输入命名空间标记和等价 Python CueMarker 的编译结果一致，实际输出 Dialogue 不含自定义标记，原文留在源 Comment。并未把这一确定的占位平移冒充通用引用图或任意逐字变形后的重排。

`tests/test_lyric_cues.py` 四项集成用例覆盖多个句首/句中标记、两次释放和任意顺序求值，检查正文框中心与注音位置的差值、源时间与身份；另覆盖独立 cue、输入/代码等价、源标记消费，以及释放发生于正文显示开始时的情况。类型正例扩充 document_lyrics 用例；错误类型工具增加非 LyricLayout 入参，总计 11 个反例均由 ty 拒绝。

新增 `examples/scene_lyric_cues.py` 固定展示 SING ALONG 与注音、句首短条、句中数字和独立 READY/SET/GO。生成 57 个事件、峰值 23、25,842 字节；系统 libass 连续 300 帧，以及 11 个关键时间（含 1s 和 2.5s 释放边界前后）的新实例跳转哈希一致，重复构建字节相同。见[报告](scene-lyric-cues-validation.json)及[预览](images/scene-lyric-cues.png)，ASS 位于可重建的 `build/ass-engine/scene-lyric-cues.ass`。

最终 Ruff、ty 全仓库通过；完整测试 829 passed、16 subtests passed（22.13 秒）；补充注音时间不变断言后四项定向回归通过。P2 的标记/时间与输出消费两项已有证据并勾选。动态遮罩、通用引用图、整词覆盖合成、Track 适配与全案例/整曲/发行验收仍待完成，整体目标保持进行中。

## 第十批：局部/动态遮罩及颜色场求交

RectangleClip/VectorClip 增加 screen/local 坐标声明，默认保持历史屏幕坐标。local 路径在输出前应用对象及父组的缩放、旋转和平移；文字以 alignment 锚点为局部零点。局部矩形转为标准矢量 clip，需随对象运动时使用共享采样器，固定屏幕裁剪仍允许原生 move。

VectorClip.deform 复用 GeometryAnimation/PathFunction，时间相对对象出生。None 表示空区域，普通遮罩隐藏对象、反向遮罩完整显示。回调声明点数、实际输出、生命周期内的时间边界和复杂度均有检查；异常附对象、采样时刻和来源。任意遮罩回调仍按全寿命保守采样，不把若干静止样本当成恒定函数证明。

正向矢量遮罩可与颜色场条带求交，每条仅输出一个标准矢量 clip。凸条带求交保留路径孔洞，曲线以 0.25 脚本像素容差细分，预算覆盖中间/结果点数。新增 peak_clip_points 报告遮罩及求交路径的峰值复杂度。反向遮罩与颜色场、局部遮罩与 skew、直接共享组遮罩仍明确诊断，未静默改变语义。

新增固定 `examples/scene_masks.py`：局部裁剪随父组运动/旋转/缩放、屏幕聚光路径、椭圆遮罩内的渐变。输出 823 个事件、峰值 322、453,693 字节；重复生成字节相同，系统 libass 连续 300 帧及 6 个关键时刻重新加载跳转哈希一致。见[报告](scene-masks-validation.json)和[预览](images/scene-masks.png)，ASS 位于可重建的 `build/ass-engine/scene-masks.ass`。

`tests/test_scene_masks.py` 最终 8 项用例覆盖：局部矩形与显式世界坐标遮罩的实际光栅等价（包含颜色场组合）、原生/采样策略、空区域和反向语义、复制时钟、回调前预算与实际点数超限、孔洞/颜色插值，以及错误坐标组合和异常来源。公共类型用例为 tests/typing/scene_masks.py；错误空间名称的反例使类型拒绝验证增至 12 项。

全仓库 Ruff、ty 通过。主要实现后的完整测试 835 passed、16 subtests passed（22.30 秒）；新增异常来源与变换+颜色场组合验证后 8 项遮罩定向回归通过。P3 矩形/矢量遮罩坐标关系条目已按证据勾选；通用引用图、整词合成、Track 统一接入、共享组遮罩/仿射组合及最终全案例/整曲/发行验收仍需继续。


## 第十一批：显式引用图与世界状态跟随

新增 StateReference、FollowObject、ReferenceFunction 与 SceneEvaluator。目标以对象 ID 声明，依赖图包含父子变换边；不存在的目标和循环在回调执行前拒绝。世界状态逐次独立求值，支持跨父组、延迟历史和多个依赖；读取超出目标寿命时取端点，显示寿命保持独立。局部动画与引用接管通道冲突、未声明依赖读取和越界通道写入均有诊断。

Scene 编译统一使用求值器，FollowObject 将目标边界延迟传播到输出时间网格。含引用对象保守采样，不以少量样本推断原生动画。ObjectGroup.copy 对整棵子树一次重定向，补偿内部目标的共同时间平移，避免嵌套复制重复延迟；外部引用保留原目标历史。text_to_path 保留引用，echoes 保留动态引用并正确衰减透明度。

新增固定 examples/scene_follow.py，包含曲线路径文字、跨父组标签、五个延迟圆点与双目标中点回调。输出 1,417 个事件、峰值 9、758,353 字节；重复生成字节一致，系统 libass 连续 300 帧与 6 个关键时刻重新加载跳转哈希一致。见[报告](scene-follow-validation.json)与[预览](images/scene-follow.png)，ASS 可由示例重建，当前位于 build/ass-engine/scene-follow.ass。

全仓库 Ruff、ty 与 13 项错误公共类型契约检查通过；完整测试 847 passed、16 subtests passed（21.93 秒）。随后补充跨父组位置/缩放/旋转/透明度的实际光栅对照，11 项引用测试全部通过：采样跟随输出与显式世界变换逐像素相同。引用回归还包括插入/求值顺序、回调前循环预检、边界传播、内部与外部复制时钟及残影透明度。

显式依赖图不分析任意 Python 闭包；自定义非线性时间映射的输出边界由作者声明。整词覆盖合成、Track 统一接入、共享组遮罩/完整仿射组合、全案例多背景误差、整曲压力与发行验收仍需继续，整体目标未完成。

## 第十二批：Track 准备阶段与混合场景入口

拆出 prepare_karaoke/PreparedKaraoke，将 Track、TrackGroup 和旧 Effect 共用的布局、样式、动态采样与可选栅格编码结果放入带来源 NativeEvent。返回 scene 可以继续加入文字、路径和残影，通过 Scene.compile 共同排序、序列化并检查总事件/字节/峰值活动预算。原 render_karaoke 复用准备阶段及同一事件插入器，保持 RenderResult 与历史归属字段。

场景原生事件的标记/Dialogue 清理提取为共享逻辑，先成对清理旧场景输出，再导入和筛选旧 karaoke 输出，避免后者先移除 Dialogue 导致标记悬空或误删下一行。导入器跳过其他场景生成的 Dialogue；改变选择会恢复未匹配源字幕，其他 owner 保留。损坏的来源标记明确报错，输入与准备场景在编译时均不修改。

tests/test_track_scene.py 的 6 项集成用例覆盖普通/栅格 Track 的新旧入口逐像素等价、来源与诊断、未知段保留、重新生成与切回旧入口、选择变化、其他 owner、动态回调仅执行一次、混合预算及标记损坏。类型正例增加 PreparedKaraoke 与 Scene 返回契约，错误 Track 元组反例使负例总数增至 14。

新增固定 examples/scene_tracks.py，展示带注音与唱时缩放的 Track 歌词、Scene 轨道圆点残影和淡入淡出标题。输出 1,717 个播放事件、峰值 39、987,298 字节；重复生成字节相同，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转哈希一致。见[报告](scene-tracks-validation.json)、[预览](images/scene-tracks.png)；ASS 位于可重建的 build/ass-engine/scene-tracks.ass。

最终全仓库 Ruff、ty 通过，完整测试 854 passed、16 subtests passed（22.40 秒）；14 项错误公共类型契约通过。Track 文档和迁移表已注明预算时机与可编辑性：准备阶段已经运行 Track 回调，SceneBudget 只能约束之后的混合编译；NativeEvent 不能作为可变形文字或世界状态引用目标。本批接通共享场景输出，不代表 Track 的属性求值与整词合成后端已经统一。该迁移、整词覆盖合成、共享组遮罩/完整仿射组合和最终全案例/整曲/发行验收仍待完成。

## 第十三批：二维仿射组合与路径降级

新增 Affine2D 和 VisualState.transform，明确本地剪切、轴向缩放、顺时针旋转、平移的顺序。SceneEvaluator 用矩阵乘法组合父子，保持既有无剪切组合的分解结果；非等比父缩放与子旋转不再拒绝，返回等价的世界 scale/rotation/skew。ObjectGroup 支持 skew 属性和动画。当前分解要求非退化且保持方向；反射或近奇异组矩阵仍明确诊断，未宣称全部仿射情况已完成。

核对仓库内固定 libass 0.17.5 源码的 calc_transform_matrix：文字剪切包含基线相关项，不能直接将通用组矩阵拼接成 fax/fay。需要仿射时改为文字轮廓/已有路径控制点变换，局部遮罩使用相同矩阵；标准 ASS 绘图负责最终填充和边缘绘制。已知需要轮廓的对象在属性回调前检查点预算，编译内复用原始轮廓。自定义动画按实际输出样本决定统一后端，避免零剪切时来回切换；不推断未采样时刻的连续性。报告包含 affine-path 策略与路径点数。

DocumentLayout.range_bounds 的本地布局框查询也使用该矩阵，支持动画剪切。该查询仍不含父组、引用状态和模糊范围。描边/模糊是在变换后路径上绘制的脚本空间参数；本批没有加入离屏覆盖率仿射合成。多行文字轮廓尚未支持，明确提示拆成单行对象。

tests/test_scene_affine.py 的 7 项用例包含独立几何计算与矩阵分解对照、文字/路径及局部遮罩的逐像素等价、乱序求值和重复编译、轮廓预算/来源、回调前预检、奇异组与多行诊断、动画剪切后的布局框。此前拒绝非等比组合和局部剪切遮罩的测试改为验证成功降级。公开类型正例与错误 Affine2D.apply 入参反例通过，类型反例总计 15 项。

固定 examples/scene_affine.py 展示非等比父缩放、父旋转/剪切、子旋转与局部遮罩。输出 405 个事件、峰值 3、476,581 字节；重复生成字节一致，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转哈希一致。见[报告](scene-affine-validation.json)、[预览](images/scene-affine.png)；ASS 位于可重建的 build/ass-engine/scene-affine.ass。另在固定字体下重新编译全部 16 个既有 scene 示例，与保留 ASS 字节输出全部相同，预算未放宽。

主要实现后的完整测试 860 passed、16 subtests passed（23.47 秒）；随后加入布局框剪切查询，23 项仿射/文本定向回归通过。全仓库 Ruff、ty 和 15 项错误类型契约通过。共享组遮罩、反射/奇异组状态、整词覆盖合成、Track 可编辑对象迁移与全案例/整曲/发行验收仍待继续，整体目标保持进行中。

## 第十四批：共享组遮罩与嵌套求交

ObjectGroup 开放 RectangleClip/VectorClip。新增内部 ClipResolver，以遮罩所属对象的世界矩阵和出生时钟求值；组局部遮罩不会被子对象自己的位移/旋转再次变换。动态祖先遮罩参与后代活动区间、采样边界与量化报告。世界遮罩按 owner/time 缓存，最多 128 项，回调仍要求纯函数。

嵌套正向矩形取交集；矢量与矩形/凸边界通过已有有界几何求交，保留孔洞，曲线以 0.25 脚本像素容差细分。完全相同的遮罩去重，空交集不生成事件。单一反向共享遮罩保留标准 iclip 语义；多个不同非凸遮罩或反向与其他遮罩的组合仍明确拒绝，等待通用路径交集/差集，没有让多个 ASS 标签互相覆盖来假装求交。

预检覆盖组及所有祖先遮罩的路径和回调声明点数，执行时检查实际结果与求交复杂度；错误定位到遮罩 owner 和 EventOrigin。叶对象报告包含继承遮罩的 peak_clip_points。该能力将共同几何规则分配给后代事件，不提供先离屏合成整组再做覆盖率蒙版的语义。

tests/test_group_masks.py 最终 9 项用例覆盖组坐标与独立世界多边形的逐像素等价（含颜色场）、多孩子不同变换、嵌套矩形与带孔子遮罩、空交集、组动态时钟与延迟复制、量化边界、反向与重复遮罩、非凸组合诊断、回调前预算与错误来源、共享缓存，以及矩形取整为空的正反向行为。公共类型用例增加 ObjectGroup.clip。

新增固定 examples/scene_group_masks.py：移动聚光路径裁剪文字与嵌套装饰条，装饰组另外限制局部矩形。输出 905 个事件、峰值 5、567,618 字节；重复生成字节相同，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转哈希一致。见[报告](scene-group-masks-validation.json)、[预览](images/scene-group-masks.png)，ASS 位于可重建的 build/ass-engine/scene-group-masks.ass。

主要实现后的完整测试 869 passed、16 subtests passed（23.02 秒）；随后修复取整空矩形，组/叶遮罩 17 项定向回归通过。全仓库 Ruff、ty 和 15 项错误类型契约通过。全部 18 个固定 scene 示例重新编译后均与留存的验证 ASS 字节一致。通用非凸/反向布尔遮罩、反射/奇异组状态、整词覆盖合成、Track 可编辑对象迁移与最终全案例/整曲/发行验收仍待继续。

## 第十五批：镜像、零缩放与退化组状态

VisualState.scale 开放有限带符号值与零，新增 singular 查询。父子矩阵分解保留有符号第二轴，第一基向量归零时使用剩余基向量；已知父/子退化时保留零面积状态，不让浮点抵消误差重新产生微小面积。移除绝对行列式阈值，接近奇异但仍有效的变换不再一概拒绝。

负缩放使用标准路径降级，不输出负 fsc；零面积文字或填充路径在对应样本不输出事件，描边/阴影也不额外留下细线。坐标仍可查询或用于引用。局部遮罩跟随镜像，退化时正向为空、反向不限制；即使后代通过引用覆盖父组世界通道，该遮罩规则仍成立。源字体测量仍要求正缩放，PositionedText 新增独立保存的 layout_scale，使布局后的镜像/归零不破坏范围测量。

仿射回归新增三种镜像的实际轮廓像素对照、四种奇异矩阵的独立坐标对照与空输出、缩放穿零的事件与像素行为、近奇异坐标及替换对象后布局范围。组遮罩回归增加奇异局部蒙版与世界引用覆盖的正反向验证。原有测试中的奇异组合拒绝改为验证有效空输出。

新增固定 examples/scene_mirror.py，通过普通 SceneTimeline 展示旋转文字、箭头及共享局部遮罩的 1 → 0 → −1 → 0 → 1 缩放。输出 387 个事件、峰值 3、770,217 字节；重复生成字节一致，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转哈希一致。见[报告](scene-mirror-validation.json)、[预览](images/scene-mirror.png)，ASS 位于可重建的 build/ass-engine/scene-mirror.ass。全部 18 个既有固定 scene 示例重编译后保持原 ASS 字节输出。

全仓库 Ruff、ty 通过，完整测试 881 passed、16 subtests passed（23.14 秒），15 项错误公共类型契约通过。通用非凸/反向布尔遮罩、整词覆盖合成、Track 可编辑对象迁移、全案例多背景误差和整曲/发行验收仍需继续，整体目标未完成。

## 第十六批：一般路径布尔运算与反向遮罩组合

新增类型化 path_boolean/PathBooleanOperation，支持闭合填充路径的交集、并集、差集、异或，输入按非零绕向解释。曲线按显式容差细分，顶点/交点分割水平扫描区间；公共内部边消去并重新连接外轮廓与孔洞，使输出可正常描边。处理凹多边形、孔洞、自交、重合边和点接触；开放轮廓拒绝。点数、临时边界规模与工作计数均有上限，数值归一与共线清理容差写入契约。

ClipResolver 在原有正向矩形/凸边界快速路径之外接入一般交集与差集；两个反向遮罩通过并集再反向表达。SceneBudget 新增每次通用操作的 max_boolean_work。错误继续保留遮罩所属对象和来源。反向矩形颜色分条拆为最多四个互斥原生矩形，预检计入数量；反向矢量通过色带减去遮罩输出正向矢量 clip。

实际验证发现矢量裁剪覆盖率与原生硬矩形边界不同。几何组合以独立手写矢量参考逐像素对照，数学矩形内部保持精确；不把原生矢量抗锯齿与硬矩形参考的边缘差异误判成布尔拓扑错误。tools/validate_boolean_masks.py 使用系统 libass 的 RGB 合成，在黑、白和彩色测试图背景测量固定 320×240、8px 色带夹具：反向原生矩形误差 0，矢量分条最大 RGB 差 3/255。见[误差报告](boolean-masks-validation.json)，不将此夹具结果推广为任意输入上界。

新增 tests/test_path_boolean.py 的 10 项几何测试，包含 20 组固定种子多边形的四种操作与独立非零绕向点查询、孔洞和相反/同向重叠、无内部描边线的光栅等价、曲线细分及工作/输入/输出预算。组遮罩回归新增四种反向组合、反向矩形/矢量颜色场和预算来源；旧的非凸/反向拒绝用例改为独立结果验证。公开类型正例与非法操作名称反例通过，类型反例总计 16。

固定 examples/scene_boolean.py 展示移动圆形与凹星形的四种操作，支持作者替换路径和纯函数。输出 813 个事件、峰值 9、1,051,514 字节；重复生成字节一致，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转哈希一致。见[报告](scene-boolean-validation.json)和[预览](images/scene-boolean.png)，ASS 位于可重建的 build/ass-engine/scene-boolean.ass。19 个既有固定示例重编译仍保持原 ASS 字节输出。

最终全仓库 Ruff、ty 通过，完整测试 898 passed、16 subtests passed（24.21 秒）；16 项错误公共类型契约通过。整词覆盖合成、Track 可编辑对象迁移、全案例多背景/参考误差及整曲/发行验收仍需继续，整体目标保持进行中。

## 第十七批：整词几何合并与共享辉光基础

新增 merge_geometry(ObjectGroup) → PathObject，将文字轮廓和路径做有界几何并集，消除内部描边。根组状态、动画、遮罩与引用保留，子几何的变换、寿命、动画与路径变形参与采样；复制后使用相对时钟，静态轮廓预计算，动态轮廓留到编译预算检查后执行。后代遮罩与世界引用明确拒绝。该操作忽略子外观与透明度，不宣称实现离屏覆盖率合成或先扫色再模糊。

新增 6 项回归覆盖重叠轮廓的边界、根组状态保留、动态子寿命、逆序采样、延迟复制、回调前预算、空组、后代遮罩诊断、点数与工作量限制，以及共享描边/模糊与独立矩形参考的实际像素等价。公开类型正例验证明确返回 PathObject。

固定 examples/scene_word_glow.py 展示重叠 WAVE 字形合并后共享辉光与变换。输出 405 个事件、峰值 3、522,028 字节；重复生成一致，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转一致。见 scene-word-glow-validation.json 与 images/scene-word-glow.png，可重建 ASS 位于 build/ass-engine/scene-word-glow.ass。

主要实现后的完整测试 903 passed、16 subtests passed（24.26 秒），随后追加像素对照后 6 项定向测试通过。整词覆盖率合成、Track 可编辑对象迁移、多背景参考误差、整曲与发行验收仍待继续。

## 第十八批：Track 准备与降级解耦

将 BoundTrack.build 中布局、样式、正文/注音视觉目标、演唱轨道、属性及材质绑定拆为有类型的 PreparedTrack。prepare 默认不进行原生动画降级，保留可供场景后端求值的属性；lower 独立消费准备结果，不重复布局或绑定。旧 build 根据原有输出模式选择是否原生降级，再调用 lower，原生与栅格后端继续共享前端。

tests/test_track_preparation.py 新增四项验证：正文/注音、颜色、来源与时钟保留；原生缩放在未降级准备中仍为可求值属性；准备阶段不采样自定义回调；修改准备目标后独立降级且不污染原结果。主要变更后的完整测试 907 passed、16 subtests passed（24.01 秒）；之后提取 lower 并新增编辑测试，Track 相关 67 项回归通过。最终 Ruff、ty 通过。固定 scene_tracks 重建文件（含 UTF-8 BOM）与已有标准 ASS 产物逐字节相同。

这一步是可编辑场景迁移的内部基础，不将 NativeEvent 适配宣称为完整对象迁移；不新增尚未实现语义的公共 API。Scene 对象转换、扫色/辉光及组透明度语义统一、整曲与发行验收仍待继续。

## 第十九批：Track 可编辑文字对象的内部转换

新增内部 _track_scene.track_objects，将未降级 PreparedTrack 的未扫色目标转换为 ObjectGroup/TextObject，保留正文、注音、字体、位置、寿命与来源。几何动画复用 sample_hierarchy，材质复用 sample_materials；辉光为独立文字层。缩放按 Track 语义同时缩放描边与模糊，动画仅声明实际写入的 Scene 通道，未控制的颜色仍能直接修改。时间断点包含属性区间、显式断点、材质区间与关键帧；动态回调不在转换阶段执行。

新增七项定向回归（准备模块现 11 项）：静态正文/注音与旧输出逐像素相同，缩放 pivot/描边与延迟复制一致，辉光加缩放在采样中心与旧原生输出逐像素相同，几何动画不覆盖无关颜色编辑，编译预算预检先于回调，颜色及描边宽度动画保留，以及扫色缺口的明确诊断。

动态对照揭示并保留两种输出的时间差异：Scene 在每个采样区间保持中心值，旧原生动画连续插值。因此当前证据是采样中心等价，不是连续时间完全等价。扫色、多层透明度合成与公开 Document→可编辑 Track Scene 入口仍未完成；未把此内部转换加入正式示例或替换旧入口。

完整测试 914 passed、16 subtests passed（24.44 秒）；随后补充材质动画测试，11 项定向测试通过。最终 Ruff 与 ty 通过。整体计划继续进行，剩余功能与最终验收未缩减。

## 第二十批：动态矩形遮罩与 Track 扫色对象转换

新增公开 RectangleFunction，返回有限正面积矩形或空区域，接入 Scene/组遮罩的动态识别、断点、采样、复制、来源诊断及预算预检。屏幕矩形和轴对齐的局部动态矩形使用原生整数 clip；旋转/剪切降为矢量路径。静态局部矩形维持既有行为。

Track 内部对象转换开始复用 _compile_targets 的结构化扫色分区，不反解 ASS 字符串。不同唱前/唱后外观分为可编辑文字层，动态矩形跟随对应文字的几何动画；release 阶段用寿命组移除遮罩，不重置动画时钟。共享分区编译器改接收明确的 source ID，旧 Track/Effect 调用同步更新。静止原生矩形的整数端点插值与几何运动时连续边界分开处理，修复了直接插值原始浮点端点导致的一像素偏移。

新增动态矩形的三项回归，覆盖正反向空区域、出生时钟、复制、局部轴对齐及镜像、非法边界和回调前预算。Track 准备测试增至 13 项；固定正文/注音夹具在 7 个采样中心分别对照静止扫色与带缩放扫色，实际像素与旧原生输出相同。该证据不扩大为任意动画全时刻等价，动态 Scene 仍为采样保持。公开 Track Scene 入口、分区诊断传播与高级覆盖率合成仍未完成。

固定 examples/scene_rectangle.py 输出 526 个事件、峰值 2、230,596 字节；重复生成一致，系统 libass 连续 300 帧及 6 个关键时刻新实例跳转一致。预览与报告为 images/scene-rectangle.png、scene-rectangle-validation.json，ASS 可在 build/ass-engine/scene-rectangle.ass 重建。

全仓库 Ruff、ty 通过；完整测试 920 passed、16 subtests passed（24.68 秒），16 项非法公共类型契约通过。整体计划继续进行，尚未满足全部功能与发行验收。

## 第二十一批：公开 Document → 可编辑 Track Scene 入口

新增 prepare_track_scene(document, tracks=..., items=..., owner=..., max_objects=...) → PreparedKaraoke。旧 prepare_karaoke 与新入口复用私有准备流程，统一导入、选轨、样式、布局、源注释、重复生成与 owner 清理；旧入口仍输出 NativeEvent，新入口输出普通歌词 ObjectGroup。动态属性回调延迟到 Scene 编译预算预检之后。每条歌词分配连续图层区间，TrackGroup 行位配置保留。对象预算和 Scene 输出预算分开执行。

扫色分区诊断通过 prepared.diagnostics 返回，并明确 SceneBudget 采样与逐绘制层透明度语义。PreparedKaraoke.layer_count 在可编辑入口表示生成文字层数；对象不必与来源一一对应。公共类型正例及非法 Track/RectangleFunction 回调反例补充，类型反例总计 18。

tests/test_track_scene.py 新增四项公开入口回归：输入不变、解析/直接 Document 等价、重复生成与两入口切换无旧事件；回调晚于预算且重复采样确定；自定义组变换与辉光硬裁剪诊断；双行组布局、图层区间及取消选轨恢复原字幕。原有 13 项准备/转换回归继续通过。

固定 examples/scene_editable_tracks.py 使用公开入口配置歌词、独立注音和音节缩放，再为返回对象组添加纯函数浮动与下划线路径。输出 7,146 个事件、峰值 33、3,496,927 字节；重复生成一致，系统 libass 连续 300 帧与 6 个关键时刻新实例跳转一致。见 scene-editable-tracks-validation.json、images/scene-editable-tracks.png；ASS 可在 build/ass-engine/scene-editable-tracks.ass 重建。

主要实现后完整测试 923 passed、16 subtests passed（24.52 秒），随后追加双行/恢复测试，公开 Track Scene 10 项定向回归通过。最终 Ruff、ty 通过，18 项非法公共类型契约通过。昂贵覆盖率合成与材质迁移、全案例多背景参考、整曲和发行验收仍未完成，目标继续进行。

## 第二十二批：整曲组合压力验证与复制时钟修复

新增 examples/scene_whole_song.py，以 12 类现有视觉示例的完整组为模板，每 6 秒复制一段，形成 180 秒固定夹具；对象与内部引用随组复制，保持原帧率与效果内容。tools/validate_whole_song.py 测量编译、重复生成、事件/字节/峰值、RSS、系统 libass 连续 9000 帧、150 个逆序新实例跳转与 5400 个复制段落帧对照。预算沿用事前规定的 250,000 事件、100 MiB、峰值 2,000。

首次预检发现恒等组织组使原生 move 退回采样，令渐变示例的事件上界不必要地膨胀。编译器现允许无变换/动画/遮罩/引用的恒等祖先保持原生 move；若父组截断子对象出生时间，仍采样以避免重置原动画时钟。新增普通/移动组、预算与裁剪出生时刻回归。

严格复制段落比较随后发现 159 帧不一致，涉及浮点减法把透明度与半格事件边界推到不同整数。对象、路径、颜色场和遮罩的局部时间统一到 1e-10 秒；ASS 百分之一秒取整前统一到 1e-8，稳定 ties-to-even。新增延迟 72/144 秒的半格寿命、透明度与事件文本回归。另通过同一 ASS 的精确整数毫秒渲染确认 FFmpeg 的事件边界浮点截断差异；整曲工具使用明确毫秒时间基与 +1 ms 帧偏移，并如实记录，不把它当作编译器容错。

最终输出 93,957 事件、峰值 556、50,593,439 字节、预估 112,626；生成 3.82 秒，重复生成 4.23 秒，连续 9000 帧约 14.31 秒，150 次新实例跳转约 43.99 秒。重复生成字节一致，全部跳转与连续播放一致，5400 个复制帧全部一致。RSS 采用 Linux resource 聚合测量，子进程峰值可能含 exec 前继承内存，不能当作 ffmpeg 独立稳态内存。完整证据见 whole-song-validation.json；ASS 可在 build/ass-engine/scene-whole-song.ass 重建。

Ruff、ty 通过，完整测试 927 passed、16 subtests passed（25.13 秒），18 项非法公共类型契约通过。新增整曲成本条目已勾选；单例全部背景/参考误差、高级覆盖率合成与发行验收仍待继续，未将整曲压力通过等同于完整计划完成。

## 第二十三批：源码包到隔离安装的 Python 3.12 验证

新增 tools/validate_distribution.py：从源分发包抽取测试、示例、工具和文档，单独创建虚拟环境安装指定 wheel，不复制 kara_templater 源目录。验证全部 Python 模块、pyi/py.typed、原生扩展及关键 native/font/计划资产存在；记录实际包和扩展导入路径，运行完整测试、全部固定 Scene 示例与旧 CLI，并保存日志、哈希和耗时。

第一次隔离导入暴露 _raster.RasterCanvas.over 的注解引用仅存在于 _metrics.pyi 的 RasterImage，Python 3.12 在定义函数时求值而报 AttributeError；开发环境 Python 3.14 延迟注解掩盖了该问题。新增 _native_types.py 作为运行时可导入的 Point/Outline/RasterImage 定义，stub 与 Python 实现共享这些类型。新增 get_type_hints 回归，保证运行时注解解析也有效。

修复后从源码包重建 cp312 Linux wheel，严格 twine 元数据检查通过。首次测试还发现工具继承开发环境 PATH，导致 ty 看不到隔离安装包；验证工具现安装源包规定的 ty 版本并设置隔离 PATH/VIRTUAL_ENV。CI 的 wheel test-requires 添加固定 ty，sdist 安装测试使用 checks 依赖组。

最终 Python 3.12.16 隔离安装运行 928 passed、16 subtests passed（45.20 秒），24 个固定 Scene 示例全部成功导出标准 ASS，含 180 秒整曲；旧 CLI 通过。运行时库模块来自独立虚拟环境。原开发环境 49 项栅格回归及随后 51 项栅格/类型定向检查通过，Ruff、ty 及 18 项非法公共类型契约通过。见 distribution-validation-py312.json 与 docs/releasing.md。

这份证据限定于本地 linux_x86_64 wheel；尚未运行修复后的 manylinux/Windows 发布矩阵。忽略目录 vendor/runtime-licenses 含大量无关宿主许可证，保留原文件未清理，本地分发包不作为干净 CI 许可证收集后的正式发布产物。高级覆盖率合成、完整案例参考/多背景验收与最终发行审计仍待继续，未声明整体目标完成。

## 第二十四批：显式整组 RGBA 合成与标准 ASS 烘焙

公开 rasterize_group → RasterizedGroup：源 ObjectGroup 先按普通 Scene 规则降级，合成到指定视口，再对预乘 RGBA 施加整组模糊，最后应用根透明度与显式空间量化。返回包含 NativeEvent 的独立 Scene，可添加其他对象并继续使用标准编译出口。普通 ObjectGroup 的逐层透明度语义保持不变。来源为空的纯图形不再误创建空 EventOrigin；有来源时汇总后代来源和轨道，显式根来源优先。

输出时间网格加入源事件起止与根动画断点，避免低采样率漏掉短寿命子对象；相邻相同帧合并。粗帧数/画布预算先于回调，源降级后的边界切分继续受帧数限制，最终编译计入来源 Comment 与样式的开销。blur_radius 在 0–100 范围，非法值提前拒绝。源图形已经在视口内栅格化，视口外形状不贡献向内扩散；遮罩位于整组模糊之前。时间采样和颜色量化的界限在 scenes.md 中分别说明。

tests/test_scene_raster.py 的 11 项回归覆盖重叠颜色与合成后透明度、子对象透明度/组模糊顺序、跳转、相同帧合并、短寿命事件、预算、非法 blur、来源轨道及根运动/遮罩/延迟复制。零空间量化情况下用实际 libass 比较 RGBA；错误的逐层模糊/透明度结果作为反例。公共类型正例补充，非法类型契约增至 19 项。

固定 examples/scene_composite.py 将四个彩色字母组合后模糊和淡出，使用 320×180、10 Hz、8/255 空间量化容差及显式高预算。输出 65,729 事件、峰值 3,276、23,476,844 字节，含来源开销的预检估算 131,457；不将这种输出成本称为轻量。初次默认峰值预算与随后 100,000 事件预算均按预期拒绝，示例最终显式使用 250,000 事件、峰值 10,000、128 MiB 上限。重复构建及系统 libass 连续 300 帧/逆序新实例跳转一致，报告记录实际预算与字体，见 scene-composite-validation.json、images/scene-composite.png。

完整测试 938 passed、16 subtests passed（47.84 秒），随后追加运动/遮罩/复制回归，11 项定向测试通过；Ruff、ty 与 19 项非法类型契约通过。此批实现通用 RGBA 烘焙，不将其等同于 Track 扫色覆盖率材质的完整迁移，也未完成所有案例的多背景参考与最终发行矩阵。整体目标继续进行。


## 第二十五批：提取与几何无关的覆盖率材质核心

新增内部 `_material_composition.py`：MaterialLayer 表达覆盖率遮罩、完整颜色分区、模糊半径及透明度作用域权重；compose_material_layers 按半径组合辉光再模糊，然后组合描边、填充，保留加权覆盖率的遮挡与饱和归一化。TrackRasterPlan 不再实现这套角色合成算法，只提供从歌词几何与扫色得到的材质层，并负责来源组件、音节和整行作用域。单平面快速路径继续复用原 RGBA 合成。

材质核心不依赖 Track、歌词、字体或时间。它预先诊断不匹配的作用域、非法半径/权重、错误角色模糊及层数预算；标准事件编码仍复用现有输出模块。公开 Scene 材质绑定尚未完成，因此本批不新增尚无完整语义的作者侧 API，也不将通用 rasterize_group 等同于这一覆盖率模型。

现有 Track 栅格、独立材质参考与覆盖率栈 57 项回归通过。新增 tests/test_material_composition.py 的 6 项程序化遮罩测试，独立于字形布局，覆盖填充对描边/辉光的遮挡、不同权重、几何范围、颜色交界先合并后模糊、单/多平面量化差、非法契约及实际 libass 标准 ASS 回读。共享核心五项主要测试加入后完整测试 944 passed、16 subtests passed（27.32 秒）；随后补充标准 ASS 回读，六项定向测试通过。Ruff 与 ty 均通过。

修正迁移文档中仍称可编辑 Track 公共入口未实现的旧描述。下一步仍需将共享覆盖率材质接入可编辑场景的对象/属性模型，保留局部、音节和整行归属，并完成全案例视觉与发行验收；整体目标未完成。


## 第二十六批：Scene 几何接入共享覆盖率材质求值

新增内部 SceneCoverageSampler，直接消费 ObjectGroup/TextObject/PathObject。复用 SceneEvaluator、ClipResolver 与 _painted_events 处理世界几何、字体、仿射降级和遮罩，分别提取填充、描边与显式辉光覆盖率，交给上一批的共享材质核心。每个叶对象暂为一个组件，各组按原子子树合成并在结束后施加本地透明度。源对象、来源、局部时钟与延迟复制保留。

填充/描边使用现有 PaintField，辉光支持独立的颜色场，在模糊之前分配颜色。MaterialLayer 增加横纵分区：纵向遮罩临时转置着色，再回到世界方向参与统一模糊和合成。窗口/对象/路径/颜色分条预算在可确定时提前检查；无效辉光半径也在回调前拒绝。路径动画返回 None 时真正隐藏填充、描边和辉光，修复原型中错误退回原始路径的行为。

新增 tests/test_scene_coverage.py 的 11 项测试：文字/路径填充描边参考、根透明度、嵌套组遮挡、显式辉光、运动/遮罩/任意跳转/延迟复制、回调前预算、横纵颜色场、辉光跨前沿扩散、空路径及标准 ASS 编码回读。颜色场覆盖率 alpha 与原生参考相同；额外 8 位预乘/还原在黑白背景的当前夹具中最多产生 1/255 显示差，不能扩大为任意输入的误差承诺。共享材质另增加纵向分区的独立世界像素参考。

完整测试 957 passed、16 subtests passed（32.18 秒）；随后强化非法辉光半径预检，11 项定向测试继续通过。Ruff 与 ty 通过。SceneCoverageSampler 保持内部：多叶对象材质组件、Track 不同来源权重、帧网格和统一编译预算尚需接入；不以当前单叶组件原型宣称 Track 材质迁移完成。完整案例与发行验收继续保留。

## 第二十七批：多对象覆盖率组件与贡献透明度

SceneCoverageSampler 增加内部 components 选择：指定的 ObjectGroup 后代成为一个材质组件，共享填充/描边/辉光角色的覆盖率合成。组织组保留几何、遮罩、寿命及贡献透明度；等半径辉光先合并再模糊，各角色按固有覆盖率遮挡。贡献透明度不同使用双平面加权覆盖率，相同则在已明确的组件内选择单平面快速路径。组件关闭后，普通父组与兄弟组件继续按组图层和各自透明度合成。未指定的叶对象行为保持原有单叶组件语义。

预检拒绝未知/非组组件身份和嵌套组件，先于动画回调；组件内错误继续定位到具体叶对象及来源。组件复制后的身份目前由调用方显式提供，不将配置字典隐式绑定到旧对象。内部组件同角色是加法归一化，不以子对象 layer 改变材质角色顺序；兄弟组件的层级仍参与合成。

增加五项回归：不同颜色/透明度的重叠贡献有独立解析像素预期；同一形状的互补裁剪共享辉光后与完整形状逐像素相同；曝光容器、透明度权重和延迟复制保留；未知/嵌套组件提前诊断且叶错误保持身份；相同 alpha 的兄弟组件仍按身份与图层合成。最初独立矩形的拼接参考暴露抗锯齿差异，改用真正同源的互补裁剪验证扫色分区，未宣称材质合成等价于任意几何并集。

全仓库 Ruff、ty 通过；完整测试 962 passed、16 subtests passed（29.02 秒）。此步补齐多叶组件内部合成；Track 按目标变化的上级作用域权重、动态辉光外观及公开帧网格/编译入口仍需完成，整体计划继续进行。

## 第二十八批：有空间上界的动态辉光外观

新增内部 GlowFunction，纯函数接收世界 VisualState 与叶对象出生后的秒数，返回 Glow 或 None。支持颜色、半径、宽度及透明度变化，None 仅隐藏辉光，填充/描边继续存在；辉光颜色场在动态外观之后执行。半径和宽度为脚本像素，是否跟随世界缩放由回调显式决定。

函数声明最大 blur/border 和局部断点；构造时检查有限值、范围和回调类型，采样器核对断点位于叶寿命内，并按视口加最大模糊核/宽度扩展进行保守像素预算预检，先于回调。每次返回值继续核验 Glow/None 和声明边界，错误保留叶身份与来源。声明上界过松可能提前超预算，不静默收窄。静态 Glow 也走相同的空间预检。

新增八项参数化/定向回归，覆盖任意顺序取样、局部出生时钟、延迟复制、世界缩放影响动态半径/宽度、仅关闭辉光、半径/宽度像素预检不调用函数、局部断点、运行时越界来源及非法声明。完整测试 970 passed、16 subtests passed（29.64 秒）；随后强化父组缩放的世界状态断言，覆盖率场景 24 项定向测试通过。Ruff 与 ty 均通过。

动态辉光目前仍为内部覆盖率求值能力。下一步需完成按目标变化的上级作用域权重，以及将该模型接入 Track 适配和统一帧网格/输出入口；尚未宣称高级材质迁移或整个计划完成。

## 第二十九批：按视觉贡献携带上级透明度作用域

新增内部 ScopeOpacity，按叶身份绑定额外透明度因子及明确的 owner。owner 可为该叶或真实祖先，函数接收 owner 出生后的秒数，因子与 owner 原有状态 opacity 相乘；不改变几何求值或辉光回调的世界状态。预检核对目标、归属链、重复 owner 和局部断点，先于回调；运行时强制有限的 0–1 数值并保留叶来源诊断。

SceneCoverageSampler 增加多平面作用域求值路径。每个叶将局部权重和逐级祖先权重携带到材质层，组件内部先按未加权覆盖率完成角色遮挡，再逐层关闭组件及普通父组。上级权重不同不改变本级遮挡所用的覆盖率，因此不会因逐绘制层 alpha 而泄露被遮住的材质。组件内组织组仍折入贡献权重，组件外祖先保留各自合成边界；无有效规则保留此前快速路径。

预检将最大祖先深度所需的平面数计入保守像素预算，避免深层层级在第一次求值时才展开大量缓冲。共享材质层合成收敛到同一方法，普通与带权重路径均复用上一批核心。

新增六项参数化/定向测试，使用手算像素验证相同及不同整行权重、音节与整行两级关闭、组件保留上级权重；还验证归属时钟、延迟复制、空规则等价、无效归属/重复/断点的回调前错误、工作区预检和运行时来源。已有 24 项场景覆盖率回归保留。Ruff、ty 通过，完整测试 976 passed、16 subtests passed（35.80 秒）。

该步骤建立了 Track 不同目标的上级权重所需语义；实际 PreparedTrack→覆盖率场景适配、统一帧网格/公开编译入口、案例最终视觉与发行验收仍待完成。整体目标未完成。

## 第三十批：PreparedTrack 到可编辑覆盖率场景的适配

新增内部 track_coverage / CoverageTrack，将未降级 PreparedTrack 组织为整行、来源单元、正文/读音组件和唱前/唱后片段。保留来源、字体、布局及时间；几何/填充/描边复用 _text_object，透明度分离为明确 ScopeOpacity，辉光通过 GlowFunction 消费原材质绑定。调用者声明最终缩放后的最大辉光半径/宽度；转换与采样器预算预检均不执行动态属性回调。原 editable Track 的目标验证抽为共享方法。

新增 CoveragePartition 处理原 Track 的小数前沿：分区在着色前按每像素交叠比例分配覆盖率，而非整数 ASS 裁剪。区域数量、断点、横向色带组合预算和实际返回区域上界都受检查。现有前沿可随正向、轴对齐、等比的几何变换；二维旋转/剪切/不等比前沿明确拒绝，未静默使用错误投影。

新增六项 Track 适配回归：正文/注音分组、小数前沿与端点、辉光加缩放位移、不同唱前/唱后透明度及上级作用域、延迟回调与可编辑组平移、动态辉光颜色/宽度/半径，以及旧标准 ASS 在相同采样网格的实际渲染对照。现有夹具与原覆盖率后端逐像素相同；采样覆盖率对照关闭旧后端的原生整行 alpha 曲线优化，不扩大为任意时间的原生插值等价。另有两项基础测试验证手算的半像素材质混合及回调前区域预算。

Ruff、ty 通过；完整测试 984 passed、16 subtests passed（32.55 秒）。随后补充视口边界复现，发现真实差异：字形左边界 -12、辉光半径 8 时，旧后端在视口外采样，而 SceneCoverageSampler 先裁掉视口外覆盖率，最大 alpha 差为 41/255。复现以 strict xfail 保留在 test_track_coverage.py，不把它列为通过验收；必须补齐 overscan 后移除标记。适配仍为内部，公开编译入口、案例与最终发行验收继续进行。

## 第三十一批：视口外覆盖率采样与有限核对齐

修复上批保留的画面边缘辉光差异，移除 strict xfail。SceneCoverageSampler 按实际模糊核扩展采样画布，遮罩在原始世界坐标解析后与几何一起平移到扩展画布；输出覆盖率移回世界坐标，颜色场使用扩展后的负坐标/画面外区间，所有组件合成后才裁回视口。标准 Scene 降级仅增加可选的预解析遮罩参数，普通出口保持原路径。

最初按声明的最大半径固定扩展，虽修复 41/255 的原始差异，却在 0.1/2 px 半径的部分边界出现取整差。当前把两个职责分开：声明上界用于回调前的保守画布、输出模糊与作用域平面预算；每次查询在局部快照里求值活动辉光，再按实际最大半径的有限核决定采样余量，不修改原采样器状态，也不重复调用外观函数。

Track 边界复现扩为 6 个位置 × 3 个半径，覆盖左/右/上/下、角落及完全位于画面外仍能扩散到画面的字形；18 例与原 Track 栅格结果逐像素一致。新增 8 组正反矩形/矢量遮罩 × 横纵颜色场检查，确认 overscan 不改变世界坐标；覆盖率另对照未分条的普通 ASS 遮罩，避免将矢量色条额外抗锯齿缝当作参考。随后补充局部遮罩与非等比/旋转/剪切组合，验证遮罩先解析再做画布平移。

全仓库 Ruff、ty 通过；完整测试 1010 passed、16 subtests passed（32.85 秒），无预期失败。随后局部仿射遮罩回归加入后，65 项场景/Track 覆盖率定向测试通过。本批修复的是覆盖率采样，rasterize_group 的视口内 RGBA 烘焙契约不变。公开帧网格、Track 场景入口及完整案例/发行验收仍需继续，整体目标未完成。

## 第三十二批：公开覆盖率编译与固定作者示例

新增公开 compile_coverage(document, group, ...)，将已有覆盖率采样器接入 Document 保留、来源事件注释化、owner 再生成、标准 ASS 像素编码与统一预算。公开 GlowFunction、ScopeOpacity、CoveragePartition 和 CoverageResult，类型声明移至 coverage_animation；内部引用同步更新。结果包含 SceneResult、实际绝对采样时刻与显式空间量化容差。

帧网格包含对象寿命、状态/路径/遮罩动画、引用、颜色场、动态辉光、分区及作用域透明度断点，先在 ASS 厘秒网格分段，再按区间中心求值。完整帧数在回调前校验，最终核验事件、峰值、输出文本及含样式/来源注释的字节预算。输出同时合并相邻相同画面和变化画面中仍相同的像素矩形；出现空白区间后不跨空白合并。输入 Document 不修改，专用样式碰撞在回调前报错，样式插入避免改变原记录索引。

新增 tests/test_coverage_output.py 的十项回归，含实际 libass 与覆盖率参考逐像素对照、静态和局部矩形合并、消失/重现与反向跳转、文档保留和来源替换、幂等再生成、局部断点与量化误差、回调前帧预算、事件/字符/字节/峰值预算及样式碰撞。增加公开类型正例和四个反例，现有类型反例检查共 23 项。完整测试以 `uv run python -m pytest -q` 运行：1021 passed、16 subtests passed（31.79 秒）；Ruff、ty 通过。最初直接运行 pytest 控制台入口无法导入仓库 examples/tools，改用模块入口完成全量验证，未更改生产行为绕过测试。

固定 examples/scene_coverage.py 使用普通 TextObject、SoftSweep、纯函数动态辉光和组淡入淡出，输出 320×180、10 Hz、8/255 显式量化容差的标准 ASS。50 个样本合并后为 117,000 条可见事件、5,674 峰值、32,676,006 字节。tools.validate_scene_core 增加 coverage 模式；两次生成字节相同，实际 libass 300 帧连续播放与七次独立跳转一致，预览已检查。报告与图片保存至 docs/scene-coverage-validation.json 和 docs/images/scene-coverage.png，ASS 在 build/ass-engine/scene-coverage.ass。文档明确保持采样误差及高输出成本，不将该短例当作整曲性能验收。

本批完成通用覆盖率的公开编译入口。PreparedTrack 转换仍为内部，下一步需接到公开 Document/Track 前端，随后继续全案例逐项视觉、参考误差及最终发行验收。整体目标仍未完成。

## 第三十三批：公开 Track 覆盖率前端与可编辑注音示例

新增 prepare_track_coverage / PreparedTrackCoverage，把内部 PreparedTrack 转换接到上一批的 compile_coverage。准备结果保留 Document、普通组/文字对象、组件与材质配置；作者可以替换组、添加路径/动画或编辑绑定字典，然后输出标准 ASS。复用 _prepare_karaoke 的导入、选择、样式、布局、来源与 owner 管理，只为可编辑组构建增加内部类型化回调；原 prepare_track_scene 的原生分层透明度语义保持。空选择恢复来源并保留其他 owner，显式 items 不改对白，准备不采样动态属性函数。

修复实际集成发现的辉光断点遗漏：仅改变辉光时填充对象没有状态动画，原适配从填充动画推导断点会漏掉材料区间/关键帧。GlowFunction 现在直接从原属性和材料绑定取得断点，仍使用叶出生时钟；新增 30 ms 辉光动画夹具验证粗采样网格被正确拆分。

六项公共前端回归覆盖回调延迟、Document 不变、来源/其他 owner 保留与重新选择恢复、重复生成、根平移在实际 ASS 中的像素位置、自定义路径、对象/辉光上界、显式 items 与两级透明度参考。最后一项发现并记录了旧单平面透明度优化与新带权平面的舍入差异：该夹具 1.85 秒最大 RGBA 差为 1/255，黑白背景显示 RGB 差也至多 1/255，其余选定时刻相同。测试没有扩大为任意输入的误差承诺，也没有把该差异归因于空间量化。迁移文档说明两种时间/透明度降级的边界。

固定 examples/scene_coverage_tracks.py 从写死的 ASS 歌词配置正文、注音、扫色和辉光颜色变化，再编辑根组增加纯函数漂移和下划线。240×135、10 Hz、8/255 显式空间量化容差；72,722 条可见事件、峰值 2,610、21,745,391 字节。真实 libass 连播 300 帧与八次独立跳转一致，两次生成字节相同，预览已检查；报告和图片在 docs/scene-coverage-tracks-validation.json、docs/images/scene-coverage-tracks.png，ASS 在 build/ass-engine/scene-coverage-tracks.ass。

全仓库 Ruff、ty 通过，公开反例类型检查增加到 24 项。完整测试 1027 passed、16 subtests passed（35.09 秒）。额外检查覆盖率 → prepare_karaoke / prepare_track_scene → 覆盖率的两种往返，源注释与生成事件计数保持。公开 Track 覆盖率端到端路径已经接通；全案例视觉/参考误差、完整能力矩阵、整曲成本及最终发行验收继续推进，整体目标未完成。

## 第三十四批：当前安装包 ABI 验证与案例覆盖核对

增强 tools.validate_distribution：除检查 wheel 模块存在外，逐字节核对其 Python/类型文件与源码包一致；显式记录公共类型夹具和扩展反例结果。构建使用 /tmp/kara-engine-release-current/stage 独立暂存树，排除扩展缓存与本机无关 runtime-license 目录，只保留许可证声明；从生成的同一源码包构建三个本地 Linux ABI wheel。

第一次 Python 3.12 隔离检查发现上一批随后添加的文档片段使用了未定义 track，1026 通过、1 失败；因此未把初次产物记为通过。修正文档为完整的小型 Document/Track 示例，文档测试切换至临时工作目录以保护工作区文件，并检查 CoverageResult 有输出。重新生成源码包并重建三个 wheel 后，Python 3.12.16、3.13.11、3.14.8 各通过 1027 项测试及 16 项子测试，分别为 68.98、36.71、37.86 秒；每个安装环境均通过公开类型、24 个反例、27 个固定 Scene 导出及旧 CLI。所有 27 个示例在三个 ABI 下的 ASS 哈希完全相同。Ruff、ty 通过，源码包和三个 wheel 的 twine strict 元数据检查通过。

结果保存在 docs/distribution-validation-current.json 及三个 per-ABI JSON，包含源码/wheel 哈希、安装位置、示例哈希和许可证条目。当前产物没有捆绑外部系统共享库；auditwheel show 指出本机 CPython 3.12 wheel 需要 manylinux_2_38 符号，不能冒充 manylinux_2_28。对应构建镜像和 Windows 修复包仍需验收；没有发布、上传或打标签。

另逐例核对 E01–E12 作者代码及已有实际 ASS 报告，在案例卡补充实现/成本证据表。各原生/分条单例报告均在既定单例预算内，但四种背景、所有离散边界与独立参考误差尚未全覆盖。发现整曲夹具的 12 个工厂中包含 scene_follow，却缺少 E06 的 scene_cues 测量背景框/贝塞尔装饰；原 180 秒成本报告有效但不证明 E01–E12 全覆盖。下一步需加入 E06 并重新跑整曲验证，再推进完整视觉/误差和发行矩阵。整体目标未完成。

## 第三十五批：补齐整曲 E06 与独立导出对照

scene_whole_song 使用带明确 id、名称、工厂的 Case 表，逐项对应 E01–E12；E06 改为 scene_cues 的词背景框和贝塞尔装饰，scene_follow 保留为独立能力示例。180 秒、30 个六秒槽位及事前预算均不变。验证器先检查十二个 case id 和槽位覆盖，再保留原有连续播放、延迟复制、逆序独立跳转与重复生成检查。

新增逐例单独导出对照：每个原始示例单独 compile/save，系统 libass 渲染六秒 300 帧，与整曲首轮对应片段比较。十二例共 3600 帧相同，且各例都有画面变化；报告记录实际工厂、case id、独立 ASS 哈希，避免只比较重复槽位而遗漏持续发生的对象丢失。该参考仍由同一引擎输出，文档明确它证明组合一致性，不能代替独立视觉误差目标。

新结果为 89,916 可见事件、峰值 556、48,320,735 字节，预检估算 106,851；生成约 3.57 秒、连续 9000 帧约 14.55 秒，150 次逆序跳转一致，5400 帧重复槽位相同，重复生成字节相同。报告更新至 docs/whole-song-validation.json，旧报告保留为 whole-song-validation-initial.json。实际 ASS 位于 build/ass-engine/whole-song-current/scene.ass；E06 的四个实际整曲时刻预览已检查，保存至 docs/images/whole-song-e06.png。

完整测试 1027 passed、16 subtests passed（37.06 秒），Ruff、ty 通过。案例卡与 TODO 已标注该缺口解决。前三 ABI 安装报告是上批归档快照，发布前仍需重建包含最终案例更新的产物。接下来继续四种背景、关键离散边界和独立参考误差验收，以及剩余修复发行矩阵；整体目标未完成。


## 第三十六批：四背景播放与独立颜色参考

新增 tools.validate_engine_backgrounds，E01–E12 在黑、白、棋盘、自制 RGB 渐变上各渲染六秒 600 帧，并以另一个 renderer 按置换顺序访问全部时刻。48 组通过；整数毫秒时钟为 n*10+1，报告保留字体、背景和 ASS 哈希、逐帧检查及成本。实际预览已检查，保存为 docs/images/engine-backgrounds-E01.png 至 E12.png；白字无描边的 E03 在白底不可见，属于配色限制。该验证不宣称独立几何正确，也不是每帧启动全新 renderer。

新增 tools.validate_case_colors，以手写普通 ASS 获取字形覆盖率、独立标量公式检查 E09 渐变和 E11 扫色内部。初次发现目标 RGB (37,246,247) 被 FFmpeg 输出为 (48,227,228)：默认 ASS 颜色矩阵转换导致偏色。Document.create 现写入标准 YCbCr Matrix: None，两个手写 Scene 示例也明确声明；解析既有 ASS 仍保留缺省、TV.601 或 TV.709。新增元信息往返回归，将依赖固定记录下标的旧测试改为定位实际源行。

修复后四背景、13 时刻共 1,562,376 个不透明内部像素最大 RGB 差为 0，记录于 docs/case-colors-validation.json。填充与描边分别检查，E11 明确使用 20 ms 中点保持；抗锯齿边缘、辉光、连续时间误差及其他案例独立几何仍未验收。

重新验证整曲：89,916 事件、峰值 556、48,320,754 字节；生成约 4.06 秒，9000 帧连播约 14.86 秒，150 次独立跳转、5400 复制帧及 3600 单例对照帧相同，重复生成一致。新报告为 docs/whole-song-validation.json，RGB 修复前报告保存为 whole-song-validation-before-rgb.json；实际 ASS 位于 build/ass-engine/whole-song-rgb/scene.ass。E06 整曲预览也重新生成。

完整测试 1028 passed、19 subtests passed（39.04 秒），Ruff、ty 通过。三 ABI 归档产物早于本次生产代码修复，最终仍需重建；manylinux 与 Windows 修复包验收未完成。整体目标保持未完成。


## 第三十七批：独立文字几何与精确结束边界

新增 tools.validate_case_geometry，以手写原生文字 ASS 核验 E05 完成态、E07 未变形/恢复态，参考绕过 Scene、text_to_path 和路径编译。E05 根据原生墨迹框独立居中，不复用路径测量结果。通过 native libass 整数毫秒时钟，E05 检查 1600/1601/2500/4990/4999 ms，E07 检查 0/1/990/999/1000/4000/4001/4500/4999 ms；半覆盖率轮廓均满足双向 1 像素 Chebyshev 容差。两个案例在 5000/5001/5010 ms 均为空白。注入三像素横向漂移与完全缺失墨迹的反例均被检测到。

不混淆几何和抗锯齿误差：E05 最大覆盖率差 54/255、归一化 L1 约 1.403%；E07 分别为 11/255、0.391%。差异集中于边缘，参考/实际/差图已检查，保存于 docs/images/case-geometry.png，机器报告 docs/case-geometry-validation.json。原始 ASS 和参考在 build/ass-engine/case-geometry。该工具未核验动画中间的完整几何，也不证明跨播放器一致。

本批只新增验证工具与证据，未更改生产行为。实际工具运行通过，故障注入通过，全仓库 Ruff、ty 通过；未无理由重复上一批完整测试。后续仍需完成其余案例、动态几何与时间采样参考，以及最终发行矩阵，整体目标未完成。


## 第三十八批：书写笔尖断点修复与独立轨迹参考

核对 E08 实际输出发现独立笔尖 StateFunction 没有声明书写的离散断点，50 Hz 中点采样使 1.35/3.05 秒开笔提前 10 ms，2.25 秒停笔也提前。examples/scene_writing.py 的 AnimationClip 现显式传入 writing.breakpoints。移除这些断点的故障注入复现了三处错误；新增 tests/test_writing_example.py 在四段笔画起止前后 1 ms 检查实际 ASS 的粉色笔尖。

新增 tools.validate_writing，使用独立标量 Bézier 公式与每段 10,000 步弧长积分，不复用 WritePath/flatten/tip。检查 518 个整数毫秒时刻：383 个落笔位置、135 个抬笔状态均通过。相对明确的 20 ms 网格加断点、中点保持参考，笔尖最大偏差 0.21217 px；相对连续轨迹最大观测偏差 3.31188 px，单独报告且不承诺全时间误差上界。机器报告 docs/writing-validation.json；完整墨迹参考仍待验收。

重新导出 E08：387 事件、峰值 2、460,735 字节，重复生成一致，实际 300 帧连续播放与独立跳转一致，预览已检查。更新 scene-writing-validation.json 与图片，旧报告保留为 scene-writing-validation-before-boundaries.json。四背景工具增加 --case 选择，E08 四背景各 600 帧连续/置换访问相同，报告 engine-backgrounds-writing-validation.json；原全案例报告的 E08 条目明确为修复前快照。

整曲亦重跑：89,918 事件、峰值 556、48,321,970 字节，估算 106,867；生成 3.62 秒、9000 帧连播 14.70 秒。150 次独立跳转、5400 复制帧、3600 单例对照帧和重复生成一致。报告更新 whole-song-validation.json，旧版保留 whole-song-validation-before-writing.json。完整测试 1029 passed、19 subtests passed（35.45 秒），Ruff、ty 通过。最终发行归档必须包含本次示例和回归；其他动态几何/视觉证据与发行矩阵仍未完成。


## 第三十九批：E10 动态孔洞和字形的独立参考

新增 tools.validate_morph。圆环参考采用解析圆与方形周长等距 64 点，按独立 smoothstep 插值，孔洞反向，不使用 VectorPath、resample_path、MorphPath 或 Scene 降级。B 参考采用手写原生文字 ASS，再以独立逆仿射公式缩放和错切覆盖率，绕开文字转路径与路径插值。

两对象各核对 55 个整数毫秒时刻，含 1/4 秒前后 1 ms；参考显式按 20 ms 中点保持。半覆盖率轮廓的双向 Chebyshev 距离均在 1 像素内，孔洞保留，5000/5001/5010 ms 无残留。故意填孔但保持外包围盒不变的反例被拒绝。圆环最大覆盖率差 53/255、归一化 L1 最大 0.05281%；B 分别为 78/255、2.07881%。B 参考包含原生文字光栅化及双三次重采样，边缘差不与几何容差混为一谈。

报告 docs/morph-validation.json，实际/参考/差图 docs/images/morph-reference.png 已检查；原始 ASS 和手写参考保存在 build/ass-engine/morph-reference。本批只增加验证工具与证据，未改动生产代码或示例；工具运行、全仓库 Ruff 和 ty 通过。E10 连续时间误差及其他播放器仍需单独检查，其余案例与最终发行验收继续推进，整体目标未完成。


## 第四十批：E12 导唱布局隔离与标签参考

核对输入标记、CuePreset/CueFactory 与普通对象生成路径，确认 E12 的行内条形/数字和独立 READY/SET/GO 使用同一类型化模型；自定义图形工厂继续由 scene_cues 的 sparkle 展示。新增 tools.validate_cues，手写原生 ASS 为独立标签参考，只直接测量固定字体用于居中，不经过 CueFactory、bind_cues 或 Scene 布局。

29 个整数毫秒时刻检查独立标签切换前后、第二个行内提示时段和结束边界；独立标签覆盖率与参考差为 0。将歌词根组平移 (40,20)，实际正文、注音及行内提示覆盖率与原图平移逐像素相同，独立标签区域不变。5 秒结束后为空，生成 Dialogue 不包含 cue/ruby 输入标记。报告 docs/cues-validation.json；实际、平移与手写参考 ASS 在 build/ass-engine/cues-reference。

重新运行 test_document_text/test_scene_text/test_lyric_cues，共 32 项通过，覆盖颜色作用域、输入与直接标记等价、来源与时序、自定义工厂、占位释放和注音/背景跟随及错误来源定位。全仓库 Ruff、ty 通过。本批未修改生产行为或作者示例；正文/注音绝对布局与全部行内图形独立参考仍待完成，最终发行矩阵也未完成，整体目标继续保持。


## 第四十一批：E02 逐字入退场与轨道几何参考

新增 tools.validate_staggered，独立标量公式计算各字位置、入场过冲和透明度，再直接写静态 ASS；不调用 SceneTimeline、Tween 或示例 bounce。核对 80 ms 入场错峰、650 ms 进入、40 ms 退出错峰和 500 ms 退出，空格保留索引和 59 px 步距但没有可见墨迹。参考采用 20 ms 网格与每字断点、中点保持。

166 个整数毫秒时刻覆盖每字动画边界前后 1 ms；实际填充、描边各自乘透明度后的覆盖率与独立参考最大差均为 0。轨道菱形另以三角函数计算位置和旋转并写绘图 ASS，半覆盖率轮廓满足双向 1 像素容差；最大覆盖率差 48/255，归一化 L1 最大约 3.477%。轨道寿命之外为空。报告 docs/staggered-validation.json，实际 ASS 在 build/ass-engine/staggered-reference。

本批未改生产代码或作者示例，验证工具实际运行通过，Ruff、ty 通过。覆盖率平面比较没有扩展为任意叠层合成或连续时间误差承诺。其余案例的独立参考和最终发行矩阵仍需推进，整体目标未完成。


## 第四十二批：E03 解析圆弧和单次注音变换参考

新增 tools.validate_round，以解析半径 240 的圆、六个等 advance 的角位置和切线方向构造手写原生文字参考，不调用 layout_path、Polyline 或 Scene 组变换。正文/注音共享一次缩放，注音偏移 52 px，两轮 250 ms 高亮由独立标量公式计算；采样明确采用 20 ms 网格加断点、中点保持。

98 个整数毫秒时刻覆盖两轮起止前后 1 ms，半覆盖率轮廓满足双向 1 像素容差。故意让注音缩放两次的反例被拒绝。实际一度步进折线与解析圆的边缘不同，最大覆盖率差 106/255、归一化 L1 最大约 3.707%；不以几何通过声称像素相同。共同不透明且内缩一像素的内部共 37,215 个像素检查 RGB，最大差为 0；5000/5001 ms 全部为空。

报告 docs/round-validation.json，实际/参考/差图 docs/images/round-reference.png 已检查，原始脚本和参考在 build/ass-engine/round-reference。本批仅新增验证与证据，未改生产实现或示例；工具运行、Ruff、ty 通过。连续时间误差、其余案例与最终发行验证仍需继续，整体目标未完成。


## 第四十三批：E04 发射表、出生捕获与原生历史运动

新增 tools.validate_sakura，检查 18 片环境曲线花瓣、6 片直线花瓣和 12 片游标触发花瓣的身份、发射表与三秒寿命。触发位置以作者游标起点/路程为输入，按出生时间独立计算线性位置；未把该项扩大为歌词绝对排版验证。初次使用整行 native text_extents 作为布局宽高参考时，与当前字符布局存在亚像素差异，因此明确拆开排版参考与出生捕获的验证职责，未放宽实际轨迹的 1 像素阈值。

实际独立导出游标和四个残影，检查生灭边界前后与多个中间位置；30 个可见质心位置最大误差约 0.0851 px，残影 alpha 与 0.4×0.7 的逐层衰减相符，60 ms 逐层延迟与独立寿命一致。原游标为原生连续运动，残影对照明确的 20 ms 中点历史样本。六个直线花瓣各保留单个 native-move 事件，18 次位移检查最大误差约 0.1034 px。报告 docs/sakura-validation.json 保存作者参考参数及各独立 ASS 哈希，脚本在 build/ass-engine/sakura-reference。

tests/test_particles.py 的 10 项检查通过，覆盖随机稳定性、工厂前预算、捕获/持续跟随、原生与曲线运动和残影；验证工具实际运行、Ruff、ty 通过。本批未改生产代码或作者示例。曲线 flutter 与完整重叠合成的独立参考、其余验收和最终发行矩阵仍需推进，整体目标未完成。


## 第四十四批：Document 文件入口等价性与功能清单复核

重新核对计划、TODO、Scene/Document/Cue 类型与契约、预算与来源回归，发现基础接口定义仍有历史未勾选项，而后续阶段实现与测试已提供证据。本批更新 14 项明确的定义/实现/确定性检查，逐项附实现、测试或报告位置；没有将表达能力、接口定义或类型检查等同于全案例视觉/发行验收。TODO 现有 51 项勾选、40 项保留未完成，阶段退出条件仍未整体通过。

新增 tests/test_scene_document_roundtrip.py。E01–E12 各先以作者 Document 编译，再保存源 ASS、Document.load 重载并用同一对象计划编译，输出字节一致且源文档保持不变。另以含颜色标签、重置、正文注音和导唱标记的文件，在布局/导唱绑定之前重载，对照直接构造 Document 的输出，避免只覆盖已准备对象。新增 13 项全部通过。

同时复核并运行 Scene、文字、导唱、引用与粒子 74 项定向测试，公开类型正例通过、24 项错误扩展反例均被拒绝。完整测试 1042 passed、19 subtests passed（38.92 秒），Ruff、ty 与 git diff --check 通过。修正 scenes.md 中仍称局部/动态遮罩未实现的历史概述，明确 screen/local 两种模式。

下一步仍需补 E01/E06 的独立参考、曲线花瓣与书写墨迹等尚未覆盖的动态形状/边缘证据，汇总完整质量与成本结论，重建最终安装包并验证 manylinux/Windows 发行矩阵。本批没有缩减计划范围，也没有将本机测试替代发行平台验证，整体目标未完成。


## 第四十五批：E06 词背景、正文和贝塞尔装饰参考

新增 tools.validate_word_backgrounds，直接使用原生整词测量构造手写 ASS，不经过 DocumentLayout/CuedLayout/range_bounds。固定参考明确 72+12 px 的导唱保留占位、词框 6/8 px 内边距、64 px 正文以及按整行宽度计算的双三次曲线装饰。每种颜色角色分别提取覆盖率，避免背景框遮住文字差异。

1000/1001/1500/2500/3999/4000/4999 ms 七个时刻的四角色共 28 项检查满足双向 1 像素半覆盖率轮廓容差；最大边缘差 34/255，来自整词测量与塑形簇布局的亚像素差异，单独记录。5000/5001 ms 无残留。报告 docs/word-backgrounds-validation.json，逐角色实际/参考/差图 docs/images/word-backgrounds-reference.png 已检查；脚本与手写参考位于 build/ass-engine/word-backgrounds-reference。

本批仅新增验证与证据，未修改生产行为或示例。工具运行、Ruff、ty 通过。1 秒前自定义导唱、描边和最终图层合成仍不由此参考证明，其他未完成验收与最终发行矩阵继续推进，整体目标未完成。


## 第四十六批：E01 正文与注音共享脉冲的前景几何

新增 tools.validate_lyric_geometry，以原生整字和整段注音测量构造手写 ASS，独立计算正文中心枢轴、注音位置与 sin² 缩放包络，不复用歌词布局、unit_group 或示例 pulse。参考采用 20 ms 中点保持，分别覆盖 1–2.2 秒、2.8–4 秒两段演唱。

59 个整数毫秒时刻含边界前后 1 ms。实际输出仅提取完全不透明的前景填充，排除辉光与描边；正文、注音半覆盖率轮廓满足双向 1 像素容差。最大边缘差 51/255，未混同于几何失败或声称像素一致。5000/5001 ms 前景为空。报告 docs/lyric-geometry-validation.json、图片 docs/images/lyric-geometry-reference.png 已检查；原始和手写参考在 build/ass-engine/lyric-geometry-reference。

本批没有改动生产实现或示例；工具运行、Ruff、ty 通过。E01 辉光、描边和颜色合成仍需另行参考，其他动态形状与最终发行验收未完成，整体目标继续保持。


## 第四十七批：manylinux 实际构建与宿主字体依赖修复

发现本地已有可运行的 manylinux_2_28 镜像，通过 Podman 实际推进发行验证。独立暂存当前源码，排除扩展缓存和宿主 runtime-license 目录（保留 NOTICE），生成新源码包；在 AlmaLinux 8.10 / glibc 2.28 / Python 3.12.14 / HarfBuzz 1.7.5 / FriBidi 1.0.4 / Fontconfig 2.13.1 中安装依赖、从归档构建 wheel 并按现有 repair 配置修复，twine strict 检查通过。遵守 README 已明确的 Linux 宿主动态库策略，没有改为自包含 wheel，也未发布任何产物。

初次安装隔离测试为 1040 通过、2 失败、19 子测试通过（62.77 秒）。失败定位为旧字符测试使用 DejaVu 加宿主回退渲染 今天/かな，而随包 CJK 字体只包含 時々。新增重命名的 KaraTestMultiscript.ttf，包含 今天/かな/한글，沿用现有 Sarasa OFL 许可并在字体生成工具中加入可复现子集配方。两个测试显式选择该字体；原示例字体未修改。MANIFEST 和发行验证器要求新字体存在。

开发环境 33 项字符测试通过；原 manylinux 安装环境仅替换测试文件/夹具后，全套为 1041 passed、1 skipped、19 subtests passed（61.17 秒）。该次手工复验 PATH 未包含 ty 导致一项类型检查跳过，随后设置正确 PATH/VIRTUAL_ENV，两项类型检查及 24 个类型反例单独通过。Ruff、ty 通过。上述是诊断复验，初始归档尚不含修复，不能宣称最终发行包验收完成。

机器记录 docs/distribution-validation-manylinux-trial.json 保存归档/wheel/font 哈希、ABI 环境、auditwheel 输出及失败/复验摘要。工作目录 /tmp/kara-engine-manylinux-validation；首个容器已正常退出（测试失败状态），修正夹具的复验容器已退出。预装依赖的本地镜像 localhost/kara-engine-manylinux-audit:validation 可用于后续构建。下一步重建包含修复的归档、重跑 27 个示例与三 ABI 容器验证，再推进 Windows 矩阵及最终许可证/元信息检查；整体目标未完成。


## 第四十八批：包含字体修复的三 ABI manylinux 安装验证

在 /tmp/kara-engine-manylinux-fixed 建立新的干净暂存树，先在 manylinux 容器内收集原生依赖许可证，再生成包含 KaraTestMultiscript 和修正测试的同一源码包。归档 SHA256 为 87afd4f561af00b3050a40739dbc8765481cae32181a6229edbd1d8362d18952。分别用 Python 3.12.14、3.13.15、3.14.7 从该归档构建 wheel，执行现有 pyproject 配置的 auditwheel repair 和 twine strict 元数据检查。

三个 ABI 的安装隔离验证全部通过：每个 1042 passed、19 subtests passed、无跳过，测试耗时分别 62.20/48.42/49.63 秒；公开类型与 24 个错误扩展反例通过；27 个固定 Scene 示例和旧 CLI 通过。所有 27 个示例的 ASS 哈希跨 ABI 相同；十二个核心案例还与当前开发机四背景导出（含 E08 断点修复）哈希一致。验证器逐字节核对 wheel Python/类型文件与源码归档，记录安装目录以排除源树误导入。

汇总 docs/distribution-validation-manylinux.json，另有三个 per-ABI JSON，包含源码/wheel 哈希、许可证列表、native 文件列表、auditwheel 输出和实际解释器。容器基于 glibc 2.28 / HarfBuzz 1.7.5 / FriBidi 1.0.4 / Fontconfig 2.13.1。继续遵守 README 规定的 Linux 宿主动态库策略，不将该矩阵称为无需系统依赖的 wheel。容器与脚本正常完成，没有标签、上传或发布。

本批完成受测快照的 Linux 三 ABI 修复安装矩阵；Windows 矩阵、剩余独立视觉参考与最终整体验收仍未完成。后续生产代码或必需夹具变化需重建对应产物。更新发行说明与 TODO，整体目标继续保持。


## 第四十九批：E07 动态轮廓与解析采样误差界

新增 tools.validate_outline_motion，直接使用固定 DejaVu WAVE 的原生直线顶点，以独立标量正弦公式扰动后写原生绘图 ASS，不复用 text_to_path、VectorPath.map 或 PathFunction。工具断言五个闭合多边形轮廓和 A 的孔洞，其他字体/曲线不在此专用参考范围内。

55 个时刻包含入唱、恢复边界前后，半覆盖率轮廓满足双向 1 像素容差；最大覆盖率差 3/255，去掉扰动的反例被检出。报告 docs/outline-motion-validation.json，实际/参考/差图 docs/images/outline-motion-reference.png 已检查，原始参考位于 build/ass-engine/outline-motion-reference。

该已知公式的包络导数界为 π/3，顶点 x/y 速度界分别 4*(π/3+11)、4*(π/3+9)。20 ms 中点保持误差至多 0.01 秒，得到对应几何点偏差上界 0.627478953 px；线段凸组合保持此界。验证器核对采样间隔和时间量化条件，光栅/字体误差和寿命外显隐明确排除，不将该证明扩展为任意回调保证。

本批仅新增验证工具和证据，生产代码/固定示例/必要字体未变；工具运行、Ruff、ty 通过。上一批三 ABI Linux 的库和示例证据仍对应相同实现，完整发行归档应在最终收尾时包含新增文档/工具。其他视觉参考和 Windows 矩阵仍未完成，整体目标继续保持。


## 第五十批：E08 书写墨迹宽度与曲线参考

新增 tools.validate_writing_ink，以独立密集 Bézier 点、弧长前缀和 6 px 平端/斜接轮廓构造手写 ASS，不调用 WritePath、flatten、stroke 或场景几何降级。每段曲线固定 500 步，时间采用 20 ms 中点保持加笔画断点。此前笔尖参考使用同一组作者曲线的独立标量求值，本次扩展到实际墨迹几何。

66 个有墨迹时刻满足双向 1 像素半覆盖率轮廓容差；开笔前和 5000/5001 ms 为空，笔宽翻倍的反例被拒绝。最大覆盖率差 96/255，来自细分及笔画交叠的抗锯齿边缘差，不声称像素相同。报告 docs/writing-ink-validation.json，图片 docs/images/writing-ink-reference.png 已检查，原始输出与参考位于 build/ass-engine/writing-ink-reference。

本批仅增加验证和证据；工具运行、Ruff、ty 通过，未改生产实现和示例。最终笔尖/墨迹合成、连续曲线误差界、其他剩余视觉项及 Windows 发行矩阵仍需继续，整体目标保持未完成。

## 第五十一批：时间线公开采样断点与书写示例简化

核对 P1 编排接口时发现 AnimationClip 已支持 breakpoints，而 SceneTimeline.play 尚未提供入口。新增类型化 keyword-only 参数 breakpoints: tuple[float, ...]，复用 clip 的有限值/区间校验，明确采用本次 play 起点后的秒数，所有并行动画共享断点，重复排程保留各副本的局部断点。参数默认空元组，已有调用不变。

书写示例改用命名的 pen_motion 时间线，传入 writing.breakpoints；仍保留 StateFunction 自定义笔尖位置与显隐。生成的 ASS SHA256 为 8340af777f283f7e5d9fec697d8b9faa7355916ced0b763b7a17349eefacc056，与 writing-validation.json 完全相同，387 事件、峰值 2、460735 字节，既有视觉证据仍对应同一输出。

新增实际 libass 回归：出生于 1 秒的对象，等待 0.1 秒后安排含 0.35/0.75 秒断点的动画，重复两次，核对 1450/1850/2550/2950 ms 前后 1 ms 的显隐；另检查越界、NaN、无穷断点拒绝且不改变原排程。公开类型正例覆盖新参数。uv run python -m pytest -q：1047 passed、19 subtests passed；全仓库 Ruff、ty 通过。首次直接运行 uv run pytest 因 examples 未在模块搜索路径而在收集阶段失败，改用项目根目录的 python -m pytest 后通过。

本批修改了公共实现与示例源代码，已有发行矩阵仍仅证明此前快照，最终发行需重建。完整编排协议、剩余视觉及 Windows 发行验收仍未完成，目标保持进行中。

## 第五十二批：Scene 状态关键帧与固定编排示例

对照计划第 75 行，Scene 此前仅能手写逐段 Tween，没有状态关键帧入口。新增公开 StateKeyframe(time, target, rate) 与 SceneTimeline.keyframes：正且严格递增的局部秒数、多属性目标、逐段用户缓动；内部展开现有 AnimationClip/Tween，保持现有捕获、求值、冲突和编译策略，不新增平行的动画引擎。初值由对象 VisualState 或此前时间线提供，终值保持，遗漏属性保留已有状态/动画。插入先完整验证，失败不部分修改时间线。

新增 8 项测试覆盖乱序求值、非线性缓动、遗漏属性、后续 cursor、重复、与手写 play 的 ASS 字节等价、并行通道、冲突原子性、非法时间/目标。公开类型正例加入 keyframes；24 个既有错误扩展反例仍被拒绝。

固定 examples/scene_keyframes.py 展示回弹移动、两次变色、并行旋转、等待和淡出；只接受输出路径，生成标准 ASS。实测 147 事件、峰值 1、66916 字节；两次生成相同，300 帧连续播放与七个全新 libass 跳转帧一致。报告 docs/scene-keyframes-validation.json，实际预览 docs/images/scene-keyframes.png 已查看；该单例播放验证不替代完整 E01–E12 独立参考验收。

完整测试 1055 passed、19 subtests passed，Ruff、ty 通过。补充 scenes.md 关键帧单位、缓动、保持/冲突语义与例子。新示例会由发行验证器的 scene_*.py 自动发现；此前 wheel 快照未含这些变化，最终发行仍须重建。计划剩余整体契约、视觉、迁移与发行验收保持未完成。

## 第五十三批：歌词选择契约与词背景断点跟随

核对 document_lyrics.py、scene_lyrics.py、scene_text.py 与对应回归，补齐 scenes.md“歌词选择与来源范围”表：code point 半开范围、独立塑形簇、作者指定词范围、演唱单元与续唱片段、注音局部范围及源投影、空格/无时间文本。明确跨簇选择拒绝、正文与原文索引不可混用、单行绑定范围和多记录组合方式。P1 对应语义定义项已有实现和测试依据，标为完成，不据此标记全例视觉验收。

审查发现 DocumentLayout.background(follow=True) 只继承字符动画起止时间，遗漏内部 breakpoints；现将它们转换成场景绝对秒并加入背景分段边界。新增实际 libass 回归，以明确 PlayRes 的文档和屏内矩形排除渲染缩放/裁剪影响：对象出生 1 秒，等待 0.1 秒，动画内部 0.35 秒处跳转 100 px；背景在 1450 ms 前后 1 ms 精确切换，逆序查询结果一致。最初试验使用不带 Script Info 的简化测试文档，受到 libass 默认分辨率与左边缘裁剪影响；已改为 Document.create(width=640, height=360) 并使用屏内位置。

63 项字符/歌词/绑定定向测试通过；完整测试 1056 passed、19 subtests passed；Ruff、ty 通过。修改生产代码，最终发行需在收尾时重建。其余计划契约、视觉与发布验收继续保持未完成。

## 第五十四批：输入标记 v1 契约与转义回归

核对 document_text.py 的 CueMarker、_cue 与解析分支，以及 bind_cues 的作用域/边界检查，补齐 scenes.md 的输入载体比较与 v1 契约。明确选择非执行行内注释保存锚点，标准 ASS 标签保留颜色/重置/演唱时序，Effect/Actor 保留旧选择语义；类型化 Python CuePreset 承担内容与动画配置。文档规定命名空间、版本/kind、大小写、必需/默认参数、未知/重复参数、POSIX 引用但不执行表达式、不可表示字符、记录级 id 作用域、原文诊断偏移与解码正文 offset 的区别，以及保存/再次生成规则。

新增 16 项回归覆盖含单双引号、Unicode、空格、制表符、等号及特殊字符的 markup 往返；未知 kind、未闭合引用、缺少等号、非法 offset 参数；emoji 后原始 Text 位置诊断；跨记录复用 id；花括号、反斜杠、换行禁止进入 id/preset。49 项标记/导唱/布局定向测试通过，Ruff、ty 通过。P1 输入标记载体契约项据实际实现与证据完成。本批只补充测试与文档，未修改生产实现或示例输出；其余视觉与最终发行验收继续进行。

完整测试结果：1072 passed、19 subtests passed（37.78 秒）。

## 第五十五批：双语、续唱、注音与跨行装饰组合

新增固定 examples/scene_bilingual.py，分别从两条源 ASS 事件绑定日文与英文；日文第一字使用 # 续唱，两次演唱共用同一正文/注音组，并按各片段缩放及变色。英文行独立时间轴以颜色高亮。类型化 singing_line helper 接收 LyricLayout，保留回调与组关键帧的高级自定义。两个不可见测量锚点置于各自歌词组，独立青色装饰通过 ReferenceFunction 查询两者世界坐标的中点；READY/SET/GO 则由输入标记绑定为固定画面位置的独立提示。

最初预览发现英文整词组缩放会挤压词间距，改为显式 scale_pulse=False 的颜色高亮；日文仍保留共用缩放。锚点使用布局中心的 x/y，而非顶部 y。最终预览 docs/images/scene-bilingual.png 已查看，报告 docs/scene-bilingual-validation.json：6731 事件、峰值 28、2997085 字节；重复生成相同，300 帧连续播放与 8 个全新跳转一致。该例仅证明逐记录组合，不宣称自动多行排版或任意译文对齐。

新增 tests/test_bilingual_example.py 验证两次高亮中的正文/注音来源和脉冲、英文不缩放、修改父组后的双目标引用/独立提示、源 Document 不变、两条源 Comment 和生成标签消费。完整测试在示例最终微调前通过 1075 项、19 子测试；最终示例重跑实际播放与 3 项组合回归通过，Ruff、ty 通过。发行验证器将自动发现新增示例，旧归档不包含本批文件，最终仍需重建。P5 跨行组合验证项据此完成，其余计划验收继续进行。

## 第五十六批：边界时序与 Document 塑形错误定位

核对 P5 短音节、零时长、连字、空格、字体回退及来源定位，发现 Document 绑定仅转发临时 unit 0 的塑形错误，没有源记录定位。scene_text.py 现在在布局/样式能力错误上补充记录下标、当前解码视图范围和样式名，以异常链保留底层原因；document_text.py 的 kt 逆行诊断也补充记录与解码偏移，不再只显示游标错误。

新增 DocumentLyrics 回归：k0、k1、零时长续唱及 kt 间隙保持原始秒数和来源，未改写显示窗口；样式重置后的不支持簇报告正确的非零文本范围并保留 cause。扩展现有 Linux 隔离 Fontconfig 测试，确认 DocumentLayout 的实际字体面与底层主字体/回退字体一致，缺字报错包含源记录/范围和底层异常。既有簇、连字、组合字符、空格和源偏移检查一起运行，共 66 项通过。

补充 scenes.md 边界输入语义及诊断范围；P5 对应项据此完成。零时长片段保持数据，作者需显式跳过其动画或另设显示寿命，不擅自拉伸演唱时间。Linux 字体测试不替代 Windows 字体提供器/发行矩阵。Ruff、ty 与相关格式检查通过；生产诊断改变，最终发行归档需包含本批代码。

完整测试：1078 passed、19 subtests passed（38.94 秒）。整体计划尚未完成，剩余视觉、契约与发布验收继续推进。

## 第五十七批：坐标、变换中心与编排协议核验

对照 scene_animation.py、scene_evaluation.py、object_references.py、geometry.py 和对应测试，补充 scenes.md“坐标与变换中心速查”。明确 Path/Text 的原点和 alignment、T×R×S×H 次序、剪切系数单位、父矩阵组合、组中心不自动推断、显式偏移实现任意 pivot、局部与世界求值及寿命夹取、FollowObject 的屏幕偏移和遮罩所属坐标。检查引用图确实包含父子边，带延迟的闭环仍在回调前被拒绝，原生事件不能冒充可引用对象。

同时核对第五十一、五十二批补齐后的动画接口：StateAnimation 声明写通道，Tween/StateFunction/StateKeyframe 共享 VisualState 与 AnimationClip；顺序/并行/at 错峰/wait/repeat、保持/释放、局部 breakpoints 和重复后的断点保留均有当前测试依据。因此 P1 的坐标契约、编排协议定义两项完成，并修正第十一批遗留的“完整仿射组合仍待完成”说明；不将定义完成解释为全部案例图像验收。

当前定向核验命令包含 test_scene、test_scene_affine、test_scene_references、test_group_masks、test_scene_masks、test_scene_keyframes、test_writing_example，共 88 项通过；Ruff、ty 通过。本批仅修改文档与清单，未修改生产实现/示例或生成 ASS，不重复完整测试。剩余计划和最终发行验收继续进行。

## 第五十八批：固定资产清单与可重跑审计

新增 tools.validate_engine_assets，使用现有检查依赖 fontTools 读取六份随附字体的 family/style、版权元信息、cmap 和字节哈希，核对四个改名子集的准确码点集合及字体/许可在 MANIFEST.in 中的显式包含。读取 scene_whole_song.CASES 固定映射，记录十二个作者源码文件的哈希及项目许可；输出 docs/engine-assets-validation.json，不将资源审计冒充实际字体选择或图像验收。

案例卡新增固定资产表，说明 DejaVu 主字体/斜体/强制回退子集、Sarasa CJK/韩文/多脚本子集及各自许可位置、再生成依赖。确认 CJK 仅含時々，多脚本夹具独立；短歌词、花瓣、切片、书写笔画、圆环/方形等由项目示例定义，没有待下载贴图或笔顺文件。外部模板仅作为计划中列明的机制参考；用户截图不作为分发素材。明确字体注册不能保证任意播放器选中相同文件，仍须提供字体。

实际审计通过 6 字体/12 案例，重复报告逐字节一致；在独立进程故意为 A/空格子集增加 B 的预期，审计在写报告前正确拒绝。全仓库 Ruff、ty 通过。本批新增工具和文档，未改生产实现/示例输出，不重复完整测试。P0 资产准备与参考依赖项完成；最终归档需收录本批工具/报告，其他视觉与发行验收仍继续。

## 第五十九批：全部曲线樱花的独立几何与透明度参考

新增 tools.validate_sakura_flutter，独立复现固定 seed/id/key 的参数、三次贝塞尔、smoothstep、横向收缩、旋转与淡出，用标量运算变换手写花瓣控制点后生成标准 ASS；不复用 MoveAlong、示例 PETAL、StateFunction 或引擎采样函数。检查出生相对的 20 ms 网格量化与 2.25 秒断点，覆盖全部 18 个 ambient 和 12 个 sung 曲线花瓣。ambient 出生位置也用独立随机参数核对，sung 出生位置取作者对象，其出生捕获另由既有 sakura-validation.json 验证。

最初三个整厘秒出生花瓣的 48 时刻通过，再扩展到全部 30 片、480 时刻。非整厘秒出生时 alpha 半整数的浮点舍入产生 1/255 差，采用预先质量目标允许范围内的 1/255 容差并逐项报告实际/预期 alpha，不改生产动画。全部填充半覆盖率轮廓满足双向 1 像素容差；最大抗锯齿覆盖率差 77/255。三个去掉旋转的反例被检出；量化寿命边界外无可见粒子。

报告 docs/sakura-flutter-validation.json，30 份独立 ASS 保存在 build/ass-engine/sakura-flutter，局部放大实际/参考/差图 docs/images/sakura-flutter-reference.png 已检查。描边、多粒子重叠合成、连续时间误差界、其他渲染器均明确留待后续。本批只新增验证工具与证据，未改生产库/示例；工具运行、Ruff、ty 通过，不重复完整测试。整体计划继续进行。

## 第六十批：樱花细描边的独立外轮廓参考

扩展 tools.validate_sakura_flutter 到同一 30 片花瓣、480 个时刻的描边。初始直接对透明度加权的细环做 128 阈值比较，在 ambient/1 的 2500 ms 失败：实际/参考外包围框相同，但 0.5 px 描边淡出后的超阈值像素分别仅 2 个/1 个，阈值点不构成稳定外轮廓。保留覆盖率差，不把不适用的阈值测试判作成功；改为未乘透明度的填充/描边包络检查外轮廓，细环本身的透明度加权覆盖率差单独报告。

480 项外轮廓均满足双向 1 像素半覆盖率几何容差；外包络最大覆盖率差 106/255，细环覆盖率最大差 141/255，明确不满足像素一致的主张。三个将参考描边强制加粗为 8 px 的反例均检出。此前 480 项填充、alpha 检查和旋转反例仍通过。

当前报告 docs/sakura-flutter-validation.json 新增 outline_checks 与方法说明，原填充阶段证据保留在 docs/sakura-flutter-fill-validation.json。实际/参考局部图已检查；本批不改生产库、示例或原 ASS 输出。Ruff、ty、格式检查通过；多花瓣重叠合成、连续时间误差与其他播放器仍待验证，整体目标继续进行。

## 第六十一批：统一入口的模块复用与迁移范围审计

逐入口核对 Engine.apply/to_scene、render_karaoke/prepare_karaoke、prepare_track_scene、prepare_track_coverage 及其底层适配，补充计划中的“当前模块复用与适配审计”。明确 Document 忠实解析与语义视图的分工，旧模板经 NativeEvent 进入 Scene，Track 准备/降级分离，普通可编辑文字与显式覆盖率合成各自的出口。特别记录 render_karaoke 复用准备和事件插入而保留历史 RenderResult/OutputSettings，并非直接调用 Scene.compile；不把共享架构描述成全部路径使用同一降级算法。

修订 track-migration.md 与 scenes.md 中第三十三批之后仍写作“覆盖率适配内部、下一步公开”的陈旧说明；底层函数保持内部，公共 Document 前端已提供。保留旋转/剪切/非等比自动前沿、每层透明度与整组覆盖率合成、采样保持与原生插值的真实差异。旧 Effect/Halo/逐字事件仍保留，无新增弃用日期；不能据“迁移”标记隐式删除旧能力。

定向运行旧 v0.1.0、旧 Scene 适配、Track 准备/可编辑输出/覆盖率前端、十二案例 Document 文件往返，共 82 项及 16 子测试通过；Ruff、ty 通过。P0 模块复用与旧基线审计项完成。本批仅更正文档与清单，不改生产实现/示例输出，完整视觉与发行验收仍继续。

## 第六十二批：樱花完整场景的四背景合成参考

新增 tools.validate_particle_composite。先验证 36 片花瓣，再扩展到完整 E04 的 42 个根对象：花瓣、歌词组、游标和四个残影。参考将各对象单独编译为 ASS，读取原生覆盖率位图，以独立的 8-bit RGB source-over 按稳定图层/来源顺序绘制；实际值由 FFmpeg 渲染合并 ASS。该方法验证组合顺序与透明度，不冒充独立的几何算法；几何已有前两批标量参考。

六个时刻 501/1301/2501/3001/3501/4501 ms，黑/白/棋盘/RGB 渐变四背景，共 24 帧逐通道最大差 2/255。显式计数的重叠像素分别为 0/673/12/0/53/0；故意反转顺序的参考能产生超过阈值的差异，确保不是仅验证互不相交对象。最终报告包含字体、背景、42 份单独 ASS/合并 ASS 哈希及实际 FFmpeg libass/Shaper 版本。

docs/particle-composite-validation.json 与 docs/images/particle-composite.png 保存最终证据，预览已检查；构建目录 build/ass-engine/particle-composite-full 保存实际 ASS 和背景。Ruff、ty 通过。本批未改生产实现或示例，不重复完整测试。E04 的有限时刻合成参考已补齐，连续时间误差界和其他播放器仍待验收，整体目标继续推进。

## 第六十三批：补齐可见扫色触发樱花并更新整曲基线

重新审查未完成清单时确认 E04 实际缺口：此前花瓣按游标发射，但正文没有可见扫色。examples/scene_sakura.py 现为所有歌词字符共享 SoftSweep，使用与游标相同的整行左右边界和 1–2 秒时钟；填充 24 px、描边 32 px，从白扫为粉。正文初始描边由黑改白是本次有意的视觉变化。保留现有矢量花瓣、种子、寿命、曲线、自定义 flutter、出生捕获和残影；游标原生连续 move 与颜色场采样保持的时域差异明确保留。

新增 test_sakura_example.py 检查共享范围/时钟以及实际 libass 的唱前白、唱后粉、中间连续色带。完整测试 1079 passed、19 subtests passed，Ruff、ty 通过。新单例输出 14805 事件、峰值 244、7053588 字节；仍低于 25000/1000/10 MiB 案例预算。validate_sakura 增加分组成本：18 环境曲线 2718 sampled 事件、12 触发曲线 1812 sampled 事件、6 直线花瓣仅 6 native-move 事件，并重验发射/历史/原生位移。

实际场景预览、300 帧连播/关键跳转已重建；四背景各 600 帧连续/乱序通过，新增 engine-backgrounds-sakura-validation.json。完整合成四背景 24 帧重新对照，最大 RGB 差仍为 2/255。42 个单独对象的旧/新 ASS 哈希仅 lyric 不同，已有粒子独立几何参考仍对应同一花瓣输出。文档主预览/当前报告更新，静态正文旧快照另存 *-before-sweep.json，资产清单的 E04 源码哈希及基线报告引用同步刷新。

180 秒整曲也重新生成并完成验收工具：120104 事件、峰值 556、62539000 字节、估计 142489 事件；生成 4.55 秒、9000 帧连续渲染 15.33 秒，十二例单独导出/重复片段一致，150 次独立跳转通过。当前 whole-song-validation.json 已更新，旧版保留 whole-song-validation-before-sakura-sweep.json。P0 樱花变体与 P3 独立/扫色触发及成本项据此完成。其余几何/颜色/连续时间和跨平台发行验收仍继续；新示例与工具必须纳入最终发行重建，不能沿用旧 wheel 结论。

## 第六十四批：修正扫色中心与发射位置，保留浮点合成参考

前一批测试只检查扫色和游标共享输入跨度，未覆盖实际过渡中心为确保端点完全换色而向外延伸半宽的行为。新增公开 SoftSweep.front_at(time) 返回实际中心，复用既有颜色场计算；time 为对象出生后的局部秒数。樱花游标改从左边界外 16 px 移至右边界外 16 px，残影和触发花瓣出生位置随之校正。颜色场仍采样保持，游标仍原生连续移动，不宣称采样区间内像素前沿严格一致。

新增缓动/不等填充描边宽度/区间外固定/非有限输入测试与类型正例，示例测试用独立公式核对中心。全测试 1083 passed、19 subtests passed，Ruff、ty 通过。单例仍为 14805 事件、峰值 244、7053588 字节；36 粒子出生及历史引用检查、四背景各 600 帧连续/乱序检查通过。曲线花瓣填充和描边各 480 项通过 1 px 轮廓容差，最大填充覆盖率差 72/255、外包络 106/255、细环 141/255，未声称覆盖率逐像素一致。

重叠合成最初在 2501 ms 渐变背景的一像素出现 3/255 差。追查独立参考发现每层提前量化 alpha 和 RGB 累积舍入；改为浮点 source-over、最终图像一次取整，保留原阈值 2/255。24 帧全部通过，反转图层的故障仍检出；预览已检查。更新报告明确记录参考运算方式，此参考验证合成顺序，不代替独立几何验证。

180 秒整曲重新验收：120104 事件、峰值 556、62539000 字节，9000 帧连续渲染 15.39 秒，3600 帧单例对照、5400 帧重复片段、150 次独立跳转通过。十二例独立 ASS 哈希仅 E04 改变。当前预览、六份报告及资产清单更新，旧报告保留为 *-before-front.json。连续时间误差界、其余案例完整视觉目标和最终跨平台发行仍待完成，整体目标继续。

## 第六十五批：自定义导唱图形的独立参考与案例范围核对

核对 E12 的作者接口和固定示例：scene_lyric_cues 包含行内 BarsCue、行内 TextCue 与独立 READY/SET/GO；scene_cues 的 sparkle 工厂直接返回普通 PathObject 和 Tween，提供独立矢量旋转/淡出。无需为特定形状新增引擎标签。P0 的“建立案例”项据此完成，P2 完整视觉验收仍保留。

新增 tools.validate_custom_cue，手写八顶点并用独立标量三角函数旋转，生成原生 ASS 参考；验证固定 50 Hz 中点保持及寿命边界。109 时刻、填充/描边共 218 项通过 1 px 轮廓容差；alpha 完全一致，最大填充覆盖率差 17/255、描边 134/255。故意偏移 5 px 被检出，1 秒后无残留。docs/custom-cue-validation.json 及三行覆盖率预览已保存并检查；参考图不包含淡出权重，alpha 另验。不将有限采样视为连续时间证明。

21 项导唱布局/自定义工厂回归通过，Ruff、ty 通过。本批未改生产实现或示例输出，不重复整曲和全测试；既有报告仍适用。计划中“尚未规定标签拼写”的历史描述已改为当前已实现的 v1 注释协议并链接详细契约。仍需补齐所有行内元素的独立绝对参考、其他案例视觉目标及发行验收，整体目标继续。

## 第六十六批：指定唱段触发与相对歌词锚点示例

对照计划的导唱触发/定位要求，确认 CuePreset.trigger 可直接使用解析后的任意 SingingSpan.start；普通对象引用可以提供歌词相对锚点，不需要再增加一种特殊输入标签或平行坐标模型。新增固定 examples/scene_cue_follow.py：第二唱段 ME 开始于 2.5 秒，READY/SET/GO 在此前一秒显示；透明子锚点参与歌词组位移和旋转，独立提示只跟随其世界 position，保持正立、原字号和不透明。

测试以独立三角函数核对倒序/重复时刻的世界位置，核对提示不继承透明锚点 opacity、不占正文宽度，并实际渲染 1499/1500、1830、2170、2499/2500 ms 边界，确认生成 Dialogue 消费标记、源注释保留唱词时间。2 项针对性测试、Ruff、ty 通过。本批不改引擎实现或 E01–E12 主案例输出。

验证工具新增 cue-follow 入口，最终示例 2541 事件、峰值 11、1103855 字节，重复生成一致；300 帧连播与 11 次新建轨道跳转一致。报告 docs/scene-cue-follow-validation.json 与预览已保存，scenes.md 补充固定定位/世界位置跟随/共同父组的区别和可运行示例。新增文件由发行验证工具的 scene_*.py 自动发现；最终发行重建仍待执行。整体目标继续。

## 第六十七批：首版能力边界与真实降级策略核对

新增 ass-engine-capabilities.md，对照 scene_output、scene_raster、_scene_coverage、cues 及已有契约，明确默认对象出口、显式高成本出口与不提供的语义。列出公开功能、实现/示例证据、默认预算、组透明度及模糊顺序、覆盖率分区与引用限制、文档保留和可编辑布局之间的边界；能力范围不缩减十二案例验收目标。

特别确认当前 Scene 只有 native-static/native-move/native-event 和 sampled 策略及后缀，没有通用 Tween/fade → 原生 t/fade 自动优化器。能力表明确此差距，TODO 的 P3 增加原生优化范围核对及实现后的语义/成本验证项，不以兼容原生事件已有标签冒充实现。P0 首版范围项据此完成，全部视觉/发行项继续保留。

运行对象/预算、仿射、整组栅格与覆盖率契约的 90 项测试通过；未改生产代码或示例。同步修正 scenes.md 仍引用旧整曲成本、旧花瓣覆盖率和旧重叠计数的当前态描述，保留进度历史。Ruff、ty 通过。整体目标继续。

## 第六十八批：显式原生连续 Tween 降级

新增 Scene.compile(native_tweens=True)，符合条件的单段、保持、线性 Tween 生成标准 ASS t，支持缩放、旋转、填充/描边颜色、透明度、描边、模糊及阴影的组合。报告 native-tween；预检按原生事件计数，最终预算照常检查。复杂父组、遮罩、材质、路径变形、引用、释放、自定义缓动、非正缩放及位置混合等组合继续采样。默认 False 保留旧中点保持输出，明确连续插值不是其逐像素等价优化；更一般的多段/复杂组合优化仍留待后续。

新增 tests/test_native_tween.py：手写原生 ASS 对照 13 个边界和内部时刻的完整 RGBA，全部相同；1 事件预算通过，默认采样超过 40 事件；另七种不适用条件回退正确。增加公开编译参数类型正例。完整测试 1093 passed、19 subtests passed，Ruff、ty 通过。

新增固定 examples/scene_native_tween.py：文字同时淡入、缩放、旋转、变色，输出 1 事件、峰值 1、1462 字节。实际标准 ASS 的 300 帧连播及 6 次新建轨道逆序跳转一致，重复生成一致；docs/scene-native-tween-validation.json 与预览已保存并检查。工具新增 native-tween 模式，文档说明适用条件、两种时间语义及回退。现有案例默认输出未改变，最终发行仍须包含新增源码及示例，整体目标继续。

## 第六十九批：顺序与并行 Tween 的原生串接

扩展显式 native_tweens 降级到多个保持的线性 Tween，先按开始时间排序，再仅为各段声明的属性输出 t。相同属性在不重叠时间段接续，不同属性可并行；任一片段不符合条件时整叶仍走采样，不将混合语义隐式拼接。默认输出保持不变。

新增路径对象对照：反向声明两个旋转段与两个透明度段，出生时间为 1 秒，包含停顿、重叠的不同通道和终态保持。16 次边界/内部/乱序重复访问与独立手写 ASS 完整 RGBA 一致；实际 alpha 与 Python 理想浮点求值的取整差不超过 1/255；寿命外为空。连同上一批文字与回退用例共 9 项通过，完整测试 1094 passed、19 subtests passed，Ruff、ty 通过。

scene_native_tween.py 改用 SceneTimeline 编排入场、停留一秒、并行退场，仍输出 1 事件、峰值 1、1579 字节。实际 ASS 300 帧连播和 8 次独立逆序跳转通过；新报告与预览更新，单段旧报告保留为 scene-native-tween-validation-single.json。文档能力表和 TODO 同步描述已实现范围；复杂父组、遮罩/材质、释放与非线性缓动的原生优化、默认策略选择和最终发行仍待完成，整体目标继续。

## 第七十批：P2 核心实现状态与未完成视觉验收分离

逐项核对 P2 对象/组与布局查询、类型化编排和随机访问求值、共享来源追踪、标准 ASS 能力检查、导出到真实预览的五项实现。新增 ass-engine-core-audit.md，逐项列出当前源码、针对性测试、可证明的结论和边界；TODO 对应五项改为完成。未将所有动画原生化、源计划可逆恢复或任意回调确定性列为已完成承诺。

核心八组回归共 104 项通过，Ruff、ty 通过；上一批全套 1094 项及 19 子测试仍为当前代码的完整基线。本批仅更新审计文档与状态，不改生产代码或示例，不重复视觉渲染。P2 的 E01/E02/E06/E12 完整质量与成本门槛仍待逐项合并验收，尤其辉光和行内元素绝对参考；阶段整体未完成。其他阶段及发行目标继续。

## 第七十一批：E12 行内导唱、正文与注音的独立绝对布局参考

扩展 tools.validate_cues：原生测量 SING /ALONG、sing/along 和数字整段宽度，以标量公式处理 84 px 条形占位、数字宽度加 12 px 间距、注音居中与 1/2.5 秒两次释放；手写条形路径和 330/670/1000、1830/2170/2500 ms 切换。参考不读取作者生成对象的位置，也不调用 CueFactory 或布局函数。

29 个时刻的填充和描边外包络均通过双向 1 px 半覆盖率几何容差，最大覆盖率差 34/255、69/255，描边细环最大差 69/255。保持独立标签、群组平移隔离与寿命结束检查；5 px 全局漂移和 8 px 描边反例均被检出。报告与左右覆盖率预览更新并检查，原报告存为 cues-validation-before-inline.json。

Ruff、ty 和完整验证工具通过。本批不改生产库或示例输出，不重复全套测试和整曲生成。P2/E12 的绝对布局参考缺口已推进；完整颜色合成、连续时间误差与其他播放器仍列为剩余项，不将轮廓容差当作逐像素视觉一致。整体目标继续。

## 第七十二批：E12 导唱与正文的四背景颜色参考

新增 tools.validate_cue_colors，复用独立的行内/正文/注音及标签手写 ASS，逐位图记录覆盖率为 255 且未被后续边缘混合的像素。实际值由 FFmpeg 渲染编译后的 ASS；参考按浮点 source-over 叠到固定黑/白/棋盘/渐变背景。使用实际与参考共同内部检查颜色，独立几何结论仍来自上一批，不因共同区域筛选而忽略轮廓缺失。

17 个时刻、四背景共 68 帧通过：473,688 个内部像素 RGB 差 0，其中黑描边 122,064、白正文/注音 325,640、青导唱 25,984。完整图像最大通道差 69/255，包括整段原生字形与逐簇输出的边缘差，未把该值隐去或放宽为像素一致。报告保存字体、背景、实际/参考 ASS 哈希和实际 renderer；三列实际/参考/8 倍差图已检查。

此前独立标签参考只用于覆盖率，默认白色未参与颜色判断；本批明确青色后重跑 29 时刻几何验证，通过并刷新哈希，原报告存为 cues-validation-before-color.json。Ruff、ty 通过；不改生产代码、示例输出，不重复全套测试与整曲。边缘/合成差异、连续时间及其他播放器仍须按案例质量目标合并验收，整体目标继续。

## 第七十三批：E12 有限静态状态的时间边界与案例验收

扩展 validate_cues，以严格白名单确认生成 Dialogue 只有静态覆盖标签、固定 owner Effect 和单个前置覆盖块。全部输出事件边界形成 0–6 秒的 9 个状态区间；逐区间比较首/中/末整数毫秒的原生位图完全一致，既有参考时刻覆盖每个区间。将 pos 改为 move 的反例被静态证明检查拒绝。固定倒计时的三等分边界量化最大 1/300 秒，低于 10 ms，不把这个状态穷尽结论应用到任意动画回调。

重跑当前 E12 四背景，每背景 600 帧连续/乱序一致；单例 300 帧连播和 11 次新轨道跳转通过，57 事件、峰值 23、25861 字节。独立 ASS 与整曲中 E12 的原始哈希不同，追查确认仅有 UTF-8 BOM 差异，utf-8-sig 解码后的全文严格相同。当前报告和预览更新，旧报告留快照，资产清单纳入新的 E12 四背景报告。

新增 e12-acceptance.md，逐项对应内容工厂、两种放置、占位、唱词时间、1 px 几何、2/255 内部颜色、10 ms 时间、四背景、预算及标记消费。结合现有自定义矢量/锚点跟随证据，判定 E12 固定案例达到约定 libass 首版门槛；TODO 增加明确完成项，不勾选其他三例或整个 P2。Ruff、ty、两项渲染工具与资产审计通过；生产代码未变，不重复全套测试。跨播放器、Windows 与最终发行仍待 P5，整体目标继续。

## 第七十四批：E06 导唱期间的完整参考与四背景颜色

扩展 validate_word_backgrounds 的手写参考：保留整词字体测量、矩形背景与贝塞尔装饰，加入独立位置/时间的行内短条和数字，复用标量旋转 sparkle 参考。22 个时刻覆盖初始、倒计时切换、采样边界及收尾，六类填充/描边角色共 125 项通过 1 px 轮廓容差；角色最大覆盖率差 125/255 单列。

validate_cue_colors 增加 E06 选择，按时刻使用完整参考，四背景 68 帧共检查 1,496,488 个共同不透明内部像素，六种预期颜色 RGB 差均 0，最终整帧最大差 34/255。半透明图形不计入内部不透明颜色结论，其 alpha 另由 custom-cue-validation 验证。新报告及三列实际/参考/差图保存并检查。共享工具默认 E12 重新运行，仍为 68 帧、473,688 内部像素差 0、整帧最大差 69。

Ruff、ty 和两个参考工具通过；本批未改生产代码、示例或其输出，不重复整曲和全套测试。E06 的时间、预算与当前输出一致性仍需合并审查后给出案例验收，其他阶段目标继续。

## 第七十五批：E06 全部输出状态与固定组合验收

将独立几何参考扩展到每个静态事件状态：0–6 秒共 54 区间，区间首/中/末原生位图一致；69 个参考时刻、407 项角色检查覆盖所有有内容状态。扩大覆盖后在 440 ms 的淡出白色细环失败，确认透明度阈值导致轮廓碎成孤点；改用未乘透明度的整场填充/描边外包络判断几何，原始角色覆盖率差单独保留。移除 sparkle 和加粗其描边均被新判据检出，1 px 容差未改变。几何比较最大覆盖率差 34/255，原始角色差最大 125/255。

当前输出重跑四背景每背景 600 帧连续/乱序，以及单例 300 帧/8 次跳转，全部通过。70 事件、峰值 19、36618 字节，最大量化差 1/300 秒；与整曲 E06 文本在解码 BOM 后严格相同。旋转/淡出仍明确为 20 ms 中点保持，不用有限状态输出替代理想连续动画误差证明。

报告/预览与资产清单更新，新增 e06-acceptance.md 将几何、前批四背景内部颜色、alpha、自定义内容、占位、时间、预算逐项合并，判定 E06 固定案例通过 libass 首版门槛。TODO 单列完成，E01/E02、其他阶段及发行继续。Ruff、ty、全部状态验证、两项播放验证与六字体/十二案例资产审计通过；无生产代码/示例变更，不重复全套测试。

## 第七十六批：E02 全部状态与四背景淡出合成验收

将 validate_staggered 扩展到全部 255 静态事件区间，严格静态标签检查和区间首/中/末原生位图一致；337 个参考时刻覆盖所有状态，文字填充与描边的透明度加权覆盖率差均为 0。独立三角函数装饰参考满足 1 px 轮廓容差，最大覆盖率差 48/255；时间量化差 0，最长采样保持 20 ms。

新增 validate_staggered_colors：23 时刻、四背景共 92 帧，手写参考的原生覆盖率以浮点 source-over 合成，实际由 FFmpeg 渲染。文字区域包括抗锯齿和淡出 alpha，最大 RGB 差 2/255；装饰覆盖并外扩 1 px 的区域从文字判据排除，其共同不透明内部颜色差 0，整帧最大差 26/255 单独报告。三列预览已检查；报告记录字体、renderer、背景和所有参考哈希。

当前四背景每背景 600 帧连续/乱序通过，单例 300 帧/6 次跳转通过。809 事件、峰值 11、334575 字节，重复构建一致，与整曲 E02 解码 BOM 后全文相同。更新报告、预览、资产清单，新增 e02-acceptance.md 并标记 E02 固定 libass 案例完成。Ruff、ty、参考与播放工具及资产审计通过，生产代码未变，不重复全套测试。P2 的 E01、其他阶段、其他播放器与最终发行继续。

## 第七十七批：E01 两层辉光的独立布局与原生 ASS 对照

新增 validate_lyric_glow，实际选取两单元的 wide/near 四个组保留其共享脉冲；参考不使用示例 glow 或框架布局/变换，用原生整段与孤立字形轮廓差得到位置、测量字形范围，以标量公式计算居中和缩放，再手写每个字形的边框/blur/alpha。

初始前缀宽度定位加独立浮点 source-over 的参考在 1 ms 黑背景出现 18/255 差；诊断发现其字形位置不等于轮廓网格定位，且直接用实际 ASS 覆盖率浮点合成与 FFmpeg 也有最大 4/255 的逐层舍入差。最终改为轮廓定位的手写 ASS，实际/参考使用同一 FFmpeg/libass，保持 2/255 阈值。17 时刻、四背景共 68 帧完整 RGB 差 0；将 near alpha 从 102 改为 166 的错误参考被检出。

报告保存字体、背景、实际与参考 ASS 哈希及 renderer，三列预览保存并检查。Ruff、ty 和最终验证通过；本批不改生产实现或示例输出，不重复全套测试。此对照验证框架的辉光表达，不是独立实现 libass 模糊算法；前景扫色/描边和完整 E01 仍待验收，整体目标继续。

## 第七十八批：E01 独立扫色公式与完整层次合成

新增 validate_lyric_sweep，复用上一批已核对的原生字形轮廓定位参考，独立计算固定屏幕前沿、填充 24 px 与描边 16 px 的标量 RGB。逐列计算颜色，仅合并完全相同的相邻颜色对，再手写 clip 事件；不调用 SoftSweep、PaintField、SceneTimeline 或 Scene 编译器构造参考。与两层原生辉光参考合并，实际为原示例完整输出。

17 时刻、四背景共 68 帧完整 RGB 差 0；将描边过渡宽度改成 24 px 的错误参考被检出。报告记录字体、背景、实际/参考 ASS 哈希和真实 renderer，实际/参考/8 倍差图保存并检查。Ruff、ty、最终验证通过。

本批没有生产代码或示例变更，不重复全套测试与整曲。有限时刻完整合成补齐了前景与辉光组合证据；E01 仍需全部输出状态、当前四背景播放与成本合并核对，连续理想函数及其他播放器不由此推断。整体目标继续。

## 第七十九批：E01 全部输出状态与 P2 固定案例验收

将静态标签证明扩展为允许固定矩形 clip；完整扫色参考覆盖全部 124 区间，在四背景比较 516 帧，完整 RGB 差 0，错误描边宽度仍被检出。分批读取 24 帧，避免同时保留全部图像。每区间首/中/末原生位图一致，时间量化差 0，最长中点保持 20 ms。

当前四背景每背景 600 帧连续/乱序通过，单例 300 帧与 11 次跳转通过；16614 事件、峰值 155、7567351 字节，重复构建一致，与整曲 E01 解码 BOM 后全文相同。报告和预览归档，旧报告留存，资产清单加入当前 E01 报告。手写参考与实际共享 libass，不扩大为独立光栅算法验证。

新增 e01-acceptance.md，结合已有 E02/E06/E12 逐项证据完成 P2 固定 libass 案例退出核对。核心、文件往返、原生 Tween、旧模板和导唱 108 项回归通过，Ruff、ty 通过。没有生产代码变化，不重复整曲或全套测试；P0/P1 未完审计、P3/P4 效果与 P5 发行仍继续，整体目标未完成。

## 第八十批：E05 运动碎片的独立几何与透明度参考

新增 tools.validate_fragments，从原生字体的直线/二次轮廓取点，二次段独立均匀细分为 64 份，用单独的半平面多边形裁切构建 4×3 网格。手写 ASS 参考独立计算 seed 37 键控随机、25 ms 出生错峰、smoothstep 聚合和 200 ms 淡入；不调用 split_path、路径布尔操作、Tween 或 Scene 求值构造参考。逐片隔离实际 owner 事件，检查所有局部量化区间首端及 +1 ms 和聚合结束。

12 片共 1794 项，含 1770 项有内容几何检查，全部满足 1 px 轮廓容差；alpha 完全一致，最大原始覆盖率差 94/255 单列。量化最大 5 ms，符合 10 ms 门槛；每片额外偏移 5 px 的错误参考均被检出。前三片 800 ms 实际/参考/差图已检查，参考样本和实际 ASS 留在构建目录。

报告、预览已归档，Ruff 与 ty 通过。没有修改生产代码或示例，未重复全套测试。此项补齐运动中每片形状、位置和透明度，不将独立碎片检查扩大为重叠合成或连续理想曲线结论；E05 四背景最终合成、预算及整体 P3 验收继续。

## 第八十一批：E05 重叠合成与固定案例验收

新增 validate_fragment_colors，复用独立密集轮廓/标量运动参考，聚合后改用原生文字居中参考。33 时刻、四背景共 132 帧，以浮点 source-over 与实际 FFmpeg 比较；排除每片实际/参考轮廓的局部边界区域后，内部 RGB 最大差 1/255。累计检查 8108 个重叠内部像素，含 2344 个半透明重叠像素；删除一片的反例被检出。全帧最大差 54/255 单列，几何另由逐片 1 px 参考验证。三列预览已检查。

静态白名单及全部 160 区间首/中/末位图一致；当前四背景各 600 帧连续/乱序一致，单例 300 帧/8 次新轨道跳转通过。880 事件、峰值 12、576897 字节，重复构建一致，与整曲 E05 解码 BOM 后全文相同。新报告、预览和资产清单更新，旧报告留存。

新增 e05-acceptance.md，完成固定 libass 案例的几何/alpha/合成/时间/预算逐项审查。粒子和文件往返相关 23 项回归、Ruff、ty、资产审计通过；没有生产代码或示例变更，不重复全套测试。P3 其他案例、连续理想动画界和其他播放器/最终发行继续，整体目标未完成。

## 第八十二批：P3 路径与采样核心核对

逐项阅读 Contour/Polyline/flatten、PathItem/layout_path、MoveAlong、仿射降级及 scene_output 的变化区间、断点汇总、中点求值、逐对象事件合并和复杂度报告。新增 ass-engine-path-sampling-audit.md 对应七类要求与具体实现/回归，明确 Contour 参数进度不等于弧长、切线差分在尖角的限制、量化后实际间隔、纯回调前提及序列化文本等价合并。

路径几何、粒子、场景、仿射、组遮罩、颜色场、引用和书写断点共 110 项回归通过，Ruff、ty 通过。将 P3 的路径能力及确定性采样/合并/报告两项标记完成；没有生产代码或示例输出变化，不重复视觉渲染或全套测试。P3 案例总体验收、扫色策略比较、原生优化范围与 P4/P5 继续，整体目标未完成。

## 第八十三批：原生 Tween/fade 的策略范围核对

核对 _native_move/_native_tween、绝对目标通道序列化、动画保持/捕获、父组引用依赖和时间量化。新增 ass-engine-native-tween-audit.md，逐项对应线性多通道、同通道顺序/异通道并行、淡入淡出以及材质/遮罩/变形/引用/父组等回退范围。明确默认中点保持与显式连续插值是不同输出语义，不因预算自动切换。

原生 Tween、关键帧、场景与引用相关 49 项回归、Ruff、ty 通过。重跑固定 native-tween 示例，1 事件、峰值 1、1579 字节，300 帧/8 次跳转和重复生成一致；报告及预览更新，保留旧快照。没有生产代码或示例变化，不重复全套测试。P3 的优化范围核对标记完成，剩余案例、扫色策略比较与 P4/P5 继续。

## 第八十四批：E03 全部状态与圆弧案例验收

解析圆弧参考扩展到全部有内容输出状态，198 时刻满足 1 px 轮廓容差，内部 RGB 差 0；0–6 秒 138 静态区间首/中/末位图一致，量化差 0，重复注音缩放反例仍被检出。覆盖率最大差 111/255 作为边缘差报告。

共享颜色工具增加 E03 分支及第二字体资产哈希，26 时刻、四背景 104 帧共 302716 个不透明内部像素 RGB 差 0，整帧最大差 106/255 单列；两轮中间态预览归档。默认 E12 重跑仍为 68 帧、473688 内部像素差 0。当前 E03 四背景各 600 帧连续/乱序及单例 300 帧/8 次跳转通过，348 事件、峰值 12、143630 字节，重复生成一致，与整曲 E03 解码 BOM 后全文相同。

新增 e03-acceptance.md 并更新 TODO、报告及资产清单，旧报告留存。相关粒子/布局与文件往返 23 项回归、Ruff、ty、资产审计通过；未改生产代码或示例，不重复全套测试。P3 其他案例、P4/P5 与整体目标继续。

## 第八十五批：E07 全部状态与轮廓扰动验收

标量轮廓参考扩展到全部有内容输出状态，175 时刻满足 1 px 几何容差，覆盖率最大差 6/255；保留四外轮廓与 A 孔洞检查及缺失扰动反例。全部 153 静态区间首/中/末位图一致，量化差 0；固定公式的连续位置误差界仍为 0.627479 px。参考新增显式青色，以供完整颜色对照。

共享颜色工具增加 E07 分支，将参考选择抽为类型化 references_at；E03/E06/E12 全部既有参考哈希保持一致。E07 四背景 104 帧共 672124 个内部像素 RGB 差 0，整帧最大差 4/255 单列，三列预览已检查。当前四背景每背景 600 帧连续/乱序及单例 300 帧/6 次跳转通过，152 事件、峰值 1、204507 字节，重复构建一致，与整曲 E07 解码 BOM 后全文相同。

新增 e07-acceptance.md，更新 TODO、报告、预览和资产清单，旧报告留存。相关几何与文件往返 28 项回归、Ruff、ty、资产审计通过；未改生产代码或示例，不重复全套测试。P4 另两例、P3 剩余及 P5 发行继续，整体目标未完成。

## 第八十六批：E10 全部状态与连续插值误差界

将圆环/孔洞和 B 字形的独立参考扩展到全部有内容输出区间，两对象各 175 时刻满足 1 px 容差；0–6 秒 153 静态区间首/中/末位图一致，量化差 0。圆环覆盖率最大差 54/255，字形原生图像重建差 87/255 单独记录；填洞反例仍被检出。

增加固定动画的连续位置界：测量实际源/目标对应控制点的最大位移，乘 smoothstep 最大导数 1.5/3 和中点时间偏差 0.01 秒。直线与三次曲线均为控制点凸组合，因此圆环界 0.207107 px，字形界 0.347224 px。工具显式检查缓动、时段、无额外动画/引用和单位线性变换前提，不把光栅/字体近似纳入此界。

报告与预览归档，旧报告留存。15 项路径几何回归、Ruff、ty 通过；没有生产代码或示例变化。E10 的四背景颜色/完整案例验收仍继续，不据此完成 P4。

## 第八十七批：E10 四背景颜色与形状插值验收

新增解析圆环与原生仿射字形的完整颜色参考，颜色工具增加 E10 分支。26 时刻、四背景 104 帧共 3352316 个共同不透明内部像素 RGB 差 0，整帧最大差 100/255 单列。为防止颜色比较掩盖参考位置误差，额外以新原生字形参考核对全部 175 时刻，满足 1 px 容差，覆盖率最大差 109/255；既有逆仿射图像参考保留。三列预览已检查。

当前四背景每背景 600 帧连续/乱序及单例 300 帧/6 次新轨道跳转通过，304 事件、峰值 2、647447 字节，重复生成一致，与整曲 E10 解码 BOM 后全文相同。相关几何与文件往返 28 项回归、Ruff、ty、资产审计通过。新增 e10-acceptance.md，更新报告、资产清单和 TODO；旧报告留存。没有生产代码或示例变更，不重复全套测试。E08、P3 剩余和 P5 继续，整体目标未完成。

## 第八十八批：E08 全部笔迹状态与笔尖形状

将密集曲线/独立描线参考扩展到全部有内容输出状态，216 项墨迹几何检查满足 1 px 容差，覆盖率最大差 96/255；共 195 静态区间首/中/末位图一致。新增独立 128 边解析圆笔尖参考，使用密集弧长计算中点位置，197 项有内容笔尖形状满足 1 px 容差，覆盖率最大差 106/255；停笔状态明确要求无粉色图形。

重新运行原有中心位置/显隐检查，518 时刻覆盖 383 次可见和 135 次抬笔，最大采样位置误差 0.212169 px；观察到的相对连续理想轨迹误差为 3.311876 px，保留该事实，不用采样位置容差代替连续误差。笔宽翻倍反例仍被检出，5000 ms 精确结束通过。

当前两份报告归档并保留旧快照。21 项书写边界及路径几何回归、Ruff、ty 通过；没有生产代码或示例变化。E08 最终笔尖/墨迹合成、四背景与整体 P4 验收继续。

## 第八十九批：E08 合成验收与 P4 固定案例退出

共享颜色工具增加 E08 独立墨迹/解析圆笔尖参考，覆盖落笔、停笔、结束与两层叠加。29 时刻、四背景 116 帧共 205744 个共同不透明内部像素 RGB 差 0，其中 453 个参考重叠位置进入实际内部比较；整帧最大差 67/255 单列，空白区间与背景完全一致，三列预览已检查。

当前四背景每背景 600 帧连续/乱序和单例 300 帧/6 次跳转通过，387 事件、峰值 2、460735 字节，重复生成一致，与整曲 E08 解码 BOM 后全文相同。报告、预览和资产清单更新，旧报告留存。新增 e08-acceptance.md，保留相对连续轨迹最大观察误差 3.311876 px，不把中点保持验收混为连续 1 px 目标。

书写/路径/文件往返 34 项及布尔/整组栅格 21 项回归、Ruff、ty、资产检查通过。结合 E07/E10 的几何、颜色、时间、预算逐项证据完成 P4 固定案例退出核对。没有生产代码或示例变化，不重复全套测试。P3 剩余、其他播放器和 P5 发行继续，整体目标未完成。

## 第九十批：E09 逐字配色与残影完整合成

新增 validate_gradient_echoes，隔离实际示例的 COLOR 行；参考手写五字的原生连续 move，以及 80/160/240 ms 延迟的中点保持残影，独立计算各字 RGB、0.35×0.7 次幂透明度及负图层顺序，不调用 echoes、ColorRamp、动画求值或 Scene 构造参考。四背景 28 时刻共 112 帧完整 RGB 差 0，包含逐层出生、移动、主体结束与残影逐层消失；删除第一层残影的错误参考被检出。

报告记录字体、背景、实际/参考 ASS 哈希和真实 renderer；实际/参考/差图已检查并归档。两侧共享 FFmpeg/libass，验证的是框架表达而非独立字体光栅算法。Ruff、ty 通过，没有生产代码或示例变更，不重复全套测试。上方固定屏幕渐变/描边整层参考及 E09 最终验收仍继续，整体目标未完成。

## 第九十一批：E09 渐变边缘与完整场景验收

扩展 validate_gradient_echoes，提供 bands 与 complete 模式。上行参考逐屏幕列计算填充/描边 RGB，仅合并完全相同颜色对，再手写原生 move 和固定 clip；完整参考合并上下行并显式恢复下行字号/零描边。上行及完整场景各四背景 112 帧完整 RGB 差 0，包含边缘和条带边界。错误描边颜色及完整场景缺失残影反例分别被检出，三列完整预览已检查。

当前四背景每背景 600 帧连续/乱序和单例 300 帧/6 次跳转通过，3196 事件、峰值 556、1364829 字节，量化差 0，重复生成一致，与整曲 E09 解码 BOM 后全文相同。报告/预览、资产清单和 TODO 更新，旧报告留存，新增 e09-acceptance.md。

颜色场、粒子及文件往返 36 项回归、Ruff、ty、资产审计通过。没有生产代码或示例变化，不重复全套测试。关键时刻 RGB 对照不冒充逐毫秒穷尽；默认残影中点保持与主体连续 move 的语义差别保留。P3 的 E04/E11、策略比较及 P5 继续，整体目标未完成。

## 第九十二批：E11 完整柔和扫色与辉光验收

新增 validate_soft_sweep，逐屏幕列独立计算填充/描边 24/36 px 过渡，手写互斥 clip 条带及独立整字恒定粉色辉光。153 输出区间首/中/末位图一致；四背景 624 帧完整 RGB 差 0，删除辉光反例被检出。每批读取 24 帧，报告保存字体、renderer、背景及实际/参考哈希；三列预览已检查。

当前四背景每背景 600 帧连续/乱序及单例 300 帧/6 次跳转通过，5667 事件、峰值 39、2455362 字节，量化差 0，重复生成一致，与整曲 E11 解码 BOM 后全文相同。新增 e11-acceptance.md，更新报告/预览、资产清单和 TODO，旧报告留存；同时完成 P0 中 E11 交界目标及背景参考项。

颜色场与文件往返 26 项回归、Ruff、ty、资产审计通过。没有生产代码或示例变化，不重复全套测试。恒定辉光不代替前沿颜色扩散模式；P3 的 E04、组合及策略比较和 P5 继续，整体目标未完成。

## 第九十三批：E04 歌词独立布局与扫色参考

审查 E04 现有粒子/合成报告时发现歌词绝对布局尚未独立检查。新增 validate_sakura_lyrics，用整段与孤立字形原生轮廓的位置差测量 SAKURA 的各字偏移、单字 advance 得到居中宽度，独立计算 24/32 px 扫色和半宽 16 px 的起止延伸。参考保留字形网格导致 U 的 -0.125 px 垂直位移，不以整段 advance 或前缀宽度替代实际轮廓定位。

隔离歌词层的全部 53 输出区间，四背景 236 帧完整 RGB 差 0，错误颜色反例被检出；量化差 0，区间首/中/末位图一致。报告含字体/renderer/背景和 ASS 哈希，预览归档。Ruff、ty、樱花示例及文本布局 18 项回归通过。

没有生产代码或示例变化，不重复全套测试。补齐的是歌词布局与前沿色彩，E04 的完整发射/曲线/重叠与当前输出证据还需合并核对后验收，整体目标继续。

## 第九十四批：E04 发射、直线几何及整例验收

将游标/触发出生参考由作者坐标改为独立原生整段/单字轮廓测量，计算歌词 advance 范围、高度、居中及 16 px 半宽延伸；36 粒子身份/寿命、12 次捕获、30 游标/残影及 18 直线位移检查通过。补齐 6 片直线花瓣的初始旋转/缩放、填充/描边及画外状态共 72 项独立几何检查。30 片曲线仍为填充/描边各 480 项，1 px 容差和最多 1/255 alpha 舍入差通过。

重跑完整叠加参考，四背景 24 帧最大 RGB 差 2/255，累计 2856 重叠像素，反转层序被检出。当前四背景各 600 帧连续/乱序及单例 300 帧/8 次跳转通过，14805 事件、峰值 244、7053588 字节，量化最大约 4.706 ms，重复构建一致，与整曲 E04 解码 BOM 后全文相同。预览已检查，报告/预览、资产清单更新且旧报告留存。

新增 e04-acceptance.md，明确几何独立参考与复用原生覆盖率的合成参考各自范围，标记 E04 固定案例完成。35 项樱花/粒子/引用/文件往返回归、Ruff、ty、资产审计通过。没有生产代码或示例变化，不重复全套测试；P3 组合与策略比较、P5 发行仍继续，整体目标未完成。

## 第九十五批：P3 遮罩与组变换组合验收

逐项阅读仿射和组遮罩回归，确认覆盖独立标量矩阵、显式世界遮罩、父级/子级坐标区分、嵌套孔洞、非凸及反向组合、组时钟/复制、镜像/退化和预算来源。新增 ass-engine-mask-combinations.md，列明参考独立范围及共享路径/光栅后端的限制。44 项组合回归、Ruff、ty 通过。

重跑 group-masks、affine、mirror，均为 300 帧/6 次新轨道跳转、重复生成一致、量化差 0；成本分别 905/5/567637、405/3/476600、387/3/770236（事件/峰值/字节），低于预算。共享遮罩预览已检查，三份报告/预览更新且旧报告留存。

结合已完成的 E03/E04/E05/E09/E11 逐例证据，标记 P3 案例与组合任务完成；扫色多策略比较、P0/P1 剩余审计及 P5 继续。没有生产代码或示例变化，不重复全套测试，整体目标未完成。

## 第九十六批：固定扫色多策略示例与生成成本

新增 examples.scene_sweep_strategies，固定 320×180、2 秒、10 Hz、白到粉的相同填充/描边前沿和恒定辉光。支持 bands、layers、raster、diffused 四种输出；16 层方案使用递增 alpha 权重，使理想内部累计透明度按 1/16 增加，避免以简单等 alpha 叠加制造必然偏差。raster 保留整组 RGBA，diffused 在着色后整组模糊；全部仅使用公共接口和标准 ASS 出口。

四模式生成通过，事件/峰值/字节依次为 419/27/178330、290/18/124882、51887/4365/17804049、83979/7022/28826025。明确实验预算为 250000/10000/128 MiB，栅格零颜色量化；普通单例预算不变。示例说明及生成测量归档，Ruff、ty 通过。尚未完成四背景图像差异/接缝对照，因此不勾选 P3 策略比较。整体目标继续。

## 第九十七批：扫色策略实测与 P3 退出

完成固定四策略的四背景实测，归档报告与四列预览。320 帧产生 240 项相对分条的 RGB 比较、60 项黑背景红通道覆盖比较。叠层整帧/内部差 85/7，覆盖只增不减（最大 85），显示重复抗锯齿绘制导致边缘变厚；零额外模糊栅格整帧/内部差 2/0，内部覆盖不丢失，但输出约大百倍；着色后模糊差 116/51、内部覆盖损失 46，明确为不同视觉语义。

新增 sweep-strategies-comparison.md，决定默认分条，保留显式栅格与模糊选项，说明样本范围和原始报告研究提示。已有报告与四份实际 ASS/字体哈希核对通过；不重复渲染。更新 scenes 和 TODO，完成策略比较及 P3 阶段门槛。

当前全套 1094 项测试、19 项子测试通过（39.69 秒），全仓库 Ruff、ty 通过。新示例需纳入最终发行包验证；P0/P1 剩余核对及 P5 继续，整体目标未完成。

## 第九十八批：Track 迁移与旧接口保留决定

核对 render 的共用准备分支、可编辑 Track 对象适配及 coverage 前端，阅读来源重建、双行分配、采样中心、材质/动态辉光、嵌套透明度、根组编辑和预算回归。新增 track-scene-migration-audit.md，集中列明三个出口、常用配置的共享实现与证据、显式能力限制和固定示例；为混有早期未接入描述的迁移文档增加当前状态入口。

重新执行相关 93 项测试、16 项子测试，8.14 秒通过。旧模板差分重新提取 v0.1.0，23 组去除新增归属注释后的完整 ASS 一致，单独归档 legacy-template-migration-validation.json。全仓库 Ruff、ty 与迁移文档本地链接检查通过。无生产代码变化，不重复上一批全套测试。

明确本次版本保留 Effect/recipe/Track 和旧模板入口，不加弃用警告、不设移除日期；显式 --templates 的命令行变化及毫秒/秒边界继续单列。完成 P5 的 Track 常用配置适配与旧接口迁移/兼容决定两项。最终发行、跨播放器、其余审计和示例检查仍继续，整体目标未完成。

## 第九十九批：作者指南与固定示例入口

新增 scene-authoring.md，提供 E01–E12 无输入文件的模块索引、各例修改点、自定义对象工厂与纯动画完整脚本、生成器/复制/持续跟随区别，以及时间单位、断点、确定性、预算诊断和显式昂贵出口说明。补充 layered_glow 的固定夹具命令与 Track Blur/旧 Halo/Scene 恒定辉光的有意差别。README 和 scenes 开头接入指南，修正早期“注音/粒子/Track 尚未接入”的过时说明。

layered_glow.apply 的路径参数与 RenderResult 返回值、main 返回值补齐类型；未改变输出逻辑。实际执行指南 Python 脚本，生成 400 事件、峰值 4、231226 字节标准 ASS；本地链接存在性检查通过。19 项 CLI/文档回归通过（3.91 秒），包括实例/子类配置逐字节一致；全仓库 Ruff、ty 通过。

完成 P5 示例与自定义使用文档两项。未将文档脚本运行当作全案例发行证明；P0/P1 剩余核对、播放器差异、预览/导出预算总审查与最终发行仍继续。

## 第一百批：实际 ASS 预览与预算总审查

核对单例、四背景和整曲工具均从实际落盘 ASS 渲染。validate_scene_core 增加导出/预览 SHA-256、复制后及渲染后字节断言，保证报告对应的预览输入与输出文件相同；将过时的“所有案例仍待验收”模板文字改为该工具的明确检查范围，不改已有历史报告。

重跑固定 sweep：5667 事件、峰值 39、2455362 字节，300 帧连续播放、6 次重新加载跳转和重复构建通过，导出/预览哈希一致；报告独立归档 preview-export-validation.json。新增 preview-budget-audit.md，核对预计/实际事件、字节、峰值、路径、条带、布尔、帧和像素预算及来源粒度，明确全局汇总错误无唯一对象。

82 项 Scene/栅格/覆盖率/组遮罩/布尔/颜色场回归通过（3.06 秒），Ruff、ty 通过。完成 P5 预览与预算检查；播放器差异、前期剩余审计和最终发行仍继续。

## 第一百零一批：全案例接口与明确预期核对

新增 case-interface-audit.md，对照 CASES 的十二例作者接口、模块依赖、明确边界与逐例独立验收，区分机制夹具与外部作品复刻。重新编译全部十二例，成本均低于默认预算，源码 SHA-256 与已验收资产清单一致；导入检查未发现私有模块依赖。机器可读结果保存为 case-interface-audit.json。

发现作者指南误将 E06 指向 scene_word_glow 扩展示例，修正为整曲实际使用的 scene_cues。案例卡增加当前核对入口，保留历史快照而不混淆其状态。13 项文件/Document 等价及标记绑定回归通过（2.97 秒）；24 个无效公开扩展契约正确拒绝，全仓库 Ruff、ty 通过，本地链接检查通过。

完成 P1 全案例接口/依赖核对和 P0 明确预期/参考项。扩展模板算法、环境与成本基线汇总、跨播放器和最终发行仍需收尾，整体目标未完成。

## 第一百零二批：环境与成本基线汇总

新增 engine-baseline.md 和 baseline-current-audit.json，统一当前十二例、整曲、固定字体/背景、真实渲染器版本、采样/播放时间基与预设质量/成本预算。重新编译并保存十二例及整曲，逐份实际 SHA-256 与现有四背景/整曲独立片段/整曲报告完全一致；成本字段一致，字体字节与报告一致。没有重新渲染或用历史源码状态推断新结果。

整曲仍为 120104 事件、峰值 556、62539000 字节，默认十二例及预设整曲预算不变。文档区分参考算法成本、实际输出、工具总耗时、纯渲染时间、BOM 字节及内存测量口径；历史快照保留。完成 P0 环境与成本两项；扩展模板算法核对、其他播放器和最终发行仍继续。

## 第一百零三批：外部模板扩展与标准输出算法核对

使用 gh 获取计划固定提交的七份模板，源码缓存于忽略目录 .firecrawl，哈希与链接归档。使用 firecrawl 获取 Aegisub 标签文档，核对直线 move 和矩形/矢量 clip 动画边界；本地 PyonFX 几何源码作为生成端操作参考。新增 template-standard-ass-audit.md，逐来源说明 Lua/ILL、word/mixin、帧循环、几何/随机数据如何转换为本库对象与标准事件。没有复制外部歌词或路径资产进入产品。

重新编译十二例并枚举可见 Dialogue 的覆盖标签。初始正则误把字体/重置样式参数算作标签，修正字符串参数归一化后全部属于当前标准集合；机器可读清单明确只检查名称，实际语义仍以既有 libass 验收为准。说明 NativeEvent 忠实保留任意调用者内容的边界，不声称自动净化全部外部模板。

完成 P0 最后一项扩展依赖与算法映射。此次无生产或示例代码修改，无需重复上一轮完整测试；其他播放器、最终发行及总验收继续。

## 第一百零四批：当前源码发行重建与首个 ABI 验证

增强 validate_distribution：在全部 scene_*.py 默认入口之外，运行显式 --templates 的 v0.1.0 夹具以及 layers/raster/diffused 三种扫色模式，分别保存输出哈希。Ruff、ty 和 git diff --check 通过；发行说明补充这些检查范围。

在 /tmp/kara-engine-final-linux 建立独立暂存树，排除本机缓存和无关 runtime-license，只保留 NOTICE，并在 manylinux 2.28 容器内重新收集许可证、构建当前源码包。Python 3.12 修复 wheel 的 strict 元数据、源归档/安装模块一致性、隔离导入、1094 项测试与 19 子测试（64.01 秒，无跳过）、公开类型正反例、32 个固定 Scene 示例、3 个额外扫色模式、原 CLI 和显式旧模板 CLI 全部通过。归档首个 ABI 报告 distribution-validation-final-linux-py312.json。

三 ABI 运行尚未结束：同一个容器 kara-engine-final-linux 和 exec session 60026 正在继续 Python 3.13，然后 3.14；不要重复启动或将本条视为三 ABI 完成。最终矩阵生成后还要比较额外扫色哈希。工作区后续新增发行说明/进度属于验证记录，当前包不包含这些事后记录；库、示例和验证器均来自受测暂存快照。P5 发行总门槛保持未勾选，Windows/其他播放器继续独立追踪。

## 第一百零五批：发行平台标签缺陷与修复

上一轮三 ABI 已全部正常结束：分别 1094 测试与 19 子测试通过（64.01/51.62/53.03 秒），32 固定示例及 3 额外扫色模式跨 ABI 哈希一致。重建前核对 293 个库/原生/示例/测试/工具文件与归档字节相同。诊断矩阵保存为 distribution-validation-linux-tag-trial.json，不作最终发行通过证据。

审查 auditwheel show 发现实际 glibc 符号最低 2.28，但修复产物自动附加了 manylinux_2_24 标签。pyproject 修复命令加入 --only-plat；实际重新修复 3.12 原始 wheel，文件名和 WHEEL 元信息仅保留 manylinux_2_28。validate_distribution 增加元信息标签检查，旧错误产物在安装前被拒绝。Ruff、ty 通过，文档说明先前运行测试不证明较低平台标签正确。

已建立 /tmp/kara-engine-final-linux-tags 新源码快照，包含修复和验证器；三 ABI 新矩阵将重新构建、修复、安装测试，脚本同时核对默认与额外扫色哈希。之前 session 60026 已 exit 0，不再等待该句柄；后续检查新容器与新 exec 句柄。Windows、播放器差异与总验收仍继续。

## 第一百零六批：播放器差异记录与修复包运行状态

使用 firecrawl 获取 libass 官方 VSFilter 差异说明及 mpv 稳定版手册，新增 player-compatibility.md 和来源哈希记录。区分官方确认的描边/字体/小数字号/颜色矩阵差异与本项目实测，提供禁用样式覆盖和保持 RGB 的 mpv 配置，但明确未执行 mpv/VSFilter 本项目像素验收。连接当前 libass 基线，完成 P5 的“基线与差异记录”项，不将此扩大为全部播放器逐像素一致。最初猜测的 wiki 页面地址不存在，最终使用官方实际页面 Differences-between-Libass-and-VSFilters，未引用无内容页。

修复平台标签后的矩阵仍在原 exec session 54717、容器 kara-engine-final-linux-tags 中运行；已确认 3.12 新 wheel 名称只含 manylinux_2_28，隔离全套 1094 测试/19 子测试通过（65.06 秒），当前继续示例输出。未重新启动该进程；两个其余 ABI 及最终矩阵尚未结束。整体剩余发行与总验收两项，Windows 平台仍待验证。

## 第一百零七批：修复包前两 ABI 通过与 Windows 运行环境

修复配置后的 Python 3.12/3.13 各 1094 测试、19 子测试、32 示例、3 额外扫色、类型与 CLI 验证全部通过。实际 WHEEL Tags 分别只有 cp312/cp313-manylinux_2_28_x86_64，保存两份 final-tagged 报告。原 session 54717 / 容器 kara-engine-final-linux-tags 已推进到 3.14 validate，仍在运行，未重新启动。

本机无 Windows Python/MSYS，只有 Wine。通过 gh 获取官方 uv 0.13.8 Windows 归档，在 /tmp/kara-engine-windows/prefix 独立 Wine 11.22 前缀运行，uv 成功下载并安装 Windows CPython 3.12.16。实际解释器报告 win32、.cp312-win_amd64.pyd，Python.h 与 python312.lib 存在；记录 windows-environment-probe.json。没有修改用户默认 Wine 环境。

该环境仅用于继续尝试 Windows 构建，不等同真实 Windows 验收。UCRT64 编译器/依赖、修复 wheel 和安装测试尚未完成；Linux 最终矩阵及整体目标仍保持进行中。

## 第一百零八批：修复标签的 Linux 三 ABI 最终矩阵

原 session 54717 正常 exit 0，容器退出，三 ABI 修复矩阵完成。每个 wheel 仅声明配置的 manylinux_2_28 标签，分别 1094 测试、19 子测试通过（65.06/52.25/52.40 秒）；类型正反例、32 默认 Scene 示例、3 额外扫色、常规 CLI 和显式旧模板 CLI 全部通过。两类示例输出的跨 ABI 哈希均一致。

重新核对当前 293 个库/原生/示例/测试/工具及字体/ASS 夹具与源码归档逐字节一致，另核对 pyproject/setup/MANIFEST。最终源码包 SHA-256 为 1a939536930948bcec2f15afdd3f2b1132c012f4a17a34866d7d634334f9fbd9。归档 distribution-validation-final-linux.json 和三个 final-tagged 报告，附 auditwheel 输出、严格元数据检查、native 文件及实际标签，发行文档明确替代旧诊断矩阵。没有发布产物；宿主动态库策略保持不变。

Windows 侧从官方 UCRT64 包数据库解析 44 个工具链/依赖包（约 125.4 MiB），逐包校验数据库 SHA-256 后解包到 /tmp/kara-engine-windows/msys64。Wine 下 GCC 16.2.0 可运行，并实际编译/运行 Windows C 程序，记录环境报告。下一步构建 native 扩展与修复/安装验证；这不等于真实 Windows 验收。下载 session 13739、编译探针 session 62333 均已正常结束，没有遗留运行任务。P5 发行总项及整体目标仍未完成。

## 第一百零九批：Windows 原生构建、DLL 修复与隔离安装

在独立 Wine 11.22 前缀内，以官方 Windows CPython 3.12.16、UCRT64 GCC 16.2.0 和 MSYS patch 构建最终 Linux 矩阵同一源码归档。libass 补丁、Meson 原生扩展编译和 wheel 构建成功；delvewheel 1.13.2 修复完成，包内包含 16 个 DLL。原始与修复 wheel 哈希已写入 windows-environment-probe.json。这里的“Windows”指实际 Windows ABI 产物，运行宿主仍为 Wine，不冒充真实 Windows 验收。

修复工具在 __init__.py 前添加 DLL 目录加载代码。发行验证器仅对 Windows wheel 接受核对过的完整 bootstrap，去掉后仍逐字节比较全部原始 Python/typing 文件；实际产物通过，篡改 bootstrap、追加源码及把 Windows 修复内容用于 Linux 比较均被拒绝。全仓库 Ruff、ty 与 diff 空白检查通过。此次修改仅涉及验证工具与说明，库/示例保持受测归档版本；Linux 既有报告对应旧版验证工具快照。

session 66873 正在运行 /tmp/kara-engine-windows/validation-cp312 的隔离安装验证，PATH 已去掉 UCRT/MSYS 编译路径。安装及隔离导入通过，pytest 仍在运行；不得将本条视为全套或三 ABI 通过，也不要重复启动已有进程。整体发行与总验收继续。

本批后续：session 66873 已 exit 1；完整 pytest 结果为 1088 通过、19 子测试通过、1 个 Linux Fontconfig 专用测试跳过、5 个文档示例失败（104.00 秒）。五个失败均为 test_track_docs 在 Windows cp1252 下读取 UTF-8 中文 Markdown，未出现其他实现失败。将该文件读取改为显式 UTF-8 后，在同一隔离安装目录覆盖测试文件重跑，5 项全部通过（2.15 秒，session 88709 exit 0）。这项覆盖重跑不是干净源码包验收；下一步需更新验证快照，继续全部测试、类型、示例与其他 Windows ABI。Ruff、ty 通过。

本机同一文档回归使用 `uv run python -m pytest tests/test_track_docs.py -q`，5 项通过（0.83 秒）；直接使用 pytest 可执行入口会因 examples 不在模块搜索路径而收集失败，因此使用项目模块入口执行。当前本批构建、完整测试及修复重跑句柄均已终止，没有需要继续等待的任务。

## 第一百一十批：三 Windows ABI 与控制台编码修复

从受测源码包制作 UTF-8 文档测试/验证器更新快照。CPython 3.12/3.13 的安装测试分别 1093 项、19 子测试通过（106.98/94.78 秒），各跳过 1 项 Linux Fontconfig 专用测试；公开与反例类型检查通过。随后固定示例在 scene_cues 的 Unicode 箭头日志处失败，ASS 已写出。核对所有 Scene 示例后，仅 scene_cues 与 scene_staggered 有同类控制台提示，将它们统一为其他示例的 ASCII 统计信息。两个失败任务 session 37980/84022 均 exit 1，未把局部通过记作整体验收。

新快照 SHA-256 为 145e8d0eeacbffae33e0a3aecac8a4b966de7f5c968d0d6c6f14a10b6be64452，变更清单保存在 distribution-validation-windows-source.json。库/原生源码未变；十二例 build() AST 均与已验收版本相同，case-interface-audit.json 保留 E02/E06 CLI 改动前后的源码哈希。新增总验收索引 ass-animation-engine-acceptance.md，连接公共契约、十二例、组合与剩余发行边界，状态仍为进行中。

Windows CPython 3.13.18/3.14.10 均已成功构建并修复 wheel。三个修复 wheel 及新源码包通过 twine check --strict（session 25300 exit 0）。当前 3.12 session 9608、3.13 session 20239、3.14 session 26139 正在分别验证新快照：输出目录为 validation-cp312-ascii、cp313/validation-ascii、cp314/validation。前两个 ABI 复用库源码未变的现有 wheel，安装前仍严格核对 Python/typing 字节；3.14 从新快照构建。不得重复启动仍活跃任务。

当前宿主完整测试 1094 项、19 子测试通过（41.49 秒，session 18018 exit 0），Ruff、ty 与 git diff --check 通过。当前矩阵仍运行，Windows ABI 测试宿主为 Wine，不冒充真实 Windows 机器。

## 第一百一十一批：最终发行与计划验收

三个原验证任务均正常结束：session 9608/20239/26139 exit 0，没有遗留等待任务。Windows CPython 3.12.16/3.13.18/3.14.10 各通过 1093 项测试、19 子测试（106.02/95.14/96.93 秒），均只跳过 Linux Fontconfig 专用测试；公开类型、24 个错误类型用例、32 个默认 Scene 示例、3 个额外扫色模式、常规 CLI 及显式旧模板 CLI 全部完成。运行 PATH 排除 UCRT/MSYS 工具链，实际 Windows ABI wheel 的 bundled DLL 隔离导入通过。归档 final-windows 总报告及三个分报告，明确宿主为 Wine 11.22，不宣称真实 Windows 宿主验收。

35 个固定示例在 Windows 三 ABI 之间逐字节相同；统一 UTF-8 BOM/换行后与 Linux 最终矩阵完全一致。常规 CLI 亦相同。最初比较全部 37 个 ASS 时发现 templates.ass 不同，逐行核对只有四个 pos 的横坐标不同；旧模板夹具使用系统 Arial 绘制中文，保留平台测量差异及具体坐标，不将其抹平或误报一致。总报告记录 36 个归一化相同文件与该例外。

严格核对当前 300 个库/原生/示例/测试/工具、字体和构建文件与新验证源码包相同。Linux 既有修复矩阵保持其原始快照证据；之后只更改文档测试编码、两个 CLI 提示与 Windows 验证工具，库/原生不变，十二例 build() AST 不变。当前宿主全套 1094 项测试/19 子测试通过；最终 Ruff、ty、diff 空白检查通过。后续 README、验收索引和进度记录属于验证后文档，不冒充已经包含于归档。

完成总验收索引、发行说明、能力边界与 README 入口分工，计划和 TODO 的 P0–P5 全部勾选。最终核对计划/TODO/索引的本地链接及三个 Windows 报告门槛，均通过。E01–E12 分别有独立质量/时间/成本/播放证据，整曲、预览、预算、旧模板、Track 迁移及公开扩展类型均由索引连接；不把测试数量当作视觉验收替代。

本次目标完成于既定首版范围：Document/Scene 标准 ASS 引擎与可修改的固定效果 examples。保留所有已记录边界：昂贵栅格显式启用、有限采样不保证任意连续回调误差、字体/播放器可能不同、Wine 不等于真实 Windows、没有 mpv/VSFilter 项目像素验收。未提交、打标签、上传或发布。
