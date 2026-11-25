# 选择输出格式

导出独立的 libplacebo Hook 可在 mpv 与 FFmpeg 中保留完整着色器效果；需要可编辑的字幕文件时，则可编译为标准 ASS。两种输出都来自同一个场景。

## Hook 与标准 ASS 对比

独立的 Hook（libplacebo 着色器 Hook）是主要输出格式。它将字形覆盖、渐变、裁剪和动画参数打包进单个着色器文件，因此播放效果不依赖目标机器是否安装了对应字体。标准 ASS 则是兼容输出格式，适合普通字幕播放器或需要纯文本 `.ass` 字幕的交付场景。

| 维度 | 独立 Hook | 标准 ASS |
| --- | --- | --- |
| Python 导出入口 | `scene.export("song.hook")` | `scene.ass.compile().document.save("song.ass")` |
| 播放与渲染方式 | mpv（`--vo=gpu-next`）与 FFmpeg（`libplacebo`） | 标准 ASS 字幕播放器（mpv、libass、VSFilter） |
| 播放端字体要求 | 无需安装；导出时已烘焙字形遮罩 | 必须安装，或随视频容器封装字体 |
| 支持的效果 | 文字、静态路径、羽化与倾斜走字、渐变（最多 16 个色标）、柔和扫光、融合辉光、立体挤出、GPU 动画、WGSL 材质、`Petal` 与 `Sparkle` 粒子 | 文字、矢量绘图、硬边走字、线性移动、符合条件的补间与淡入淡出、静态与反向矢量裁剪、线性 `Sparkle` 粒子、保留的 `AssDialogue` |
| 不支持的功能 | `AssDialogue`、矢量裁剪与反向裁剪、分组局部裁剪、变形路径、对象引用 | 渐变、羽化或倾斜走字、柔和扫光、融合辉光、立体挤出、着色器材质、逐帧采样动画 |

## 立即播放或渲染

在 mpv 中直接叠加预览 Hook，无需预先烧录视频。关闭自动加载字幕，避免 mpv 在着色器之上再绘制一层普通字幕：

```sh
mpv --vo=gpu-next --sub-auto=no --glsl-shader=karaoke.hook video.mp4
```

用 FFmpeg 按匹配的导出帧率（默认 60 fps）将 Hook 烧录进成品视频：

```sh
ffmpeg -init_hw_device vulkan=vk -i video.mp4 \
  -vf 'fps=60,libplacebo=custom_shader_path=karaoke.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac karaoke.mp4
```

如果所用特效完全符合标准 ASS 能力，可在 Python 中直接编译并保存字幕文件：

```python
result = scene.ass.compile()
result.document.save("karaoke.ass")
```

## 让模板兼容标准 ASS

当 `Scene`（场景）包含标准 ASS 无法表达的效果——例如渐变、羽化走字、柔和扫光、融合辉光、立体挤出或自定义程序动画时，`scene.ass.compile()` 会抛出 `SceneCompileError` 并指明对应的 `object_id`，不会悄悄降级效果。调高 `AssBudget` 预算上限也不会开启这些不支持的特性。

如果希望模板能顺利导出为标准 ASS，可以注意以下几点：

- 使用硬边双色走字，例如 `KaraokeEffects.duotone(feather=0)`，避免羽化或倾斜扫色。
- 填充与描边保持纯色，不使用 `LinearGradient` 或自定义 WGSL 材质。
- 粒子优先选用线性补间驱动的 `Sparkle`，而非常规 ASS 不支持的 `Petal`。

> [!TIP]
> 同一个工程可以同时产出两种文件：分发 Hook 用于高质量渲染，同时附带一份简化版 ASS 作为纯字幕播放器的兜底字幕。

## 下一步

- [播放与渲染 Hook](hook.md)
- [导出标准 ASS](ass.md)
- [故障排查](troubleshooting.md)
- [命令行](../guides/cli.md)
