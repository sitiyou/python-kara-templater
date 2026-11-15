# E01 正文、注音与分层扫色验收

第七十九批：固定的 scene_lyrics.py 达到案例卡的 **libass 首版目标**。输出使用标准 ASS，动画采用 20 ms 中点保持；以下证据不宣称连续理想曲线或其他播放器具有相同结果。

| 要求 | 独立证据 | 结果 |
| --- | --- | --- |
| 正文与注音布局、共享唱时缩放 | lyric-geometry-validation.json 的独立字体测量；完整参考进一步用整段与单字原生轮廓的位置差，独立计算居中与缩放 | 原前景几何 59 时刻满足 1 px；完整合成覆盖所有输出状态 |
| 填充与描边平滑过渡 | [完整参考](lyric-sweep-validation.json)逐屏幕列独立计算 24 px 填充、16 px 描边过渡，只合并相同颜色对，手写矩形 clip | 四背景共 516 帧，完整 RGB 差 0；错误描边宽度被检出 |
| 两层辉光和缩放后的相对位置 | [辉光参考](lyric-glow-validation.json)以标量公式计算每字位置、border、blur 和 alpha；完整参考包含全部层 | 单独辉光 68 帧差 0，完整场景亦为 0；错误 near alpha 被检出 |
| 时间与全部状态 | 静态标签白名单含固定矩形 clip；全部 124 区间首/中/末原生位图一致，独立参考覆盖每个状态 | 时间量化差 0，最长保持 20 ms；不是连续动画误差界 |
| 连续播放和跳转 | [四背景报告](engine-backgrounds-lyrics-validation.json)每背景 600 帧连续/乱序；[单例报告](scene-lyrics-validation.json)300 帧与 11 次新轨道跳转 | 全部一致，重复构建一致 |
| 成本及整曲集成 | 单例 16,614 事件、峰值 155、7,567,351 字节；生成约 0.42 秒，300 帧渲染约 6 秒（本机测量） | 低于预设 25,000 / 1,000 / 10 MiB；与整曲夹具 E01 解码 UTF-8 BOM 后全文相同 |

[实际、参考及放大差图](images/lyric-sweep.png)已检查。参考不使用 Scene 布局、动画或 SoftSweep 编译算法，但两侧共享字体测量和 FFmpeg/libass 光栅器；这是对框架表达的对照，不是独立验证 libass 的模糊算法。辉光语义是每字两层原生 blur，整组 RGBA 合成及前沿颜色向辉光扩散属于另行明确选择的能力。

重现：

```sh
uv run python -m tools.validate_lyric_glow build/ass-engine/lyric-glow-native-reference
uv run python -m tools.validate_lyric_sweep build/ass-engine/lyric-all-states
uv run python -m tools.validate_engine_backgrounds --case E01 build/ass-engine/lyrics-final-backgrounds
uv run python -m tools.validate_scene_core --scene lyrics build/ass-engine/lyrics-final
```

报告记录字体、背景、参考与实际 ASS 哈希和 renderer。P2 核心与导唱相关回归本批 108 项通过，Ruff、ty 通过。P3–P5、其他播放器及最终发行仍须独立完成。
