# 标准 ASS 引擎首版能力范围

本表固定首版的功能与语义范围，依据当前公共接口和编译器核对；它不是发布完成声明。视觉误差、播放器差异和发行检查仍以 [TODO](ass-animation-engine-todo.md) 为准。详细作者契约与可运行示例见 [scenes.md](scenes.md)。

## 默认对象出口

入口为 `Scene(Document).add(...)`，出口为 `Scene.compile().document`。旧 `Engine` 通过 NativeEvent 接入；已有 Track 提供独立准备适配。输出仅含标准 ASS 播放语义，输入扩展标记保留于源注释或被消费，不要求播放器插件。

| 能力 | 首版承诺 | 实现、例子与证据 |
| --- | --- | --- |
| 文档与旧模板 | 保留标准记录、来源、明确 owner 和重复生成；v0.1.0 Python 模板兼容，不扩展成 Lua 解释器 | ass.py、engine.py；legacy-templates.md、test_legacy_v010.py |
| 歌词选择 | 正文、演唱片段、重复唱段、注音、code point 范围与塑形簇；词范围由作者指定 | document_lyrics.py、scene_lyrics.py；scene_lyrics、scene_bilingual |
| 文本属性 | 标准颜色/样式重置作用域、来源诊断；不以逐码点拆字破坏复杂塑形 | document_text.py、scene_text.py；test_document_text.py、test_document_lyrics.py |
| 对象与布局 | 文字、矢量路径、组、原生事件；局部/世界状态、测量与墨迹范围、层次与来源 | scene.py、scene_evaluation.py；scene_affine、scene_mirror |
| 动画 | 秒制寿命、类型化属性、关键帧、顺序/并行/错峰/重复、纯回调、保持/释放及冲突检查 | scene_animation.py、choreography.py；scene_keyframes、scene_staggered |
| 几何 | 字形轮廓、曲线布局、切片、显露、显式对应的 morph、有限预算多边形布尔近似 | path_geometry.py、path_boolean.py、path_animation.py；scene_fragments、scene_writing、scene_morph、scene_boolean |
| 遮罩与变换 | 矩形/矢量、局部/屏幕坐标、嵌套组合、镜像/零面积、非等比缩放与剪切 | _scene_clipping.py；test_group_masks.py、test_scene_affine.py |
| 颜色场 | 填充/描边分别指定横向或纵向场，渐变与 SoftSweep，显式宽度与条带步长 | paint_fields.py；scene_gradient、scene_sweep、scene_sakura |
| 关系与粒子 | 显式依赖、世界位置跟随、历史、出生捕获、稳定键控随机和独立跳转 | object_references.py、particles.py；scene_follow、scene_sakura |
| 导唱符 | 用户内容工厂，文本/矢量、行内占位与释放、独立定位、任意唱段时间、显式歌词锚点跟随 | cues.py；scene_cues、scene_lyric_cues、scene_cue_follow |
| 扩展 | StateAnimation、PaintField、路径/遮罩函数、StateReference 等类型化协议；回调声明通道、断点及复杂度 | tests/typing、tools.check_scene_types；不以无类型属性字典作为协议 |

普通组的 opacity 乘到后代绘制贡献，不等同于“先离屏合成整个组，再统一透明”。普通模糊/裁剪沿 ASS 渲染顺序；不能将重叠半透明颜色层解释为 RGB 空间线性渐变。

当前 Scene 编译器报告 `native-static`、`native-move`、`native-tween`、`sampled`、`native-event`，按需要附加 `-affine-path`、`-bands`。静态和符合条件的匀速直线优先原生；第六十八批新增显式 `compile(native_tweens=True)`，第六十九批扩展到顺序/并行的保持线性 Tween，使用标准 `\t`，含透明度淡入淡出。默认保留旧采样行为，因为连续插值与中点保持并非逐像素等价。复杂父组/材质/遮罩等组合、释放动画和非线性缓动仍采样，具体条件见 scenes.md 的“显式连续 Tween 降级”。原生事件可保留原有标签；当前首版原生策略与复杂组合回退已逐项核对，见 [范围审计](ass-engine-native-tween-audit.md)；更广泛的自动优化不在已支持范围内。

## 显式高成本出口

| 入口 | 适用语义 | 必须接受的边界 |
| --- | --- | --- |
| 普通 Scene 的 PaintField | 标准 ASS 分条着色，仍可编辑文字/路径 | 作者显式指定 material；空间条带与时间采样相乘，受 max_bands、事件和字节预算约束 |
| `rasterize_group` | 已降级子对象先合成，再对整组模糊及应用根透明度 | 组自包含；根世界引用须事先求值。输出为烘焙后的标准 ASS 像素矩形，不保留可编辑字形 |
| `compile_coverage` | 填充/描边/辉光固有覆盖率、材质组件、分区与作用域透明度 | 组自包含；显式 Glow/GlowFunction，不能混用普通 blur/shadow；分区限横向，写 opacity 的引用拒绝 |
| `prepare_track_coverage` | Document/Track 前端转为可编辑组，再调用覆盖率出口 | 保留选择、来源和 owner；自动扫色前沿在旋转/剪切/非等比组合下仍明确拒绝 |

像素出口显式使用 RasterSettings 和 SceneBudget，不在普通编译失败时偷偷切换。空间颜色量化容差不包含时间保持误差、YUV 色度抽样或播放缩放误差。相邻相同事件可合并；不能靠合并假定任意长曲都可实时播放。

默认 SceneBudget：50 Hz、25,000 事件、10 MiB、1,000 峰值同时事件、4,096 路径点、1,024 色带、每次布尔操作 1,000,000 工作量。采样上限为 100 Hz，对应 ASS 厘秒事件时间网格。作者可明确提高预算；超限报错，不自动降帧率、减少对象或扩大误差。最终序列化和峰值仍检查，预估通过不等于输出必然通过。

## 明确不提供或不保证

- 不提供播放端 shader、自定义播放器标签、任意混合模式、视频纹理或真实 3D 场景。任何未来离线近似须另外定义，不属于当前接口承诺。
- 不自动推导节拍、字体笔顺、跨拓扑 morph 对应或逐帧推进的有状态物理模拟。作者可提供笔画、映射及预计算结果，再用纯函数求值。
- Document 能保留的数据不意味着全部标准 ASS 覆盖标签都可转换为可编辑 Scene 对象；超出布局视图的语义必须诊断或经 NativeEvent 保留，不静默重解释。
- 多行文本不能进入需要字形路径的仿射降级；复杂塑形不能保证任意字符边界可独立绘制。错误应保留对象/来源信息；调用底层几何 API 的 ValueError 仍是独立契约。
- 布尔运算使用有限曲线细分与数值容差，不是解析曲线求交；morph 要求显式可匹配轮廓，不自动改变孔洞拓扑。
- 有限时间采样不能证明任意用户回调的连续误差界。所有视觉参考均须声明时刻、空间容差及边缘覆盖率差。
- 标准 ASS 不代表 libass、VSFilter 或不同字体提供器逐像素一致。[最终验收](ass-animation-engine-acceptance.md)分别记录 Linux 与 Wine 内 Windows ABI 的发行检查；真实 Windows 宿主及 mpv/VSFilter 视觉输出没有本项目验收，不能把已测环境的结果扩大到它们。

能力实现、默认性能和视觉验收分别判断。上述限制不能用来取消 E01–E12 已约定的画面目标；未完成的目标仍在 TODO 中，必须继续实现或验证。
