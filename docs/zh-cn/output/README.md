# 预览与导出

用 WGSL 编写材质，在浏览器里实时查看特效，或导出可播放的着色器。需要可编辑的字幕文件时，可以从同一个场景编译标准 ASS。

## 着色器如何生成

导出时，Naga 会校验 WGSL 材质函数并转译为 GLSL。场景编译器再把这些函数接入 GLSL 渲染器，与字形遮罩及时间轴数据一起交给预览或播放端。当前整场景的着色器产物为 GLSL，WGSL 用于材质函数。

| 用途 | Python 入口 | 结果 |
| --- | --- | --- |
| 浏览器实时预览 | `scene.preview()` | 打开独立的 WebGL 2 预览页，可播放、拖动时间轴和调节具名材质参数。 |
| 接入自己的预览播放器 | `scene.export_resources("preview-resources")` | 写出 GLSL、二进制纹理和 `textures.json`。 |
| 在视频上播放或压制 | `scene.export("song.hook")` | 将着色器和纹理打包为 libplacebo `.hook`，供 mpv 或 FFmpeg 使用。 |
| 交付普通字幕 | `scene.ass.compile().document.save("song.ass")` | 从场景编译标准 ASS，供 libass、VSFilter 等字幕渲染器使用。 |

## 在浏览器里实时预览

场景构建完成后，调用 `scene.preview()`。预览会在默认浏览器中打开，播放器可离线使用。你可以通过返回的路径重新打开这个 HTML 文件。

```python
preview_path = scene.preview()
```

要只查看副歌片段，或在无桌面的环境里生成预览页，指定文件路径和时间范围：

```python
scene.preview("chorus.html", start=36, duration=8, open_browser=False)
```

`start` 和 `duration` 以秒为单位，`start` 必须与导出帧率对齐。浏览器里的参数调整仅作用于当前预览。分段导出与帧率限制见[播放与渲染 Hook](hook.md#导出指定时间段)。

## 着色器与标准 ASS 的能力对比

| 维度 | 着色器渲染 | 标准 ASS |
| --- | --- | --- |
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
