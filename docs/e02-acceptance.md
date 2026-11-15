# E02 固定错峰动画验收

第七十六批结论：scene_staggered.py 达到案例卡的 **libass 首版目标**。该结论针对固定文字、字体、bounce/smoothstep 参数与 20 ms 采样保持输出，不适用于任意回调或其他播放器。

| 要求 | 证据 | 结果 |
| --- | --- | --- |
| 80 ms 逐字入场、回弹、多阶段退出；空格保留索引但不画字形 | [独立标量参考](staggered-validation.json)：单独计算三次回弹、多项式退出、650/500 ms 时段和 alpha，不调用示例 bounce 或 SceneTimeline | 337 时刻覆盖全部 255 输出区间；文字填充和描边的透明度加权覆盖率差均为 0 |
| 装饰曲线运动与旋转 | 同报告使用独立正弦/余弦及手写多边形参考 | 满足 1 px 轮廓容差，最大覆盖率差 48/255 单独报告；500–4500 ms 外不出现 |
| 颜色与淡出合成 | [四背景颜色参考](staggered-colors-validation.json)：23 时刻 × 4 背景，独立原生覆盖率浮点 source-over，与 FFmpeg 输出比较 | 文字区域含抗锯齿及 alpha 的最大 RGB 差 2/255；装饰共同不透明内部差 0。装饰覆盖区域外扩 1 px 后从文字判据排除，其几何另验；整帧最大差 26/255 单独记录 |
| 时间与采样 | 静态标签白名单、全部事件区间首/中/末原生位图一致；参考涵盖每个状态 | 原始断点在厘秒网格上，时间量化差 0。每字采样被入场/退出断点截断，最长 20 ms；不把有限采样输出说成与理想连续曲线相同 |
| 四背景与跳转 | [当前四背景报告](engine-backgrounds-staggered-validation.json)每背景 600 时刻连续与乱序一致；[单例报告](scene-core-validation.json)另有 300 帧和 6 次独立跳转 | 全部通过，报告记录字体、renderer、时钟及背景 |
| 质量预算和重复生成 | 809 事件、峰值 11、334,575 字节；重复生成一致 | 低于 25,000 / 1,000 / 10 MiB。与当前整曲 E02 在解码 UTF-8 BOM 后全文一致 |

[实际/参考/8 倍差图](images/staggered-colors.png)已检查。几何参考与颜色参考检查范围不同，不能把文字区域 2/255 的结论扩大到装饰边缘或任意视频色度格式。

重现：

```sh
uv run python -m tools.validate_staggered build/ass-engine/staggered-all-states
uv run python -m tools.validate_staggered_colors build/ass-engine/staggered-colors
uv run python -m tools.validate_engine_backgrounds --case E02 build/ass-engine/staggered-final-backgrounds
uv run python -m tools.validate_scene_core --scene staggered build/ass-engine/staggered-final
```

其他播放器、连续理想曲线误差上界和最终发行仍独立处理。P2 的 E01 尚未完成，因此不据此宣布整个阶段结束。
