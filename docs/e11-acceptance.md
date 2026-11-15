# E11 固定柔和扫色验收

第九十二批：scene_sweep.py 达到案例卡的 **libass 首版目标**。固定 SOFT SWEEP 的填充从白到粉、描边从粉到深粉，分别使用 24/36 px 过渡；整字辉光保持粉色，不随前沿变色。

| 要求 | 独立证据 | 结果 |
| --- | --- | --- |
| 填充/描边独立过渡 | [完整参考](soft-sweep-validation.json)逐屏幕列独立计算 RGB，按相同颜色对合并，手写标准 clip 和颜色标签 | 四背景 624 帧完整 RGB 差 0，覆盖全部输出状态和关键边界，包含条带接缝及抗锯齿边缘 |
| 辉光与前景交界 | 独立整字原生 ASS：粉色填充/描边、border 7、blur 9、opacity 0.6、layer -1；前景不模糊且不透明 | 与前景完整组合差 0；删除辉光的错误参考被检出 |
| 时间及状态 | 0–6 秒共 153 静态区间，首/中/末原生位图一致；每个区间均有完整参考 | 量化差 0，演唱 1–4 秒采用 20 ms 中点保持；不宣称与任意连续时刻的理想前沿相同 |
| 播放和跳转 | [四背景报告](engine-backgrounds-sweep-validation.json)每背景 600 时刻连续/乱序；[单例报告](scene-sweep-validation.json)300 帧、6 次新轨道跳转 | 全部一致，重复生成一致 |
| 预算和整曲 | 5667 事件、峰值 39、2455362 字节 | 低于 25000 / 1000 / 10 MiB；与整曲 E11 解码 UTF-8 BOM 后全文相同，耗时见单例报告 |

[实际/参考/8 倍差图](images/soft-sweep.png)已检查。实际和参考共享字体与 FFmpeg/libass；独立部分是前沿/颜色公式、条带构造和辉光表达，不是独立实现光栅器。参考不调用 SoftSweep、PaintField 或 Scene 编译器。源截图不能证明原作的渲染器或时序，验收使用案例卡中明确的固定语义。

重现：

```sh
uv run python -m tools.validate_soft_sweep build/ass-engine/soft-sweep-all-states
uv run python -m tools.validate_engine_backgrounds --case E11 build/ass-engine/sweep-final-backgrounds
uv run python -m tools.validate_scene_core --scene sweep build/ass-engine/sweep-final
```

颜色场与文件往返 26 项回归、Ruff、ty 通过。分条、图层与显式栅格策略的成本/语义比较仍单独列在 P3；尤其是“前沿色彩扩散到辉光”不能用本例的恒定辉光验收替代。其他播放器及最终发行仍继续。
