# 播放与渲染 Hook

将场景导出为独立的 libplacebo 着色器 Hook，即可在 mpv 中实时预览或通过 FFmpeg 直接烧录到视频。Hook 内置了字形覆盖、渐变、裁剪和动画参数，渲染端无需安装 Python 或原始字体。

## 导出并用 FFmpeg 渲染

![着色器渐变与缓动动画](../../examples/assets/gpu-gradient.gif)

制作与导出阶段需要 Python 和目标字体；负责播放或压制的机器只需具备支持 `libplacebo` 的 mpv 或 FFmpeg 以及可用的 Vulkan 设备。

对于由 `Track`（声部轨道）构建的歌词场景，直接调用 `scene.export("song.hook")` 即可（默认 60 fps）。下面这个完整示例手动构建一个带纵向渐变的 `Scene`（场景），并顺带写出一份纯 ASS 兜底文件：

```python
from kara_templater import (
    Color, ColorRamp, ColorStop, Document, Lifetime, Line,
    LinearGradient, Scene, TextObject, Vec2, VisualState,
)

fallback = Document.create(width=640, height=360)
fallback.records.append(Line(
    text=r"{\an7\pos(100,140)\fs56}Sing in color", end_time=3000,
))
scene = Scene(fallback).add(TextObject(
    id="lyric", text="Sing in color", font_size=56, lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(100, 140), border=2),
    material=LinearGradient(axis="y", space="local", fill=ColorRamp((
        ColorStop(5, Color.hex("#60E8FF")),
        ColorStop(65, Color.hex("#F075CB")),
    ))),
))
fallback.save("song.ass")
scene.export("song.hook")
```

包含完整动画的版本可参阅[渐变示例脚本](../../../examples/gpu_gradient.py)。要将 `song.hook` 烧录到宽高比匹配、不透明、从歌曲 0 秒开始的 SDR 视频上，可执行：

```sh
ffmpeg -init_hw_device vulkan=vk -i video.mp4 \
  -vf 'fps=60,libplacebo=custom_shader_path=song.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a copy output.mp4
```

> [!WARNING]
> 请仅保留 Hook 作为唯一的字幕层。如果在 Hook 之上同时加载兜底 `.ass` 文件，歌词会重复绘制两遍。另外，`-c:a copy` 要求输出容器兼容源音频编码，否则请改用 `-c:a aac` 重编码。

## 在 mpv 中播放与跳转

调校模板时，可以直接在 mpv 中挂载 Hook 实时预览：

```sh
mpv --vo=gpu-next --gpu-api=vulkan --sub-auto=no --glsl-shader=song.hook video.mp4
```

mpv 会把当前视频帧的显示时间戳（`PTS`，单位秒）传给着色器。Hook 依据该时间戳在导出帧网格上计算动画状态，因此无论是快进还是回退跳转，画面都保持准确。

请打开与歌词时间轴一致的原始视频。如果导出的是 36–44 秒区间 Hook，它也只会在原视频的 36–44 秒之间显示。像 FFmpeg 的 `libplacebo` 滤镜这样不传入 `PTS` 的宿主环境，则会自动改用从导出 `start` 开始累加的顺序帧计数器。

## 导出指定时间段

你可以只导出歌曲中的某一段来快速审核副歌，或将超长场景拆成多个片段：

```python
scene.export("chorus.hook", fps=60, start=36, duration=8)
```

配合 FFmpeg 的顺序帧计数器渲染片段时，把输入视频定位到相同的 `start` 时刻，并保持滤镜帧率与导出的 `fps` 一致：

```sh
ffmpeg -init_hw_device vulkan=vk -ss 36 -i video.mp4 -t 8 \
  -vf 'fps=60,libplacebo=custom_shader_path=chorus.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac chorus.mp4
```

`start` 必须为非负数且对齐到 `fps` 帧网格；`duration` 默认覆盖剩余场景，总长度须在 1 到 250,000 帧之间。

## 支持的效果与资源上限

Hook 着色器按图层顺序绘制文字与静态路径，支持仿射变换、透明度、普通矩形裁剪、填充与描边 `LinearGradient` 渐变（最多 16 个色标）、羽化走字、柔和扫光、融合辉光、立体 `Extrusion`、自定义 `ShaderMotion` 以及 WGSL `MaterialEffect`。这些效果的编写方法请参阅[颜色与材质](../guides/materials.md)、[动画与时间轴](../guides/animation.md)和[形状、裁剪与遮罩](../guides/geometry.md)。

Hook 对常见卡拉 OK 特性的处理方式如下：

- **走字与色带合并**：共享几何与动画、且在移动边界处相接的走字图层会合并为单次遮罩绘制；划分同一移动色带的柔和扫光与融合辉光同样每层只绘制一次覆盖遮罩。
- **内置动画与缓动**：静态绘制在状态变化前持续复用；线性矩形关键帧在 GPU 上实时插值。独立的 `FadeIn`、`FadeOut`、`ScalePulse`、`Slide`、`Jump`、单缓动 `DriftOut` 以及针对 `position`、`scale` 或 `opacity` 的 `Tween` 均可直接导出，支持 `linear_rate`、`smooth_rate`、`smoother_rate`、`ease_in`、`ease_out`、`ease_in_out` 以及分段线性 `ProgressCurve`（包括控制点在 0..1 范围内的 `ProgressCurve.cubic_bezier(0.17, 0.17, 0, 1).at`）。
- **描边与淡入淡出**：缩放时普通描边默认保持脚本像素宽度，设置 `scale_border=True` 则随图形一起缩放。带描边文字淡入淡出时会自动切换遮罩，防止描边穿透半透明字面。
- **分组裁剪**：`ObjectGroup` 上的普通屏幕空间 `RectangleClip`（静态矩形或按分组时钟运行的 `RectangleKeyframes`）会与每个子对象的裁剪求交，同时作用于歌词走字色层与立体挤出侧面。

Hook 导出器不支持 `AssDialogue` 记录、矢量裁剪、反向裁剪、分组局部裁剪、变形路径（`PathObject.deform`）、依赖对象引用的变换、同一节点上相互重叠的变化动画，以及不受支持的动画回调。遇到不支持项时会抛出 `SceneCompileError`，并给出对象 ID 与时间戳。

为保证播放流畅，Hook 导出强制执行以下资源上限：

| 限制项 | 上限 | 超限时处理 |
| --- | --- | --- |
| 帧率（`fps`） | 整数 `1`–`240` | 抛出 `ValueError`。 |
| 导出区间帧数 | `250,000` 帧 | 拆分为帧对齐的多个时间段。 |
| 渐变色标数 | 每条渐变 `16` 个 | 减少填充或描边渐变中的色标。 |
| 单张覆盖遮罩宽度 | `2,048` 像素 | 拆分对象或缩小尺寸。 |
| 覆盖图集（`KARAMASK`） | `2,048 × 8,192` 像素 | 缩短导出时间段。 |
| 数据纹理（`KARADATA`） | `2,048 × 8,192` `rgba32f`（最多 67,108,864 个浮点数，超过 2²⁴ 后按纹素对齐） | 缩短导出时间段。 |
| 单个 64 × 64 像素图块候选平面数 | `1,024` | 复用遮罩或收紧动画覆盖范围。 |
| 单帧像素检查总量 | `128 × min(场景面积, 1920 × 1080)` | 减少同时重叠的平面或拆分特效。 |
| 文件体积（`max_bytes`） | 可选正整数 | 在替换目标文件之前检查。 |

> [!TIP]
> 对于会改变位置、缩放、旋转或斜切的自定义 `ShaderMotion`，Hook 导出会在输出帧网格上调用其 Python 回调函数来计算图块包围盒。请确保整个片段内 Python 回调与 GLSL 计算出的姿态完全一致，并在目标显卡上实测自定义着色器的性能。

由于 `.hook` 文件以十六进制文本存储纹理，长曲或复杂特效生成的文件可能较大。传输时建议先压缩 `.hook` 文件，渲染前再解压。

## 重复导出预览窗口

在本地浏览器中查看场景，可调用 [`scene.preview()`](README.md#在浏览器里实时预览)。需要频繁拖拽时间轴的预览宿主可以先准备一次快照，再反复导出任意时间窗口，避免重复测量字形：

```python
prepared = scene.prepare_hook()
defaults = prepared.material_inputs()
prepared.export_resources("preview-window", start=36, duration=8, fps=60)
```

`prepared.material_inputs()` 会汇总整个场景中所有命名 `PaintInput` 的默认值，即使某个输入直到歌曲后段才首次出现。`prepared.export_resources` 会将二进制 `.bin` 纹理、`textures.json` 和 `scene.frag` 写入新目录，并在连续请求（包括回退跳转）之间复用已解析的对象层级与字形缓存。预览宿主可直接更新 `textures.json` 中声明的 `PaintInput` uniform 参数，无需重新导出。

修改 `Scene` 后，请重新调用 `scene.prepare_hook()` 生成新的快照。

## 下一步

- [预览与导出](README.md)
- [颜色与材质](../guides/materials.md)
- [动画与时间轴](../guides/animation.md)
- [故障排查](troubleshooting.md)
