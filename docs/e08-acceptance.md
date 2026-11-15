# E08 固定书写路径验收

第八十九批：scene_writing.py 达到案例卡的 **libass 首版目标**。作者明确提供四笔路径、顺序和时段；不从字体推断笔顺。动画输出采用声明的 20 ms 中点保持并切开落笔/停笔边界。

| 要求 | 证据 | 结果 |
| --- | --- | --- |
| 笔迹显露、宽度及曲线形状 | [笔迹参考](writing-ink-validation.json)独立密集三次曲线弧长、前缀及 butt/bevel 描线多边形 | 全部有内容状态共 216 项满足 1 px；覆盖率最大差 96/255，笔宽翻倍反例被检出 |
| 笔尖形状、位置与停笔 | 同报告的独立 128 边圆；[位置参考](writing-validation.json)以更密集弧长计算中心并验证全部边界 | 197 项有内容形状满足 1 px，覆盖率最大差 106/255；518 时刻含 383 次可见、135 次抬笔，中心对采样目标最大差 0.212169 px |
| 时序与输出状态 | 195 静态区间首/中/末位图一致；四笔起止与停顿、5000 ms 精确结束 | 量化差 0。相对理想连续轨迹的已观察中心差最大 3.311876 px，保留报告，不以 1 px 采样位置容差替代 |
| 墨迹与笔尖叠加 | [四背景合成](writing-colors-validation.json)独立墨迹先绘、粉色圆后绘，与实际 FFmpeg 对照 | 29 时刻 × 4 背景，205744 个共同不透明内部像素 RGB 差 0；453 个参考墨迹/笔尖重叠位置进入实际内部比较。整帧最大差 67/255 单列 |
| 播放与跳转 | [四背景报告](engine-backgrounds-writing-final-validation.json)每背景 600 帧连续/乱序；[单例报告](scene-writing-validation.json)300 帧与 6 次新轨道跳转 | 全部一致，重复构建一致，空白时段与背景完全一致 |
| 预算与整曲 | 387 事件、峰值 2、460735 字节 | 低于预设 25000 / 1000 / 10 MiB，与整曲 E08 解码 UTF-8 BOM 后全文相同；耗时见单例报告 |

[实际/参考/8 倍差图](images/writing-colors.png)已检查。内部颜色与采样几何达标不意味着抗锯齿边缘一致，也不意味着每个连续时刻都在理想曲线 1 px 内。固定快速笔尖的中点保持限制已明确保留；作者可显式调整采样预算，当前验收未偷偷提高帧率或放宽阈值。

重现：

```sh
uv run python -m tools.validate_writing build/ass-engine/writing-pen-final
uv run python -m tools.validate_writing_ink build/ass-engine/writing-ink-all-states
uv run python -m tools.validate_cue_colors --case E08 build/ass-engine/writing-colors
uv run python -m tools.validate_engine_backgrounds --case E08 build/ass-engine/writing-final-backgrounds
uv run python -m tools.validate_scene_core --scene writing build/ass-engine/writing-final
```

书写/路径/文件往返相关 34 项、布尔/整组栅格相关 21 项回归通过，Ruff、ty 通过。结合 [E07](e07-acceptance.md) 和 [E10](e10-acceptance.md)，P4 固定三例的质量与成本证据齐备；其他播放器、P3 剩余和最终发行仍继续。
