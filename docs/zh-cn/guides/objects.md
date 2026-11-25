# 场景对象与分组

在场景中创建并组合文本、矢量路径和对象分组，查询它们的世界坐标状态，并生成可复用的副本。当你要在歌词轨道之外添加自定义画面，或直接编排场景对象时，参考本指南。

## 创建对象并加入场景

`Scene`（场景）依托一份 `Document`（歌词文档），可容纳四类元素：`TextObject`、`PathObject`、`ObjectGroup` 和 `AssDialogue`。整份 `Scene` 中所有对象的 `id`（包括分组内的后代对象）必须唯一。

```python
from kara_templater import (
    Color,
    Document,
    FadeIn,
    Lifetime,
    ObjectGroup,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)

badge = ObjectGroup(
    id="badge",
    lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(320, 180)),
    children=(
        PathObject(
            id="badge/bg",
            lifetime=Lifetime(0, 3),
            path=VectorPath.rectangle(260, 84),
            state=VisualState(position=Vec2(-130, -42), fill=Color.hex("#2A2245")),
        ),
        TextObject(
            id="badge/label",
            text="Chorus",
            font_size=44,
            alignment=5,
            lifetime=Lifetime(0, 3),
            state=VisualState(fill=Color.hex("#FFE08A")),
        ),
    ),
).animate(FadeIn(), duration=0.4)

scene = Scene(Document.create(width=640, height=360)).add(badge)
scene.export("badge.hook")
```

创建对象时注意以下几个实用细节：

- **不可变值**：所有视觉对象都是不可变 dataclass。使用 `dataclasses.replace(...)` 或 `.animate(...)` 派生修改后的新对象，原对象不会被改动。
- **字面量文本**：`TextObject.text` 按纯 Unicode 渲染，花括号 `{}` 和反斜杠 `\` 会原样显示而不会被解析为 ASS 标签；`\n` 表示换行。
- **仅描边与随形缩放描边**：在 `TextObject` 或 `PathObject` 上设置 `filled=False` 可只画描边。对象缩放时描边默认维持脚本像素宽度不变；设置 `scale_border=True` 可让描边随图形一起缩放。

坐标使用脚本像素（画布 `PlayRes`），角度为顺时针度数，透明度为 `0..1`，`TextObject.alignment` 沿用 ASS 1–9 小键盘对齐，`Lifetime(start, end)` 为半开区间（单位为秒）。完整坐标与生命周期说明见[核心概念](../concepts.md)。

## 分组层级与变换支点

`ObjectGroup` 为子对象建立局部坐标系。父级的 `position`、`scale`、`rotation` 与 `skew` 会向下叠加到所有后代，因此把底板和标题放进同一分组即可同步移动与缩放。

分组的 `(0, 0)` 原点就是它的变换支点。分组不会自动把子对象居中，请围绕目标支点布置子对象的局部坐标：

- `VectorPath.rectangle(width, height)` 从 `(0, 0)` 向右下延伸（如上例用 `Vec2(-130, -42)` 使其居中）。
- `VectorPath.circle(radius)` 默认以 `(0, 0)` 为圆心。

以下三条继承规则能帮你避开常见误区：

1. **生命周期取交集**：子对象仅在自身生命周期与所有祖先生命周期重叠的时段内可见，但它的局部动画时钟仍从自身的 `time_origin` 起算。
2. **透明度逐子相乘**：分组的 `opacity` 会分别乘到每个子绘图上，而不会先将整组离屏合成后再调透明度。
3. **着色不继承**：给 `ObjectGroup` 设置 `fill`、`outline` 或 `material` 不会改变子对象的颜色，请直接设置子对象本身。

为文字配底框或对齐装饰时，`TextObject` 的位置是其对齐锚点，描边和辉光不会增加排版步进宽度。请用 `text_extents`、`outline_text` 或 `line.layout` 获取实测边界，不要按字数估算宽度。

## 复制对象与查询世界状态

对任意 `TextObject`、`PathObject`、`ObjectGroup` 或 `LyricLine` 调用 `copy(id=..., offset=..., delay=...)`，即可生成位置与时间平移后的新副本：

```python
second = badge.copy(id="badge-2", offset=Vec2(0, 100), delay=0.5)
```

延迟副本会同时平移 `lifetime` 和显式 `clock_start`，局部动画会在新时间点原样播放。复制 `ObjectGroup` 时，所有后代 ID 会自动重命名，分组内部的 `StateReference` 依赖（例如 `FollowObject`）也会自动重映射。

要查询某个对象在指定时刻的最终世界坐标状态，请使用 `scene.evaluator()`：

```python
evaluator = scene.evaluator()
world_state = evaluator.at("badge/label", 0.2)
```

`evaluator.at(id, time)` 会完整应用父分组变换与对象引用。直接调用 `node.at(time)` 只会计算该节点自身的局部动画，不包含父级与引用。

## 混入已有 ASS 对话

使用 `AssDialogue(id=..., event=Line(...), origin=...)` 可以把已编好的 ASS `Line` 直接送入同一条 `Scene` 管线，保留其原始 ASS 文本、时间戳（含零时长事件）和来源信息。

在导出 ASS 时如需替换 `Document` 中的原有行，调用 `scene.replace_source(record_index)` 即可把原记录转为 `Comment` 保留，避免重复输出。

关于 ASS 导出策略、几何预算与 `AssObjectReport`，请参阅[导出标准 ASS](../output/ass.md)。

## 下一步

- 回顾坐标系、对齐与时间单位，见[核心概念](../concepts.md)。
- 绘制矢量图形、立体挤出与遮罩，见[图形、裁剪与遮罩](geometry.md)。
- 用动画片段和时间线驱动对象，见[动画与时间控制](animation.md)。
- 通过延迟副本和引用联动对象，见[粒子、副本与残影](particles.md)。
