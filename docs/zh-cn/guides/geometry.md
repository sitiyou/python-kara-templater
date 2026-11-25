# 图形、裁剪与遮罩

绘制矢量图形、提取和拆分文字轮廓、为文字或图形添加立体挤出侧面，并用静态或动态遮罩裁剪画面。需要自定义矢量几何或遮罩效果时，参考本指南。

## 绘制图形与文字转路径

`VectorPath` 由包含 `LineSegment` 与 `CubicSegment` 的轮廓组成。用 `VectorPath.rectangle(w, h)`、`VectorPath.circle(r)` 或 `VectorPath.polygon(*points)` 创建常见图形，再通过 `PathObject` 放进 `Scene`（场景）。设 `filled=False` 可绘制仅描边的线框；坐标运算使用 `Vec2` 和 `Affine2D`。

需要拆分字符、合并剪影或替换自定义字形轮廓时，可以把文本转为矢量路径：

- `outline_text(node)`：按字体实测轮廓并返回 `TextOutline(path, layout_bounds, fonts)`。空白字符的 `path` 为 `None`，但仍保留有效的 `layout_bounds`。
- `text_to_path(node, path=None)`：将 `TextObject` 转为同一局部坐标系下的 `PathObject`，同时保留可见窗口、动画与裁剪时钟。传入 `path=` 可替换为自定义的脚本像素轮廓；若原轮廓基于基线且单位为 em，只需按字形的 `em_size` 缩放并将每个 `y` 坐标加上局部 `baseline`。

下表列出了常用的测量、排布、切分与布尔几何工具：

| 函数 | 作用 |
| --- | --- |
| `path_bounds(path)` | 返回变换前的控制点包围盒（`Box`） |
| `flatten(contour, tolerance=0.25)` | 将曲线 `Contour` 展平为 `Polyline` |
| `resample_path(path, points_per_contour)` | 生成点数与拓扑匹配的均匀采样轮廓 |
| `layout_path(items, path, orient=True)` | 沿曲线排布 `PathItem`，可选随切线旋转 |
| `path_boolean(a, b, operation)` | 在显式点数与计算量预算下执行 `"intersection"`、`"union"`、`"difference"` 或 `"xor"` |
| `intersect_convex(path, boundary)` | 用凸多边形裁剪填充轮廓并保留镂空孔洞 |
| `split_path(source, columns=..., rows=...)` | 将静态填充 `PathObject` 切分为规则网格或自定义凸多边形 `cells=` 碎片 |
| `merge_geometry(group)` | 合并分组内子图形为单个 `PathObject`，用于共享剪影、描边或辉光 |

用 `split_path` 切分斜带或不规则碎片时，向 `cells=` 传入局部坐标下的凸 `Vec2` 多边形列表。静止停留阶段请保留未切分的原对象，避免抗锯齿切缝处露出细线。

## 立体挤出文字与图形

给 `Track`（声部轨道）、`TextObject` 或 `PathObject` 传入 `Extrusion`，即可沿局部偏移向量从正面轮廓扫出立体侧面。`offset` 指向从正面到背面的方向，单位为脚本像素。

```python
from kara_templater import (
    Color,
    Document,
    Extrusion,
    KaraokeEffects,
    Line,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=58, bold=True, outline=2, shadow=0),),
)
document.records.append(Line(start_time=500, end_time=2800, text=r"{\k60}Bold {\k170}depth"))

side = Extrusion(
    Vec2(6, 11),
    Color.hex("#CEDAD1"),
    back_color=Color.hex("#929F86"),
)
scene = build_lyric_scene(
    document,
    tracks=(Track(id="lead", extrusion=side, effects=(KaraokeEffects.duotone(),)),),
)
scene.export("extruded.hook")
```

省略 `back_color` 时侧面为纯色；提供 `back_color` 时，侧面会沿深度从正面的 `color` 平滑过渡到背面的 `back_color`（包括字符内部镂空处的侧面）。

立体挤出的行为特点：

- 同时扫过填充轮廓与硬主描边（`filled=False` 时仅扫过描边）。
- 随正面同步平移、缩放和淡入淡出；同一图层中，所有挤出侧面均绘制在正面背后。
- 应用在 `Track` 上时同时作用于正文和注音，卡拉 OK 走字变色仍保留在正面，且不改变原有排版尺寸。
- 浏览器预览和着色器播放支持立体挤出。标准 ASS 编译遇到挤出对象时会报错。

## 裁剪与遮罩

为视觉对象设置 `clip` 属性，可用 `RectangleClip` 或 `VectorClip` 限制绘制区域：

- `space="screen"`（默认）：遮罩固定在画布坐标中，对象可在遮罩内部移动。
- `space="local"`：遮罩绑定到对象自身，随对象层级一同变换。
- `inverse=False`（默认）仅保留遮罩内部；`inverse=True` 挖空遮罩区域。空的正向遮罩会隐藏对象，空的反向遮罩则会完整显示对象。

使用 `RectangleKeyframes` 通过 `(局部秒数, (left, top, right, bottom))` 关键帧为矩形遮罩添加动画：

```python
from kara_templater import RectangleClip, RectangleKeyframes

mask = RectangleClip(
    0,
    0,
    100,
    40,
    deform=RectangleKeyframes((
        (0.0, (0, 0, 0, 40)),
        (1.0, (0, 0, 50, 40)),
        (1.5, (0, 0, 50, 40)),  # 停顿保持
        (2.0, (0, 0, 100, 40)),
    )),
)
```

连续两个相同边界表示停顿，同一时刻的两个关键帧表示瞬间重置，零宽或零高表示空遮罩；关键帧范围之外保持端点值。

在 `SceneEvaluator` 中如需程序化边界，可传入 `RectangleFunction(function, breakpoints=())`，返回 `(left, top, right, bottom)` 或 `None`。

### 分组遮罩与后端支持

在 Hook 导出中，给 `ObjectGroup` 添加正向画布空间 `RectangleClip`（静态或 `RectangleKeyframes`）会自动与所有后代绘图的裁剪区求交，涵盖歌词变色层与立体挤出侧面。分组的关键帧沿分组自身时钟运行，每个子对象仍保留自己的裁剪坐标与时钟。

> [!NOTE]
> Hook 导出支持正向画布空间和局部空间 `RectangleClip`、`RectangleKeyframes` 以及画布空间分组矩形。`VectorClip`、`inverse=True`、局部空间分组裁剪和 `RectangleFunction` 回调不被 Hook 导出支持；详见[播放与渲染 Hook](../output/hook.md)与[导出标准 ASS](../output/ass.md)。

## 路径拖尾、书写与变形

给 `PathObject.deform`（或 `VectorClip.deform`）传入 `GeometryAnimation`，可按局部秒数动态变形路径：

- **`TrailPath`**：沿 `Contour` 或 `Polyline` 的弧长区间绘制拖尾，头部在 `duration` 内延伸，尾部延迟 `lag` 后收缩。

```python
from kara_templater import (
    Contour,
    CubicSegment,
    Lifetime,
    PathObject,
    TrailPath,
    Vec2,
)

trail = TrailPath(
    Contour(
        Vec2(),
        (CubicSegment(Vec2(10, -60), Vec2(60, -40), Vec2(80, 0)),),
        closed=False,
    ),
    duration=0.6,
    lag=0.2,
    width=2,
)
strand = PathObject(
    id="strand",
    lifetime=Lifetime(1.0, 1.8),
    path=trail.full_path,
    deform=trail,
)
```

上例中头部在局部 `0.0` s 至 `0.6` s 行进，尾部在 `0.2` s 至 `0.8` s 跟随，区间外路径为空。把 `trail.line` 传给 `MoveAlong` 可让另一对象沿完全一致的弧长曲线运动；调用 `trail.tip(time)` 可取头部位置，或直接用 `Polyline.slice(start, end)` 截取片段。描边采用斜角连接与平头端点。

- **`WritePath` 与 `WritingStroke(path, start, duration)`**：按作者指定的笔画顺序渐显路径（不会从字体自动推断笔顺）。读取 `pen_down(time)` 与 `tip(time)` 可同步驱动独立的笔尖对象及提笔间隙。
- **`MorphPath` 与 `morph(source, target, progress)`**：在拓扑一致的两条路径间插值轮廓和顶点。变形前先用 `resample_path` 对齐点数，对应关系始终由作者显式指定。
- **`PathFunction(function, max_points, breakpoints=())`**：在显式点数上限内调用自定义 `(base_path, local_seconds) -> VectorPath | None` 回调。

> [!WARNING]
> 逐帧变形的路径几何（`TrailPath`、`WritePath`、`MorphPath`、`PathFunction`）仅在 `SceneEvaluator` 中求值，着色器与标准 ASS 导出均不支持。

## 下一步

- 在分组中组合 `PathObject` 绘图，见[场景对象与分组](objects.md)。
- 在自定义粒子中使用矢量几何，见[粒子、副本与残影](particles.md)。
- 查看 Hook 裁剪与图集限制，见[播放与渲染 Hook](../output/hook.md)。
- 查阅完整几何签名，见[几何 API 参考（英文）](../../reference/geometry.md)。
