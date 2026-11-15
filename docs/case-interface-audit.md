# 全案例接口与缺口核对

以 `examples.scene_whole_song.CASES` 的 E01–E12 映射为准。十二个作者工厂均返回 Scene，使用公开接口构建对象，未导入私有实现模块；固定自定义函数直接写在示例内，不需要修改编译器。当前编译结果和源码哈希见 [机器可读核对](case-interface-audit.json)。哈希与既有验收资产清单一致，未用修改后的示例冒充旧视觉证据。

## 从案例意图到公共接口

| 案例 | 作者接口与实现依赖 | 当前边界及验收 |
| --- | --- | --- |
| E01 | `layout_document_lyrics`、对象组、`SoftSweep`、动画；document_lyrics → scene_lyrics → scene/paint_fields | 保留原唱段和注音，共享缩放，显式多层辉光；[完整参考](e01-acceptance.md)，恒定辉光不等于跨前沿色彩扩散 |
| E02 | `SceneTimeline`、`Tween`、自定义缓动与 `StateFunction`；choreography/scene_animation | 每字错峰及多阶段进退可直接表达；[验收](e02-acceptance.md)区分中点保持与连续理想曲线 |
| E03 | 轮廓/路径布局、文字组与动画；path_geometry/path_layout/scene_lyrics | 字体注音不重复缩放，重复高亮独立排程；[验收](e03-acceptance.md)，折线路径近似误差单列 |
| E04 | `emit_particles`、`ParticleContext`、`MoveAlong`、`echoes`、`SoftSweep`；particles/path_motion | 36 花瓣、出生捕获、曲线摆动与直线原生运动；[验收](e04-acceptance.md)，有状态物理模拟需作者预计算 |
| E05 | `text_to_path`、几何分片、复制、位移与透明度；text_geometry/path_geometry | 自定义分片和归位可组合；[验收](e05-acceptance.md)，完成态恢复整形，避免永久切片边缘 |
| E06 | `layout_document_text`、`range_bounds`、`background`、`bind_cues`、自定义 `CueFactory`；document_text/scene_text/cues | 固定词范围由作者给出；[验收](e06-acceptance.md)，不依赖自动分词或硬编码导唱文本 |
| E07 | 字形路径、`PathFunction`、固定随机轮廓与纯时间包络；text_geometry/path_animation | 按声明点数与断点预算；[验收](e07-acceptance.md)，固定扰动公式有时间误差界，不推广至任意回调 |
| E08 | `Polyline` 路径显露与笔尖 `StateFunction`；path_geometry/choreography | 显式笔顺/抬笔断点；[验收](e08-acceptance.md)，不从字体轮廓推断笔顺，快速笔尖连续目标观察差约 3.312 px 单列 |
| E09 | `LinearGradient`、逐字外观、`echoes`；paint_fields/particles | 填充和描边独立颜色场；[验收](e09-acceptance.md)，原生主体与采样残影的时间语义不同 |
| E10 | 对应轮廓的 morph 与字形路径变换；path_animation/path_geometry | 显式控制点/拓扑匹配；[验收](e10-acceptance.md)，不提供自动跨拓扑对应 |
| E11 | `SoftSweep`、独立文字辉光；paint_fields/scene_output | 宽度/颜色/时间可调；[验收](e11-acceptance.md)，额外模糊需显式选择，[策略比较](sweep-strategies-comparison.md)说明成本 |
| E12 | `CueMarker`、`CuePreset`、`TextCue`、`BarsCue`、用户工厂；document_text/cues/scene_lyrics | 行内占位/释放与独立定位；[验收](e12-acceptance.md)，标记只引用预设，不执行代码；跟随扩展示例 scene_cue_follow |

这些案例均已具有可检查的明确预期和独立参考工具。外部作品只作为机制来源，静态截图不能证明原作时序、渲染器或像素结果。案例卡固定自有文字、几何与语义；上述逐例验收明确无法从来源推导的部分，不把固定机制验证改称外部作品复刻。

## 模块依赖与扩展出口

Document 保存标准记录；document_text/document_lyrics 提供非执行的语义视图。布局测量和字体轮廓依赖原生 metrics，输出为普通场景对象。动画/生成器处理秒制时间和身份，SceneEvaluator 组合变换及引用。最后 scene_output 将对象降级为原生事件、采样、颜色条带和路径，返回新的 Document 与报告。作者工厂不反向依赖输出模块。

旧模板通过 NativeEvent 保留直接生成的标签，Track 通过共享准备阶段转为原生事件、可编辑对象或覆盖率组件；具体边界见[迁移核对](track-scene-migration-audit.md)。显式 RGBA 与覆盖率出口复用场景求值，但保留不同合成契约；不要求用一个算法掩盖透明度差异。

上述十二例的表达缺口已由公开接口覆盖。保留限制包括显式笔顺/形状对应、确定性纯函数、采样误差、横纵颜色场和有限预算几何近似。完整能力边界见[能力清单](ass-engine-capabilities.md)，这些限制不取消案例卡的固定视觉目标。发行与其他播放器仍属未完成验收，不由接口覆盖表代替。

第 101 批核对：24 个无效扩展契约被固定版本 ty 正确拒绝；全仓库 ty 覆盖类型正例；十二例文件/Document 等价回归与标记绑定回归单独执行。生成成本未超默认预算，且源码哈希与已验收资产快照一致。当前测试结果见[进度记录](ass-animation-engine-progress.md)。
