# 故障排查

按安装、歌词导入、排版与字体、动画、着色器预览与播放以及标准 ASS 排查常见问题。建议先从报错里的对象 ID 或记录索引入手，用最小输入复现问题。

## 读懂报错上下文

异常中的定位信息指向结构化的数据模型，而不是 `.ass` 文件中的物理行号：

- `Document.load`、`Document.parse` 或 `DocumentText.require_supported()` 抛出的 `ValueError` 会指明 `Document.records` 中的记录索引以及不支持标签或语法错误对应的文本偏移。
- `SceneCompileError` 包含 `object_id` 和可选的 `origin`；Hook 导出报错还会附带出错的时间戳（单位秒）。
- `SceneReferenceError` 包含 `object_id` 和可选的 `origin`，用于定位缺失目标、循环依赖或引用求值失败。
- `LayoutCapabilityError` 和 `OutputCapabilityError` 表示当前运行环境缺少所需的原生库能力。

排查自定义回调函数报错时，请保留完整的堆栈跟踪与异常链（`__cause__`）。

## 安装与导入

| 现象 | 排查与修复 |
| --- | --- |
| 找不到公开 API 符号 | 确认已安装的 `kara-templater` 版本与当前文档一致，并对照 [API 参考](../../reference/README.md) 核对最新符号名。 |
| 报错 `No module named examples` 或 `tools` | `examples` 与 `tools` 仅存在于源码仓库中。独立运行的模板脚本只需导入 `kara_templater`。 |
| 原生扩展加载失败 | 安装与当前 Python 版本和操作系统匹配的 wheel，并确认原生运行库齐全。请参阅[开发环境配置](../contributing/setup.md)。 |

## 歌词导入与声部轨道

| 现象 | 排查与修复 |
| --- | --- |
| 导入的歌词忽略了源 ASS 的字体、颜色或边距 | 导入的 ASS 只提供文本与时间轴；模板视觉样式应在 `Track` 上配置（`styles`、`theme`、`layout` 和 `effects`）。请参阅[布置声部轨道](../guides/tracks.md)。 |
| 提示预设未知或标记格式无效 | 检查提示预设名、标记键名、引号、偏移量与字形簇边界是否符合[注音读音与提示](../guides/text-and-cues.md)的要求。 |
| 文本范围或提示切开了字形簇 | 请按完整可独立绘制的字形簇选择范围，不要按任意 Python 字符切片分割组合字符。 |
| 多条 `Track` 命中了同一歌词行 | 让各条 `Track.source` 筛选条件互斥，或把需要叠加的效果合并到同一条 `Track` 中。 |
| 重新生成 ASS 时出现重复事件或残留旧特效 | 指定稳定的 `owner`（命令行用 `--owner`），并保留 ASS 文件中的生成标记注释。 |

## 排版与字体

| 现象 | 排查与修复 |
| --- | --- |
| 缺字或回退到了其他字体 | 检查准确的字体族名、系统字体回退以及 `load_font` 注册。播放 ASS 时需向播放器提供同一字体文件；Hook 会在导出端烘焙字形覆盖。请参阅[选择与注册字体](../guides/fonts.md)。 |
| 脚本分辨率（`PlayRes`）不匹配 | 检查 `Document.meta.res_x` 与 `res_y` 是否与渲染器或预览画布一致。 |
| 分组半透明叠得过暗或过浓 | `ObjectGroup` 会把透明度逐一乘到每个子对象上，而不是离屏合成整组。请调整重叠子图层的透明度。 |

## 动画与时间

| 现象 | 排查与修复 |
| --- | --- |
| 动画通道写入冲突 | 检查受影响的通道声明、时间区间是否重叠、`hold` 设置以及合成规则，参阅[动画与时间轴](../guides/animation.md)。 |
| 时间出现意外偏移 | 核对秒与毫秒单位（`Line` 用毫秒，`Scene` 与 `Track` 用秒）、对象出生起的局部时间与绝对时间，以及显示窗口与歌词计时时钟的区别。 |
| 对象跟随的位置不对 | `object.at(t)` 只计算局部状态；要获取叠加父级变换和引用后的画布坐标，请改用 `scene.evaluator().at(id, t)`。 |
| 拖动进度条后回调结果前后不一致 | 移除依赖上一帧的状态和全局随机数调用；改用带种子的确定性随机，并声明依赖项与断点。 |

## 着色器预览与播放

| 现象 | 排查与修复 |
| --- | --- |
| 着色器编译抛出 `SceneCompileError` | 着色器渲染不支持 `AssDialogue`、矢量或反向裁剪、分组局部裁剪、变形路径、超过 16 个色标的渐变、同一节点上重叠的变化动画以及依赖引用的变换。请参阅[播放与渲染 Hook](hook.md)。 |
| 超出 GPU 工作量、图集或数据纹理上限 | 减少同帧重叠平面、收紧动画包围盒（检查 `ShaderMotion` 的 Python 姿态回调），或用 `start` 和 `duration` 拆分为较短的帧对齐时间段。 |
| 浏览器未打开或预览无法启动 | 在启用 WebGL 2 的浏览器中打开 `scene.preview()` 返回的 HTML 路径。如果纹理超出显卡上限，可缩短预览时段。 |
| mpv 或 FFmpeg 中歌词画了两遍 | 在 mpv 中传入 `--sub-auto=no`，渲染时不要在 Hook 之上再叠加兜底 `.ass` 文件。 |
| 辉光在走字边界处被生硬截断 | 确认 `LyricHighlights` 的 `blend_glow=True`（默认值）未被关闭，且唱前与唱后 `Glow` 使用相同的 `border` 和大于 0 的 `blur`。 |

## 标准 ASS 导出与播放

| 现象 | 排查与修复 |
| --- | --- |
| ASS 编译抛出 `SceneCompileError` | 渐变、羽化或倾斜走字、柔和扫光、融合辉光、立体挤出、着色器材质和逐帧采样动画需要着色器渲染。请预览或导出着色器，或改用 ASS 兼容方案（如 `KaraokeEffects.duotone(feather=0)` 或 `Sparkle`）。请参阅[预览与导出](README.md)。 |
| 超出事件数、字节数、并发数、路径点数或布尔运算预算 | 查看 `AssResult` 与 `AssObjectReport` 找出开销最大的对象，精简特效，或在 `AssBudget` 中有针对性地调高对应上限。请参阅[导出标准 ASS](ass.md)。 |
| 锐利彩色边缘出现细微色边 | YUV420 色度抽样会在 2 × 2 像素块上混合色度。请改用 RGB 或全分辨率色度输出进行核对。 |
| 不同播放器渲染结果有差异 | 确认播放器加载了完全相同的字体文件，并核对[导出标准 ASS](ass.md) 中的 mpv 参数及 libass 与 VSFilter 的已知差异。 |

## 下一步

- [预览与导出](README.md)
- [播放与渲染 Hook](hook.md)
- [导出标准 ASS](ass.md)
- [选择与注册字体](../guides/fonts.md)
