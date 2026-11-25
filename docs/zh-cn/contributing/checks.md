# 检查与文档验证

在提交拉取请求前运行代码风格检查、类型检查、测试、文档校验与视觉预览。每一项代码改动都必须通过 Ruff、ty 和相应的测试套件。

## 标准检查套件

安装好包本体和 `checks` 依赖组后，在仓库根目录运行：

```sh
uv run ruff check .
uv run ty check
uv run python -m pytest
uv run python -m tools.check_scene_types
uv run python -m tools.check_docs
```

Ruff 和 ty 的版本锁定在 [pyproject.toml](../../../pyproject.toml) 中。公共函数和方法必须补全参数与返回值类型标注，且公共类型推断不能泄漏 `Any` 或 `Unknown`（由 `tests/test_typing.py` 和 `tests/typing/` 验证）。

`tools.check_scene_types` 会执行一批反向类型测试用例，每条用例都必须因 `invalid-argument-type` 报错才算通过；导入失败不能证明类型契约生效。

## 选择测试范围

日常开发直接运行 `uv run python -m pytest`。它在 [pyproject.toml](../../../pyproject.toml) 中配置了默认的 `testpaths`，覆盖 ASS 解析、字体、歌词源、结构化歌词、进度曲线、歌词布局、轨道编排、命令行预设、特效参数、光栅合成与 GPU 场景。要调试单个功能，直接传入测试文件或节点 ID 即可。

发布前或大规模重构后，请运行完整测试套件：

```sh
uv run python -m pytest tests
```

显式传入 `tests` 目录会覆盖 `testpaths`，运行全部回归测试、示例测试、类型测试和文档测试。

### 编写有效测试

重点验证需要长期保持的行为：源记录与归属保留、计时与变换、图形选择、材质语义、诊断信息、资源预算、确定性跳转，以及必要时的实际渲染输出。涉及几何和颜色校验时，应使用聚焦且独立的参考计算。测试基线放在 `tests/fixtures/`，测试字体及其许可证文件放在 `tests/fonts/`。

文档测试（`tests/test_documentation.py`）会直接执行面向作者的完整脚本。不要让测试耦合历史方案、无关标题文本或内部实现快照。替换公共接口时，应把仍有价值的行为校验迁移到新接口上，并删除只针对废弃语法的测试。

## Arch 打包检查

[AUR 核心检查脚本](https://aur.archlinux.org/cgit/aur.git/tree/check-core.sh?h=python-kara-templater)会在源码树之外安装构建好的 Wheel，并在 30 秒的墙钟时间预算内（原生编译完成后开始计时）执行默认核心测试、命令行与 Hook 导出检查。超时会直接导致构建失败。

| 测试分组 | 验证内容 | 运行环境 |
| --- | --- | --- |
| 核心包检查 | 字体选择与原生塑形、ASS 计时导入、结构化注音与提示定位、分行分配、CPU 光栅往返、可跳转 GPU 绘制准备、已安装命令行与独立 Hook 导出 | AUR |
| 渲染回归 | 帧间曲线精度、走字与描边像素覆盖率、特效/时钟/字体组合，以及 Vulkan 可用时的真实 Hook 播放 | 上游完整套件 |
| 开发与发布检查 | 文档脚本与链接、公共类型契约、独立原生测量、Wheel 元数据与打包库检查 | 上游测试与发布工具 |

发布前如需重新评估耗时，可以在已安装 Wheel 的环境下运行带耗时统计的完整套件：

```sh
python -m pytest tests --durations=30 --junitxml=timings.xml
```

同时查看最慢的单个用例和按模块汇总的耗时——内置特效目录中单个预设很快，但合计耗时可能不低。

## API 参考与链接检查

[API 参考](../../reference/README.md)是提交进仓库的 Markdown 文档，由脚本从 `kara_templater.__all__`、运行时签名、dataclass 字段和英文文档字符串自动生成。修改公共契约后，请重新生成并核对结果：

```sh
uv run python -m tools.generate_reference
uv run python -m tools.generate_reference --check
```

`tools.check_docs` 会检查以下四项：

- `README.md`、`skills/kara-templater/SKILL.md` 和 `docs/` 中所有本地文件链接与 Markdown 标题锚点。
- `docs/` 下的英文页面与 `docs/zh-cn/` 下的中文页面一一对应（自动生成的英文 `docs/reference/` 除外）。
- 所有非参考页中 `python` 代码块的语法正确性。
- 仓库中提交的 `docs/reference/*.md` 与 `tools.generate_reference` 的输出完全一致。

`tools.check_docs` 也会在隔离 Wheel 验证目录中针对已安装的包源码运行。仅靠类型签名远远不够，请务必在对应的 API 文档字符串与用户指南中写清单位、状态组合方式、默认值、异常和边界限制。

## 视觉预览与回归检查

修改 Hook 相关代码时，请把目标场景导出为 `.hook`，并用 FFmpeg 和 `libplacebo` 渲染到目标背景上核对画面，命令见[播放与渲染 Hook](../output/hook.md)。如果改动涉及画廊示例，也请在[文档站点](documentation-site.md)的浏览器 WebGL 播放器中拖动时间轴检查。

### ASS 画廊 GIF 生成

`tools.render_gallery` 会把 `examples/scene_cues.py` 编译成 ASS，用内置 CPU 预览光栅化事件，并通过 FFmpeg 编码成动态 GIF：

```sh
uv run python -m tools.render_gallery --case word-backgrounds
```

在安装好 FFmpeg 和 `checks` 依赖的源码目录中运行该命令，会在 `build/gallery/` 下写入导出的 ASS、复制的预览字体以及包含 SHA-256 哈希的 `report.json`，并更新 `docs/examples/assets/word-backgrounds.gif`。本地试验时可传入 `--output` 或 `--assets` 避免覆盖受版本控制的媒体文件（同时支持 `--width`、`--fps` 和 `--duration`）。旧版采样 ASS 导出器生成的历史 GIF 不再由该工具重新生成。

### ASS 连续播放与跳转校验

如需通过 FFmpeg 的 `ass` 滤镜（`libass`）对固定 ASS 示例做连续播放与随机跳转一致性校验：

```sh
uv run python -m tools.validate_scene_core --scene cues build/preview-cues
```

`--scene` 支持 `cues`（默认）和 `native-tween`。脚本会把导出的 ASS、带时间戳的帧拼图 PNG，以及 50 fps 连续播放与全新跳转的 MD5 对比 JSON 报告写入指定的被忽略 `build/` 目录。该工具只验证当前预览环境下的固定示例，不能等同于所有播放器的渲染结果。

与 Karaoke Studio 做帧对比时，先在两个渲染器上对齐测得的字体 em 尺寸，再在静止状态下配准图像，整行使用同一套固定配准；字体尺寸换算见[选择与注册字体](../guides/fonts.md)。`docs/examples/assets/` 下只跟踪精选预览媒体，生成报告和临时产物一律放在 `build/` 中。

## 下一步

- [编写与构建文档站点](documentation-site.md)
- [构建与验证发布包](releasing.md)
- [架构概览](architecture.md)
