# E03 圆弧歌词与注音验收

第八十四批：scene_round.py 达到案例卡的 **libass 首版目标**。范围是六个固定字形、半径 240 的圆弧、切线旋转、上方注音及两轮 250 ms 高亮/缩放，不据此声明任意路径的连续误差界。

| 要求 | 独立证据 | 结果 |
| --- | --- | --- |
| 圆弧位置与切线、注音相对位置 | [解析参考](round-validation.json)直接以 sin/cos 和切线角计算位置，手写原生文字 ASS，不调用 layout_path | 198 时刻满足 1 px 几何容差；覆盖全部有内容状态 |
| 两轮高亮、缩放只应用一次 | 同参考单独计算两轮时段及标量比例，注音偏移随同一变换计算 | 内部 RGB 差 0；把注音再次缩放的错误参考被检出 |
| 全部输出状态与时间 | 静态标签检查，0–6 秒共 138 区间首/中/末原生位图一致；参考覆盖全部有内容区间 | 时间量化差 0；5000/5001 ms 空白。动态区间按 20 ms 网格并在演唱边界切开，不宣称连续理想脉冲一致 |
| 四背景实际颜色 | [颜色参考](round-colors-validation.json)26 时刻 × 4 背景，与独立解析参考的共同不透明内部比较 | 302716 像素 RGB 差 0；两轮中间色均覆盖。完整画面最大差 106/255 单列 |
| 播放、跳转与生成 | [四背景报告](engine-backgrounds-round-validation.json)每背景 600 帧连续/乱序；[单例报告](scene-round-validation.json)300 帧与 8 次新轨道跳转 | 全部一致，重复生成一致 |
| 成本和整曲 | 348 事件、峰值 12、143630 字节 | 低于预设 25000 / 1000 / 10 MiB；与整曲 E03 解码 UTF-8 BOM 后全文相同，生成/渲染耗时见单例报告 |

解析圆弧与实现的一度折线近似、原生文字与路径定位带来边缘差；几何报告最大覆盖率差 111/255 单独记录。内部颜色结论不推广到这些边缘。[实际/参考/8 倍差图](images/round-colors.png)展示两轮脉冲中间状态。两侧共享字体与原生光栅器，独立验证的是布局、变换和色彩公式。

重现：

```sh
uv run python -m tools.validate_round build/ass-engine/round-all-states
uv run python -m tools.validate_cue_colors --case E03 build/ass-engine/round-colors
uv run python -m tools.validate_engine_backgrounds --case E03 build/ass-engine/round-final-backgrounds
uv run python -m tools.validate_scene_core --scene round build/ass-engine/round-final
```

相关粒子/布局与文件往返 23 项回归通过，Ruff、ty 通过。共享颜色工具默认 E12 重跑仍为 68 帧、473688 内部像素差 0；E06 分支保持原样。P3 其余案例、其他播放器及最终发行继续。
