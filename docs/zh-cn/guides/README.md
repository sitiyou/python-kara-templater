# 指南总览

按任务组织的指南覆盖了导入带时间轴的歌词、编写卡拉 OK 特效以及使用命令行工具。你可以先运行下面的最小模板了解整体流程，再按需查阅对应专题。

## 从带时间轴的 ASS 文件起步

加载一份带时间轴的 ASS 文件，为主唱声部配置一条 `Track`（声部轨道），再导出独立的 Hook（libplacebo 着色器 Hook）。在源码目录中可直接运行下面这段脚本体验示例歌词，也可以替换为你自己的 `.ass` 文件。

```python
from kara_templater import Document, KaraokeEffects, Track, build_lyric_scene

lyrics = Document.load("examples/karaoke.ass")
lead = Track(id="lead", effects=(KaraokeEffects(),))
scene = build_lyric_scene(lyrics, tracks=(lead,))
scene.export("karaoke.hook")
```

`Document`（歌词文档）保存带时间轴的歌词与脚本元数据；每条 `Track` 负责筛选一个声部并定义它的外观与动画；`build_lyric_scene` 将这些轨道组装为 `Scene`（场景），供后续导出为 Hook 或标准 ASS。

如果需要加入和声或翻译，只需再添加一条带筛选条件的 `Track`，并指定各自在画布上的位置。

## 歌词与排版

- [导入带时间轴的歌词](documents.md) —— 读取 ASS 文件、查看歌词时间轴，了解支持的计时与注音标签。
- [布置声部轨道](tracks.md) —— 按声部筛选歌词行、排布多行或多列位置，并调整唱前预览与唱后停留时长。
- [注音读音与提示](text-and-cues.md) —— 为歌词片段附加注音（振假名）和带时间轴的倒数提示。
- [选择与注册字体](fonts.md) —— 挑选清晰易读的字体、启用假名比例间距，并通过 `load_font` 注册字体文件。

## 特效

- [内置卡拉 OK 特效](karaoke-effects.md) —— 配置歌词行入场、高亮走字、缩放脉冲与退场预设。
- [颜色与材质](materials.md) —— 定制填充、描边、辉光、渐变以及自定义 WGSL 材质。
- [动画与时间轴](animation.md) —— 在歌词行、音节或字符上编排补间、缓动曲线与自定义 GPU 动画。
- [场景对象与分组](objects.md) —— 添加拥有独立时间线的文字对象、路径对象与分组图层。
- [形状、裁剪与遮罩](geometry.md) —— 绘制矢量路径、应用矩形或矢量裁剪，以及添加立体挤出效果。
- [粒子、复制与回声](particles.md) —— 沿高亮前沿发射星点或花瓣粒子，或构建多层回声效果。

## 工具

- [命令行](cli.md) —— 在终端中通过预设参数、`tracks` 配置或 `build` 函数直接导出 Hook 或标准 ASS。

## 下一步

- [核心概念](../concepts.md)
- [教程总览](../tutorials/README.md)
- [预览与导出](../output/README.md)
- [API 参考](../../reference/README.md)
