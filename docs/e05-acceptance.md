# E05 固定碎片聚合验收

第八十一批：scene_fragments.py 达到案例卡的 **libass 首版目标**。结论针对固定 KARA 字形、4×3 网格、seed 37、25 ms 错峰及 1.6 秒聚合，不推广为任意轮廓或连续动画误差界。

| 要求 | 证据 | 结果 |
| --- | --- | --- |
| 独立碎片、运动中裁切、错峰与随机位置 | [独立参考](fragments-validation.json)直接读取字体二次轮廓、64 段细分、独立半平面矩形裁切，按标量 smoothstep 和键控随机生成手写 ASS | 12 片共 1794 项检查，1770 项有内容几何满足 1 px；原始覆盖率最大差 94/255 单列。每片额外偏移 5 px 均被检出 |
| 淡入与出生/结束时序 | 同报告独立计算 200 ms 淡入，覆盖全部局部采样区间首端及 +1 ms，包含聚合结束边界 | alpha 完全一致；25 ms 源错峰量化误差最大 5 ms，低于 10 ms 门槛 |
| 聚合完成后完整文字 | [原生文字参考](case-geometry-validation.json)独立测量居中，检查 1600/1601/2500/4990/4999 ms 及精确结束 | 满足 1 px，5000 ms 起空白。实现在 1600 ms 替换为未切分轮廓，避免永久接缝 |
| 重叠颜色与透明度合成 | [四背景合成参考](fragment-colors-validation.json)：33 时刻 × 4 背景，独立移动碎片/原生完成态覆盖率浮点 source-over 与实际 FFmpeg 对比 | 内部 RGB 最大差 1/255；累计 8108 个重叠内部像素，其中 2344 个含半透明层。删除一片的错误参考被检出 |
| 输出状态与跳转 | 合成报告验证静态标签及全部 160 区间首/中/末位图一致；[四背景播放](engine-backgrounds-fragments-validation.json)每背景 600 时刻连续/乱序；[单例播放](scene-fragments-validation.json)300 帧、8 次新轨道跳转 | 全部一致，重复构建一致 |
| 成本与整曲 | 880 事件、峰值 12、576897 字节，生成约 0.052 秒、300 帧渲染约 2.08 秒（本机） | 低于预设 25000 / 1000 / 10 MiB；与整曲 E05 解码 UTF-8 BOM 后全文相同 |

合成颜色判据排除实际和参考的每片轮廓边界（3×3 局部最大/最小覆盖率不一致的区域），包含其余淡入及重叠内部；几何由前批逐片独立验证。完整画面 RGB 最大差 54/255 单独报告，不宣称边缘像素一致。[实际/参考/8 倍差图](images/fragment-colors.png)已检查。

碎片由几何切割生成并随自身移动，不依赖固定屏幕 clip；保留来源的接口回归在 test_particles.py。字体测量/光栅器由实际和参考共享，独立部分是轮廓细分、裁切、运动、alpha 与浮点合成。

重现：

```sh
uv run python -m tools.validate_fragments build/ass-engine/fragments-motion
uv run python -m tools.validate_fragment_colors build/ass-engine/fragment-colors
uv run python -m tools.validate_engine_backgrounds --case E05 build/ass-engine/fragments-final-backgrounds
uv run python -m tools.validate_scene_core --scene fragments build/ass-engine/fragments-final
uv run python -m pytest -q tests/test_particles.py tests/test_scene_document_roundtrip.py
```

本批相关 23 项回归、Ruff、ty 通过。P3 其他案例、其他播放器和最终发行仍待完成。
