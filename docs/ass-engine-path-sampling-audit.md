# P3 路径与采样实现核对

第八十二批对当前实现逐项核对。以下完成的是通用能力，E03/E04/E09/E11 的完整视觉验收和柔和扫色策略比较仍由 TODO 单独跟踪。

| 要求 | 当前实现与契约 | 验证证据 |
| --- | --- | --- |
| 路径采样 | geometry.py 的 Contour.point 按段参数推进，包含隐式闭合边；path_geometry.py 的 flatten 按容差自适应细分并执行点数预算。Polyline.point/prefix/resample 按累计折线长度查询，重复点、单点和端点有明确行为 | test_path_geometry 的弧长/重复点、三次曲线、共线过冲与点数预算回归；test_particles 的隐式闭合边回归 |
| 路径布局与注音 | path_layout.py 的 PathItem/layout_path 以 advance 中心分布，anchor 包装组保留子对象身份、来源、寿命和局部动画；可选切线朝向、反向区间及外层位置 | test_particles::test_curve_layout_preserves_grouped_annotation_and_local_animation；E03 固定圆弧独立解析参考见 round-validation.json |
| 曲线运动 | path_motion.py 的 MoveAlong 按捕获的基础位置叠加路径坐标，可选朝向；Contour 是参数进度，Polyline 是近似弧长进度。只有明确满足条件的线性路径使用原生 move，其余采样 | test_particles::test_move_along_native_linear_and_curve_tangent；E04 直线/曲线成本见 sakura-validation.json，曲线参考见 sakura-flutter-validation.json |
| 旋转与倾斜组合 | VisualState 的 rotation/skew/scale 构成仿射矩阵；父组非等比缩放与子旋转等无法保留为简单标签的组合降为文字轮廓/世界路径，并转换局部遮罩 | test_scene_affine 的矩阵次序、显式世界参考、镜像/零面积/近奇异、动画乱序和预算；test_group_masks 的父级时钟、复制及非凸/反向组合 |
| 确定性时间采样 | scene_output.py 的 _active_intervals 识别已知变化区间，未知几何/遮罩回调保守采样；_boundaries 收集对象、父组、引用、动画、几何、遮罩和材质断点，量化到厘秒，按区间中点求值 | test_scene 的已知变化区间预算、自定义回调整寿命预算、半网格整曲平移；test_writing_example 的重复排程与非网格显隐断点；test_scene_references 的乱序查询 |
| 边界切分和等价合并 | 相邻区间只在同一对象、事件文本完全相同且时间连续时合并；不以少量相同样本推断回调恒定。颜色条带逐条匹配，最终恢复对象顺序 | test_scene::test_sampler_merges_constant_states_and_preserves_boundaries；test_paint_fields 的静止段合并、重复构建、颜色场及裁剪组合 |
| 复杂度报告与失败 | SceneResult 给出实际事件、峰值、UTF-8 BOM 字节、保守预估和量化差；ObjectReport 给出来源、策略、实际采样间隔、路径/裁剪点数、条带峰值。预检与生成中均执行预算，异常保留对象/来源 | test_scene 的回调前预检、字节/峰值/点数/不可表示时段检查；test_paint_fields/test_group_masks 的展开、回调与布尔工作预算；真实案例报告记录上述字段 |

## 作者需要知道的区别

- 想沿曲线近似匀速行走，可先用 `flatten(contour, tolerance=..., max_points=...)` 得到 Polyline，再传给 MoveAlong 或 layout_path。直接传 Contour 不保证等弧长。
- 朝向使用当前位置附近的路径差分方向；尖角、停滞点不保证切线连续，零方向保留既有朝向。需要平滑朝向时可以提供自定义类型化动画。
- `fps` 是采样网格设置，不能当作所有输出区间都恰好等长的承诺。非整厘秒出生、额外断点和网格量化会改变长度；以 `sample_interval` 和 `max_time_quantization` 为准。静止平台不计入动态间隔。
- 确定性要求用户回调纯粹依赖输入时刻和显式参数。引擎不为读取外部可变状态的回调承诺相同输出，也不自动推断任意函数的连续误差界。
- 合并依据最终序列化文本相同，不是几何近似相同；不同对象的重叠层次不会为压缩而合并。

## 本批复验

```sh
uv run python -m pytest -q tests/test_path_geometry.py tests/test_particles.py tests/test_scene.py tests/test_scene_affine.py tests/test_group_masks.py tests/test_paint_fields.py tests/test_scene_references.py tests/test_writing_example.py
uv run ruff check .
uv run ty check
```

110 项通过，Ruff、ty 通过。没有生产代码或示例输出变化；已有视觉报告仅用于证明对应组合，不能替代尚未完成的全案例验收、其他播放器或最终发行。
