# E07 固定轮廓扰动验收

第八十五批：scene_outlines.py 达到案例卡的 **libass 首版目标**。范围是固定 DejaVu Sans 的 WAVE、seed 17、4 px 空间连续正弦扰动及 1–4 秒包络。

| 要求 | 独立证据 | 结果 |
| --- | --- | --- |
| 字体轮廓、孔洞、演唱中的扰动及恢复 | [标量参考](outline-motion-validation.json)直接从原生字体读取直线轮廓，以独立正弦公式生成手写 ASS，不调用 text_to_path、VectorPath.map 或 PathFunction | 175 时刻涵盖全部有内容状态，1 px 轮廓容差通过；四个外轮廓与 A 的孔洞明确检查；覆盖率最大差 6/255 单列 |
| 扰动确实生效 | 将参考振幅设为 0 | 错误参考被检出 |
| 唱前/恢复态与结束边界 | case-geometry-validation.json 的独立原生文字参考检查；本轮参考亦包含首尾静态状态 | 唱前/恢复满足 1 px，5000 ms 起无残留 |
| 时间与连续公式界 | 全部 153 静态区间首/中/末位图一致，量化差 0；20 ms 中点保持 | 固定公式位置误差上界 0.627479 px，推导见报告；不含字体及光栅误差，也不推广到任意回调 |
| 实际四背景颜色 | [颜色报告](outline-colors-validation.json)：26 时刻 × 4 背景，与独立参考共同不透明内部对照 | 672124 像素 RGB 差 0；整帧最大差 4/255，边缘单列 |
| 播放与跳转 | [四背景报告](engine-backgrounds-outlines-validation.json)每背景 600 帧连续/乱序；[单例报告](scene-outlines-validation.json)300 帧与 6 次新轨道跳转 | 全部一致，重复生成一致 |
| 预算与整曲 | 152 事件、峰值 1、204507 字节 | 低于 25000 / 1000 / 10 MiB；与整曲 E07 解码 UTF-8 BOM 后全文相同，生成和渲染耗时见单例报告 |

[实际/参考/8 倍差图](images/outline-colors.png)已检查。参考与实现共享字体轮廓及光栅器，独立部分是变形、坐标和时钟公式；不宣称抗锯齿像素完全相同。WAVE 的固定字体轮廓全为直线，其他字体或曲线轮廓的近似误差需另验。

重现：

```sh
uv run python -m tools.validate_outline_motion build/ass-engine/outlines-all-states
uv run python -m tools.validate_cue_colors --case E07 build/ass-engine/outline-colors
uv run python -m tools.validate_engine_backgrounds --case E07 build/ass-engine/outlines-final-backgrounds
uv run python -m tools.validate_scene_core --scene outlines build/ass-engine/outlines-final
```

相关几何与文件往返 28 项回归、Ruff、ty 通过。共享颜色工具将分支抽为类型化 references_at，E03/E06/E12 的全部既有参考哈希保持不变。P4 另外两例、其他播放器及最终发行仍继续。
