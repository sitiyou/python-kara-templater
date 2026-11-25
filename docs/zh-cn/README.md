# 概览

用 Python 把带时间轴的歌词编排成卡拉 OK 特效，以 WGSL 编写自定义材质，再到浏览器里实时预览。

## kara-templater 能做什么

`kara-templater` 读取带时间轴的歌词——通常是包含 `\k` 音节时长、可选注音（振假名）和倒数提示标记的 ASS 文件——让你用 Python 编写可复用的卡拉 OK 模板。库内部通过 FreeType 和 HarfBuzz 测量真实字形轮廓，使走字（扫色）、注音对齐、描边和装饰图形都能紧贴实际文字。

Naga 校验 WGSL 材质函数并将其转译为 GLSL。着色器可在 WebGL 2 中实时预览，也可随纹理打包成供 mpv 和 FFmpeg 使用的 libplacebo `.hook`。需要普通字幕时，可另行导出标准 ASS。

## 模板的基本结构

歌词依次经过 `Document`、`Track` 和 `Scene`，最后进入实时预览或导出。

| 阶段 | 核心 API | 作用 |
| --- | --- | --- |
| 歌词与画布 | `Document`、`Style`、`Line` | 保存脚本分辨率（PlayRes）、字体样式和带时间轴的歌词行，可从 ASS 导入或在 Python 中构建。 |
| 声部轨道 | `Track`、`KaraokeRows`、`Layout`、`KaraokeEffects`、`LyricRule` | 筛选各声部的歌词行、安排行或列布局、管理唱前与唱后留白，并挂载内置或自定义特效。 |
| 场景组合 | `build_lyric_scene`、`Scene`、`TextObject`、`PathObject`、`ObjectGroup` | 汇总完成测量和排版的歌词行，以及额外添加的文本、矢量图形、分组和动画。 |
| 预览与导出 | `Scene.preview`、`Scene.export_resources`、`Scene.export`、`Scene.ass.compile` | 打开浏览器预览，导出着色器资源或播放文件，也可单独编译标准 ASS。 |

各阶段共用的时间单位、坐标空间与生命周期规则，请阅读[核心概念](concepts.md)。

## 文档导航

### 从这里开始

- [快速上手](getting-started.md) — 安装 `kara-templater`，运行内置预设，编写第一个 Python 模板并在浏览器里预览。
- [核心概念](concepts.md) — 掌握 `Document` → `Track` → `Scene` 模型、时间单位、坐标体系、生命周期和输出方式。
- [示例脚本](examples/README.md) — 按视觉效果浏览可运行的示例脚本与动态预览。

### 教程

- [教程概览](tutorials/README.md) — 从排版到自定义动态，选择适合你的动手教程。
- [设计整曲布局](tutorials/karaoke-design.md) — 配置主唱与和声轨道、行距和整曲配色。
- [让高亮动起来](tutorials/lyric-highlights.md) — 根据实测的走字前沿触发字符和音节动画。
- [编写自定义动画](tutorials/custom-animation.md) — 使用 `Transform`、时间线和规则打造可复用动态。
- [特效配方](tutorials/effect-recipes.md) — 直接改写对焦、打字、裂口入场和尾字散开等独立配方。
- [动态研究](tutorials/lyric-studies.md) — 横向对比八组计时、残影、粒子与装饰研究。

### 指南

- **歌词与布局**：[指南概览](guides/README.md) · [导入带时间轴的歌词](guides/documents.md) · [布置声部轨道](guides/tracks.md) · [注音与倒数提示](guides/text-and-cues.md) · [选择与注册字体](guides/fonts.md)
- **特效与场景制作**：[内置卡拉 OK 特效](guides/karaoke-effects.md) · [色彩与材质](guides/materials.md) · [动画与计时](guides/animation.md) · [场景对象与分组](guides/objects.md) · [形状、裁剪与遮罩](guides/geometry.md) · [粒子、副本与残影](guides/particles.md)
- **工具**：[命令行](guides/cli.md)

### 输出与参考

- **播放与导出**：[预览与导出](output/README.md) · [播放与渲染 Hook](output/hook.md) · [导出标准 ASS](output/ass.md) · [故障排查](output/troubleshooting.md)
- **参考与开发**：[API 参考（英文）](../reference/README.md) · [参与贡献](contributing/README.md) · [模板编写 Skill](../../skills/kara-templater/SKILL.md)

## 下一步

- [快速上手](getting-started.md) — 导出你的第一个场景，并在浏览器里查看效果。
- [核心概念](concepts.md) — 写自定义模板前先理清时间单位、坐标和生命周期。
- [示例脚本](examples/README.md) — 找一个最接近目标视觉效果的可运行脚本。
- [设计整曲布局](tutorials/karaoke-design.md) — 动手完成一套包含主唱与和声的完整模板。
