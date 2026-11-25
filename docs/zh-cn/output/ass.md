# 导出标准 ASS

将场景编译为标准 ASS 字幕文件，无需插件或着色器即可在 mpv、libass 等播放器中正常播放。了解哪些特效能直接编译、如何配置资源预算，以及怎样保持字体和播放环境一致。

## 将 Scene 编译为 ASS

调用 `scene.ass.compile()` 会生成一份全新的 `Document`（歌词文档），并附带资源统计和诊断信息。编译过程不会修改调用方传入的源文档或场景对象。

```python
result = scene.ass.compile()
result.document.save("song.ass")
```

标准 ASS 导出器支持静态文字与矢量路径、线性 `MoveAlong` 与位置 `Tween`、符合条件的原生变换（`Tween`，以及采用 `linear_rate` 或二次 `ease_out` 且保持终态的 `FadeIn` / `FadeOut`）、硬边走字、`RectangleKeyframes`、静态与反向矢量裁剪，以及原样保留的 `AssDialogue` 记录。

需要逐帧采样的动画、渐变（`LinearGradient`）、羽化或倾斜走字（`sweep_angle != 0`）、色带效果（柔和扫光或融合辉光）、立体 `Extrusion` 以及自定义着色器材质都会抛出 `SceneCompileError`，并指明对应的 `object_id`。保留 `AssDialogue` 可以维持原有的 ASS 特效标签，但这些覆盖标签不会转化为可编辑的 `Scene` 属性。

ASS 事件的起止时间会四舍五入到最近的厘秒（10 ms），恰好位于中点时向偶数厘秒舍入。`result.max_time_quantization` 会报告整曲中最大的时间边界偏移（单位秒）。直接调用 `Document.save()` 保存原始文档不受此规则影响。

## 资源预算与编译报告

编译阶段会检查全场景资源预算（资源上限），防止生成的字幕文件过于庞大而拖垮播放器。一旦超出预算，编译器会直接报错，不会悄悄降低精度或删减细节。

| 预算项 | 默认值 | 限制内容 |
| --- | --- | --- |
| `max_events` | `25,000` | 生成的 ASS 事件总数（命令行 `--max-events` 默认为 `10,000`）。 |
| `max_bytes` | `10,485,760`（10 MiB） | 序列化后的 ASS 文件字节数，包含保留的源事件与标记注释。 |
| `max_active` | `1,000` | 同一时刻处于显示状态的非注释事件峰值数。 |
| `max_path_points` | `4,096` | 单个矢量路径、文字轮廓或裁剪图形的顶点数上限。 |
| `max_boolean_work` | `1,000,000` | 裁剪布尔求交的计算量上限。 |
| `clip_error_px` | `0.75` | 缓动矩形裁剪在屏幕像素上的最大插值误差。 |

如果特效确实需要更高额度，可以传入自定义的 `AssBudget`，还可以提供 `on_estimate` 回调在正式生成事件前检查 `AssEstimate.estimated_events`：

```python
from kara_templater import AssBudget, AssEstimate

def check_size(estimate: AssEstimate) -> None:
    if estimate.estimated_events > 5_000:
        raise RuntimeError(f"Too many events: {estimate.estimated_events}")

result = scene.ass.compile(
    budget=AssBudget(max_events=40_000),
    on_estimate=check_size,
)
```

在 `on_estimate` 中抛出异常会干净地中止编译，不会影响源文档。

通过 `AssResult` 可以定位每个对象的开销：

- `result.event_count`、`result.peak_active`、`result.byte_count` 和 `result.estimated_events` 汇总了整体规模（`event_count` 仅统计生成的 `Dialogue` 事件，不含标记注释）。
- `result.objects` 为每个对象提供一条 `AssObjectReport`，包含 `id`、编译策略 `strategy`、事件数 `events`、来源 `origin`、峰值路径点数 `peak_path_points` 与峰值裁剪点数 `peak_clip_points`。
- `result.diagnostics` 和 `result.event_origins` 可用于查看警告，并将生成的事件追溯回源歌词行。

## 字体与播放环境

`load_font(path)` 只会把字体字节注册到当前 Python 进程中用于排版测量，并不会把字体嵌入导出的 `.ass` 文件。你必须把完全相同的字体文件提供给播放器——安装在系统中、作为字体附件封装进 MKV 等视频容器，或通过播放器的字体目录参数指定。

> [!IMPORTANT]
> 仅仅字体族名相同并不足以保证排版一致。不同版本的字体文件或回退字体都会改变字宽、换行位置和描边形态。

最终像素结果还取决于脚本分辨率（`PlayRes`）、视频分辨率、时间戳、色彩矩阵以及字幕缩放方式。做画面对比时请固定这些变量。进行像素级色彩检查时，请使用 RGB 或全分辨率色度输出；YUV420 色度抽样可能会在锐利彩边处产生细微色晕。

## 渲染器差异与 mpv 参数

符合标准 ASS 语法并不意味着所有渲染器都会画出完全相同的像素。[libass 与 VSFilter 差异指南](https://github.com/libass/libass/wiki/Differences-between-Libass-and-VSFilters)详细列出了两者在描边、变换、小数点字号、边框样式、字体查找与色彩处理上的差异。

在 mpv 中播放按 RGB 编写的脚本时，可结合 [ASS 样式覆盖选项](https://mpv.io/manual/stable/#options-sub-ass-override)与 [VSFilter 色彩兼容选项](https://mpv.io/manual/stable/#options-sub-ass-vsfilter-color-compat)，避免用户样式覆盖或兼容色彩矩阵偏移：

```sh
mpv video.mkv --sub-file=effect.ass --sub-ass-override=no --sub-ass-vsfilter-color-compat=no
```

交付前，请在目标播放器中完整测试字体加载、缩放、入场退场、重复高亮、连续播放以及拖动进度条跳转。

## 在源码目录中预览与验证

在源码仓库中安装了 FFmpeg 与检查依赖后，可以用内置的 CPU 预览工具渲染 ASS 图库用例：

```sh
python -m tools.render_gallery --case word-backgrounds
```

该命令会在 `build/gallery` 下输出编译好的 ASS、复制后的预览字体和报告，并更新 `docs/examples/assets` 下的 GIF。本地调试时可传入 `--output` 和 `--assets` 避免覆盖仓库中的预览图。

如需在系统 libass 中验证内置场景（`cues` 或 `native-tween`）连续播放与随机跳转是否完全一致，可运行：

```sh
python -m tools.validate_scene_core --scene cues build/preview-cues
```

它会将生成的 ASS 和诊断报告写入目标目录，用于核对当前预览环境，不能替代目标播放器的实际测试。

## 下一步

- [选择输出格式](README.md)
- [选择与注册字体](../guides/fonts.md)
- [播放与渲染 Hook](hook.md)
- [故障排查](troubleshooting.md)
