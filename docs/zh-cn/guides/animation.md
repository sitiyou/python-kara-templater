# 动画与时间控制

使用规则、时间线、缓动曲线和自定义 GPU 运动为歌词目标和场景对象制作动画。当内置卡拉 OK 预设无法满足你的运动设计时，参考本指南。

## 用规则为歌词添加动画

将 `LyricRule` 放入 `Track.effects`，就能把同一套可复用动画绑定到歌词行、音节、字符、注音或提示上，无需手写逐字循环。

```python
from kara_templater import DriftOut, LyricRule, ScalePulse

animations = (
    LyricRule("character", "timing", ScalePulse(peak=1.06, peak_at=0.42)),
    LyricRule("character", "after_timing", DriftOut(), offset=0.14, duration=0.56),
)
```

这段配置会让每个字符在自己的计时区间内脉冲放大，在最后一次计时结束后等待 0.14 s，再用 0.56 s 漂移淡出。排版会自动为退场预留显示时间，并让高亮层随字符同步运动。完整可运行脚本见[脉冲与漂移示例](../../../examples/lyric_pulse_drift.py)。

每条 `LyricRule(target, anchor, animation, ...)` 由三部分组成：

- **目标（`target`）**：可选 `"line"`、`"syllable"`、`"segment"`、`"character"`、`"ruby"`、`"cue"`，或从歌词行查询到的显式 `LyricTarget` 对象；可通过 `tags=frozenset({...})` 进一步筛选。
- **锚点（`anchor`）**：可选 `"enter"`（行显示开始）、`"exit"`（在行显示结束时完成）、`"timing"`（每个计时区间）、`"after_timing"`（最后一次计时结束；选择 `"segment"` 则在每次重复后都触发）、`HighlightArrival`（高亮前沿到达字符时）、另一个 `LyricTarget`，或自定义函数 `(line, target) -> tuple[TimeSpan, ...]`。
- **时间选项**：设置 `duration`（省略时采用计时区间长度或 `AnimationSequence` 自身时长）、`offset`（秒数偏移）、`hold=True`（结束后保持终态）和 `stagger`（按选中顺序错开的秒数）。使用 `"exit"` 时，最后一个目标在显示结束加 `offset` 处完成，排版会预留整段错开时间；其余锚点则将后续目标依次向后推迟。

在 `LyricRule` 中省略 `ScalePulse`、`DriftOut`、`CurveIn` 或 `Transform` 的 `pivot` 时，引擎会自动取目标的实测中心作为支点（歌词行和音节取正文中心，避免被注音或辉光拉偏）。直接动画化场景对象时，省略 `pivot` 默认使用局部原点 `(0, 0)`；若要在 `LyricRule` 中强制使用局部原点，显式传入 `pivot=Vec2()`。

> [!NOTE]
> `Scene`（场景）中的生命周期、动画、时间线和 `LyricRule` 偏移统一使用**秒**（而原始 ASS `Line` 时间戳使用毫秒）。完整时间单位对照表见[核心概念](../concepts.md)。

## 按音符时长与字号缩放参数

两种方式可以让同一条规则自动适配短音、长音和不同字号，不必按行手写分支。

### 相对表达式

在规则字段或支持的特效宽度中直接使用 `Note.duration`、`Glyph.font_size`、`Canvas.height` 与 `Animation.duration`，并用 `.clamp(minimum, maximum)` 限制上下界：

```python
from kara_templater import FadeOut, Glyph, KaraokeEffects, LyricRule, Note, ScalePulse

ink = KaraokeEffects.duotone(feather=Glyph.font_size / 8)
attack = LyricRule("character", "timing", ScalePulse(), duration=Note.duration / 2)
release = LyricRule(
    "character",
    "after_timing",
    FadeOut(),
    offset=(Note.duration / 4).clamp(0.06, 0.20),
    duration=0.18,
)
```

表达式会在排版分配前的准备阶段一次性求值。`Note.duration` 只能用于计时类锚点（`"timing"` 或 `"after_timing"`），`Animation.duration` 只能在时长确定后用于 `offset`。

### 按区间生成的工厂函数

当动画参数依赖具体音符时长或排版几何时，传入接收 `LyricAnimationContext` 的工厂函数：

```python
from kara_templater import LyricAnimationContext, LyricRule, ScalePulse, smooth_rate

def pulse(timing: LyricAnimationContext) -> ScalePulse:
    return ScalePulse(
        peak=1 + 0.06 * smooth_rate(min(1, timing.duration / 0.6)),
        peak_at=0.42,
    )

rule = LyricRule("character", "timing", pulse)
```

工厂函数对每个解析出的区间只调用一次，不会逐帧执行。如果同一字符先唱 0.25 s 再重复 1.0 s，两次会各自得到独立的峰值。

在工厂内部，`timing.duration` 是请求时长或当前区间长度（不含停顿），`timing.interval` 是绝对 `TimeSpan`（`"enter"` / `"exit"` 排版前为 `None`），`timing.target` 保留完整计时历史，`timing.line` 提供实测排版，`timing.resolve(...)` 可求值任意相对表达式。工厂也可以返回多段 `Timeline.animation` 序列，见[音节脉冲示例](../../../examples/syllable_pulse.py)。

## 内置动画、时间线与缓动

所有场景对象（`TextObject`、`PathObject`、`ObjectGroup`）与 `LyricRule` 共用同一套 `StateAnimation` 类型：

| 动画 | 作用 |
| --- | --- |
| `Tween(target, rate=linear_rate)` | 从当前状态插值到稀疏的 `StatePatch` 目标 |
| `FadeIn(rate=linear_rate)` / `FadeOut(rate=linear_rate)` | 将透明度从 `0` 淡入或淡出至 `0` |
| `Slide(offset, entering, fast_reveal=True, rate=smooth_rate)` | 相对平移 `offset` 并淡入淡出；入场默认在前四分之一时长内完全显现 |
| `Jump(height=12)` | 向上跃起 `height` 脚本像素再回落 |
| `ScalePulse(pivot=None, peak=1.1, peak_at=0.5, rate=smooth_rate)` | 绕固定局部支点放大并回落 |
| `DriftOut(offset=Vec2(0, -36), scale=0.96, pivot=None, rate=smooth_rate, travel_rate=None)` | 漂移、缩小并淡出；设 `travel_rate=linear_rate` 可保持匀速位移同时缓动缩放与淡出 |
| `CurveIn(offset=..., bend=..., scale=0.85, rotation=-12, pivot=None, rate=smooth_rate)` | 沿二次曲线飞入基础姿态 |
| `ScatterOut(spread=24, rise=36, rotation=30, scale=0.85, seed=0)` | 用于 `LyricRule` 的确定性旋转散开退场工厂 |
| `MoveAlong(path, rate=linear_rate, orient=False)` | 沿 `Contour` 或 `Polyline` 移动，可选随切线旋转 |

### 动画片段与时间线

给对象附加单个动画时直接调用 `obj.animate(anim, duration=..., at=0, hold=True)`。多段编排请使用 `Timeline`：

- `timeline.play(*animations, duration=..., at=None, hold=True, breakpoints=())`：在同一时段并行播放通道不冲突的一个或多个动画。
- `timeline.wait(duration)`：推进局部时间游标。
- `timeline.keyframes(*frames, at=None)`：按局部秒数串联多个 `StateKeyframe(time, target, rate)` 关键帧。
- `timeline.repeat(count)`：重复整段编排，并保留各片段的局部时钟与断点。
- 将 `timeline.clips` 赋给对象的 `animations`，或读取 `timeline.animation` 冻结为可复用的 `AnimationSequence`，传给 `LyricRule` 或 `.animate(...)`。

完整串行与并行示例见[时间线补间示例](../../../examples/scene_native_tween.py)。

`AnimationClip` 默认在结束后保持终态（`hold=True`）；设为 `hold=False` 则在结束后恢复先前通道。重叠写入同一通道会直接报错，避免依赖求值顺序。

对象的局部时钟默认从 `lifetime.start` 起算。如果裁剪或延长可见窗口但不想挪动动画时刻，可设置 `clock_start` 保留原绝对起点（通过 `obj.time_origin` 读取）。当可见窗口早于 `clock_start` 时，几何和着色回调会收到负数局部秒，而动画片段会等到各自的局部 `start` 才启动。

### 缓动曲线

可将任意缓动函数传给 `rate`：

- 内置平滑曲线：`linear_rate`、`smooth_rate`（三次曲线，两端速度为零）、`smoother_rate`（五次曲线，两端速度与加速度均为零）、`ease_in`、`ease_out`、`ease_in_out`。
- `there_and_back(peak_at=0.25, return_at=0.5, rise=ease_in, fall=ease_out)`：生成可复用的“上升—保持—回落”曲线供 `Tween` 使用。
- `ProgressCurve(knots)` 与 `ProgressCurve.cubic_bezier(x1, y1, x2, y2)`：分段线性或控制点在 `0..1` 内的三次贝塞尔曲线。节点仅存一次，在 Python 求值与场景着色器中表现完全一致。

缓动允许有限过冲：RGB 通道自动截断在 `0..255`，几何通道外推，但透明度必须保持在 `0..1` 且描边与模糊不能为负。

## 自定义运动与连续乐句

如果只需根据归一化进度 `p`（`0..1`）描述相对运动，使用 `Transform` 即可：

```python
from kara_templater import Transform, Vec2, smooth_rate

exit_motion = Transform(
    offset=lambda p: Vec2(24 * smooth_rate(p), -36 * p * p),
    scale=lambda p: 1 - 0.04 * smooth_rate(p),
    opacity=lambda p: 1 - smooth_rate(p),
)
```

`offset`、`scale`、`rotation` 与 `opacity` 均可传常量或关于 `p` 的纯函数；省略的字段不会写入对应通道。`Transform` 会自动推导写入通道（绕 `pivot` 缩放或旋转时包含 `position` 补偿）。

需要读取完整输入 `VisualState` 时，用 `StateFunction(function, channels=...)` 包装纯函数 `(base, progress) -> VisualState`。回调必须确定性求值，不能依赖上一帧状态或全局随机数，突变处请通过 `breakpoints` 声明。

> [!IMPORTANT]
> `Transform` 与 `StateFunction` 中的任意 Python 回调可在 `SceneEvaluator` 中求值，但 Hook 和 ASS 导出不支持未编译的 Python 回调。要在 Hook 中运行自定义方程，请使用 `ProgressCurve` 或下文的 `ShaderMotion`。

### 让光标平滑掠过整句歌词

跟随歌词飞行的标记需要同时满足两点：准点抵达每个音节边界，且在边界间速度衔接自然。如果直接用直线连接 100 ms 和 600 ms 的相邻音节，速度会在一帧内骤降六倍；而给每段单独加缓入缓出又会让标记在每个音节处停顿。

把从 `line.layout` 测得的音节时间与位置当作一整条乐句的节点来处理：

1. 计算每个音节跨度的水平前进速度。对于相邻两段的前进速度 `a` 与 `b`，在内部连接点使用调和平均 `2 * a * b / (a + b)` 作为共享水平速度（静止停顿处取 `0`）。
2. 对时长 `dt`、从 `x0` 到 `x1`、两端速度为 `v0` 与 `v1` 的段落，将三次贝塞尔的水平控制点设在 `x0 + v0 * dt / 3` 与 `x1 - v1 * dt / 3`。
3. 沿整条乐句设计垂直弧线，并让标记随路径切线倾斜。

预览时重点检查“短音接长音”的交界帧，以及长音起止点附近的连续帧。

## 编写 GPU 运动着色器

需要在预览或播放时用 GPU 计算自定义运动方程时，使用 `ShaderMotion`。同时提供 GLSL 代码片段（`source`）和与之等价的 Python 求值函数（`function`），供状态捕获与输出帧网格的瓦片索引使用：

```python
from dataclasses import replace

from kara_templater import (
    Document,
    Lifetime,
    Scene,
    ShaderMotion,
    TextObject,
    Vec2,
    VisualState,
)

late_fade = ShaderMotion(
    lambda base, p: replace(base, opacity=base.opacity * min(1.0, 2.0 * (1.0 - p))),
    frozenset({"opacity"}),
    "alpha *= p < 0.5 ? 1.0 : (1.0 - p) * 2.0;",
)

scene = Scene(Document.create(width=640, height=360)).add(
    TextObject(
        id="title",
        text="GPU motion",
        font_size=56,
        alignment=5,
        lifetime=Lifetime(0, 2),
        state=VisualState(position=Vec2(320, 180)),
    ).animate(late_fade, duration=2)
)
scene.export("gpu-motion.hook")
```

在 `source` 中可以直接使用以下变量与函数：

- `p`：归一化片段进度（`progress_offset + progress * progress_scale`）。
- `item(data + i)`：读取 `parameters=(...)` 中的第 `i` 个浮点数。
- 可修改的局部通道：`pos`（`vec2`）、`scale`（`vec2`）、`skew`（`vec2`）、`angle`（角度）、`alpha`、`pen`（描边半径）、`fill`（`0..1` 的 `vec3`）与 `outline`（`0..1` 的 `vec3`）。
- 辅助函数 `basisOf(scale, skew, angle)`：返回局部线性变换矩阵。

必须在 `channels=frozenset({...})` 中声明 GLSL 写入的全部通道（支持 `position`、`scale`、`skew`、`rotation`、`opacity`、`border`、`fill` 和 `outline`）。只要 `ShaderMotion` 改变了几何姿态（`position`、`scale`、`rotation` 或 `skew`），`function` 必须在整个片段内与 GLSL 计算出相同的姿态，场景编译器才能把对象放进正确的屏幕瓦片中。

可复用的 GLSL 辅助函数可通过 `functions="..."` 传入（函数名需在模板内保持唯一）。如果你习惯用 Python 生成 GLSL，也可以选装 Metashade，在模块加载时生成一次辅助函数字符串传给 `functions=`。

## 采样与输出说明

Hook 导出会直接在 GPU 上计算内置动画（`FadeIn`、`FadeOut`、`Slide`、`ScalePulse`、单缓动 `DriftOut`、`Tween`）、`ProgressCurve` 节点以及 `ShaderMotion`。多个实例各自携带时长和支点，共享同一套着色器。

动画求值与通道冲突检查统一使用 `1e-10` s 数值容差，因此 `0.1 + 0.2` 与 `0.3` 这样的相邻片段能够无缝衔接，不会误报冲突。

导出标准 ASS 时，开启 `scene.ass.compile(native_tweens=True)` 可将符合条件的线性或缓动 `ScalePulse`、`DriftOut` 与 `Tween` 转为紧凑的原生变换（按 ASS 10 ms 网格对齐）。完整规则与限制见[导出标准 ASS](../output/ass.md)与[播放与渲染 Hook](../output/hook.md)。

## 下一步

- 组合对象层级与延迟副本，见[场景对象与分组](objects.md)。
- 发射粒子并跟随运动目标，见[粒子、副本与残影](particles.md)。
- 一步步完成自定义动画实战，见[编写自定义动画](../tutorials/custom-animation.md)。
- 研读八组完整动态编排案例，见[动态编排研究](../tutorials/lyric-studies.md)。
