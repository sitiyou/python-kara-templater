# P2 核心实现核对

第七十批核对当前源码与测试。这里判断核心能力是否实现，不以“代码存在”替代 E01/E02/E06/E12 的完整视觉目标；P2 阶段尚未整体验收。

| P2 要求 | 当前实现与直接证据 | 判断及边界 |
| --- | --- | --- |
| 对象、组、歌词绑定、布局和几何查询 | `scene.py` 的 TextObject/PathObject/ObjectGroup/NativeEvent、寿命交集与复制；`scene_text.py` 的 range_bounds/background；`scene_lyrics.py` 的正文/注音布局和单元组。`test_scene.py::test_group_transforms_once_and_intersects_lifetimes` 核对变换仅组合一次；test_scene_text 验证颜色范围、簇边界、词背景尺寸和动态测量断点；test_document_lyrics 验证重复唱段、注音及样式重置 | 实现完成。字符选择按 code point 与塑形簇契约，不能把不可独立绘制的簇任意切开；单行绑定和多行仿射限制见能力清单 |
| 类型化属性、动画编排、任意时刻求值 | `scene_animation.py` 的 VisualState/StatePatch/StateAnimation/SceneTimeline/StateKeyframe；`scene_evaluation.py` 的依赖图和世界状态。test_scene 检查冲突、声明写集合、保持/释放、随机访问；test_scene_keyframes 检查关键帧与显式编排的输出等价及原子冲突；test_scene_references 检查乱序求值、延迟引用、复制重定向、回调前循环拒绝 | 实现完成。任意自定义回调须遵守纯函数契约；引擎不会自动把外部可变状态改为确定性模拟 |
| 共享场景计划与来源 | Document → 绑定布局 → 带 EventOrigin/SourceRef 的普通对象 → SceneResult.objects 与生成事件。`scene_output.py` 的 append 使用对象 id 标记 owner 事件，ObjectReport 保留 origin；SceneCompileError 保留对象及来源。test_legacy_scene 核对旧模板来源、新对象混用；test_scene_document_roundtrip 核对十二例文件/Document 一致；test_scene 核对源文档不变、自定义列、重复编译和 owner 隔离 | 实现完成。纯装饰可无歌词来源；来源跟踪不意味着生成物可以无损反解成原作者计划。原生兼容事件保留其原 Effect，另存来源标记 |
| 标准 ASS 原生表达与能力检查 | `scene_output.py` 生成普通文字/绘图、move、显式启用的 Tween t，保留 NativeEvent；不适用的动画进入有报告的采样路径。test_native_tween 用手写 ASS 验证文本/路径连续渲染；test_scene 验证相对时钟的 native-move；test_scene_text 验证不支持布局语义明确报错；路径、仿射、遮罩与覆盖率入口各有能力和预算检查 | 实现完成。原生支持范围见 ass-engine-capabilities.md；默认采样和可选连续 Tween 是明确选择，不宣称所有动画都已优化。复杂组合优化仍由 P3 跟踪 |
| 导出、实际预览、关键帧检查与诊断流程 | 示例 CLI 保存编译后的 Document；tools.validate_scene_core 对同一输出 ASS 调用 FFmpeg/libass，保存图像、连续帧/新轨道跳转对照、字体/renderer、策略、预算及时间量化报告。新 scene-native-tween 报告包含 300 连续帧及 8 次跳转；既有四例均有对应报告。错误路径由上述来源和能力回归覆盖 | 流程打通。预览流程可复现不等于每个视觉目标通过；独立参考、四背景、抗锯齿/辉光误差和成本门槛仍逐例验收 |

## 复验命令

```sh
uv run python -m pytest -q tests/test_scene.py tests/test_scene_text.py tests/test_document_lyrics.py tests/test_scene_keyframes.py tests/test_scene_references.py tests/test_scene_document_roundtrip.py tests/test_native_tween.py tests/test_legacy_scene.py
uv run ruff check .
uv run ty check
```

第六十九批全套结果为 1094 项及 19 子测试通过；本次核心复验结果记录于进度日志。类型正例在 tests/typing 中受 ty 检查，错误扩展协议另由 tools.check_scene_types 验证。视觉报告使用其实际生成时的源码与字体，不能因本次测试通过就自动扩展报告适用范围。

## P2 固定案例退出证据（第七十九批更新）

- E01：全部 124 输出区间及完整填充/描边/辉光组合已核对，四背景 516 帧差 0，见 [逐项结论](e01-acceptance.md)。
- E02：第七十六批已完成固定错峰动画的 libass 验收，见 [逐项结论](e02-acceptance.md)。装饰边缘与连续理想曲线仍按明确范围另报。
- E06：第七十五批已完成固定组合的 libass 验收，见 [逐项结论](e06-acceptance.md)。20 ms 采样保持与连续理想动画的差别仍明确保留。
- E12：第七十三批已完成固定案例的 libass 验收，见 [逐项结论](e12-acceptance.md)。任意自定义回调的误差与其他播放器仍不在该结论范围内。

第七十九批补齐四例固定 libass 质量和预算证据，核心与导唱相关 108 项回归、Ruff、ty 通过，P2 退出条件已满足。发行与其他播放器验收仍在 P5，其他阶段尚未完成。
