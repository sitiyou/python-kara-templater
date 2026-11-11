# kara-templater

A Python library for adding effects to existing karaoke lyrics and exporting ASS,
with native libass text measurement. Source lyrics retain their text, layout and
singing timeline; Python code supplies appearance and animation.

## Define an effect

Declare visual components in `compose()`, then select source targets and configure
styles and behavior in `configure()`. Each source line receives its own bound
instance, configured before layout. Both parsed ASS and directly constructed
`Document` inputs use the same effect system.

```python
from kara_templater import (
    BLACK, CYAN, WHITE, Body, Document, Effect, Halo, Lyrics, Ruby,
    render_karaoke,
)

class Glow(Effect):
    def compose(self):
        yield Lyrics(
            Body(fill=WHITE, stroke=BLACK, stroke_width=3),
            Ruby(follow="syllable"),
            Halo(id="light", color=CYAN, width=6, blur=8, opacity=0.2),
        )

    def configure(self):
        self.text.sweep(fill=CYAN)
        self.syllables.on_singing(pulse=1.1)
        self.query_one("#light").on_singing(opacity=(0.2, 0.8), keep=True)

source = Document.load("input.ass")
result = render_karaoke(source, effect=Glow)
result.document.save("output.ass")
```

See the [effect guide](docs/effects.md) for code-only color ranges,
source queries, timing curves, ruby, independent glow, follow controls and
sampling limits. The [implementation plan](docs/effect-system-plan.md) and
[progress record](docs/effect-system-progress.md) document the completed changes
and verification. The [backend audit](docs/karaoke-effects-audit.md) describes
the underlying rendering implementation.

Runnable examples:

```sh
python -m examples.alternating_colors /tmp/colors.ass
python -m examples.whole_glow /tmp/whole.ass
python -m examples.staggered_path /tmp/staggered.ass
python -m examples.parallel_tracks /tmp/parallel.ass
kara-templater input.ass output.ass --effect examples/layered_glow.py
```

The Chinese color example needs an installed CJK font matching its `fontname`.
`LayeredGlow`, `WholeGlow` and `ArcWave` use the same components and behaviors.

## Rendering primitives and backend extensions

The following sections describe lower-level timelines, source metadata and ASS
output. Effect scripts use `Effect` above;
custom backends can still return `EffectPlan` from `build(item, context)`.
Character layout checks independent glyph outlines against the original text;
unsafe splitting raises `LayoutCapabilityError`.

```python
from kara_templater import EdgeSweep, Region, SingingPass

singing = SingingPass(1000, 2000, Region(100, 300))
edges = EdgeSweep(padding_px=10, lead_ms=150, tail_ms=100)
assert singing.position_at(1500) == 200
assert singing.arrival(150) == 1250
# Enlarging the glow extent leaves the main sweep at the same position.
assert edges.position_at(singing, Region(0, 400), 1500) == 200
```

Run `python -m examples.timeline` from a source checkout for three pulse modes
and parallel highlight tracks. This example evaluates plans; it does not export
ASS yet. The example is independent of ASS output.

`python -m examples.characters` measures real text, preserves combining marks,
assigns colors by `TextRange`, and resolves ruby appearance and pulse timing.
The repertoire covers Latin, Greek, Cyrillic, CJK, kana (including Japanese `々` and `ー`),
karaoke guide dots (`●`) and modern Hangul
candidates, including decomposed modern jamo. Shaped jamo syllables retain their
original multi-codepoint ranges and cannot be partially selected for color.
Font shaping can further restrict independent drawing.
Joining scripts, bidi text and emoji sequences currently produce capability
diagnostics. Ink bounds are conservative outline bounds, not raster or glow
bounds. Fonts and their fallback remain part of the rendering environment.

Generate an ASS demonstration of the three pulse modes with sweeping color:

```sh
python -m examples.output_layers /tmp/layers.ass
python -m tools.render_effects /tmp/kara-review
```

The second command requires ffmpeg with libass, Pillow and pkg-config.
It saves seven keyframes, a static whole-text reference, a difference image and
an environment manifest with the font checksum. The compiler uses native ASS
transforms; a moving clip combined with scaling is subdivided to limit curve
interpolation error to 0.25 px by default. Rectangular clip coordinates add up
to 0.5 px of rounding, and event boundaries use a shared 10 ms grid. Ordinary
linear sweeps are not sampled per frame. The recipe layer adds automatic ruby
and resolves union, priority and explicit layer overlap policies by splitting
at moving-boundary intersections.

Generate the self-contained K1/K2/H1/H2/LEAD recipe example:

```sh
python -m examples.recipes /tmp/recipes.ass
```

The example includes ruby, colors within a singing segment, parallel tracks,
three pulse modes, guide text and style-based effect dispatch. Recipes can be
objects with `build(item, context)` or ordinary functions returning `EffectPlan`.

Compare simultaneous sweeps on a single multi-character segment:

```sh
python -m examples.parallel_tracks /tmp/parallel.ass
```

The three rows show separate regions sweeping simultaneously, two tracks with
priority override, and two translucent tracks with explicit stacking order.
The first row also uses two colors within the same segment. The upper track in
the other rows exits at 2000 ms, revealing the underlying sweep. Color ranges
and track regions leave the source segment intact; track paint overrides the
range paint when explicitly supplied.

For a custom object-based animation, run:

```sh
python -m examples.staggered_path /tmp/staggered.ass
```

`ArcWave.configure()` binds two offset functions with
`self.characters.on_highlight(duration_ms=400, ...)`, scheduling each character's
arc at its sweep arrival. Each 400 ms
arc moves up 24 px and sideways up to 8 px, then returns to the original
layout. Parameters are reusable; timing state is local to each build. The
example deliberately leaves ruby disabled. It uses 40 ms held samples for the
path while preserving native sweep interpolation; the fixed seven-character
example produces 166 events versus 28 without motion. It can also be loaded
with `--effect examples/staggered_path.py` for imported lyrics.

Scripts can traverse source lines, units or segments without depending on the
generated layers. Visits follow source order, retaining empty text and
zero-duration segments; static units have no segment visits.

```python
from kara_templater import walk_karaoke

for ref, segment in walk_karaoke(items, level="segment"):
    print(ref.item_id, ref.unit_index, ref.segment_index, segment.start_ms)

for ref, unit in walk_karaoke(items, level="unit"):
    print(ref, unit.text)
```

`level="line"` yields each original `KaraokeLine`. The immutable, hashable
`SourceRef` can be used as a configuration key; `ref.resolve(item)` returns the
original source object. Addresses survive item reordering and presentation
changes, but unit/segment indices refer to the current source structure, not
persistent edit IDs. Duplicate item IDs are rejected before the first visit.

`RenderResult.event_origins` pairs each generated ASS `Line` with an
`EventOrigin`, in output order. The event is the same object inserted into the
result document. Origins retain source references, the effect name and track
IDs through clip subdivision, visual layer expansion and dynamic sampling:

```python
for event, origin in result.event_origins:
    print(event.start_time, origin.effect, origin.sources, origin.track_ids)
```

Body glyphs record their unit's segment dependencies, while ruby records its
specific segment. These are source dependencies, not ownership of an event's
time interval: explicit tracks may have independent timing. Custom builders
can supply `TextLayer.origin=EventOrigin(...)`; otherwise rendering supplies
the item reference and builder name, also for raw ASS events. Low-level
`compile_layers()` returns an aligned `origins` tuple, using `None` for layers
without metadata. Structured origins live in the Python result and are not
serialized into ASS; the ASS effect field retains the existing event marker.

`OutputCapabilityError.origin` exposes the same metadata for native output
limits, pulse time resolution failures, recipe mask composition failures and
dynamic sampling errors. `time_ms` identifies the absolute failure/sample time
where known; either field can be `None` when no source or time is available.
Sampling callback failures preserve the original exception as `__cause__`.
Source notes are also printed by the CLI. During recipe execution, character
layout and color-range errors carry a unit reference, and ambiguous ruby colors
carry a segment reference. Layout/build failures without a more precise location
receive the item reference and effect name. Their original exception types and
tracebacks are retained; inspect `getattr(error, "origin", None)` when handling
these errors. Missing styles, effect dispatch/build validation and invalid raw
events also carry the owning item/effect reference. Generated layer styles are
validated before dynamic callbacks execute. Configuration constructors run
before an item is bound and cannot identify a lyric; document-wide failures
such as resolution mismatch or aggregate budgets may have no single origin.

Native shape measurement rejects missing-glyph outlines after font fallback,
reporting the Unicode codepoint instead of treating a replacement box as a
drawable character. `LayoutCapabilityError` preserves the failing unit's source
context. Each `DrawableCharacter.font_faces` reports the actual FreeType family
and style names, including fallback faces. A cluster may use several faces;
independent drawing must preserve both face selection and glyph indices as well
as the measured contours. These names are diagnostic metadata, not font file
hashes or a guarantee that another machine will select the same font file.

ASS import failures raise `AssImportError`. Its `record_index` is a zero-based
index into the input `Document.records` (not the physical file line number), and
`style` identifies the ASS style. `origin` contains the source item ID when it
has been established. A malformed source marker may have no valid ID, and
parsing failures do not invent unit/segment references before the structured
lyric exists. The underlying parser error is retained as `__cause__`.

Pulse traversal failures and scale conflicts identify the target unit and
participating track IDs. Explicit tracks are independent of the source segment
timings, so these errors do not infer a segment from coinciding timestamps.

```python
from kara_templater import (
    Body, DisplayWindow, Effect, KaraokeItem, KaraokeLine, Lyrics, Ruby,
    Segment, TextUnit, render_karaoke,
)

# document supplies ASS metadata and a Default style.
item = KaraokeItem("line-1", KaraokeLine((
    TextUnit("Karaoke", (Segment(1000, 2000),)),
)), "Default", DisplayWindow(500, 2500))
class Highlight(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby())

    def configure(self):
        self.text.sweep(fill="#33ddff")
        self.characters.on_highlight(pulse=1.1)

result = render_karaoke(document, (item,), effect=Highlight, owner="song")
result.document.save("output.ass")
```

Re-running an owner replaces only that owner's generated events; input documents,
source dialogue and other owners remain intact. Pass explicit structured items to preserve source dialogue as-is. Omit `items`
to import ASS lyrics and retain the processed source as owned comments.
The `karaoke:v1:<owner>:` effect prefix is reserved for generated-event ownership.
`RenderResult` includes diagnostics and event/layer counts. Glow safety bounds
use a reported estimate; `EdgeSweep.padding_px` adds independent compensation.

`Sweep.completion` defaults to `"release"`: after the relevant sweep and tail
phases finish, a uniform mask covering the complete drawing domain becomes an
unclipped event. This removes the estimated outer boundary while preserving the
original fade and pulse clocks. Partial coverage and spatially distinct paints
retain their clips, so release cannot expose an unsung partition. Use
`Sweep(completion="clip")` when the completed decoration should stay bounded.
Release occurs after all selected passes finish; it does not release each glyph
early as the front crosses it.

When adjacent mask regions have different visible outline/glow stacks, the
result reports an `ASS hard-clips` diagnostic with source, interval and track
IDs. This backend clips separately rendered decorations; it does not blur the
recolored regions as one image or guarantee a smooth transition between them.
Increasing temporal sampling density cannot remove that spatial boundary.
If neighboring clip edges cannot reuse compatible original clocks, the backend
reports a shared local interpolation interval so both sides use the same
quantized boundary. This approximates the original fronts. Adaptive clip cuts
retain the original position/scale/outline/blur animation clocks; the crossing
clock regression is verified with `tools/validate_clip_seams.py --scale`.
Identical decoration stacks and plain fill-color changes do not trigger this
diagnostic. For an unmasked glow independent of the color front, use the
`WholeGlow` example; it expresses a different visual effect, not seamless local
glow recoloring.

Fonts are resolved automatically from the system using each ASS style's
`Fontname` or Python `Style.fontname`. Different styles, including ruby styles,
can select different font families; no font-loading step is required for
installed fonts. Missing families or glyphs use the renderer's font fallback.

For advanced Python use with fonts that are not installed, `load_font(path)`
adds an extra font resource to the measurement renderer. It does not select a
global font or change any style. Each style still selects its own family name;
the returned `family` can be used in `Style.fontname`. Registration validates
font bytes with FreeType, reports their SHA-256 and lasts for the interpreter.
The checksum identifies the registered resource, not a guaranteed font-file
selection for a style. Playback applications must have the fonts available
separately.

Tests ship a licensed DejaVu Sans fixture. Additional visual and cost checks are
available through `tools.validate_effects` and `tools.benchmark_effects`; see the
[validation record](docs/effects-validation.md) for commands, measured costs,
pixel tolerances and the remaining validation boundaries.

## Installation

Requires Python 3.12 or newer. Wheels target CPython 3.12–3.14 on Linux x86-64 and Windows 10+ x64. Windows wheels bundle their native DLL dependencies. Linux wheels carry a `manylinux_2_28` tag but leave native libraries dynamically linked to the host; pip does not install these OS-level dependencies. They require glibc 2.28 or newer and do not support musl-based systems such as Alpine Linux.

On Linux, install the runtime libraries before installing the package. For Arch Linux:

```sh
sudo pacman -S --needed freetype2 harfbuzz fribidi fontconfig libpng gcc-libs
```

For Debian or Ubuntu:

```sh
sudo apt install libfreetype6 libharfbuzz0b libfribidi0 libfontconfig1 libpng16-16 libstdc++6
```

Package names may vary across distribution releases. Install the fonts specified by your subtitle styles. Missing fonts use system font fallback, and different fonts can change the layout.

```sh
python -m pip install kara-templater
```

### Build from source on Linux

Install a C/C++ toolchain and native dependencies.

Arch Linux:

```sh
sudo pacman -S --needed base-devel python python-pip autoconf automake libtool nasm \
  freetype2 harfbuzz fribidi fontconfig libpng
```

Debian / Ubuntu, with Python 3.12+:

```sh
sudo apt install build-essential python3-dev python3-venv autoconf automake \
  libtool nasm pkg-config libfreetype-dev libharfbuzz-dev libfribidi-dev \
  libfontconfig-dev libpng-dev
```

From the project directory:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

### Build from source on Windows

Use 64-bit Python from [python.org](https://www.python.org/downloads/windows/) and [MSYS2](https://www.msys2.org/). In the MSYS2 **UCRT64** shell, install the native toolchain:

```sh
pacman -Syu
pacman -S --needed patch mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-nasm \
  mingw-w64-ucrt-x86_64-freetype mingw-w64-ucrt-x86_64-harfbuzz \
  mingw-w64-ucrt-x86_64-fribidi
```

Restart the shell and complete the update if MSYS2 requests it. Then, in **PowerShell** at the project directory, build and install a wheel. Adjust the MSYS2 path if it is not installed at `C:\msys64`.

```powershell
$env:Path = "C:\msys64\ucrt64\bin;C:\msys64\usr\bin;$env:Path"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install delvewheel
python tools/collect_licenses.py
python -m pip wheel . --no-deps --wheel-dir dist
python -m delvewheel repair --strip --no-mangle libharfbuzz-0.dll --wheel-dir wheelhouse (Get-ChildItem dist\*.whl).FullName
python -m pip install --no-index --find-links wheelhouse kara-templater
```

The repaired wheel bundles the required DLLs so it can run without MSYS2 on the destination machine. Windows uses the system DirectWrite/GDI font provider.

## Command line

```sh
kara-templater examples/karaoke.ass output.ass --pulse char --after '#33ddff'
python -m kara_templater input.ass output.ass --pulse syllable
```

`--pulse` accepts `none`, `char` (sweep arrival), `chars` (simultaneous independent
centers), and `syllable` (one group center). The default preset uses the ASS
secondary color before singing and primary color after singing. Colors can be
overridden with `--before` and `--after` in RGB form.

`--lead-ms` and `--tail-ms` extend the display window without retiming singing.
`--fade-in-ms` and `--fade-out-ms` set fades inside that window. These are separate
from a recipe's `EdgeSweep` decoration transitions. `--style` can be repeated to
select styles; `--owner` selects the output namespace and `--max-events` sets the
output budget.

To use a Python recipe file:

```python
# song_effect.py
from kara_templater import Body, Effect, Lyrics

class SongEffect(Effect):
    def compose(self):
        yield Lyrics(Body())

    def configure(self):
        self.text.sweep(fill="#ff5599")
        self.syllables.on_singing(pulse=1.1)

effect = SongEffect
```

```sh
kara-templater input.ass output.ass --effect song_effect.py
```

The file is ordinary Python and exports `effect` (an Effect class/instance, recipe or style mapping),
or `build(item, context)` returning `EffectPlan`. Subtitle text is never executed.
Configure colors, pulses and fades inside the file when using `--effect`.

## ASS input and source preservation

```python
from kara_templater import Document, ImportSettings, render_karaoke
from song_effect import SongEffect

source = Document.load("input.ass")
result = render_karaoke(
    source, effect=SongEffect,
    import_settings=ImportSettings(lead_ms=300, tail_ms=200),
)
result.document.save("output.ass")
```

The importer accepts `\k`, `\K`, `\kf`, and `\ko` durations in centiseconds,
plus forward `\kt` offsets relative to the event start. These tags supply timing;
the recipe supplies appearance and animation. Static prefixes, empty timed
chunks, zero durations and hard spaces (`\h`) retain their meaning.
`text|ruby` or `text｜ruby` supplies a reading; `#` / `＃` continues the previous
text unit with another segment. Prefix a reading with `<` to join its layout to
the previous ruby group, or `!` to start a group.

Source dialogue becomes a comment marked `karaoke:source:v1:<owner>:`. Its text,
times, style, actor and original Effect value are retained. Subsequent runs
import the owned comments and replace only the same owner's generated output.
Other comments, plain subtitles, unknown sections and attachments are preserved.
`import_karaoke()` exposes the parsed items without changing the document.

Unsupported override tags, multiline text and reversed timing report their
source event rather than silently dropping formatting. Use structured items and
Python recipes for inline color ranges, positioning and richer animation.
Event margin overrides are used for layout. Coordinates are ASS script pixels;
`OutputSettings.resolution` must match the document's PlayRes.

## Structured lyrics and independent timing

```python
from kara_templater import KaraokeLine, Segment, Style, TextUnit, layout_line

source = KaraokeLine((
    TextUnit("A", (Segment(0, 2000),)),
    TextUnit("B", (Segment(1000, 3000),)),
    TextUnit("今日", (Segment(3000, 3500, "きょ"), Segment(3700, 4000, "う"))),
))
layout = layout_line(source, style=Style(fontname="Noto Sans CJK JP", fontsize=72))
```

Times are nonnegative integer milliseconds. Different units can overlap or be
out of chronological order. Segments within one unit are ordered; gaps and zero
durations are allowed. Ruby widths partition the base text, with equal partitions
when no readings exist. Explicit `HighlightTrack` and `SingingPass` objects can
replace this mapping, including repeated regions and parallel singing rounds.
A unit without segments is static text.

`layout_line()` returns immutable base and ruby boxes. `layout_characters()`
returns source-mapped drawable clusters, ink estimates and independent timing
regions. `text_extents(style, text)` returns advance, height, descent and external
leading (currently zero). Recipe code can traverse the source, layout and tracks
without a templating language. Use `EffectPlan.raw_lines` for manually authored
ASS events outside automatic property composition.

Unicode space separators (including nonbreaking, thin and ideographic spaces)
retain their source offsets and measured advance without becoming pulse targets.
ASS `\h` imports as U+00A0, preserving its nonbreaking-space identity. Tabs,
line breaks and bidirectional controls are outside this single-line contract.

When adjacent candidates form a ligature, contour matching keeps the smallest
verified range as one drawable cluster (for example `o`, `ffi`, `c`, `e` in
`office`). Painting or selecting only part of that cluster raises an error.
This does not add joining-script or bidi support. Contours are checked at the
actual line origin to preserve libass subpixel placement. The pinned `Karaoke`
and `office ffi` static fixtures now match whole-text rendering pixel for pixel;
other fonts and scripts still require separate validation.

## Current boundaries

- Layout targets single-line karaoke. It does not implement automatic wrapping,
  collision avoidance, a generic scene graph or a video-rendering engine.
- Character drawing checks a conservative repertoire against libass outlines;
  unsupported shaping is diagnosed. Outline bounds and glow padding estimates
  are distinct from exact raster extents.
- Complex glow joins and platform/font variations still require visual validation.
  Renderer evidence and implementation progress are tracked in the effects plan.
- Only ASS v4.00+ styles are supported. Additional fields and sections are retained,
  but serialization does not preserve byte-for-byte whitespace.
- Output limits bound generated events; Python recipe execution uses normal Python
  process semantics. Native ASS output is piecewise, with the timing and spatial
  precision limits described above.
# 底层动态属性脚本

常规作者脚本优先使用 `on_singing()`、`on_highlight()` 和 `animate()`，见
[特效指南](docs/effects.md)。以下接口用于自定义输出计划。

`EffectPlan(layers=layers, dynamic=DynamicEffect(function, seed=42, max_glow_blur=18))`
可通过普通 Python 函数返回 `DynamicProperties(offset_x=..., offset_y=...,
opacity=..., glow_blur=..., glow_opacity=...)`。回调上下文提供绝对 `time_ms`、整段显示窗口的
归一化 `progress`、稳定的 `target_id` 和可复现的 `noise()`；同一字符的
颜色区域共享结果。正文和 ruby 是独立目标。

动态 blur 需声明上限，用于预留装饰范围；不改变正文扫色区间或触发时间。
只有已经配置 `Glow` 的外观会应用 blur。位移同时移动文字、裁剪和缩放中心。
`glow_opacity` 覆盖已有辉光的不透明度（0～1），不改变主体；`opacity` 则乘到
整个绘制层。`TextLayer(component="fill" / "glow" / "both")` 可独立输出主体
或辉光，辉光层必须配置 `Paint.glow`。

[whole_glow.py](examples/whole_glow.py) 展示整音节辉光从 0.2 增强至 0.8，
辉光无局部扫色裁剪、主体保持原计时扫色。运行
`python -m examples.whole_glow /tmp/whole-glow.ass`，或使用 CLI 的
`--effect examples/whole_glow.py`。此示例只处理正文，关闭 ruby；多 segment
音节按首段开始至末段结束增强（包含间隔），无时间的正文保持初始强度。

`SamplingSettings(step_ms=40)` 默认每 40 ms 保持一次属性值，步长必须是
10 ms 的正整数倍。这是时间离散精度，不承诺任意函数的空间误差上限；
普通扫色、淡入和 pulse 仍使用原有全局时间插值。

低层接口 `prepare_sampling(layers, dynamic)` 不执行回调；先查看返回的
`estimate`，再调用 `evaluate()`。文档入口会先检查所有组的采样预算，再执行
属性回调。预计事件数不含后续原生曲线细分，最终输出仍受 `max_events` 限制。
文档入口支持 `render_karaoke(..., on_estimate=callback)`，在全部预算预检后、
任何动态属性函数执行前调用一次。`RenderEstimate` 提供 `static_events`、
`raw_events`、`sampling`、`target_samples`、`estimated_events` 和 `event_limit`。
配方 build 函数和布局此时已经执行。预览回调可抛出异常取消渲染，输入文档
保持不变。CLI 对动态效果自动先打印并刷新成本预览。

```python
def report_cost(estimate):
    print(estimate.estimated_events, estimate.target_samples)
    if estimate.target_samples > 50_000:
        raise ValueError("属性求值次数超过本脚本预算")

result = render_karaoke(document, effect=effect, on_estimate=report_cost)
```

同一原始图层的连续采样区间在有效属性完全相同时会自动合并，所有采样回调
仍照常执行，不跨时间空档或不同来源合并。预估按合并前计算，因此可能高于
实际输出；最终编译的细分仍可能增加事件。同层事件按稳定来源顺序排列，
不会因为采样或合并改变辉光的绘制先后；需要显式叠放关系时设置图层 order。

可运行示例：

```sh
python -m kara_templater examples/karaoke.ass /tmp/dynamic.ass \
  --effect examples/dynamic_effect.py
```

该示例现使用 `Effect`、`Contextual` 和独立 `Halo`，通过来源作用域的
确定性噪声同步文字位移与模糊。动态模糊在 `Halo(max_blur=18)` 声明上界，
详细接口见[特效指南](docs/effects.md)。

