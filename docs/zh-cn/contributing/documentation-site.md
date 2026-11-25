# 编写与构建文档站点

撰写中英双语指南、添加交互式 WebGL 画廊示例，并在本地构建 Astro 与 Starlight 文档站点。每次编辑文档或新增示例预览时，请参考本页。

## 双语目录结构与校验

英文源文档存放在 `docs/`，简体中文镜像以完全一致的相对路径存放在 `docs/zh-cn/`。自动生成的 [API 参考](../../reference/README.md)（`docs/reference/`）仅提供英文版；访问 `/zh-cn/reference/` 时，Starlight 会自动展示英文回退页面。

如果英文页缺少对应的中文页，或中文页缺少对应的英文页，`uv run --no-sync python -m tools.check_docs` 会直接报错。该命令同时校验本地链接、标题锚点、Python 代码块语法和 API 参考是否最新。

编写站内链接时统一使用以 `.md` 结尾的相对路径：

- 英文页之间在 `docs/` 内使用相对路径互链。
- 中文页之间在 `docs/zh-cn/` 内链接到中文对应页面。
- 中文页引用英文专属内容或仓库共享文件时，按真实路径解析：API 参考用 `../../reference/...`，共享媒体用 `../../examples/assets/...`，仓库根目录文件（如 `examples/`、`skills/`、`LICENSE`）用 `../../../...`。

## 编写文档

`docs/` 和 `docs/zh-cn/` 下的每一篇 Markdown 文档都必须遵循固定页面结构，站点构建脚本依赖这一格式提取标题和摘要：

1. **第 1 行**：`# 标题`——简短、面向任务。英文用句首大写（如 `Lay out vocal tracks`），中文用动宾短语且不加句号（如 `布置声部轨道`）。
2. **第 3 行**：一段 1–2 句的纯文本导语（不要放链接、行内代码、列表或图片），说明读者能完成什么任务以及何时阅读本页。站点构建时会把这段话提至标题下方作为页头导语，并用作页面 meta description。
3. **正文**：用 `##` 分节（建议 3–7 节，避免使用 `####`）。
4. **结尾**（可选）：`## Next steps`（中文为 `## 下一步`），放 2–4 个相关链接。

提示框使用 GitHub 告警语法，站点会自动转换为 Starlight 侧注，支持 `NOTE`、`TIP`、`IMPORTANT`、`WARNING`、`CAUTION` 五种类型，每页不超过 2 处：

```md
> [!NOTE]
> 用一两句话简洁说明约束或常见误区。
```

### 英文行文规范

- **读者画像**：熟悉带时间轴的 ASS（`\k` 标签）和基础 Python，但不一定了解图形学编程的卡拉 OK 字幕作者。
- **语气与结构**：使用第二人称、祈使句和现在时（写 "Add a `Track`"，不写 "One may add"）。先展示效果，再给代码，再说明可调参数；只有在容易踩坑的地方才解释原因。
- **清晰度**：每段只讲一个意思（不超过 4 句，每句约 25 词以内）。术语首次出现时给出定义或链接到[核心概念](../concepts.md)。面向用户的页面避免使用编译器内部术语（如 `lowering`、`frontend`、`provenance`、`semantic`、`contract`、`allocator`），除非公共 API 本身使用了该词，此时应用通俗语言解释。
- **API 与默认原则**：公共 API 名称用代码字体（`Track`、`Scene.export`），不要靠首字母大写强调普通名词。以 Hook 为主输出、ASS 为兼容性导出（ASS 的格式限制集中在[导出标准 ASS](../output/ass.md)说明）。示例中省略可选参数，除非该参数正是演示重点。文档保持与具体编辑器和制作流程解耦。
- **排版与链接**：选项和对比用表格，操作步骤用列表，原理解释用正文；链接文字直接说明目标页面，不要写 "here" 或 "this page"。

### 中文行文规范

- 面向读者用“你”，语气直接、平实，书面语但不生硬；避免翻译腔（如“被……所”“进行……操作”“对于……来说”）。
- 按中文习惯重新组织句子，不要逐字直译；信息与英文版等价，代码块保持完全一致（仅说明性注释可译为中文，不要改动标识符或测试依赖的字符串）。
- 中英文、中文与数字之间加半角空格；中文语境使用全角标点；代码、API 名称、命令和文件名保留英文并用代码格式。
- 标题用动宾短语且不加句号，链接文字描述目标页面。

### 术语表

| English | 简体中文 |
| --- | --- |
| karaoke | 卡拉 OK |
| timed lyrics / timed ASS | 带时间轴的歌词 / 带时间轴的 ASS |
| syllable / timed unit | 音节 / 计时单元 |
| karaoke wipe / sweep | 走字（扫色） |
| highlight | 高亮 |
| before / after fill | 唱前填充 / 唱后填充 |
| held note | 长音 |
| line | 歌词行 |
| ruby / reading | 注音 / 读音（日语语境可写“振假名”） |
| vocal / lead / harmony | 声部 / 主唱 / 和声 |
| `Track` | `Track`（声部轨道；首次出现时说明） |
| `Document` | `Document`（歌词文档） |
| `Scene` | `Scene`（场景） |
| Hook | Hook（libplacebo 着色器 Hook） |
| count-in / cue | 倒数 / 提示 |
| entry / exit | 入场 / 退场 |
| effect / preset / template | 特效 / 预设 / 模板 |
| material / paint | 材质 / 着色 |
| fill / outline / shadow / glow | 填充 / 描边 / 阴影 / 辉光 |
| gradient | 渐变 |
| clip / mask | 裁剪 / 遮罩 |
| particle | 粒子 |
| easing | 缓动 |
| keyframe | 关键帧 |
| canvas / script resolution | 画布 / 脚本分辨率（PlayRes） |
| render / renderer | 渲染 / 渲染器 |
| frame rate | 帧率 |
| budget | 预算（资源上限） |

## 本地构建与预览

本地构建需要 Node.js 24（`site/package.json` 要求 Node `>=22.23.4`）、`uv`、[原生构建依赖](setup.md)，以及用于画廊预览的 [DejaVu Sans](https://dejavu-fonts.github.io/) 和 [Noto Sans CJK JP](https://github.com/notofonts/noto-cjk)（Ubuntu 上对应 `fonts-dejavu-core` 和 `fonts-noto-cjk`）。

在仓库根目录运行：

```sh
uv sync --locked --group checks
uv run --no-sync python -m tools.check_docs
npm ci --prefix site
npm run build --prefix site
uv run --no-sync python -m tools.check_docs_site
npm run preview --prefix site
```

打开 Astro 输出的本地地址即可预览。修改 Astro 组件或样式时，可运行 `npm run dev --prefix site` 开启热重载；如果改动了 Markdown 文档或 Python 示例，请重启开发服务器，让 `predev` 钩子重新运行 `tools.build_docs_site`。

构建产物输出在 `build/docs-site/dist/`，浏览器通过 WebGL 2 运行交互式画廊播放器。`tools.check_docs_site` 会逐项检查：每篇 Markdown 是否生成了非空正文、站内链接和锚点是否全部有效、画廊下载脚本是否与页面展示源码一致、着色器文件非空、`KARAMASK`/`KARADATA` 纹理大小与 SHA-256 校验和正确，以及界面标签是否对应声明的 `PaintInput`。

## 向画廊添加示例

在 `examples/` 中编写一个可独立运行的脚本，提供返回 `Scene` 的 `build()` 函数，以及导出独立 Hook 的命令行入口。

在 [gallery.toml](../../examples/gallery.toml) 中添加条目，同时填写英文字段和 `[demo.zh-cn]` 中文表（包含 `title`、`category`、`summary`、`details`，以及与 `PaintInput` 参数名对应的可选 `labels`）：

```toml
[[demo]]
id = "example-slug"
title = "Short English title"
category = "Timing"
summary = "One-sentence card summary."
details = "Tell the reader which moment to watch."
source = "example_script.py"
guide = "guides/karaoke-effects/"
accent = "#c5a2ff"
duration = 4.2
still = 2.6

[demo.labels]
strength = "Effect strength"

[demo.zh-cn]
title = "简短中文标题"
category = "计时"
summary = "一句话卡片简介。"
details = "提示读者观察哪个时间点。"

[demo.zh-cn.labels]
strength = "特效强度"
```

用 `still`（单位：秒）指定画廊卡片和初始暂停帧的时间点，用 `duration` 覆盖完整特效时长。暂存阶段，`tools.build_docs_site` 会调用 `scene.export_resources()` 导出着色器与纹理，复制下载脚本并嵌入完整源码。构建完成后，请在浏览器中播放并拖动时间轴检查，再用 FFmpeg 或 mpv 验证独立 Hook 渲染效果，详见[播放与渲染 Hook](../output/hook.md)。

## 部署到 GitHub Pages

在仓库的 **Settings → Pages** 中将构建与部署来源设为 **GitHub Actions**。[docs.yml](../../../.github/workflows/docs.yml) 工作流会在每次拉取请求时运行 `tools.check_docs`、构建站点并执行 `tools.check_docs_site`，并在推送到 `main` 分支后自动发布 `build/docs-site/dist/`。

工作流会自动从 GitHub 读取 Pages 基础路径和站点域名，确保项目子路径与自定义域名下的链接都正确。要在本地复现项目子路径，可在构建和检查时设置 `DOCS_BASE=/python-kara-templater`。

## 下一步

- [检查与文档验证](checks.md)
- [配置开发环境](setup.md)
- [示例脚本](../examples/README.md)
