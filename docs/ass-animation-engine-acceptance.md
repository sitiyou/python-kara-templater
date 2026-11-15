# 标准 ASS 动画引擎验收索引

当前状态：首版计划及固定示例已完成。本文将原计划的要求与证据对应，不以测试数量替代视觉或语义验收。完成范围是既定 libass 案例、公共契约与下文明确环境的发行检查，不承诺所有字体和播放器像素一致。

## 公共契约

| 计划要求 | 实现与验收依据 |
| --- | --- |
| Document 是公共输入，文件入口先解析；只输出标准 ASS | `Scene(Document)`、`apply_templates`、`prepare_track_scene`；`test_scene_document_roundtrip.py`、[核心审计](ass-engine-core-audit.md)、[标准标签核对](template-standard-ass-audit.md) |
| 保留记录、来源、未选择事件与模板；重复生成有明确归属 | `ass.py`、`scene_output.py`、`document_lyrics.py`；Document 往返、旧模板和前端 owner 回归 |
| v0.1.0 Python 模板兼容 | [兼容矩阵](legacy-templates.md)、[23 组独立版本差分](legacy-template-migration-validation.json)；CLI 使用显式 `--templates` 的变化已记录 |
| 颜色/重置作用域、注音和演唱时间不随视觉拆分改变 | `document_text.py`、`document_lyrics.py`；对应测试及 E01/E03/E12；[公开作者契约](scenes.md) |
| 对象、组、生命周期、坐标和依赖关系 | `scene.py`、`scene_evaluation.py`、`object_references.py`；[核心审计](ass-engine-core-audit.md)、[遮罩组合审计](ass-engine-mask-combinations.md) |
| 类型化动画、顺序/并行/错峰/重复、关键帧、冲突与保持/释放 | `scene_animation.py`、`choreography.py`、`test_scene_keyframes.py`、`test_choreography.py`；[时间轴](animation-timelines.md) |
| 路径布局、切片、布尔遮罩、轮廓扰动、书写与 morph | [路径与采样审计](ass-engine-path-sampling-audit.md)、E03/E05/E07/E08/E10；不自动推导笔顺或跨拓扑对应 |
| 确定性粒子、独立寿命、出生捕获、持续跟随与历史 | `particles.py`、`object_references.py`；E04 及 `test_particles.py`、`test_scene_references.py` |
| 柔和扫色分别控制填充/描边/辉光，比较可选表达 | E11、[四种扫色策略比较](sweep-strategies-comparison.md)；默认分条，整组栅格及着色后扩散须显式选择 |
| 导唱符行内/独立定位、自定义内容与时序、输入标记 | `cues.py`、E06/E12、`scene_cue_follow.py`；[输入协议与作者契约](scenes.md)、`test_lyric_cues.py` |
| 原生表达、确定性采样、事件合并和诊断 | [原生 Tween 审计](ass-engine-native-tween-audit.md)、[路径与采样审计](ass-engine-path-sampling-audit.md)；默认采样与显式连续 Tween 的语义差异保留 |
| 显式高成本出口和预算，不静默降低质量 | [能力边界](ass-engine-capabilities.md)、[预览和预算审计](preview-budget-audit.md)、布尔/栅格/覆盖率回归 |
| Track 复用与旧 API 迁移 | [迁移审计](track-scene-migration-audit.md)，分别说明原生事件、可编辑组和覆盖率出口；没有新增弃用日期 |
| 公开类型不泄漏 Any/Unknown | `tests/typing` 正例、`tools.check_scene_types` 的 24 个错误扩展反例及全仓库 ty；发行包中另作隔离类型检查 |
| 固定示例既易读又可扩展 | [作者指南](scene-authoring.md)、[全案例接口审计](case-interface-audit.md)；例子使用公开对象/动画/材质 API，自定义花瓣、导唱工厂和状态函数仍可直接替换 |

## 固定案例与视觉证据

每个验收页连接固定资产、关键时刻、独立参考、颜色/几何误差、连续播放/跳转、预算与重现命令。2026-11-15 重新核对十二个示例源码及验收页的本地证据链接。E02/E06 随后仅将 CLI 状态信息改为 ASCII，十二例的 build() AST 均与已验收版本相同；接口审计同时保留更新前后的源码哈希。

| 案例 | 固定示例 | 验收 |
| --- | --- | --- |
| E01 正文、注音与多层外观 | [scene_lyrics.py](../examples/scene_lyrics.py) | [E01](e01-acceptance.md) |
| E02 逐字错峰和回弹 | [scene_staggered.py](../examples/scene_staggered.py) | [E02](e02-acceptance.md) |
| E03 圆弧排版和旋转 | [scene_round.py](../examples/scene_round.py) | [E03](e03-acceptance.md) |
| E04 樱花、曲线运动和残影 | [scene_sakura.py](../examples/scene_sakura.py) | [E04](e04-acceptance.md) |
| E05 文字碎片 | [scene_fragments.py](../examples/scene_fragments.py) | [E05](e05-acceptance.md) |
| E06 词背景与导唱组合 | [scene_cues.py](../examples/scene_cues.py) | [E06](e06-acceptance.md) |
| E07 轮廓扰动 | [scene_outlines.py](../examples/scene_outlines.py) | [E07](e07-acceptance.md) |
| E08 书写和笔尖跟随 | [scene_writing.py](../examples/scene_writing.py) | [E08](e08-acceptance.md) |
| E09 渐变与残影 | [scene_gradient.py](../examples/scene_gradient.py) | [E09](e09-acceptance.md) |
| E10 形状插值 | [scene_morph.py](../examples/scene_morph.py) | [E10](e10-acceptance.md) |
| E11 柔和扫色 | [scene_sweep.py](../examples/scene_sweep.py) | [E11](e11-acceptance.md) |
| E12 输入标记与自定义导唱 | [scene_lyric_cues.py](../examples/scene_lyric_cues.py) | [E12](e12-acceptance.md) |

[整曲示例](../examples/scene_whole_song.py)把十二例组合成 180 秒、30 段场景；[环境与成本基线](engine-baseline.md)记录字体、分辨率、采样时钟、生成/渲染耗时及整曲连续播放和跳转。实际预览使用落盘 ASS，字节一致性见[预览审计](preview-budget-audit.md)。

## 发行与剩余边界

[Linux 最终矩阵](distribution-validation-final-linux.json)覆盖 CPython 3.12/3.13/3.14 的 manylinux 2.28 修复 wheel、隔离测试、公开类型、32 个固定 Scene 示例、3 个额外扫色模式和两种 CLI。各 ABI 输出哈希一致。后续仅修改文档测试的 UTF-8 读取、两个示例的 ASCII 控制台提示与 Windows 验证器适配；[新源码包差异](distribution-validation-windows-source.json)保留具体范围，不能把旧报告称为新快照的完整执行记录。

[Windows 最终矩阵](distribution-validation-final-windows.json)覆盖真实 Windows CPython 3.12.16/3.13.18/3.14.10 的修复 wheel，运行宿主为 Wine 11.22；这不能替代真实 Windows 宿主测试。每 ABI 1093 项测试、19 子测试、公开类型、24 个类型反例、32 个默认示例、3 个额外扫色模式及两种 CLI 通过。仅 Linux Fontconfig 专用测试跳过；运行 PATH 移除了 UCRT/MSYS 工具链。全部 wheel/源码包通过严格元数据检查，当前 300 个库/原生/示例/测试/工具及构建文件与验证快照字节一致。

35 个固定示例的 Windows 跨 ABI 字节一致，统一 UTF-8 BOM/换行后与 Linux 输出完全相同。常规 CLI 也相同；旧模板中文夹具使用系统 Arial 测量，仅生成位置存在平台差异，报告保留具体坐标，不要求跨字体提供器复现同一布局。当前 Linux 工作树另有 1094 项测试及 19 子测试通过，Ruff、ty 通过。没有提交、发布 wheel 或 PyPI 版本。

视觉验收限定于记录的 libass、字体、分辨率和固定案例。[播放器差异](player-compatibility.md)区分官方文档与本项目实测；mpv/VSFilter 没有本项目逐像素验收。默认组透明度是 ASS 绘制语义，整组离屏合成需显式昂贵出口；任意回调不因有限采样自动获得连续误差上界。书写依赖作者提供的笔画，morph 依赖可匹配轮廓。各例边缘覆盖率和细环差异单独记录，不宣称所有像素完全相同。
