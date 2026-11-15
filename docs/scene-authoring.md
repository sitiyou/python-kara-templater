# 编写标准 ASS 特效

从固定示例的 `build() -> Scene` 开始，修改对象和时间，再调用 `compile()`、保存 `result.document`。示例不要求任意歌词输入，也不隐藏动画函数或几何构造。所有播放结果都是标准 ASS；Document 可以在 Python 中构造，也可以用 `Document.load` 读取文件。

## 先运行一个效果

在仓库根目录执行：

```sh
uv run python -m examples.scene_sweep sweep.ass
uv run python -m examples.scene_sakura sakura.ass
uv run python -m examples.scene_lyric_cues cues.ass
```

加载这些 ASS 到播放器即可查看；目标播放器的已知差异及验证范围见[兼容矩阵](player-compatibility.md)。固定视觉验收使用仓库字体及 libass；本机字体替换可能改变文字宽度。要复现项目的预览环境，使用 `uv run python -m tools.validate_scene_core --scene sweep build/preview-sweep`：工具先生成实际 ASS，再由 FFmpeg/libass 渲染该文件。

| 案例 | 固定示例模块（`examples.` 后的名字） | 主要修改点 |
| --- | --- | --- |
| E01 正文/注音辉光 | `scene_lyrics` | 歌词、注音、独立辉光层、脉冲和扫色 |
| E02 错峰入退场 | `scene_staggered` | `bounce`、`orbit`、逐字时间线 |
| E03 圆弧与重复高亮 | `scene_round` | 路径布局、切线旋转、正文/注音组合 |
| E04 樱花 | `scene_sakura` | `PETAL`、`petal` 工厂、发射表和随机种子 |
| E05 碎片聚合 | `scene_fragments` | 分片几何、出生错峰与归位动画 |
| E06 词背景与装饰 | `scene_cues` | 文字范围、测量背景、导唱工厂 |
| E07 轮廓扰动 | `scene_outlines` | 路径变形函数与时间包络 |
| E08 书写 | `scene_writing` | 显式笔画路径、显露进度、抬笔断点 |
| E09 渐变与残影 | `scene_gradient` | 颜色场、逐字颜色与延迟副本 |
| E10 形状插值 | `scene_morph` | 对应轮廓、控制点与插值时间 |
| E11 柔和扫色 | `scene_sweep` | 填充/描边过渡宽度、独立恒定辉光 |
| E12 导唱与注音 | `scene_lyric_cues` | CueMarker、预设工厂、文本、独立位置及行内占位 |

上述模块均接受输出 ASS 路径，不需要输入文件。逐例的实际验证范围见 `docs/e01-acceptance.md` 至 `docs/e12-acceptance.md`；它们演示机制，不声称逐像素复刻外部作品。

## 用普通函数定义对象与动画

对象工厂返回 TextObject、PathObject 或 ObjectGroup；不需要继承编译器或拼接 ASS 标签。下面是一份可直接执行的完整脚本：

```python
from dataclasses import replace
from math import sin, tau

from kara_templater import (
    PINK, AnimationClip, Document, Lifetime, PathObject, Scene,
    StateFunction, Vec2, VectorPath, VisualState,
)


def drift(state: VisualState, progress: float) -> VisualState:
    return replace(
        state,
        position=state.position + Vec2(300 * progress, 30 * sin(tau * progress)),
        rotation=360 * progress,
    )


def spark(identity: str, position: Vec2, birth: float) -> PathObject:
    return PathObject(
        id=identity,
        path=VectorPath.circle(8),
        lifetime=Lifetime(birth, birth + 2),
        state=VisualState(position=position, fill=PINK),
        animations=(AnimationClip(
            0, 2, StateFunction(drift, frozenset(("position", "rotation"))),
        ),),
    )


scene = Scene(Document.create()).add(
    *(spark(f"spark:{i}", Vec2(300, 250 + i * 35), i * 0.1) for i in range(4))
)
result = scene.compile()
result.document.save("custom.ass")
print(result.event_count, result.peak_active, result.byte_count)
```

`StateFunction` 明确声明写入通道。函数从输入状态和归一化进度计算结果，不能依赖上次调用、全局可变随机数或播放顺序。需要不连续切换时，在 AnimationClip 或 SceneTimeline.play 的 `breakpoints` 中声明动画内部秒数。几何变形使用 PathFunction/RectangleFunction，颜色空间函数使用 PaintField，导唱扩展使用 CueFactory；各协议和实例见[场景契约](scenes.md)。

Scene 时间使用秒；ASS Line 和旧模板 helper 使用毫秒。Lifetime 是绝对显示时间，AnimationClip 的 start 相对对象出生。SceneTimeline 提供顺序、并行、错峰、重复和关键帧；同通道冲突会报错。细节见[时间和属性](scenes.md#时间和属性)。

## 生成器、复制和跟随

少量固定对象可直接用 Python 推导式。带随机变化的粒子使用 `emit_particles` 和 ParticleContext：以稳定的发射身份和 seed 取样，使用 `context.uniform("size", ...)` 等有名字的随机通道。添加一个随机属性不会推进其他属性的随机序列。

`scene_sakura` 的 `petal(context)` 返回普通路径对象；环境、直线和歌词前沿发射复用同一工厂。发射源在出生时取位置，之后粒子独立运动。持续跟随使用对象引用，历史轨迹使用 `echoes`；这三种时间关系不能互换。可编辑组采用本地坐标，世界引用经 SceneEvaluator 求值，详见[对象引用](scenes.md#对象引用与世界坐标跟随)。

已有对象通过 `copy(id=..., delay=..., offset=...)` 派生，必须使用唯一身份。覆盖率组件的外部绑定按身份关联，复制或改名时需同步重定向，见[迁移核对](track-scene-migration-audit.md)。

## 采样、报告与昂贵出口

`SceneBudget` 控制采样帧率、事件数、活动峰值、输出字节、路径点数、颜色条带和布尔运算工作量。默认 50 Hz；ASS 的厘秒时间网格最多支持 100 次/秒。静态对象和可表达的直线运动可以用原生事件，其他组合按断点切分并取中点；任意自定义函数不因设置了帧率就获得严格误差上界。

检查 `SceneResult.objects` 中每个对象的 strategy、events、sample_interval 和 origin，以及最终 event_count、peak_active、byte_count、max_time_quantization。`SceneCompileError` 提供 object_id 和 origin；修正复杂度或显式调整预算，不要捕获错误后悄悄改低质量。保守预检可能早于回调执行；预算包含保留字幕带来的最终输出负担。

普通组的 alpha 乘入各绘制层。需要整组 RGBA 烘焙时显式调用 `rasterize_group`；需要覆盖率组件、模糊前着色及分层作用域透明度时使用 `compile_coverage`。两者不是同一种合成契约，也不自动互相切换。像素矩形仍是标准 ASS，但可能大幅增加文件和播放成本，见[四种扫色策略实测](sweep-strategies-comparison.md)。

## layered_glow 的有意变化

`examples/layered_glow.py` 保留固定夹具入口：

```sh
uv run python -m examples.layered_glow tests/fixtures/layered_glow.ass layered.ass
```

它使用普通 Track 实例，`layered_glow_classes.py` 展示对应子类配置；CLI 回归比较二者输出。字体沿用夹具样式，脚本只约定 K1/K2/LEAD，未承诺任意 ASS 样式输入。完整 `build() -> Scene` 版本由 `scene_lyrics` 演示，不依赖该夹具。

Track 的单个变色 Blur 与旧 Effect 的两套独立 Halo 混合不同；默认原生裁剪发生在文字绘制后，辉光前沿因此不是着色后扩散。`scene_lyrics` 和 `scene_sweep` 则显式放置独立、恒定粉色的辉光对象，填充/描边分别扫色。两者都不声称保留旧 Halo 的逐像素结果。需要跨前沿扩散时显式选择覆盖率或栅格材质出口，并核对预算。

原始演唱时间保持不变，显示寿命与提前入场、收尾单独安排；不把旧 padding/lead/tail 的测量补偿当作新的时间轴偏移。旧 Effect、模板和配置仍可使用，见[迁移指南](track-migration.md)。
