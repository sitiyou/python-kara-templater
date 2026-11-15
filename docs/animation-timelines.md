# 可采样动画与时间轴

Track 接受两种动画：`Animation.sample(t, context)` 按时间返回变换；
`Composition.compose(timeline, context)` 编排其他动画。两者都可以直接用函数构造，
也可以继承类。默认对每个有时间的音节分别播放；`On` 可以改为显示开始等事件。

## 底层动画

新接口的时间单位统一为秒。`t` 是当前动画内的经过时间，
`context.duration` 是实际播放时长（包括 `play(duration=...)` 的调整）。
`context.initial` 是该动画开始时的属性快照，`context.target` 是固定目标。

```python
from kara_templater import Animation, AnimationContext, Transform, there_and_back


class Pulse(Animation):
    def __init__(self, *, peak: float = 1.12, duration: float = 0.3) -> None:
        super().__init__(duration=duration)
        self.peak = peak

    def sample(self, t: float, context: AnimationContext) -> Transform:
        start = context.initial.scale
        assert start is not None
        progress = there_and_back(t / context.duration)
        return Transform(scale=start * (1 + (self.peak - 1) * progress))


pulse = Pulse(peak=1.15)
float_up = Animation(
    lambda t, ctx: Transform(offset_y=-10 * t / ctx.duration),
    duration=0.4,
)
```

`Transform` 支持 `scale`、`opacity`、`offset_x`、`offset_y`。
缩放是相对于排版尺寸的倍率，位移是相对于排版位置的像素偏移。
省略的属性不参与写入。回调必须在所有时刻返回相同的一组属性；
框架从 `sample(0, context)` 确定写入集合，并在后续求值时校验。
`scale` 必须为正，`opacity` 必须在 0..1 内，所有值必须有限。

回调应为无副作用的时间函数：可能被重复、乱序调用，不能依赖上一帧。
无需保存累积状态。默认结束时释放属性；`hold=True` 保留终值。
默认初始缩放和透明度为 1，位移为 0。这里的属性快照属于当前动画组合；
不同顶层动画之间仍使用 Track 原有的冲突检查和父子层级规则。

## 组合动画

```python
from kara_templater import (
    AnimationContext, Composition, MoveTo, OpacityTo, ScaleTo, Timeline,
)


def accent(timeline: Timeline, context: AnimationContext) -> None:
    timeline.play(
        ScaleTo(1.2, duration=0.3),
        MoveTo(y=-8, duration=0.2),
        t=0.5,
    )
    timeline.play(ScaleTo(1.0, duration=0.3), t=0.6)
    timeline.play(MoveTo(y=0, duration=0.2))


accent_animation = Composition(accent)
```

- 同一次 `play(a, b)` 同时开始。
- `at` 和 `t` 是同义参数，表示相对于这个组合起点的非负秒数。
- 省略开始时间，接在**上一次 play 中最晚结束的动画**之后。
- `duration` 覆盖这次 play 中各动画的时长；子组合会连同内部间隔一起等比伸缩。
- `during=TimeSpan(...)` 同时指定开始和结束，不能与 `at`、`t` 或 `duration` 混用。
- 叶动画未指定时长时，默认使用触发事件的持续时间；零时长事件需要显式时长。
- 组合的自然时长取子动画最晚结束时间。组合可嵌套，循环嵌套会报错。
- 时间调度按毫秒取整；最终 ASS 事件遵循其百分之一秒精度。

`ScaleTo`、`MoveTo`、`OpacityTo` 和 `TransformTo` 从开始时的快照插值到目标值，
完成后保留终值。内置线性组合保留为原生关键帧；任意回调和其他曲线使用现有采样配置。
子动画的开始、结束边界会切开采样区间，原生与 raster 后端都接收这些边界。

`Composition` 默认也保留终值。设置 `hold=False` 则在整个组合结束时释放属性。
非 hold 子动画结束后，该属性回到组合的初始值；已被接管的旧动画不会重新开始写入。

### 重叠与接续

上面的第一个 `ScaleTo` 原本会在 0.8 秒结束，但 0.6 秒开始的 `ScaleTo`
会从当时的缩放值接续并接管 scale。它不影响还在进行的位移动画。
接管根据开始时间计算，与 `play` 调用的书写顺序无关。
同一时刻开始且写入同一属性的动画会明确报错。

组合自身拥有其所有子动画的属性集合，作为一个整体参与父时间轴的接管；
不会把子动画泄漏到父时间轴。嵌套组合在执行前记录一次，采样时复用记录。
`compose` 用于声明时间和配置；开始时属性快照应在 `sample` 中读取。

## 当前音节放大，下一音节缩小

```python
from kara_templater import (
    AnimationContext, Body, Composition, LineMatch, ScaleTo, Timeline, Track, smooth,
)


class SyllablePulse(Composition):
    def __init__(self, *, peak: float = 1.12, last_release: float = 0.2) -> None:
        super().__init__(extend_display=True)
        self.peak = peak
        self.last_release = last_release

    def compose(self, timeline: Timeline, context: AnimationContext) -> None:
        current = context.syllable
        following = context.next_syllable
        if current.duration > 0:
            timeline.play(ScaleTo(self.peak, rate=smooth), during=current.interval)
        if following is not None and following.duration > 0:
            timeline.play(ScaleTo(1.0, rate=smooth), during=following.interval)
        else:
            timeline.play(
                ScaleTo(1.0, rate=smooth),
                at=current.end,
                duration=self.last_release,
            )


track = Track(source=LineMatch(), body=Body(), animations=(SyllablePulse(),))
```

`context.syllable` 和 `context.next_syllable` 返回相对于当前动画起点的 `TimeSpan`。
目标始终是当前音节：下一音节只提供时间。两者之间的间隔保持峰值；
若时间重叠，缩小阶段在下一音节开始时接管，并从当时的值平滑接续。
最后一个音节、下一音节无时间或零时长时，示例显式采用 0.2 秒收尾。
`next_syllable` 指输入中的直接后继，不会跳过没有时间的单元。

动画生命周期覆盖缩小阶段。`extend_display=True` 使超出显示窗口的收尾也可见，
并参与排版占位；扩展显示窗口不改变歌词原来的时间节点。

完整命令行示例：

```sh
python -m examples.syllable_pulse input.ass output.ass
```

输入可以是解析得到的 ASS Document，也可以是直接构造的 Document。

## 绑定到其他事件

```python
from kara_templater import Animation, Display, On, Transform

fade_in = On(
    Display.Start,
    Animation(lambda t, ctx: Transform(opacity=t / ctx.duration), duration=0.3, hold=True),
)
```

旧的 `Animate`、`@on`、`Sequence`、`Parallel` 和预设动画保持兼容，
它们的既有时间参数仍为毫秒。时间轴子动画使用新的 `sample` / `compose` 协议，
不把旧的事件处理器重复绑定为子动画。字体颜色、描边、blur 动画仍可使用现有 `Animate` 材质接口。
