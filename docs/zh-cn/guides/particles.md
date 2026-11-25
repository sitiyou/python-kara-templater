# 粒子、副本与残影

沿卡拉 OK 走字前沿发射确定性粒子、为歌词添加起音残影，或通过延迟副本与世界坐标引用联动多个对象。需要多层动态效果又不想手写逐帧循环时，参考本指南。

## 沿歌词发射粒子

将 `LyricParticles` 加入 `Track.effects`，即可沿定时走字自动发射普通场景对象，无需手写发射循环。

```python
from kara_templater import (
    CYAN,
    LyricHighlights,
    LyricParticles,
    Sparkle,
    StatePatch,
    Track,
)

track = Track(
    id="main",
    effects=(
        LyricHighlights.from_timing(StatePatch(fill=CYAN)),
        LyricParticles(factory=Sparkle(size=4), rate=16, seed=42),
    ),
)
```

完整对比星芒与花瓣的可运行脚本见[歌词粒子示例](../../../examples/lyric_particles.py)。

你可以选用三种内置粒子工厂，或传入自定义工厂：

| 工厂 | 视觉效果 | 输出支持 |
| --- | --- | --- |
| `Sparkle(color=None, size=3, duration=0.45, travel=Vec2(12, -24))` | 默认。向上飘散淡出的四角星芒 | Hook 与 ASS |
| `Petal(color=None, size=4, duration=0.9, fall=40)` | 弧线飘落、旋转并翻飞的花瓣 | Hook |
| `Ribbon(color=None, width=1.5, duration=0.55, lag=0.18, travel=..., bend=...)` | 基于 `TrailPath` 的弯曲光带 | `SceneEvaluator`（动态变形路径） |

粒子颜色遵循明确的回退顺序：工厂自身的 `color` 优先，其次是 `LyricParticles(color=...)`，再到轨道或预设的高亮角色色，最后回退到源文本片段色（脱离歌词轨道使用时采用预设强调色）。自定义工厂可从 `context.color` 读取解析后的颜色。

发射位置与数量控制：

- **`placement="front"`**（默认）：在每个正时长计时片段内，沿无装饰正文走字前沿每秒发射 `rate` 个粒子。重复片段会重新驱动前沿；空格与零时长片段不发射。
- **`placement="line"`**：从歌词行原始预显起点到最后一个正时长结束（含停顿）之间，在实测正文包围盒内均匀随机撒播粒子。此时 `rate` 表示整行每秒发射数。
- **排版与预算**：粒子在出生瞬间捕获行内局部坐标并继承整行变换，单个字符的独立动画不会拉动已发射粒子。排版会自动为粒子拖尾预留显示时间，`max_particles`（默认 `256`）会在调用工厂前按行校验上限。

## 编写自定义粒子工厂

`ParticleFactory` 是接收 `ParticleContext` 并返回 `TextObject`、`PathObject` 或 `ObjectGroup` 的任意可调用对象。保留 `context.id` 与 `context.birth`，并使用内置动画（如 `Slide`、`FadeOut`、`Tween` 或 `ShaderMotion`），发射的粒子就能直接导出为 Hook（libplacebo 着色器 Hook）：

```python
from kara_templater import (
    WHITE,
    Lifetime,
    LyricParticles,
    ParticleContext,
    PathObject,
    Slide,
    Vec2,
    VectorPath,
    VisualState,
)


def dot(context: ParticleContext) -> PathObject:
    drift = Vec2(context.uniform("dx", -14, 14), context.uniform("dy", -32, -16))
    return PathObject(
        id=context.id,
        lifetime=Lifetime(context.birth, context.birth + 0.45),
        path=VectorPath.circle(context.uniform("r", 1.5, 3.0)),
        state=VisualState(position=context.position, fill=context.color or WHITE),
    ).animate(Slide(drift, entering=False), duration=0.45)


particles = LyricParticles(factory=dot, rate=14, seed=7)
```

请使用命名随机通道 `context.uniform(key, low, high)` 和 `context.choose(key, values)`，不要在工厂或回调中调用 Python 全局 `random`。每个随机值按 `(seed, emission_id, key)` 独立索引，新增属性或重排发射序列都不会扰动已有粒子，任意拖动时间轴都保持一致。

要在歌词轨道之外发射粒子，直接用一组 `Emission(id, birth)` 调用 `emit_particles(emissions, factory, seed=..., emitter=..., max_particles=1000)`，并为粒子指定明确的生命周期而非绑定到歌词时长。

## 为歌词添加起音残影

将 `LyricEcho` 放入 `Track.effects`，在每个正时长字符（或设 `target="ruby"` 针对注音）的起音时刻生成偏移淡出的完整字形残影，包括重复音符：

```python
from kara_templater import (
    RED,
    LyricEcho,
    LyricHighlights,
    StatePatch,
    Track,
    Vec2,
)

track = Track(
    id="main",
    effects=(
        LyricHighlights.from_timing(StatePatch(fill=RED)),
        LyricEcho(
            count=3,
            offset=Vec2(0, -8),
            spacing=0.06,
            duration=0.45,
            paint=StatePatch(fill=RED),
        ),
    ),
)
```

后续每个残影依次增加 `offset` 位移、延后 `spacing` 秒出现，初始透明度乘以 `opacity`（默认 `0.35`）并按 `decay`（默认 `0.65`）逐层衰减。残影默认用 `FadeOut()` 线性淡出，你也可以通过 `animation=` 指定任意 `StateAnimation`。设置负值 `delay` 可在起音前生成提前逼近的残影（最早截断至场景零秒）。

`LyricEcho` 复制的是字形准备后的静态外观，不含走字遮罩、材质和既有动画，因此在起音瞬间呈现完整字形，同时继续继承父歌词行与音节变换。排版会自动预留残影尾部，`max_copies`（默认 `256`）在展开前检查数量上限。完整脚本见[歌词残影示例](../../../examples/lyric_echo.py)。

你也可以在 `Track.effects` 中直接放入自定义的 `(LyricLine) -> LyricLine` 函数（或用 `lyric_effects(...)` 串联多个函数）；每个函数在准备阶段运行一次，且须保持歌词行 ID 不变。

## 跟随对象与历史副本

根据对象间的时间联动关系选用对应接口：

| 时间关系 | 接口 | 行为 |
| --- | --- | --- |
| 出生时采样 | `LyricParticles`、`emit_particles` | 出生瞬间读取一次发射源位置，此后粒子独立运动 |
| 持续跟随 | `FollowObject`、`ReferenceFunction` | 在每个采样时刻读取目标对象于 `time - delay` 的世界状态 |
| 复用历史运动 | `echoes`、`object.copy(delay=...)` | 绘制延迟启动的完整动画与几何副本 |

### 历史运动残影

与 `LyricEcho`（起音静态副本）不同，`echoes(source, count=4, spacing=0.06, opacity=0.4, decay=0.7, layer_step=-1, max_objects=1000)` 会复制任意 `TextObject`、`PathObject` 或 `ObjectGroup` 的完整动画，并按 `spacing` 依次延迟播放。每个副本保留各自局部时钟，复制分组时后代与父变换一并延迟。

### 世界坐标引用

给节点的 `reference=` 传入 `FollowObject(target, offset=Vec2(), delay=0, opacity_factor=1, channels=frozenset({"position"}))`，即可持续跟踪另一对象的世界状态（含父分组变换）。

需要自定义跟随逻辑时，使用 `ReferenceFunction(function, dependencies, channels, breakpoints=())`。两者均接收绝对场景秒数和 `StateLookup` 查询函数，提前声明依赖 ID（导出前即可发现缺失 ID 或循环依赖），并在复制 `ObjectGroup` 时自动重映射内部引用。

> [!TIP]
> 粒子数量、生命周期重叠、路径点数和残影层数会成倍增加渲染开销。请合理设置 `max_particles`、`max_copies` 与 `max_objects`，在调高预算前先查阅[播放与渲染 Hook](../output/hook.md)的瓦片上限或[导出标准 ASS](../output/ass.md)的事件上限。

## 下一步

- 尝试内置过渡与计时装饰粒子，见[内置卡拉 OK 特效](karaoke-effects.md)。
- 为粒子编写自定义曲线与 GPU 运动，见[动画与时间控制](animation.md)。
- 定制粒子矢量几何，见[图形、裁剪与遮罩](geometry.md)。
- 查看 Hook 性能与瓦片预算，见[播放与渲染 Hook](../output/hook.md)。
