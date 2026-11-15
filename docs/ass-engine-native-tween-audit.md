# 原生 Tween 范围核对

第八十三批完成 P3 的原生 Tween/fade 策略核对。当前公共选择为 `Scene.compile(native_tweens=True)`；默认 False 保留中点保持语义。这里的原生连续插值是一种显式输出策略，不声称与默认采样在任意时刻逐像素等价。

| 组合 | 输出选择与原因 | 证据 |
| --- | --- | --- |
| 静态对象、纯线性位置 | 原有 native-static / native-move，不依赖开关 | scene_output.py 的 _native_move；test_scene 的相对时钟、身份组与裁剪出生回归 |
| 线性 Tween 的 scale/rotation/opacity/fill/outline/border/blur/shadow | 开关启用后可生成一个事件内的标准 t；正缩放、hold=True，非空通道 | test_native_tween::test_continuous_tween_matches_handwritten_ass_and_reduces_cost：八通道手写 ASS，13 时刻 RGBA 相同，事件由超过 40 个降为 1 |
| 同通道顺序接续、不同通道并行、停留 | 按开始时刻排序，多段 t；目标只序列化声明的绝对目标通道，保留前一段的保持值 | test_native_tween 的 path 顺序/并行测试：反向声明顺序、出生 1 秒、16 次乱序请求与手写 ASS 一致；alpha 对独立对象求值舍入差不超过 1 |
| opacity 淡入淡出 | 用 t 内 alpha，无需另一套淡入淡出对象；完全透明起点仍保留事件 | 上述两项渲染回归，以及 scene_native_tween.py 的入场/停留/退出 |
| 非线性缓动、自定义回调、释放动画 | 保持 sampled；ASS t 加速参数不能表达任意函数，释放也不等于保持 | _native_tween 的类型/rate/hold 检查，test_native_tween 的 ease/release 回退回归 |
| 位置与其他通道混合、负/零缩放、剪切 | sampled 或 sampled-affine-path，不隐式混用 move 与 t | 通道集合和 affine_paths 检查；position/negative-scale/skew 回退回归 |
| 材质、遮罩、路径变形、世界引用、复杂父组 | sampled，保留求值、几何与覆盖率组合语义 | _native_tween 及 _Leaf.affine_paths；引用依赖会传递至后代；父组透明度回退及既有仿射/引用回归 |
| 父组截去对象出生、非整厘秒出生、毫秒量化后零长 Tween | sampled，避免把对象局部时钟或插值区间重置为原生事件时钟 | 资格检查 leaf.start/lifetime/start 与舍入后时长；fractional-birth 回退回归。事件寿命仍由 ASS 厘秒网格决定 |

预检使用已选择的原生事件数，输出过程仍检查实际事件、字节和峰值；不因预算不足自动切换动画语义。默认策略与例外在 scenes.md“显式连续 Tween 降级”中公开说明。任意组合不一定都能优化，但均沿已有支持路径生成标准 ASS 或给出原有能力/预算诊断；没有为减少事件而悄悄丢弃通道。

当前固定示例 [scene_native_tween.py](../examples/scene_native_tween.py)保持 SceneTimeline 作者接口。第八十三批[实际播放报告](scene-native-tween-validation.json)：1 事件、峰值 1、1579 字节，300 连续帧及 8 次独立跳转一致，重复构建一致。字体、renderer、时间量化及成本保留在报告中。

复验：

```sh
uv run python -m pytest -q tests/test_native_tween.py tests/test_scene_keyframes.py tests/test_scene.py tests/test_scene_references.py
uv run python -m tools.validate_scene_core --scene native-tween build/ass-engine/native-tween-final
uv run ruff check .
uv run ty check
```

49 项回归、Ruff、ty 通过。本次核对没有扩大原生资格或改变默认输出；自定义缓动自动识别、复杂父组原生优化不属于当前已支持范围，其他播放器仍在 P5 独立验证。
