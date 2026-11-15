# 播放器差异与验证范围

当前画面验收以 [固定 libass 基线](engine-baseline.md)为准：FFmpeg 读取实际导出的标准 ASS，固定字体、1280×720、RGB 背景及明确取帧时钟。十二例及整曲均有证据。Windows 字体提供器、VSFilter 系列和不同播放器的视频色彩/缩放设置不由这些结果代替。

## 已知标准语义差异

下表根据 [libass 官方差异说明](https://github.com/libass/libass/wiki/Differences-between-Libass-and-VSFilters)核对（2026-11-15）。这里是文档确认的兼容风险，不是本项目在每个播放器上测得的误差。

| 差异 | 对本库的影响与处理 |
| --- | --- |
| 描边与变换的处理存在差异 | E01/E03 缩放及仿射案例需保持目标播放器测试；不能将 libass 边缘误差界移用到 VSFilter |
| Windows 版本/区域设置可影响字体和双向排版 | 提供相同字体文件，记录实际字体提供器；不只比较 family 名称 |
| VSFilter 各分支对小数字号、BorderStyle=3 等支持不同 | 默认输出使用普通描边；旧 NativeEvent 保留原语义，不能保证旧输入在所有分支等价 |
| 颜色矩阵处理依分支而异 | 新建 Document 显式声明 RGB 意图；xy-VSFilter 对实际视频色彩空间的认识有限，因此仍需实播核对 |

上述差异并不要求本库改用非标准标签，也不能用来静默改变作者效果。诊断与显式近似出口仍沿用当前契约。需要针对特定播放器修正时，应固定该播放器版本、字体、视频尺寸和颜色配置后另建参考。

## mpv 复现设置

[mpv 官方手册](https://mpv.io/manual/stable/#options-sub-ass-override)提供 `--sub-ass-override=no`，避免用户样式覆盖改变脚本效果；[颜色兼容设置](https://mpv.io/manual/stable/#options-sub-ass-vsfilter-color-compat)中的 `no` 保留 RGB 颜色而不进行 VSFilter 色彩兼容变换。对本项目 RGB 案例，可显式使用：

```sh
mpv video.mkv --sub-file=effect.ass --sub-ass-override=no --sub-ass-vsfilter-color-compat=no
```

这条命令是配置指引，当前未作为 mpv 自动化验收执行。视频缩放、字幕缩放、像素宽高比、显示色彩转换和字体安装仍可能影响最终截图；不要把缩小后的文档拼图当作目标播放器的像素参考。

## 当前验证矩阵

| 环境 | 已有证据 | 未覆盖范围 |
| --- | --- | --- |
| Linux FFmpeg/libass 固定环境 | E01–E12 独立参考、四背景连播/乱序、整曲与新轨道跳转；版本和字体哈希见基线 | 任意字体、视频色彩格式和播放器 UI 配置 |
| manylinux 2.28 安装环境 | 安装后测试含 native libass 覆盖率；最终包矩阵另见发行报告 | 不等于全部视觉工具在该环境重渲染，也不证明 Windows 字体选择 |
| mpv/libass | 官方选项语义已核对，提供复现配置 | 尚无本项目的 mpv 独立截图差分 |
| VSFilter / xy-VSFilter / XySubFilter / MPC-HC 内置渲染器 | 官方差异记录与本库影响映射 | 尚无这些播放器的本项目像素验收，不宣称与 libass 一致 |

生成阶段使用的测量扩展不要求播放端安装修改版 libass。自定义输入标记在生成时消费，播放端只读取标准 ASS。外部模板的生成器依赖与播放标签区别见[模板核对](template-standard-ass-audit.md)。

本页完成计划要求的 libass 基线和其他播放器差异记录；发行包平台验证仍由独立发行门槛约束。若以后宣称某播放器通过像素验收，必须补充其版本、系统、字体、输入视频和实际输出帧证据。
