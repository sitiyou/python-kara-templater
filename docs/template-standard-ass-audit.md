# 外部模板扩展与标准 ASS 迁移

第 103 批通过 gh 读取计划中固定提交的七份 ASS 源码。下面只总结生成机制，不复制歌词、路径资产或模板实现；源文件 SHA-256 与当前十二例输出标签清单保存在 [核对记录](template-standard-ass-audit.json)。

| 固定来源 | 生成端依赖/机制 | 本库对应方案 |
| --- | --- | --- |
| [Tiny Stars](https://github.com/ipid/my-aegisub-effects/blob/24689f4439c798795e0261f17449117fb5357c44/ass/01-tiny-stars.ass) | 逐字计数和 Lua 表达式安排多段缩放/透明度；主要输出 pos、t、blur 等。 | 按字符构造 SceneTimeline，生成标准原生或采样事件；不复用模板计数器的可变状态。 |
| [Round Karaoke](https://github.com/Seekladoom/Aegisub-Karaoke-Effect-481-Templates/blob/a6841b39db7a4891901bff633ac29b2e63c42f1e/ASS%20Template/Aegisub%20Effect%20-%20Round%20Karaoke%5Brotary%20restraint%20version%5E%5E%5D.ass) | 借助视频尺寸、字符/注音计数、retime 和 org/frz 安排圆弧。 | 显式脚本分辨率、路径布局与局部组中心；重复唱段及注音由结构化模型保留。 |
| [Bezier Move](https://github.com/Seekladoom/Aegisub-Karaoke-Effect-481-Templates/blob/a6841b39db7a4891901bff633ac29b2e63c42f1e/ASS%20Template/newBezier_Move%28ControlPointGenerator%29.ass) | Lua 内计算 Bernstein 曲线、随机控制点、帧间隔和残影寿命，再输出位置/移动片段。 | MoveAlong 加缓动、稳定身份随机和 echoes；曲线在生成端采样，不要求曲线移动标签。 |
| [Particle Effect](https://github.com/Seekladoom/Aegisub-Karaoke-Effect-481-Templates/blob/a6841b39db7a4891901bff633ac29b2e63c42f1e/ASS%20Template/AegisubParticleEffect.ass) | 循环分片，以移动与矩形裁剪组合碎片。 | 几何分片后独立动画，完成时恢复完整轮廓；标准绘图与事件承担结果。 |
| [Girls Band Cry ED](https://github.com/petzku/karaoke-templates/blob/6e1a09699ef0ba869d71fd92fe5155dc0cde5ff7/songs/gbc/ED.ass) | 依赖 ILL、petzku.easings/loadtags，以及 word、mixin、actor 条件；按词宽生成背景路径。 | 作者指定词范围，测量背景和生成贝塞尔装饰；元数据映射为类型化参数，不把模板扩展写到播放器标签。 |
| [Catharsis](https://github.com/petzku/karaoke-templates/blob/6e1a09699ef0ba869d71fd92fe5155dc0cde5ff7/songs/gbc/GirlsBandCry_11%20-%20Insert%20%28catharsis%29.ass) | 依赖 ILL 字形转路径、flatten/map、util.fbf、mixin 和分层辉光；随机扰动轮廓。 | text_to_path、PathFunction 和确定性时间包络输出采样矢量事件；不运行 ILL/Lua。 |
| [HandWriting](https://github.com/kakashi1987/aegisub-lua-pyonfx-karaoke-fx-collection/blob/68ecc75b05720afa1276554e4a76ba8d2af768c2/Aegisub/ass/pyointa2001/Aegisub%20Effect%20-%20HandWriting.ass) | 内置手写路径数据、Lua 路径取样及笔尖/粒子模板，使用视频帧时长。 | 明确提供笔画和顺序，WritePath/路径前缀及笔尖共享时间线；不从字体外轮廓自动推断笔顺。 |

这些模板里的 `word`、`mixin`、`actor` 条件和辅助库是作者工具扩展，不是 ASS 播放标签。模板文本又可能动态拼接标签，因此仅在源码里搜索反斜杠不能证明最终输出完全标准。本库迁移的是算法及对象关系；v0.1.0 兼容只保证原项目的 Python 模板，不提供上述 Lua 方言、ILL 或外部 templater 的直接执行兼容。

## 播放端边界

[Aegisub 标签文档](https://aegisub.org/docs/latest/ass_tags/)明确标准 move 为匀速直线；矩形 clip 可经 t 动画，矢量 clip 不能。相应转换如下：

- 曲线、复杂缓动和动态矢量遮罩：生成阶段计算时刻状态，输出多个标准位置/绘图/裁剪事件。不能把函数名直接写入 ASS。
- 柔和空间颜色过渡：互斥标准 clip 分条着色；不能认为普通 blur 会自动羽化裁剪边界。前沿扩散需要显式材质/栅格计算，成本见[策略比较](sweep-strategies-comparison.md)。
- 轮廓扰动、碎片和形状插值：输出生成后的标准 p 绘图；需要明确轮廓对应和几何预算。PyonFX 的本地参考源码 `refs/PyonFX/pyonfx/shape.py`（提交 c342624ee92f723bb78a1129ea0292ce549bedfb）同样将 map/flatten/split 作为生成端几何操作，不是播放器新标签。
- 输入自定义标记：CueMarker 在绑定时消费或保存在源 Comment；生成的 Dialogue 使用普通文本/矢量对象。新增导唱位置不依赖播放器识别自定义覆盖标签。

首版不使用播放器 shader、纹理、任意混合模式或非标准曲线移动/渐变标签。七份模板的抽样说明了可迁移机制，并不宣称已审计其整个仓库或所有动态代码路径；来源中含扩展工具也不等于最终播放必然需要扩展渲染器。

## 当前输出核对

重新编译 E01–E12，检查可见 Dialogue 覆盖块中的标签名称；字体名及样式重置的字符串参数单独归一化。结果均属于当前使用的标准 ASS 标签集合，记录逐例清单，不包含生成端模板指令或 CueMarker。首次粗正则把字体/样式参数误并入标签名，修正名称/字符串参数区分后完成检查；这是一项名称清单，不冒充完整 ASS 语法验证。

输出语义和实际渲染由各例 libass 参考与播放报告补充，见[全案例验收索引](case-interface-audit.md)。NativeEvent 和旧模板仍可忠实保留调用者提供的标签；不能据固定例的结果声称任意外部输入都会被自动净化为标准子集。对未知或未支持的可编辑语义，使用明确诊断，不静默猜测。

此核对完成扩展依赖到标准输出的机制映射；其他播放器的标准标签差异属于单独的 P5 验收。
