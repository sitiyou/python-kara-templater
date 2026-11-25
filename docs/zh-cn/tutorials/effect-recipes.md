# 特效配方

可直接复制到模板中并按歌曲微调的独立卡拉 OK 视觉配方。每个配方都列出视觉效果、核心 Python 写法以及最常调整的参数。

## 组合内置入场、高亮、退场与装饰

`KaraokeEffects` 可以在一条声明里自由搭配入场、走字高亮、退场和粒子装饰。

![四种内置入场、高亮与退场组合效果](../../examples/assets/karaoke-builtins.gif)

| 配方名 | 入场 / 高亮 / 退场 | 装饰 | 适用场景 |
| --- | --- | --- | --- |
| Clear | `tracking_in` / `scanline` / `char_fade` | `stroke_flash=True` | 整曲通用，动感克制且清晰易读 |
| Sakura | `wave_in` / `zoom_pulse` / `petal` | `petal`，速率 5，尺寸 0.18 | 舒缓乐段，粉色唱后填充配缓落花瓣 |
| Luminous | `glow_in` / `utopia_scanline` / `stretch_out` | `twinkle` | 强调副歌短句，光斑收束后进入走字 |
| Crystal | `assemble_in` / `scanline` / `dissolve_out` | `snow`，速率 4 | 过渡乐句，聚散雪花粒子强化情绪转折 |

```python
from kara_templater import Color, KaraokeEffects

sakura = KaraokeEffects(
    entry="wave_in",
    highlight="zoom_pulse",
    exit="petal",
    decoration="petal",
    after_fill=Color(255, 160, 205),
    particle_size=0.18,
    particle_rate=5,
    seed=17,
)
```

**可调参数：**

- 把和声放在单独的 `Track` 上，降低粒子密度并改用简洁退场，避免多层动效挤满画面。
- 粒子生成速率按计时字形单独计算，因此包含多个独立字母的英文单词会比等长单汉字发射更多粒子；英文歌词应调低 `particle_rate`。
- 可运行 [karaoke_catalog.py](../../../examples/karaoke_catalog.py) 逐项试看全部内置组合。

## 不用走字扫色也能标示节奏

取消字符内部的走字扫色，改为让一枚小标记在起唱瞬间跳到当前音节上方，同时让音节短暂放大脉冲，并在松口结束时整字切换为高亮色。

![琥珀色小菱形在夜街画面上的中文歌词间按节拍跳跃](../../examples/assets/lyric-no-sweep.gif)

```python
from itertools import pairwise
from kara_templater import (
    Color,
    Lifetime,
    LyricHighlights,
    LyricLine,
    LyricRule,
    PathObject,
    ScalePulse,
    SceneEvaluator,
    StateKeyframe,
    StatePatch,
    Timeline,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
)

WAITING = Color.hex("#EFEDE3")
COMPLETED = Color.hex("#F4BB73")
EDGE = Color.hex("#192027")

effects = (
    LyricHighlights.from_timing(
        StatePatch(fill=COMPLETED, outline=EDGE),
        wipe=False,
        base_paint=StatePatch(fill=WAITING, outline=EDGE),
    ),
    LyricRule("syllable", "timing", ScalePulse(peak=1.13, peak_at=0.24)),
)


def note_marker(line: LyricLine, evaluator: SceneEvaluator) -> PathObject:
    notes = [target for target in line.query("syllable") if target.timing]
    first, last = notes[0].timing[0].start, notes[-1].timing[-1].end
    top = line.state.position.y + line.layout.body.bounds.top - 31
    stops = [
        (
            note.timing[0].start - first,
            Vec2(
                evaluator.at(note.node_id, note.timing[0].start)
                .transform.apply(note.center)
                .x,
                top,
            ),
        )
        for note in notes
    ]
    keys: list[StateKeyframe] = []
    for (prev_t, prev_pos), (onset, target_pos) in pairwise(stops):
        travel = min(0.12, (onset - prev_t) * 0.45)
        peak = prev_pos.lerp(target_pos, 0.52) + Vec2(0, -13)
        keys.extend(
            (
                StateKeyframe(onset - travel, StatePatch(position=prev_pos)),
                StateKeyframe(onset - travel * 0.48, StatePatch(position=peak), smooth_rate),
                StateKeyframe(onset, StatePatch(position=target_pos), smooth_rate),
            )
        )
    diamond = VectorPath.polygon(Vec2(-10, 0), Vec2(0, -8), Vec2(10, 0), Vec2(0, 8))
    return PathObject(
        id=f"{line.id}/note-marker",
        path=diamond,
        lifetime=Lifetime(first, last),
        layer=2,
        state=VisualState(position=stops[0][1], fill=Color.hex("#FFC67F"), outline=EDGE, border=1.6),
        animations=Timeline().keyframes(*keys).clips if keys else (),
    )
```

**可调参数：**

- 按相邻起唱间隔缩放跳跃耗时（`min(0.12, gap * 0.45)`），保证快歌段落里标记依然跟得上、看得清。
- 若歌词带有注音，适当增大 `top` 偏移（`-31`）与弧顶高度（`-13`）以避开读音。
- 完整可运行脚本见 [lyric_no_sweep.py](../../../examples/lyric_no_sweep.py)。

## 让乐句从狭缝中滑出显现

在每个字符最终墨迹外缘紧贴着放一道静止的隐形裁剪窗口，让字符在起唱前水平滑出并快速减速到位，呈现仿佛从画面切缝背后浮现的质感。

![日语歌词从右向左透过隐形切缝滑入就位](../../examples/assets/slit-reveal.gif)

```python
from dataclasses import replace
from kara_templater import (
    Lifetime,
    RectangleClip,
    StateKeyframe,
    StatePatch,
    TextObject,
    Timeline,
    Vec2,
    VisualState,
    outline_text,
    path_bounds,
)

FPS = 30
DISPLACEMENT = (1.0, 0.573, 0.347, 0.213, 0.127, 0.067, 0.033, 0.013, 0.0)


def slit_entrance(text: TextObject, state: VisualState, start: float, end: float) -> TextObject:
    path = outline_text(text).path
    if path is None:
        raise ValueError(f"missing outline for {text.id}")
    ink = path_bounds(path.map(state.transform.apply))
    padding = 9
    distance = ink.width + 2 * padding
    return replace(
        text,
        id=f"{text.id}/entrance",
        lifetime=Lifetime(start, end),
        clock_start=None,
        state=replace(state, position=state.position + Vec2(distance, 0)),
        clip=RectangleClip(
            ink.left - padding,
            ink.top - padding,
            ink.right + padding,
            ink.top + ink.height + padding,
        ),
        animations=Timeline()
        .keyframes(
            *(
                StateKeyframe(
                    frame / FPS,
                    StatePatch(position=state.position + Vec2(distance * remaining, 0)),
                )
                for frame, remaining in enumerate(DISPLACEMENT[1:], start=1)
            )
        )
        .clips,
    )
```

**可调参数：**

- 4 到 6 字的紧凑短句可在 30 fps 下按每字错开 1 帧依次滑出，让最后一字在起唱前稳稳就位。
- 更长或带注音的歌词行，建议按音节分组，围绕正文与注音合并后的墨迹边界（含描边）开设共享的 `RectangleClip`，并在起唱前约 0.40 秒完成全部滑入。
- 若背景明暗变化剧烈，可以给字形加一层细描边并相应增大 `padding`。
- 完整脚本见 [slit_reveal.py](../../../examples/slit_reveal.py)。

## 让固定位置的歌词对焦入场与失焦退场

保持基线纹丝不动，入场时从柔和模糊收敛到清晰，整个演唱期间保持锐利，退场时再重新虚化淡出。

在 Hook 渲染中，`KaraokeEffects` 已经内置了可直接走 GPU 管线的模糊过渡（`glow_in` 与 `glow_out`）：

```python
from kara_templater import KaraokeEffects

focus_fade = KaraokeEffects(
    entry="glow_in",
    exit="glow_out",
    entry_duration=0.36,
    exit_duration=0.36,
)
```

如果你需要自定义散焦曲线，或者模拟像素格马赛克显现效果，可以在 Hook 中使用 `MaterialEffect` 或 `ShaderPaint`，在固定屏幕像素格（例如 1080p 下 92 px 正文配 7 px 网格）上混合采样覆盖率，并在起唱前收拢回清晰文本。

> [!NOTE]
> 直接用 `Tween(StatePatch(blur=0))` 从 `VisualState(blur=5)` 插值 `blur` 通道只支持 ASS 导出，在导出 Hook 时会触发 `SceneCompileError`。Hook 场景请使用 `glow_in` / `glow_out` 或自定义着色器材质。

**可调参数：**

- 起唱前保留大约 0.30 秒的清晰静止期，方便演唱者提前看词。
- 走字期间正文和注音必须全程保持清晰，并在交付分辨率下检查小号读音边缘是否发糊。

## 逐字打字显现并在唱后擦除

起唱前从左到右依次显现成形的字词单元，由一条细光标紧随最后一个可见字符移动；整行就绪后隐藏光标；唱完最后音节并短暂留白后，再沿原路径从右到左擦除。

```python
from dataclasses import replace
from kara_templater import Lifetime, LyricLine, PathObject, Vec2, VectorPath, VisualState


def typewriter_caret(line: LyricLine, *, step: float = 0.075, lead: float = 0.35) -> LyricLine:
    cells = line.layout.body.characters
    if not cells:
        return line
    pickup = min(span.start for span in line.query("line")[0].timing)
    start = max(line.lifetime.start, pickup - lead - len(cells) * step)
    bar = VectorPath.rectangle(3, line.layout.body.bounds.height)
    carets = []
    for index, cell in enumerate(cells):
        t0 = start + index * step
        carets.append(
            PathObject(
                id=f"{line.id}/caret:{index}",
                path=bar,
                lifetime=Lifetime(t0, t0 + step),
                state=VisualState(position=Vec2(cell.bounds.right + 4, line.layout.body.bounds.top)),
            )
        )
    return replace(line, children=(*line.children, *carets))
```

**可调参数：**

- 建议把每步间隔 `step` 设为约 `0.075` 秒，让整行在起唱前约 `0.35` 秒全部显现完毕。
- 让每组注音读音跟随宿主正文单元同步显隐，避免振假名悬空出现。
- 全程保持字符留在最终基线上，裁剪唱前与唱后可见区间时不要改动原始计时时钟。

## 让各音节从不同边缘切入汇合

让同一行里的各个音节（连同各自的注音）分别从裁剪视口的左、上、下、右四个方向滑入，共享同一条先快后慢的贝塞尔缓动曲线，使所有音节在同一瞬间平稳落位。

```python
from kara_templater import ProgressCurve, StatePatch, Tween, Vec2

fast_settle = ProgressCurve.cubic_bezier(0.17, 0.17, 0, 1).at


def enter_from_edge(rest_position: Vec2, direction: Vec2, distance: float) -> tuple[Vec2, Tween]:
    start_position = rest_position + direction * distance
    motion = Tween(StatePatch(position=rest_position), rate=fast_settle)
    return start_position, motion
```

**可调参数：**

- 按每个音节的正文、注音与描边合并后的墨迹范围测量 `RectangleClip` 视口，并把整个音节分组一起位移，保证读音始终紧跟正文。
- 节奏紧凑的乐句需要缩短位移距离 `distance` 或动画时长，确保起唱前整行完全就位且不与退场行打架。
- 在深色背景上用浅色唱前填充搭配高饱和高亮色，能让交汇轨迹更加利落。

## 为唱前与唱后分别指定描边

在走字前沿同时切换填充色与描边色——例如唱前是白字配青色描边，唱后转为深蓝字配白色描边——并在两种状态下方都保留一层轻巧的深色阴影。当视频画面在暗部和近白高光之间频繁切镜时，双态描边能稳住可读性。

```python
from kara_templater import WHITE, Color, LyricHighlights, StatePatch, Vec2

two_state = LyricHighlights.from_timing(
    StatePatch(
        fill=Color.hex("#000EFF"),
        outline=WHITE,
        border=2.4,
        shadow=Vec2(1.5, 2),
    ),
    base_paint=StatePatch(
        fill=WHITE,
        outline=Color.hex("#349DEA"),
        border=2.4,
        shadow=Vec2(1.5, 2),
    ),
)
```

如果想直接套用同款思路的内置预设，也可以使用 `KaraokeEffects.duotone(before_fill=..., before_outline=..., after_fill=..., after_outline=...)`。

**可调参数：**

- 按字号等比缩放 `border`（1080p 主唱行大约 `2.4` px），并给注音单独设更细的描边，防止小字内部笔画粘连。
- 除了检查静止状态，还要抽查 `FadeIn` 或 `FadeOut` 半透明过渡帧：半透明字面下方的阴影会透出来。

## 仅在唱完后打碎最后一个字符

整句歌词连同注音在整个演唱期间保持完整。短暂静止后，只把最后一个字形转成矢量路径，用 `split_path` 沿斜向条带切开，再用 `DriftOut` 让每片碎块朝不同方向飘散。

```python
from kara_templater import (
    DriftOut,
    PathObject,
    TextObject,
    Vec2,
    path_bounds,
    split_path,
    text_to_path,
)


def shatter_glyph(glyph: TextObject, *, duration: float = 0.5) -> tuple[PathObject, ...]:
    source = text_to_path(glyph)
    box = path_bounds(source.path)
    mid = box.top + box.height / 2
    cells = (
        (
            Vec2(box.left - 20, box.top - 10),
            Vec2(box.right + 20, box.top - 10),
            Vec2(box.right + 20, mid - 8),
            Vec2(box.left - 20, mid + 8),
        ),
        (
            Vec2(box.left - 20, mid + 8),
            Vec2(box.right + 20, mid - 8),
            Vec2(box.right + 20, box.top + box.height + 10),
            Vec2(box.left - 20, box.top + box.height + 10),
        ),
    )
    offsets = (Vec2(-18, -22), Vec2(28, 16))
    return tuple(
        shard.animate(DriftOut(offset=offset), duration=duration)
        for shard, offset in zip(split_path(source, cells=cells), offsets, strict=True)
    )
```

**可调参数：**

- 静止停留阶段保留未切分的原始 `TextObject`，等到碎裂开始再切换成碎片对象，避免相邻切缝在光栅化时露出细白线。
- 末字碎裂时同步淡出它的注音，同时保持下一行照常按原位置与节奏入场。

## 下一步

- [设计整曲歌词布局](karaoke-design.md)：把这些特效融入多声部整曲模板。
- [动效对比研究](lyric-studies.md)：横向对比八种常见歌词动效机制。
- [内置卡拉 OK 特效](../guides/karaoke-effects.md)：查阅 `KaraokeEffects` 的完整选项表。
- [形状、裁剪与遮罩](../guides/geometry.md)：深入了解 `RectangleClip`、`outline_text`、`text_to_path` 与 `split_path`。
