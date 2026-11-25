# 编写自定义动画

编写一个可复用的 Python 动画函数，让一排旋转火花沿波浪轨迹飞过 Hook 场景。当内置动画无法表达想要的运动曲线，或你需要带有独立生命周期的装饰对象时，可以采用这种做法。

## 让一排火花动起来

这份完整脚本定义了带正弦波动、自转和淡出的飘移曲线，把它挂到四个错开出生的粉色圆形上，并在当前目录生成 `sparks.hook`。

```python
from dataclasses import replace
from math import sin, tau

from kara_templater import (
    PINK,
    AnimationClip,
    Document,
    Lifetime,
    PathObject,
    Scene,
    ShaderMotion,
    Vec2,
    VectorPath,
    VisualState,
)


def drift(state: VisualState, progress: float) -> VisualState:
    return replace(
        state,
        position=state.position + Vec2(300 * progress, 30 * sin(tau * progress)),
        rotation=360 * progress,
        opacity=1 - progress,
    )


def spark(identity: str, position: Vec2, birth: float) -> PathObject:
    return PathObject(
        id=identity,
        path=VectorPath.circle(8),
        lifetime=Lifetime(birth, birth + 2),
        state=VisualState(position=position, fill=PINK),
        animations=(AnimationClip(
            0, 2,
            ShaderMotion(drift, frozenset(("position", "rotation", "opacity")),
                         "pos += vec2(300.*p,30.*sin(6.28318531*p)); angle=360.*p; alpha=1.-p;"),
        ),),
    )


scene = Scene(Document.create(width=640, height=360)).add(
    *(spark(f"spark:{i}", Vec2(100, 100 + i * 35), i * 0.1) for i in range(4))
)
scene.export("sparks.hook", fps=60)
```

## 运动函数与工厂的工作方式

`spark` 只是一个普通的 Python 工厂函数。每次调用都会返回一个独立可编辑的 `PathObject`，拥有唯一 `id`、初始坐标和绝对时间 `Lifetime`。里面的 `AnimationClip` 从对象局部时间 `0`（即火花出生时刻）开始，持续 `2` 秒。

`drift` 是接收 `(state, progress)` 的纯函数，其中归一化进度 `progress` 范围是 `0` 到 `1`。它直接根据传入状态计算新的 `VisualState`，不依赖上一帧的记忆，因此场景可以在任意时刻按任意顺序求值。

`ShaderMotion` 负责把纯 Python 函数桥接到 Hook 渲染：

- **声明的 `channels`**（`position`、`rotation`、`opacity`）告诉引擎这段动画会改写哪些属性，以便检测冲突动画并保留其他通道的变化。
- **GLSL 代码体** 在 GPU 上按当前帧的归一化进度 `p` 逐帧运行，更新局部着色器变量（`pos`、`angle`、`alpha`）。
- **Python 回调函数**（`drift`）在片段边界提供精确状态，并在导出 Hook 时用来为输出帧网格计算几何边界索引。

> [!IMPORTANT]
> 请务必让 Python 函数、声明的 `channels` 集合与 GLSL 代码体三者保持一致。如果回调函数修改了未在 `channels` 中声明的通道，冲突检查就会漏报；如果 Python 曲线与 GLSL 算式不一致，裁剪边界和实际渲染位置就会错位。

## 定制这段动画

你可以沿用同一套结构，独立替换任意环节：

- **形状**：把 `VectorPath.circle(8)` 换成 `VectorPath.polygon(...)` 或任意自定义 `VectorPath`。
- **轨迹与缓动**：同步修改 `drift` 和 GLSL 字符串中的振幅、位移距离或旋转圈数。
- **数量与排程**：调整循环次数、坐标间距或出生时间 `birth`，控制更多火花的节奏。
- **突变点**：如果曲线在某个局部时刻出现跳变，在 `AnimationClip` 上显式传入 `breakpoints=(...)`。

如果需要批量发射带随机变化的粒子，可以改用 `emit_particles` 为每颗粒子提供可复现的命名随机通道。想把自定义装饰与带时间轴的歌词结合起来时，只需先用 `Track` 构建歌词 `Scene`，再把你的自定义对象 `.add(...)` 进去即可。

## 下一步

- [动画与时间轴](../guides/animation.md)：了解 `Transform`、`StateFunction`、`ShaderMotion` 与 `Timeline`。
- [粒子、副本与重影](../guides/particles.md)：使用 `emit_particles` 与 `LyricParticles`。
- [播放与渲染 Hook](../output/hook.md)：用 mpv 或 FFmpeg 预览 `sparks.hook`。
- [API 参考：Animation and timing](../../reference/animation.md)：查看 `ShaderMotion` 提供的全部 GLSL 变量与字段。
