# E04 固定樱花发射与合成验收

第九十四批：scene_sakura.py 达到案例卡的 **libass 首版目标**。固定 seed 17、18 片环境曲线花瓣、6 片直线花瓣、12 片演唱前沿触发花瓣，均有 3 秒寿命；前沿另带四层历史残影。

| 要求 | 证据 | 结果 |
| --- | --- | --- |
| 歌词布局与可见前沿 | [独立歌词参考](sakura-lyrics-validation.json)使用原生字形位移/advance 测量及标量 24/32 px 颜色公式 | 53 状态、四背景 236 帧完整 RGB 差 0 |
| 发射表、出生捕获、游标/残影 | [发射参考](sakura-validation.json)独立计算三组出生表、寿命和历史时钟；游标起点/跨度/高度来自独立原生字体测量及半宽延伸 | 36 个身份/寿命、12 次出生捕获、30 项游标/残影位置与 alpha、18 项直线位移通过 |
| 30 片曲线的移动/旋转/收缩/淡出 | [花瓣参考](sakura-flutter-validation.json)独立 keyed random、三次轨迹、flutter 公式及手写花瓣路径 | 填充和描边各 480 项满足 1 px；alpha 差最多 1/255，非整厘秒出生的舍入差另报 |
| 6 片直线花瓣的完整几何 | 同报告新增独立出生坐标、匀速位置、初始旋转/缩放及原生路径参考 | 72 项包含画内/画外状态；有内容时填充与描边满足 1 px，alpha 为 0 |
| 重叠与层序 | [完整合成报告](particle-composite-validation.json)将隔离对象的原生覆盖率按固定层序浮点 source-over，与实际完整场景 FFmpeg 输出比较 | 四背景 24 帧完整 RGB 最大差 2/255，累计 2856 重叠像素；反转层序反例被检出 |
| 播放与跳转 | [四背景报告](engine-backgrounds-sakura-final-validation.json)每背景 600 时刻连续/乱序；[单例报告](scene-sakura-validation.json)300 帧、8 次独立跳转 | 全部一致，重复生成一致；最大时间量化差 4.706 ms，低于 10 ms |
| 成本与整曲 | 14805 事件、峰值 244、7053588 字节 | 低于预设 25000 / 1000 / 10 MiB。6 片直线各 1 个 native-move 事件；曲线保留采样，与整曲 E04 解码 UTF-8 BOM 后全文相同 |

曲线花瓣原始填充覆盖率差最大 72/255、描边外包络差最大 106/255，细环原始差最大 141/255 单列。几何使用未乘 alpha 的外包络，避免淡出细描边阈值碎裂；不宣称边缘完全一致。合成参考复用隔离对象的实际覆盖率，因此独立验证的是叠加运算/顺序；各对象几何、时间和颜色由其他报告分别支持。

[实际/参考/差图](images/particle-composite.png)已检查。固定关键时刻检查不推广成任意连续函数的误差界，原生游标与中点保持颜色前沿也不声称区间内像素完全重合。

重现：

```sh
uv run python -m tools.validate_sakura build/ass-engine/sakura-final-reference
uv run python -m tools.validate_sakura_flutter build/ass-engine/sakura-final-flutter
uv run python -m tools.validate_sakura_lyrics build/ass-engine/sakura-lyrics
uv run python -m tools.validate_particle_composite build/ass-engine/sakura-final-composite
uv run python -m tools.validate_engine_backgrounds --case E04 build/ass-engine/sakura-final-backgrounds
uv run python -m tools.validate_scene_core --scene sakura build/ass-engine/sakura-final
```

樱花、粒子、世界引用及文件往返 35 项回归、Ruff、ty 通过。P3 遮罩/组组合与扫色策略比较、其他播放器及最终发行仍继续。
