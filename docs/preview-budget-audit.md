# 实际导出预览与预算核对

预览读取已保存的标准 ASS。`tools.validate_scene_core` 将导出文件的原始字节复制到隔离渲染目录，FFmpeg 的 `ass=scene.ass` 过滤器用于预览、连续播放和重新加载跳转。工具现记录导出和预览输入的 SHA-256，并在渲染前后验证字节未改变；没有另一套仅用于展示的 Python 绘制实现。

第 100 批的[实测报告](preview-export-validation.json)使用固定 E11 扫色例。复现：

```sh
uv run python -m tools.validate_scene_core --scene sweep build/ass-engine/preview-export-audit
```

预览图为实际帧缩小后的拼图，缩放仅影响文档展示；连播/跳转比较使用原始分辨率。其他两条验证路径也读取落盘 ASS：`validate_engine_backgrounds` 对每例保存后用于四背景连续/乱序渲染；`validate_whole_song` 对整曲和各独立案例保存后渲染并记录文件哈希。各自的颜色背景、时间偏移及字体信息记录在报告中。该核对证明预览输入一致，不替代独立视觉参考或其他播放器验收。

## 预算执行范围

| 限制 | 执行及失败证据 |
| --- | --- |
| 预计事件数 | Scene 在动态回调前保守预检；`test_budget_preflight_never_invokes_callback` 的回调若执行即失败 |
| 实际字节、活动峰值、路径点数 | `test_actual_byte_peak_path_and_quantization_budgets` 分别触发错误；厘秒量化后消失的寿命也拒绝 |
| 变化区间 | 已知动画仅计算变化范围；未知几何回调预算覆盖整个寿命，见 Scene 的对应测试 |
| 颜色条带 | `test_paint_fields.py` 检查声明、输出及展开前的条带/事件预算，不自动增大色带宽度 |
| 组遮罩与布尔工作量 | `test_group_mask_preflight_and_callback_errors_keep_group_origin` 检查 object_id、origin 和采样时刻；布尔工作量测试定位遮罩 owner |
| RGBA 栅格帧数与像素 | `test_raster_preflight_and_output_limits` 验证回调前拒绝超限，以及输出字节预算 |
| 覆盖率帧数与输出规模 | `test_frame_budget_precedes_callbacks_including_discontinuities` 包含断点拆分；`test_output_budget_is_enforced` 覆盖事件、字符、字节和活动峰值 |

Scene 默认预算及结果字段见[作者指南](scene-authoring.md#采样报告与昂贵出口)。覆盖率和 RGBA 出口还受 RasterSettings 限制。保守估算允许提前拒绝最终可能较小的结果，但不会自动降低帧率、合并不同颜色或替换合成语义。颜色量化和更大的预算必须由作者显式选择。

错误来源的粒度依层次不同：对象/遮罩错误保留对象及来源；最终整份文档字节/活动峰值超限属于汇总错误，不能归因给唯一对象。源文档不因编译失败而被修改，也不会自动保存部分结果。作者应在成功获得结果后保存，CLI 遵循这一顺序。

本轮运行 Scene、RGBA、覆盖率、组遮罩、路径布尔和颜色场六组回归，结果见[进度记录](ass-animation-engine-progress.md)。固定 E01–E12 的视觉、成本及跳转证据仍以逐例验收文档为准。本项不声明播放器实时帧率或任意回调的误差上界。
