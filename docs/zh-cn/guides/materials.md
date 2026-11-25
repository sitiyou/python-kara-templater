# 颜色与材质

用 RGB 颜色、渐变、描边、辉光和自定义 WGSL 着色器修饰歌词与图形。在这个指南里学习如何使用材质逐像素控制颜色与不透明度。

## 颜色与视觉属性

所有颜色均按 RGB 编写，可使用 `Color(r, g, b)`、`Color.hex("#RRGGBB")`，或内置常量 `WHITE`、`CYAN`、`YELLOW`、`PINK`、`ORANGE`、`RED`、`GREEN`、`BLUE`、`PURPLE`、`MAGENTA`、`GRAY`、`BLACK`。透明度范围为 `0`（全透明）到 `1`（不透明）。标准 ASS 的 BGR 通道顺序和反向 Alpha 会在导出时自动转换。

`VisualState` 管理对象的外观通道：`fill`、`outline`、`border`、`blur`、`shadow`、`opacity`、`face_opacity` 与 `shadow_opacity`。描边宽度与模糊半径单位均为脚本像素。缩放对象时，描边和模糊默认不会跟着放大，除非为对象设置 `scale_border=True`（针对描边）或显式为 `border`、`blur` 添加动画。

不需要手动复制多层对象，借助下面两个工具就能做出层次丰富的字效：

- `SecondaryOutline(color, width)`：在主描边之外再加一层实心外描边，宽度为 `0` 时隐藏。
- `Glow(color, blur, border, opacity)`：在两层描边背后绘制柔和辉光。`Glow.from_studio(color, radius=10, outline=5)` 可对应单层高斯辉光，其中 `outline` 为硬描边超出字形的总像素宽度。

如果填充、描边和辉光需要各自独立的生命周期、动画时钟或变色前沿，请将它们拆分为独立的场景对象。

## 歌词与对象的渐变

将 `LyricGradient` 传给 `KaraokeEffects` 或 `LyricHighlights.from_timing` 的 `material`（唱后高亮态）或 `base_material`（唱前态），无需手动测量字框尺寸。

```python
from kara_templater import Color, LyricGradient, LyricHighlights, StatePatch

highlight = LyricHighlights.from_timing(
    StatePatch(),
    material=LyricGradient((
        Color.hex("#FFE7A0"),
        Color.hex("#F660A2"),
        Color.hex("#826AFF"),
    )),
)
```

默认的 `axis="y"` 让颜色沿每个测得字形纵向分布，并随字形一起缩放和平移；正文与注音各自按自身高度计算渐变。

改为 `axis="x"` 会让渐变横跨整行正文的所有可见墨迹。注音采样同一套水平坐标，因此相邻音节在走字过程中能自然衔接。

双人合唱时，可以按行内 ASS 样式名（例如用 `{\rLead}` 与 `{\rReply}` 切换声部）传入一个映射到 `LyricGradient` 的字典：

```python
from kara_templater import Color, KaraokeEffects, LyricGradient

duet = KaraokeEffects(
    base_material=LyricGradient((Color.hex("#FFF1D8"), Color.hex("#ADE4F0"))),
    material={
        "Lead": LyricGradient((Color.hex("#FF0040"), Color.hex("#0040FF")), axis="x"),
        "Reply": LyricGradient((Color.hex("#FFCC00"), Color.hex("#00EE77")), axis="x"),
    },
)
```

每位歌手的横向渐变都会跨越自己在该行中的全部文字，哪怕中间穿插了另一位歌手。未出现在映射中的样式会回退到预设的纯色高亮填充。你也可以传入自定义工厂 `(line, target) -> LinearGradient | None`，它在准备阶段对每个目标运行一次，并可读取 `target.source_style`。

对于直接创建的 `TextObject` 与 `PathObject`，用 `ColorRamp` 和按位置递增排列的 `ColorStop`（单位为脚本像素）构造 `LinearGradient`：

```python
from kara_templater import Color, ColorRamp, ColorStop, LinearGradient

grad = LinearGradient(
    axis="y",
    space="local",
    fill=ColorRamp((
        ColorStop(5, Color.hex("#60E8FF")),
        ColorStop(65, Color.hex("#F075CB")),
    )),
)
```

Hook（libplacebo 着色器 Hook）会独立计算 `fill` 和 `outline` 渐变，每条色带最多支持 16 个色标。`space="local"` 让渐变跟随对象移动，默认的 `space="screen"` 则固定在画布坐标系上。完整可运行脚本见[渐变示例](../../../examples/gpu_gradient.py)。

## 歌词高亮扫描与辉光

常规卡拉 OK 走字搭配自定义着色层时，直接使用 `LyricHighlights.from_timing`，无需手动拼装动态裁剪矩形：

```python
from kara_templater import WHITE, YELLOW, Glow, LyricHighlights, StatePatch

paint = LyricHighlights.from_timing(
    StatePatch(fill=YELLOW, outline=WHITE, border=5),
    base_glow=Glow(WHITE, blur=8, border=10),
    glow=Glow(YELLOW, blur=12, border=14),
)
```

将 `paint` 放进 `Track.effects` 即可。源歌词时间轴严格映射到无装饰的实测字框，因此厚描边和大范围辉光不会拖慢走字速度。对于单一线性区间，引擎会自动在计时前后预留短暂的过渡肩（`edge_duration` 默认为 `0.02` s）以扫过装饰边缘。

`LyricHighlights.from_timing` 的常用参数：

- `base_paint`：覆盖唱前外观，例如 `StatePatch(opacity=0)` 可把走字改成从透明浮现而非换色。
- `segment_colors`：通过 `(unit_index, reading_index)` 到 `Color` 的映射实现逐词配色。
- `ruby_fill`：单独覆盖所有注音的高亮填充色。
- `hook_feather`、`front_color`、`sweep_angle`、`reverse` 与 `wipe=False`：控制 Hook 走字柔边、前沿色、倾角与方向，语义与 `KaraokeEffects` 一致。
- `blend_glow`：默认为 `True`。当 `base_glow` 与 `glow` 具有相同的 `blur` 和 `border` 时，Hook 会在同一张模糊字形遮罩上沿走字前沿平滑混合辉光颜色与透明度；如需独立裁剪的辉光或导出标准 ASS，请设为 `blend_glow=False`。

需要自定义多段扫描、停顿或叠加高亮层时，用 `Highlight` 与 `HighlightPass` 构造 `LyricHighlights(highlights=..., mode=...)`：

- `HighlightPass(time, region, round=0, rate=linear_rate, breakpoints=(), inverse_rate=None, reverse=False)`：按绝对秒数在测得的行内水平区间上定义一次扫描。`reverse=True` 表示从右向左扫。使用非线性速度且需要精确字符到达时刻（`HighlightArrival`）时，将 `ProgressCurve.at` 传给 `rate`、`ProgressCurve.arrival` 传给 `inverse_rate`，并把曲线时间节点传给 `breakpoints`。
- `Highlight`：用 `repeat="hold"`（新轮次保留已完成区域）或 `repeat="reset"`（重置先前轮次），以及 `end="hold"` 或 `end="hide"` 控制状态保持。
- `LyricHighlights(mode=...)`：决定重叠高亮如何合成——`"union"` 合并覆盖区，`"priority"` 取优先级最高的一项，`"layer"` 按顺序逐层叠加。

## 编写 WGSL 材质

当对象的形状和时间都已就绪、你想在 Hook 输出中用 WGSL 计算每个覆盖像素的颜色或透明度时，使用 `MaterialEffect`。

继承 `MaterialEffect`，在类属性 `wgsl` 中定义 `shade` 函数，在 `parameters()` 中返回额外参数，再通过 `MaterialClip` 挂载到 `TextObject` 或 `PathObject` 上：

```python
from dataclasses import dataclass

from kara_templater import (
    Color,
    Document,
    Lifetime,
    MaterialClip,
    MaterialEffect,
    PaintInput,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)


@dataclass(frozen=True)
class TintPulse(MaterialEffect):
    color: Color
    strength: float

    wgsl = """
fn shade(ink: vec4<f32>, ctx: KaraPaintContext, color: vec3<f32>, strength: f32) -> vec4<f32> {
    let amount = strength * sin(3.14159265 * ctx.progress);
    return vec4<f32>(mix(ink.rgb, color, amount), ink.a);
}
"""

    def parameters(self) -> tuple[PaintInput, float]:
        return PaintInput("tint", self.color), self.strength


scene = Scene(Document.create(width=640, height=360)).add(
    TextObject(
        id="title",
        text="Shader ink",
        font_size=60,
        alignment=5,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(320, 180), fill=Color.hex("#7D6BF2")),
        material_effects=(MaterialClip(effect=TintPulse(Color.hex("#E8BD66"), 0.6)),),
    )
)
scene.export("tint-pulse.hook")
```

`shade` 依次接收当前非预乘 RGBA 颜色 `ink`、上下文 `KaraPaintContext`，以及 `parameters()` 返回的各个值。函数需返回 `0..1` 范围内的非预乘 RGB 与透明度（直接保留 `ink.a` 即可维持字形抗锯齿边缘）。

| `KaraPaintContext` 字段 | WGSL 类型 | 含义 |
| --- | --- | --- |
| `local` | `vec2<f32>` | 对象局部坐标（脚本像素） |
| `screen` | `vec2<f32>` | 画布坐标（脚本像素） |
| `coverage` | `f32` | 原生遮罩覆盖率（`0..1`） |
| `time` | `f32` | 自该 `MaterialClip` 启动起的秒数 |
| `progress` | `f32` | 归一化进度（`0..1`） |
| `component` | `u32` | 覆盖平面：`0` 填充、`1` 描边、`2` 阴影、`3` 挤出侧面 |

Python 参数会自动映射为 WGSL 类型：`float` 转为 `f32`，`Color` 转为 `0..1` 的 `vec3<f32>`，`Vec2` 转为 `vec2<f32>`。

通过 `MaterialClip(effect=..., start=0.0, duration=None, target="fill")` 指定着色器的作用时段与平面：

- `start` 为相对对象时钟起点的秒数；省略 `duration` 时持续到对象生命周期结束。
- `target` 可选 `"fill"`（默认）、`"outline"`、`"shadow"` 或 `"all"`。
- 同一平面上同时生效的多个片段按声明顺序依次执行，后一个片段接收前一个片段的输出。

生成预览或导出着色器时，Naga 会校验 WGSL 并将材质函数转译为 GLSL。编译报错会指出对应的场景对象 ID。另一个完整示例见[丝带材质示例](../../../examples/gallery_material.py)。如果需要底层原生 GLSL 而非 WGSL，请参阅 [`ShaderPaint`](../../reference/paint.md#shaderpaint)。

## 使用 PaintInput 暴露可调参数

在 `MaterialEffect.parameters()` 中用 `PaintInput("name", default_value)` 包装 `float`、`Color` 或 `Vec2`，或在 `KaraokeEffects` 的 `scanline_color`、`scanline_strength` 中直接传入 `PaintInput`（参见[光效示例](../../../examples/gallery_lighting.py)）。

预览宿主可以依据 `scene.export_resources(...)` 生成的 `textures.json` 元数据，在播放期间实时修改这些命名 Uniform，复用已有着色器、字形图集与瓦片数据，无需重新构建场景。

> [!NOTE]
> 多个材质只要类型和默认值一致，就可以共享同一个 `PaintInput` 名称。涉及排版、时间轴、遮罩覆盖或特效切换的改动仍需重建场景。独立导出的 `.hook` 文件会直接固化默认值。

调用 `scene.preview()` 可在浏览器里调整具名材质参数。接入自己的播放器、反复导出不同时间窗口时，先调用 `prepared = scene.prepare_hook()`，通过 `prepared.material_inputs()` 获取全部可调参数默认值，再调用 `prepared.export_resources(...)` 按窗口导出。完整的预览与导出流程见[播放与渲染 Hook](../output/hook.md)。

## 下一步

- 在预设特效中快速组合渐变和辉光，见[内置卡拉 OK 特效](karaoke-effects.md)。
- 为位移、缩放和自定义 GPU 运动编写动画，见[动画与时间控制](animation.md)。
- 了解 Hook 播放与渲染管线，见[播放与渲染 Hook](../output/hook.md)。
- 查阅全部颜色与着色签名，见[着色 API 参考（英文）](../../reference/paint.md)。
