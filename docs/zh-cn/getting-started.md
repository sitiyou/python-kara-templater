# 快速上手

安装 kara-templater，用带时间轴的歌词做出第一个卡拉 OK 动画，在浏览器里实时查看，或叠加到视频上播放。

## 安装

运行环境需要 Python 3.12 或更高版本。从源码安装还需要 C/C++ 编译器、Cargo 与 Rust 1.87+，以及 FreeType、HarfBuzz、FriBidi、Fontconfig 和 libpng 的开发头文件。Linux 和 Windows 的依赖安装命令见[开发环境配置](contributing/setup.md)。

在仓库根目录创建并激活虚拟环境，然后安装包：

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

在 Windows PowerShell 中，使用 `.\.venv\Scripts\Activate.ps1` 激活虚拟环境。

## 用预设快速导出

在仓库根目录，对自带的带时间轴 ASS 示例运行默认预设：

```sh
kara-templater examples/karaoke.ass karaoke.hook
```

示例使用 1280 × 720 画布和 DejaVu Sans 字体，包含四个带振假名的计时音节。该命令会导出一个 60 fps 的 Hook 文件（`karaoke.hook`），按 `\k` 标记驱动走字（扫色）。

想通过命令行调整唱前/唱后填充色、淡入淡出或音节脉冲，请参阅[命令行](guides/cli.md)。

## 编写第一个 Python 模板

将下面这段代码保存为 `chorus.py` 并运行 `python chorus.py`。它会创建一句带注音的日语歌词并导出 `chorus.hook`，让每个音节从深紫灰平滑扫色为暖金色。

```python
from kara_templater import (
    Color,
    Document,
    KaraokeEffects,
    Layout,
    Line,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
)

song = Document.create(
    width=640,
    height=360,
    styles=(Style(fontsize=72, bold=True, outline=3, shadow=0),),
)
song.records.append(
    Line(start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ")
)
gold = KaraokeEffects.duotone(
    before_fill=Color.hex("#281C26"),
    after_fill=Color.hex("#FFE09A"),
)
vocal = Track(id="vocal", layout=Layout(position=Vec2(80, 180)), effects=(gold,))
scene = build_lyric_scene(song, tracks=(vocal,))
scene.export("chorus.hook", fps=30)
```

各部分的作用如下：

- `Document.create(...)` 创建一个 640 × 360 的画布和一套基础样式（`shadow=0` 关闭默认的投影）。
- `Line(...)` 定义了一句从 0 ms 到 3000 ms 的歌词行。`text` 中的 `\k90` 表示第一个音节持续 90 厘秒（0.9 秒），`星|ほし` 为 `星` 附上读音 `ほし`。
- `KaraokeEffects.duotone(...)` 创建在 `before_fill` 和 `after_fill` 之间羽化过渡的双色走字效果。
- `Track(...)` 将这句歌词放到 `(80, 180)` 并挂载特效。
- `build_lyric_scene(...)` 测量字形并生成 `Scene`。`scene.export("chorus.hook", fps=30)` 按 30 fps 打包着色器，供下文的 mpv 和 FFmpeg 命令使用。

你可以修改 `before_fill` 或 `after_fill` 以配合画面配色，也可以把 `gold` 换成 `KaraokeEffects(entry="rise", exit="fade")` 为整行加上入场和退场过渡。

> [!NOTE]
> 这段示例包含日语汉字和假名。如果渲染出的字形显示为缺字方框，请安装包含日语字形的字体（如 Noto Sans CJK JP 或 Sarasa UI J），详见[选择与注册字体](guides/fonts.md)。

## 在浏览器里预览

在构建场景后加上这一行，再次运行 `python chorus.py`：

```python
scene.preview()
```

预览会在浏览器中打开本地 HTML 文件并通过 WebGL 2 渲染。用页面上的控件播放或拖动时间轴。

## 预览导出的 Hook

在 mpv 中，将 Hook 直接叠加到宽高比一致的视频上播放：

```sh
mpv --vo=gpu-next --sub-auto=no --glsl-shader=chorus.hook video.mp4
```

如果手头没有视频素材，可以用支持 `libplacebo` 滤镜和 Vulkan 的 FFmpeg 在纯色背景上渲染 4 秒预览。画布尺寸（`640x360`）和帧率（`30`）需要与导出参数保持一致：

```sh
ffmpeg -init_hw_device vulkan=vk \
  -f lavfi -i "color=c=0x181B24:s=640x360:r=30:d=4" \
  -vf "libplacebo=custom_shader_path=chorus.hook" \
  -c:v libx264 -pix_fmt yuv420p preview.mp4
```

要预览前面命令行预设生成的 `karaoke.hook`，将参数改为 `s=1280x720`、`r=60`、`d=5` 以及 `custom_shader_path=karaoke.hook`。更多叠加实拍视频与分段导出的用法见[播放与渲染 Hook](output/hook.md)。

## 使用你自己的带时间轴 ASS 文件

直接把自己的 `.ass` 文件传给 `kara-templater` 命令，或在 `chorus.py` 中用下面这行替换 `Document.create(...)` 和 `song.records.append(...)`：

```python
song = Document.load("song.ass")
```

两种方式都会读取原文件的 `PlayRes`、计时标签和注音。预览时记得将 FFmpeg 的分辨率和帧率调整为与歌词文件和 `scene.export(..., fps=...)` 一致。

## 下一步

- [核心概念](concepts.md) — 一次掌握时间单位、坐标空间、生命周期和输出格式。
- [设计整曲布局](tutorials/karaoke-design.md) — 布置带自动换行的主唱与和声声部。
- [导入带时间轴的歌词](guides/documents.md) — 查看所有受支持的 `\k` 计时、注音与续接语法。
- [预览与导出](output/README.md) — 查看浏览器预览、着色器播放和标准 ASS 的用法。
