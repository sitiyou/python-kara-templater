# Write and build the documentation site

Author bilingual guides, add gallery and component previews, and build the Astro and Starlight documentation site locally.

## Bilingual layout and checks

English source pages live in `docs/`. Simplified Chinese mirrors them file-for-file in `docs/zh-cn/` with identical relative paths. The generated [API reference](../reference/README.md) (`docs/reference/`) is English-only; Starlight serves English fallback pages under `/zh-cn/reference/`.

`uv run --no-sync python -m tools.check_docs` fails if an English page lacks a Chinese counterpart or vice versa, in addition to checking links, heading anchors, Python snippet syntax, and generated reference freshness.

Use relative Markdown links ending in `.md`:

- From English pages, link to sibling and parent pages inside `docs/`.
- From Chinese pages, link to Chinese counterparts inside `docs/zh-cn/`.
- For English-only or shared assets from Chinese pages, resolve to the real path: `../../reference/...` for API reference pages, `../../examples/assets/...` for media, and `../../../...` for repository files such as `examples/`, `skills/`, or `LICENSE`.

## Write documentation

Every Markdown page in `docs/` and `docs/zh-cn/` follows a fixed shape that the site builder depends on:

1. **Line 1**: `# Title` — short, task-shaped, sentence case in English (`Lay out vocal tracks`), or a concise verb-object phrase without a trailing period in Chinese (`布置声部轨道`).
2. **Line 3**: one plain-prose lead paragraph (1–2 sentences, no links, inline code, lists, or images) stating what the reader achieves and when to use the page. The site lifts this paragraph into the page header and uses it as the meta description.
3. **Body**: `##` sections (prefer 3–7 sections; avoid `####`).
4. **Closing** (optional): `## Next steps` (Chinese: `## 下一步`) with 2–4 links.

Use GitHub alert syntax for callouts; the site converts them into Starlight asides. Supported kinds are `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, and `CAUTION`. Keep callouts to at most two per page:

```md
> [!NOTE]
> Explain one constraint or pitfall concisely.
```

### English voice

- **Audience**: someone making karaoke subtitles who knows timed ASS (`\k` tags) and basic Python, not necessarily graphics programming.
- **Style**: second person, imperative, present tense ("Add a `Track`", not "One may add"). Lead with the result, then the code, then what to change; explain *why* only where a reader would otherwise make a mistake.
- **Clarity**: one idea per paragraph (≤ 4 sentences; sentences ≤ ~25 words). Define terms on first use or link to [Core concepts](../concepts.md). Avoid internal jargon (`lowering`, `frontend`, `provenance`, `semantic`, `contract`, `allocator`) in user-facing pages unless the public API uses the term, and then explain it plainly.
- **API and defaults**: format public symbols in code font (`Track`, `Scene.export`) and do not capitalize ordinary words for emphasis. Treat Hook as the primary output and ASS as a compatibility export (keep ASS limits on [Export standard ASS](../output/ass.md)). Omit optional arguments in examples unless the argument is the point. Keep docs independent of specific editors and production workflows.
- **Formatting**: use tables for options and comparisons, lists for steps, and prose for reasoning. Write descriptive link text (such as "Lay out vocal tracks"), never "here" or "this page".

### Chinese voice

- Address the reader as "你" in direct, natural written Chinese. Avoid translationese ("被……所", "进行……操作", "对于……来说").
- Rewrite idiomatically rather than translating word for word. Keep information equivalent to the English page and keep code blocks identical (translate comments only when they are explanatory prose, never identifiers or strings relied on by tests).
- Add a half-width space between Chinese characters and Latin letters or digits; use full-width punctuation in Chinese prose; keep code, API names, commands, and filenames in English code font.
- Use verb-object headings without trailing periods, and write descriptive link text.

### Glossary

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
| ruby / reading | 注音 / 读音（日语语境可写"振假名"） |
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

## Build and preview locally

You need Node.js 24 (`site/package.json` requires Node `>=22.23.4`), `uv`, the [native build dependencies](setup.md), and [DejaVu Sans](https://dejavu-fonts.github.io/) plus [Noto Sans CJK JP](https://github.com/notofonts/noto-cjk) for gallery previews (`fonts-dejavu-core`, `fonts-dejavu-extra` and `fonts-noto-cjk` on Ubuntu).

Card previews are rendered during the build. Install FFmpeg with `libplacebo`, `libx264` and `libass`, and provide a Vulkan device. The GitHub Actions build uses Mesa's software Vulkan driver.

From the checkout root:

```sh
uv sync --locked --group checks
uv run --no-sync python -m tools.check_docs
npm ci --prefix site
npm run build --prefix site
uv run --no-sync python -m tools.check_docs_site
npm run preview --prefix site
```

Open the URL printed by Astro. To edit Astro components and CSS with live reload, run `npm run dev --prefix site`. Restart the dev server after changing Markdown pages or Python examples so its `predev` hook re-runs `tools.build_docs_site`.

The build writes static output to `build/docs-site/dist/`. Cards use silent video loops with JPEG fallback images. Gallery details use WebGL 2 for scrubbing and editing `PaintInput` values. `tools.check_docs_site` checks rendered Markdown, links and anchors, bilingual cards and media, source downloads, and shader resources.

## Add an example to the gallery

Create a self-contained runnable script in `examples/` with a `build()` function that returns a `Scene` and a CLI entry point that exports a standalone Hook.

Add an entry to [gallery.toml](../examples/gallery.toml) with both English fields and a `[demo.zh-cn]` table for Chinese text (`title`, `category`, `summary`, `details`, and optional `labels` matching any `PaintInput` names):

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

Choose `still` (in seconds) for the card poster and initial paused frame, and set `duration` to cover the full effect. The builder renders the card with FFmpeg and calls `scene.export_resources()` for the interactive WebGL preview. Play the card and scrub the example in the browser after building. See [Play and render a Hook](../output/hook.md).

## Add a component

The [component manifest](../examples/components.toml) supplies bilingual labels for every public `KaraokeEffects` preset. The builder takes the preset values from their public types and requires a label for each value.

For a reusable visual component, add an entry with an ID, a category, English and Chinese titles, and a reference anchor. Set `gallery` to reuse an existing clip, or add a case for the ID in [component_previews.py](../../examples/component_previews.py). Pick a short playback window and a poster that shows the effect. Use standalone Hook rendering where available. Label evaluator samples and standard ASS previews in the manifest so readers can identify how they were rendered.

```sh
uv run python -m examples.component_previews entry-wave-in build/wave.hook
```

## Deploy to GitHub Pages

In the repository's **Settings → Pages**, set the build and deployment source to **GitHub Actions**. The workflow in `.github/workflows/docs.yml` runs `tools.check_docs`, builds the site, and runs `tools.check_docs_site` on every pull request, then publishes `build/docs-site/dist/` on pushes to `main`.

The workflow reads the Pages base path and origin from GitHub so links work on both a project site and a custom domain. To reproduce a project-site base path locally, build and check with `DOCS_BASE=/python-kara-templater`.

## Next steps

- [Checks and documentation](checks.md)
- [Set up a development environment](setup.md)
- [Example scripts](../examples/README.md)
