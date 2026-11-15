# E06 固定词背景与导唱组合验收

第七十五批结论：scene_cues.py 达到案例卡规定的 **libass 首版目标**。输出包含两个测量词背景、贝塞尔装饰、逐段颜色正文、行内短条、独立数字与旋转淡出的自定义图形。其他播放器与最终发行不在此结论范围内。

| 要求 | 当前证据 | 结论 |
| --- | --- | --- |
| 背景由测量范围派生，保留明确 padding 与占位 | [独立几何参考](word-backgrounds-validation.json)使用整词原生测量、标量公式及手写 ASS，不调用 range_bounds/布局函数 | 两个词背景、正文和装饰满足 1 px 轮廓容差；导唱消失后仍保留 84 px 占位，符合本例 keep_space=True |
| 导唱组合与自定义动画 | 同一参考含条形、数字和标量旋转图形；[独立图形报告](custom-cue-validation.json)另核对 alpha 与描边 | 69 个时刻、407 项颜色角色/几何检查通过；包含全部输出状态及关键边界 |
| 描边轮廓与边缘差异 | 淡出细环使用未乘透明度的填充/描边包络；原始透明度加权白色细环差另报 | 几何比较最大覆盖率差 34/255，原始角色差最大 125/255；符合案例卡抗锯齿另报的约定，不称像素一致。缺失图形和加粗描边反例检出 |
| 内部颜色误差不超过 2/255 | [四背景颜色参考](word-colors-validation.json)：68 帧、1,496,488 个共同不透明内部像素，六种预期颜色 | 内部 RGB 差 0；整帧边缘等差异最大 34/255 单独记录；半透明图形的 alpha 由独立图形报告约束 |
| 时间、采样与跳转 | 输出只有静态事件，54 个事件区间首/中/末位图一致，参考覆盖每个有内容区间；最大厘秒量化差 1/300 秒 | 低于 10 ms。旋转/淡出采用 20 ms 中点保持，明确与连续理想运动不同；不借静态输出证明连续理想动画无误差 |
| 四背景连续/乱序一致 | [当前四背景报告](engine-backgrounds-words-validation.json)：每背景 600 时刻，各跑连续与乱序；[单例报告](scene-cues-validation.json)另含 300 帧和 8 次独立跳转 | 全部通过；实际字体、renderer、背景与时钟均记录 |
| 固定预算与重复构建 | 70 事件、峰值 19、36,618 字节；重复生成一致 | 低于 25,000 / 1,000 / 10 MiB；归一化 UTF-8 BOM 后与当前整曲 E06 参考全文一致 |

全状态检查曾在 440 ms 的透明度加权细环阈值处失败。它被保留为方法修正记录：细环淡出后阈值只剩离散点，改用未乘透明度外包络判断几何，仍保留原细环覆盖率差，并加入两个故障反例。没有增加 1 px 几何容差。

重现：

```sh
uv run python -m tools.validate_word_backgrounds build/ass-engine/words-all-states
uv run python -m tools.validate_cue_colors --case E06 build/ass-engine/word-colors
uv run python -m tools.validate_custom_cue build/ass-engine/custom-cue
uv run python -m tools.validate_engine_backgrounds --case E06 build/ass-engine/words-final-backgrounds
uv run python -m tools.validate_scene_core --scene cues build/ass-engine/words-final
```

任意自定义工厂、连续时间误差界、不同字体提供器与其他播放器不得套用本固定夹具结论。P2 的 E01/E02 及 P5 发行验收仍未完成。
