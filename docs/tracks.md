# Track 配置与动画

`render_karaoke(document, tracks=(...))` 是新的配置入口。可以直接构造组件，也可以使用普通 Python 子类与显式 `__init__`。没有 CONFIG 收集、类属性转构造参数、自动合并构造参数或构造函数签名生成。

```python
from kara_templater import (
    CYAN, WHITE, Blur, Body, FadeInAnimation, FadeOutAnimation,
    LineMatch, Overlay, PaintStyle, Ruby, SingingPulseAnimation,
    TextStyle, Track, render_karaoke,
)

track = Track(
    source=LineMatch(style="K1"),
    body=Body(style=TextStyle(fill=WHITE, blur=Blur(radius=8, width=6))),
    ruby=Ruby(style=TextStyle(stroke_width=2), follow="syllable"),
    overlay=Overlay(style=PaintStyle(fill=CYAN)),
    animations=(
        FadeInAnimation(duration=400),
        FadeOutAnimation(duration=200),
        SingingPulseAnimation(peak=1.1, attack=80, release=160),
    ),
)
result = render_karaoke(document, tracks=(track,))
```

输入既可来自 `Document.load(...)`，也可以直接构造；显式 `items=(KaraokeItem(...),)` 同样支持。Track 匹配输入 style 或文本，不需要 ASS 私有标记。`LineMatch` 支持 `~` 否定，也可以传入类型为 `Callable[[KaraokeItem], bool]` 的自定义匹配函数。

一个输入只能匹配一个 Track；重复匹配报错。未匹配的原始对白保持可见。再次渲染时会替换同 owner 的输出；若某条歌词不再匹配，则恢复其原始对白。`effect=` 与 `tracks=` 必须且只能提供一个；旧 Effect 接口仍可使用。

## 配置、继承与复用

内置组件与动画的参数均有明确类型。自定义类通过普通构造函数暴露参数并调用 `super().__init__`，不会把任意带注解的类属性自动变成参数：

```python
class Lead(Track):
    def __init__(self, *, source: SourceMatch, peak: float = 1.05) -> None:
        super().__init__(
            source=source,
            body=Body(style=TextStyle(fill=WHITE)),
            animations=(SingingPulseAnimation(peak=peak),),
        )

lead = Lead(source=LineMatch(style="LEAD"), peak=1.08)
```

只有默认值复用时也可以使用工厂函数。`TextStyle`、`PaintStyle`、`Blur` 是普通不可变 dataclass 值，可共享并用 `dataclasses.replace` 派生变体。组件和动画配置在绑定时逐行复制，运行状态不放在共享声明上。

`Body(style=...)` 接收 `TextStyle`；为兼容旧 Effect，组件仍保留旧的 `.style` 样式写入入口，传入的不可变样式值可从 `.text_style` 读取。新 Track 可通过 styles=StyleSheet(...) 使用原有选择器与基础/sung 规则，但不调用旧 Effect 的 configure。来源选择通过 LineMatch 表达，范围选择通过 TextSpan/RubySpan 表达；传给旧 Effect 的新范围、blur、font_name、spacing 声明会明确报错，不会静默忽略。

## 排版

省略 `layout` 保持输入排版。`SingleLine(position=(x, y))` 将正文布局框左上角放到指定坐标；Ruby 跟着正文移动。`DoubleLine(position=(x, y), gap=120)` 在两个相距 120 像素的行位之间轮换。

行位使用完整显示窗口，包含显式延长的动画尾段。优先轮换到下一行位；若被占用则尝试其他行位，全部占用时报错。输入按显示开始时间稳定排序，结束与下一行开始相同视为不重叠。两行布局不负责自动文本换行。

多个独立 Track 的行位分配互不影响；K1 固定上方、K2 固定下方时，分别提供位置。需要共享行位时使用显式容器：

```python
tracks = (
    TrackGroup(
        Track(source=LineMatch(style="K1"), body=Body(style=TextStyle(fill=WHITE))),
        Track(source=LineMatch(style="K2"), body=Body(style=TextStyle(fill=CYAN))),
        layout=DoubleLine(position=(40, 280), gap=100),
    ),
)
```

TrackGroup 只协调布局，保留每个子 Track 的选择器、样式和动画。容器要求明确 position，子 Track 省略 layout，避免两个布局同时控制位置。按输入显示时间稳定排序；同一时刻按输入顺序分配，不按子 Track 声明顺序分配。使用延长后的显示窗口检查共同容量；跨容器、子 Track 和独立 Track 的重复匹配统一报错。独立容器仍各自管理行位，不隐式协调。当前容器只接受 Track，不支持嵌套。

render_karaoke 的 tracks 元组及 CLI 脚本导出都可以混合 Track 和 TrackGroup。绑定时复制布局与每行配置，重复渲染不保留分配状态。显式位置会重新参与字形定位，libass 的亚像素取整可能带来微小差异。

## 覆盖样式与代码分色

`Overlay(style=..., reveal=Sweep(...))` 描述覆盖外观和显露方式。默认绑定当前 Track 中存在的正文和注音；`targets=(Body,)` 只绑定正文。显式引用不存在的 Ruby 会报错。

```python
SUNG = PaintStyle(fill=CYAN, blur=Blur(color=CYAN))

overlay = Overlay(
    style=SUNG,
    ruby=PaintStyle(fill=WHITE),  # 只覆盖注音的填充
)
```

`body=None` 或 `ruby=None` 禁用对应角色的覆盖。省略角色配置则继承公共覆盖样式。每个角色从自己的基础外观开始解析，正文与注音的描边、blur 宽度不会被统一成同一个值。`blur=None` 禁用辉光，UNSET 不贡献覆盖值，INHERIT 恢复所属文字的基础绘制值。嵌套 Blur 按显式字段覆盖。

`PaintStyle` 只接受绘制属性；Overlay 不接受改变字体、字号、字距的 `TextStyle`。几何与动画复用基础文字，Ruby 的 sweep 使用各自 segment 的时间；`follow` 不会改写扫色时钟。

正文范围分色使用 `TextSpan`，索引是完整正文的 Unicode codepoint 范围：

```python
Body(
    style=TextStyle(fill=WHITE),
    spans=tuple(
        TextSpan(i, i + 1, overlay=PaintStyle(fill=(RED, GREEN, BLUE)[i % 3]))
        for i in range(6)
    ),
)
```

`TextSpan.style` 修改基础外观，`.overlay` 修改扫过后的外观；后声明的范围优先。越界或切断不可独立绘制的字形簇会报错。示例 [track_colors.py](../examples/track_colors.py) 用一个原始 karaoke 段显示六个字符，不需要给 ASS 添加逐字样式字段。Ruby 的独立范围使用 `RubySpan`，先指定来源 syllable/segment，再指定 reading 内的 codepoint 范围；省略 start/end 表示整个 reading：

```python
Ruby(spans=(
    RubySpan(0, 0, start=0, end=1, overlay=PaintStyle(fill=RED)),
    RubySpan(0, 0, start=1, end=2, overlay=PaintStyle(fill=GREEN)),
    RubySpan(0, 0, start=2, end=3, overlay=PaintStyle(fill=BLUE)),
))
```

Ruby 的范围不会复制正文的字号、描边或时间。拆分 reading 时，每个可独立绘制字形保留完整 reading 的扫色几何与变换中心，不能用范围切开组合字符或不安全的连写字形。

Track 的 `styles=StyleSheet(...)` 支持组件类名、来源 style、unit/segment、范围 start/end、以及 `:sung`。TextSpan/RubySpan 可用 `classes=("accent",)` 赋予代码侧角色。解析顺序是基础组件样式、范围基础样式、公共/角色 Overlay、sung 规则、显式范围 overlay。显式范围字段优先于同范围选择器规则，未指定字段不会清掉之前的声明。范围和 sung 状态不得修改字号，几何声明在测量前解析。

```python
Track(
    source=LineMatch(style="K1"),
    body=Body(spans=(TextSpan(0, 1, classes=("accent",)),)),
    overlay=Overlay(style=PaintStyle(fill=CYAN)),
    styles=StyleSheet(rule(".accent:sung", fill=RED)),
)
```

## 通用动画

```python
class AccentAnimation(Animation):
    def __init__(self, *, peak: float = 1.1, release: int = 160) -> None:
        super().__init__()
        self.peak = peak
        self.release = release

    @on(Syllable.Singing, where=LineMatch(style="K1"))
    def accent(self, event: Syllable.Singing) -> Animate:
        return Animate(
            event.target,
            scale=Envelope(
                peak=self.peak + 0.02 * (event.index % 3),
                attack=80,
                release=self.release,
                rise=lambda p: p * p,
            ),
        )
```

`event.start/end` 是输入中的绝对毫秒。事件在编译阶段展开，不使用实时队列。支持 `Syllable.Singing`、`SegmentSinging`、`Display.Start`、`Display.End`。后两者针对整个文字组；组动画也作用于未开启 syllable follow 的 Ruby。

动画可以直接声明，无需自定义类：

```python
On(Display.Start, Animate(opacity=(0, 1), duration=400))
On(Display.End, Animate(opacity=(1, 0), duration=200, offset=-200))
```

`Animate` 支持 scale、opacity、offset_x、offset_y，值可以是常量、二元过渡、Keyframes、Contextual 或标量 lambda。`rate` 用于二元过渡；`Envelope` 单独提供 rise/fall。Sequence/Parallel 可以任意嵌套 Animate 或其他 Sequence/Parallel，统一编译为属性轨道。Sequence 等待前一个组合中最晚结束的动画，包括 Envelope 的 release；Parallel 将同一个起始偏移传给所有分支。空组合会报错。

Envelope 在 attack 内达到 peak，保持到事件结束，再用 release 回到属性基础值。短音节压缩 attack；零时长音节直接从 peak 进入 release，attack=release=0 的零时长包络没有持续可见效果。release=0 在结束时回到基础值。

动画默认裁到原显示窗口，不改变演唱时间。`SingingPulseAnimation(extend_display=True)` 或自定义动画调用 `super().__init__(extend_display=True)` 可延长输出。原始 Display 时间锚点不会随延长重新计算；已有离场透明度仍可能遮住尾段。

同一层级的同属性重叠默认报错，可显式指定 `compose`。几何按 Ruby 局部 → 音节 → 整组的顺序组合，允许各层使用不同中心；缩放乘积和偏移通过仿射变换求值。需要多层缩放时转为采样输出，遵守输出事件预算。Ruby 的 `follow` 决定是否继承音节变换，整组变换始终作用于其内容。各层透明度相乘，覆盖层复用文字变换，不重复执行动画。

### 颜色与绘制属性动画

`Animate` 还支持 `fill`、`stroke`、`stroke_width`、`blur_color`、`blur_radius`、`blur_width`、`blur_opacity`。颜色接受常量、二元过渡、`ColorTransition`、`ColorKeyframes` 和返回 `Color` 的 lambda；按 sRGB 通道插值并取最近整数，颜色缓动结果必须在 0..1 内。数字属性接受前述数字动画值，`Envelope` 回到目标自己的基础值。

```python
On(Syllable.Singing, Animate(
    fill=(RED, BLUE),
    blur_radius=Envelope(peak=12, attack=80, release=200),
))
```

blur 动画要求目标已启用 `Blur`，不会在动画过程中隐式增删绘制层。素材属性选择作用于事件目标及其文字内容，Ruby 的几何 follow 不改变这一选择。若只想修改注音，可在 `SegmentSinging` 处理器中用 `dataclasses.replace(event.target, kind="ruby")` 创建只选注音的目标。

已知端点及内置缓动会自动推导绘制边界。任意几何回调必须给出上限，以便在调用用户函数之前完成预算与边界计算；超过上限会报错：

```python
On(Syllable.Singing, Animate(
    blur_radius=lambda p: 2 + 8 * p,
    bounds=PaintBounds(blur_radius=10),
))
```

上限仅描述回调的值域，不修改扫色时间，也不是 blur 前沿补偿。动态描边宽度、辉光宽度和半径一起参与绘制边界计算，仍受下述 ASS 合成限制。

颜色或 blur 动画与 Sweep 同时写同一属性时会报冲突；`compose="override"` 明确表示在动画期间同时替换基础与覆盖外观的该属性，其他扫色属性照常运行。多个素材动画写同一属性同样要求明确 override；显式覆盖按组、音节、Ruby 的层级应用，同层遵循声明顺序。动画结束后恢复静态材质，`keep=True` 则保持末值至显示窗口结束。

## ASS 后端当前边界

Track 的公开 Overlay 不接受 padding/lead/tail 补偿。扫色保持原演唱时钟，两种输出路径均使用 libass 量化后的有限核计算辉光外边界。**默认原生文字路径仍在绘制完成后硬裁剪不同颜色的描边/辉光**，不能实现“先选择字形外观，再模糊”的顺序。遇到该情况会返回明确诊断，普通调用不会因此中止输出；需要自然材质合成时显式选择下述栅格路径。

动画显式目标会校验 item、syllable、segment 和 reading 引用。目标为 Ruby 时，Track 必须有可见的 Ruby 组件；事件迭代器保留具体事件类型，`context.events(Display.Start)` 的元素类型为 `Display.Start`。

原生文字路径将透明度应用到各绘制层，重叠部分不等同于合成后统一应用 alpha；结果会提示该限制。栅格路径实现后者，并对不支持的局部透明度组合明确报错。独立 Halo 及旧底层接口作为兼容入口保留。

迁移后的 [layered_glow.py](../examples/layered_glow.py) 改为文字 blur 随 sweep 变色，移除两个 Halo、compose/configure 和时间补偿；其效果有意不同于旧版整音节双色辉光混合，不能以像素一致作为本轮验收条件。

[layered_glow_classes.py](../examples/layered_glow_classes.py) 提供等价的显式子类版本；CLI 测试验证两种配置生成相同 ASS。

完整旧写法对照见 [迁移说明](track-migration.md)；字体、alpha、扫色前沿与成本的实测证据见 [后端审计](track-backend-audit.md)。


## 可选的预模糊材质输出

`OutputSettings(raster=RasterSettings())` 为 Track 启用栅格合成；CLI 对应 `--raster`。它先按 sweep 区域选择颜色，再处理模糊，并在正文/注音合成后应用整体透明度。不同材质的 blur 半径、宽度以及禁用状态可以独立配置。旧 Effect 入口不支持此模式，会明确报错。默认仍使用原生文字输出。

此模式输出 ASS 像素矩形，成本可能显著高于文字事件。`RasterSettings` 分别限制像素、原生图像数量、单帧事件、矩形数量、单帧字符、输出字符、帧数和缓存 mask 数量；`OutputSettings.max_events` 继续限制整个结果。超过预算会报错，不输出部分结果。输出字符预算和全局事件预算均覆盖所有绑定行计划；字符预算计算生成事件的 Text 字段，不包含 ASS 文件头和事件元数据。

`RenderEstimate.raster` 提供帧数、目标采样数、画布像素数和单帧事件上限；预检不会调用动画回调。栅格部分的事件估计是“帧数 × 单帧上限”的保守上界，不是预计实际文件大小。实际编码会合并相邻区间中不变的矩形；连续且可线性表达的整组透明度使用原生 ASS 变换，避免为淡入淡出重复编码相同画面。

基础/覆盖材质、文字范围和动画目标可以分别设置透明度。每种材质携带自身的透明度权重进入模糊；同一组件内先按原始覆盖率遮挡描边与辉光，再结束组件透明度作用域。音节与根组依次使用完成的子组件覆盖率合成，避免重复降低 alpha 或让隐藏辉光透过文字。范围之间的透明度不要求相同；Ruby 可通过 Follow(opacity=False) 退出音节透明度跟随。

当前限制：旋转样式、非普通描边模式以及缩放后超过 100 的 blur 半径会明确报错。任意回调仍采用有预算的采样，不假定为线性曲线。此路径已接入 Track 时间轴，并完成完整夹具和九类视觉矩阵验证；它成本较高，不作为默认后端。

空间 overscan 直接查询 libass 量化后的模糊核及降采样对齐边界，不使用按半径估算的常量。最终视口裁切在合成后执行；四边越界文字的辉光与扩大画布渲染后裁切逐像素一致。

栅格 ASS 的像素保真依赖字幕合成格式。验证中，RGB 合成能保持像素矩形结果；直接在 YUV420 帧上混合会因相邻矩形共享低分辨率色度样本而出现分块色边。生成结果会给出这一诊断，库不会修改视频处理流程。需要精确结果时，应先在 RGB 或完整色度分辨率下合成字幕，再将最终画面转换为交付格式，例如 ffmpeg 的 `format=rgb24,subtitles=output.ass`。这项限制不应误解为已经解决普通 YUV420 播放器的字幕混合问题。

### 空间误差与时间采样

`RasterSettings(max_channel_error=4)` 显式允许每个合成颜色通道最多 4/255 的空间量化误差，默认 0 保持无损。算法分别分配 RGB 与 alpha 的舍入预算；在任意不透明背景上，两者带来的显示颜色误差之和不超过声明值。该上界不包含后续 ASS 变换舍入、视频色彩转换、YUV420 字幕混合或时间采样误差。`RenderEstimate.raster` 和结果诊断都会保留该值。

CLI 使用 `--raster --raster-color-error 4`；单独使用颜色误差参数会报错。此设置只减少颜色/alpha 精度，不移动字形、不改变 sweep 进度，也不降低采样频率。

```python
from kara_templater import OutputSettings, RasterSettings

output_settings = OutputSettings(
    resolution=(int(document.meta.res_x), int(document.meta.res_y)),
    max_events=1_000_000,
    raster=RasterSettings(max_channel_error=4),
)
```

这个示例显式提高了事件预算并开启空间量化；它不是默认建议。在 layered_glow 夹具上仍生成约 100 MB 的 ASS，Text 字段合计约 55.77 M 字符，低于默认 64,000,000 字符预算。默认无损配置仍可能触发资源预算。完整成本和误差见 [验收记录](track-effects-acceptance.md)。

栅格的几何与材质采用 `Track(sampling=SamplingSettings(step_ms=40))` 的默认保持采样。帧间参数保持到下一采样点；源演唱时钟不重定时。缩小 step_ms 能减小保持时间，但增加计算量和事件量。颜色误差预算不能约束移动前沿的时间误差；任意 lambda 也没有自动的时间连续性保证。

### 栅格预算参考

除 max_channel_error 为 0..255 的整数外，所有限制均为正整数；非法值立即报错。

| RasterSettings 参数 | 默认值 | 限制范围 |
| --- | ---: | --- |
| max_channel_error | 0 | RGB/alpha 空间量化误差预算 |
| max_pixels | 4,000,000 | 单次画布、覆盖率/过滤工作区及 mask 缓存像素限制；不是整个进程堆上限 |
| max_images | 50,000 | 一次原生栅格提取/合成的图像数量 |
| max_frame_events | 50,000 | 单帧编码事件 |
| max_rectangles | 200,000 | 单帧矩形分解 |
| max_frame_chars | 8,000,000 | 单帧编码的 Text 字符 |
| max_output_chars | 64,000,000 | 全部栅格计划合计的输出 Text 字符 |
| max_frames | 1,000 | 一个绑定歌词行的采样区间数 |
| max_cached_masks | 128 | 一个绑定歌词行的 mask 缓存条目数 |

`OutputSettings.max_events` 另行限制完整结果的事件数，`SamplingSettings.max_samples` 限制目标采样数。预检提供采样/画布/事件上界信息，并允许 on_estimate 取消；它不调用用户的属性采样函数。依赖实际像素和回调结果的限制在求值、分配与编码时继续检查。失败不返回部分结果，CLI 不写部分输出。

## 按时间求值与动画编排

新的 `Animation.sample()` 和 `Composition.compose()` 支持秒数调度、音节时间区间、
重叠接管与嵌套组合。见[动画时间轴](animation-timelines.md)及
[`syllable_pulse.py`](../examples/syllable_pulse.py) 的跨音节收尾示例。


## 与 Scene 特效组合

`prepare_karaoke` 接收与 `render_karaoke` 相同的 Document、Track/TrackGroup、Effect、导入和输出配置，返回类型化的 PreparedKaraoke。它保留来源、诊断及绘制层数，并将已降级的 Track 输出放入 `prepared.scene`；可以继续添加文字、路径、粒子、残影等 Scene 对象，最后统一编译为标准 ASS：

```python
prepared = prepare_karaoke(document, tracks=(track,))
scene = prepared.scene
scene.add(
    TextObject(
        id="caption", text="READY", lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(640, 180)), alignment=5,
    )
)
result = scene.compile(budget=SceneBudget())
result.document.save("output.ass")
```

完整固定示例见 [scene_tracks.py](../examples/scene_tracks.py)，包含注音、颜色覆盖、唱时缩放和独立轨道残影。[预览](images/scene-tracks.png)来自实际 ASS 播放，[报告](scene-tracks-validation.json)记录重复生成和跳转一致性。

准备阶段已经执行 Track 的布局、属性采样及可选栅格编码，`on_estimate` 仍在动态属性回调之前执行。再次编译 scene 不会重复执行这些回调。`prepared.diagnostics` 保留 Track 的采样/光栅提示，`prepared.layer_count` 是 Track 绘制层数；SceneResult 则报告混合场景的事件、体积、峰值活动量和各对象输出策略。

两层预算有不同检查时机：OutputSettings/SamplingSettings/RasterSettings 在准备和编码时约束 Track；SceneBudget 在最终混合编译时检查总事件、字节和峰值活动量。场景预算不能追溯取消已经执行的 Track 回调。NativeEvent 的来源 Comment 计入场景记录预算与文件体积，但不计入播放事件数和活动事件数。

原 `render_karaoke` 现在复用同一准备阶段和事件插入器，仍返回 RenderResult，保留历史归属字段及报告。场景入口默认 owner 为 `karaoke:` 加原 owner，生成时按这个归属替换之前的整组输出；重新准备时应重新添加需要保留的装饰。其他 owner 和未匹配字幕保留。输入 Document 不修改，Scene 编译也不修改准备结果。

这是保持现有效果语义的迁移入口：Track 当前成为带来源的 NativeEvent，并非可继续修改几何的 TextObject。不能给这些已降级事件应用 ObjectGroup 变换或 FollowObject；需要这类能力时使用 Document 歌词绑定得到视觉对象。将 Track 的属性、采样与整词合成进一步迁移至公共对象模型仍在进行，不能将本适配理解为全部底层实现已经合并。

## 将 Track 转为可编辑 Scene

`prepare_track_scene(document, tracks=(...))` 返回 `PreparedKaraoke`。其 `scene.objects` 中每条选中歌词都是普通 `ObjectGroup`，正文、注音、辉光和扫色分区由 `TextObject`、动态矩形遮罩及寿命组表示。可以使用 `dataclasses.replace` 修改组状态、添加动画或附加装饰，然后调用 `scene.compile()` 输出标准 ASS。

```python
from dataclasses import replace
from kara_templater import ObjectGroup, Vec2, VisualState, prepare_track_scene

prepared = prepare_track_scene(document, tracks=(track,))
scene = prepared.scene
lyric = scene.objects[0]
assert isinstance(lyric, ObjectGroup)
scene.objects[0] = replace(lyric, state=VisualState(position=Vec2(0, -30)))
scene.compile().document.save("output.ass")
```

直接构造或解析得到的 Document、显式 KaraokeItem、TrackGroup 行位分配均使用原有前端语义。导入模式保留源歌词为同 owner 的注释；未选中字幕保持可见，取消选择后恢复原字幕。与 `prepare_karaoke` 使用相同 owner 时，可在两种入口间重新生成而不留下旧输出。输入 Document 不会被修改。

准备时解析样式、布局、绑定属性并构造对象，不采样动态属性回调。`max_objects`（默认 25,000）约束生成文字节点数量和每行遮罩分区；随后 `scene.compile(budget=SceneBudget(...))` 控制帧率、输出事件、体积、峰值及路径预算。旧 Track.sampling 不控制此入口，相关说明保存在 `prepared.diagnostics`。`layer_count` 在此入口表示生成文字层数，不是最终 ASS 事件数。

返回对象保留原有演唱时钟和来源；局部修改未被动画写入的通道仍有效。替换文字长度不自动重新测量布局；一个来源可能对应多个扫色/辉光对象，整体歌词修改应以组或来源为单位。Track 几何缩放继续影响其描边与辉光半径；后续添加的普通 Scene 组变换遵循 Scene 自身的属性组合规则。

Scene 动态部分按采样中心保持状态，旧原生 Track 动画可能连续插值。透明度按绘制层应用；不同扫色外观的描边/辉光是硬裁剪，分区诊断原样保留，不代表扫色后再进行整词模糊。当前不提供此入口的 RasterSettings 模式，也不迁移旧 Effect 的任意 build() 返回值；仍可用 `prepare_karaoke` 将其作为 NativeEvent 混入 Scene。下划线、删除线、样式角度及非普通 BorderStyle 在此对象转换中明确诊断。

固定 [scene_editable_tracks.py](../examples/scene_editable_tracks.py) 演示 Track 配置、独立注音、音节缩放与自定义组动画/路径组合。见[预览](images/scene-editable-tracks.png)及[实际 ASS 验证](scene-editable-tracks-validation.json)。

```sh
uv run python -m examples.scene_editable_tracks output.ass
```
