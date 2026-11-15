# E09 固定渐变与残影验收

第九十一批：scene_gradient.py 达到案例卡的 **libass 首版目标**，涵盖固定屏幕渐变的文字填充/描边、逐字配色及三层延迟残影。主体使用原生连续 move，残影使用 20 ms 中点保持；两种时间语义有意并存。

| 要求 | 独立证据 | 结果 |
| --- | --- | --- |
| 屏幕坐标渐变、独立填充与描边 | [上行完整参考](gradient-bands-validation.json)逐屏幕列计算 RGB，只有完全相同的相邻颜色对才合并；手写原生 move 与固定 clip | 四背景 28 时刻共 112 帧完整 RGB 差 0，包含文字边缘和条带接缝；用填充色替代描边色的反例被检出 |
| 逐字配色及历史残影 | [下行参考](gradient-echoes-validation.json)独立计算五字 RGB、80/160/240 ms 延迟、透明度及负图层顺序 | 四背景 112 帧完整 RGB 差 0；缺失第一层残影被检出 |
| 完整上下行组合 | [完整场景参考](gradient-complete-validation.json)合并两份独立手写 ASS，显式恢复下行字号与零描边 | 四背景 112 帧完整 RGB 差 0，覆盖逐层出生、移动、主体结束和残影消失；缺失残影反例仍被检出 |
| 连续播放和跳转 | [四背景报告](engine-backgrounds-gradient-validation.json)每背景 600 时刻连续/乱序；[单例报告](scene-gradient-validation.json)300 帧、6 次新轨道跳转 | 全部一致，重复生成一致；时间量化差 0 |
| 质量预算和整曲 | 3196 事件、峰值 556、1364829 字节 | 低于预设 25000 / 1000 / 10 MiB；与整曲 E09 解码 UTF-8 BOM 后全文相同；耗时见单例报告 |

[完整实际/参考/8 倍差图](images/gradient-complete.png)已检查。参考不调用 ColorRamp、LinearGradient、echoes、Scene 编译或动画求值；两侧共享字体及 FFmpeg/libass，不能据此独立证明光栅器算法。原生 move 连续帧与采样残影的理想连续历史误差不混为一谈；112 帧是明确列出的关键时刻对照，不宣称逐毫秒穷尽。

重现：

```sh
uv run python -m tools.validate_gradient_echoes --part bands build/ass-engine/gradient-bands
uv run python -m tools.validate_gradient_echoes --part complete build/ass-engine/gradient-complete
uv run python -m tools.validate_engine_backgrounds --case E09 build/ass-engine/gradient-final-backgrounds
uv run python -m tools.validate_scene_core --scene gradient build/ass-engine/gradient-final
```

颜色场、粒子/残影及文件往返相关 36 项回归、Ruff、ty 通过。P3 的 E04/E11、扫色策略比较及 P5 仍继续。
