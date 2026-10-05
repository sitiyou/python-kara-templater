# kara-templater

An ASS karaoke template engine rewritten in Python and C++. It runs without Aegisub or Lua.

The package keeps the karaoke templater's ASS template format, `$variables`, modifiers, and helper functions. **Expressions inside `!…!` and `code` lines use Python.** Lua code in existing templates must be rewritten manually; there is no Lua compatibility interpreter.

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
kara-templater input.ass output.ass
python -m kara_templater input.ass output.ass
```

Try the included example from a source checkout:

```sh
kara-templater examples/karaoke.ass output.ass
```

To correct horizontal coordinates for the video's actual dimensions:

```sh
kara-templater input.ass output.ass --video-size 1920 1080
```

Templates are ASS `Comment` events. Put the template type and modifiers in the **Effect** field. For example:

- Effect: `template syl noblank`
- Text: `!retime("syl")!{\an5\pos($scenter,$smiddle)\fad(50,80)}`

For lyrics such as `{\k50}你{\k50}好`, this generates one positioned effect event per nonblank syllable.

The output preserves templates, turns processed lyrics into comments with Effect `karaoke`, and marks generated events with Effect `fx`. Running the engine again removes old `fx` events and regenerates them.

## Python API

```python
from kara_templater import Document, Style, apply_templates, text_extents

source = Document.load("input.ass")
result = apply_templates(source)
result.save("output.ass")

width, height, descent, external_leading = text_extents(
    Style(fontname="Noto Sans CJK SC", fontsize=48), "你好"
)
```

`apply_templates` returns a new document without modifying its input. `Document.parse(text)` and `result.dumps()` support in-memory use.

## Templates

| Type | Behavior |
| --- | --- |
| `template syl`, or no explicit type | Generate effects per syllable, including the empty syllable at index 0; usually combined with `noblank` |
| `template char` / `template syl char` | Generate effects per Unicode code point, retaining syllable timing |
| `template line` | Concatenate the per-syllable template into one complete effect event |
| `template pre-line` | Prefix a complete event; use the same identifier to merge it with a `line` template |
| `template furi` | Generate effects for furigana |
| `code once / line / syl / furi` | Execute Python statements in that scope; defaults to `once` |

Modifiers include `all`, `repeat N` / `loop N`, `notext`, `keeptags`, `noblank`, `multi`, `fx NAME`, and `fxgroup NAME`. Templates match their own style by default; `all` matches every style. Unknown modifiers, variables, and execution errors report the template event number instead of being silently ignored.

- `\k`, `\K`, `\kf`, `\ko`: syllable duration in centiseconds.
- `\-NAME`: inline effect name, inherited by subsequent syllables.
- `#` / `＃`: continue the preceding syllable; `multi` runs the template separately for each highlight.
- `漢|かん` / `漢｜かん`: separate base text from furigana. A furigana prefix `!` starts a new group; `<` allows spillback to the left. Full-width prefixes are also accepted. A missing furigana style is created as `STYLE-furigana` at half the base font size.

### Variables and execution environment

`$variables` are case-insensitive:

- Line timing and indices: `$lstart`, `$lend`, `$ldur`, `$lmid`, `$li`, `$syln`.
- Syllable timing and indices: `$sstart`, `$send`, `$sdur`, `$skdur`, `$smid`, `$si`.
- Layout: prefix `l` or `s` to `left`, `center`, `right`, `width`, `top`, `middle`, `bottom`, `height`, `x`, or `y`.
- Current-scope aliases: `$start`, `$end`, `$dur`, `$kdur`, `$mid`, `$i`, and unprefixed layout variables.
- Other values: `$layer`, `$style`, `$actor`, `$margin_l`, `$margin_r`, `$margin_v`, `$margin_t`, `$margin_b`.

Expressions and code share Python variables. The environment provides `math`, `random`, `meta`, `styles`, `orgline`, `line`, `syl`, `basesyl`, `j`, `maxj`, `fxgroup`, and `text_extents`. `line` is the current mutable output event; in a code template it is the source lyric event. `syl` is a dictionary with attribute access.

Example Effect and Text pairs:

```text
code once                  → amplitude = 12
code line                  → fxgroup["spark"] = orgline.actor == "solo"
template syl repeat 3      → !retime("syl")!{\an5\pos(!$x + amplitude * j!,$y)}
```

An expression returning `None` produces an empty string. Integral floating-point values are written without a trailing `.0`.

### Helpers

- `retime(mode, addstart=0, addend=0)`: modes are `syl`, `presyl`, `postsyl`, `line`, `preline`, `postline`, `start2syl`, `syl2end`, `sylpct`, and `set` / `abs`. Offsets are milliseconds, except that `sylpct` uses percentages of syllable duration. Timing is based on the current `line`, so consecutive calls use the previously modified times.
- `relayer(layer)`, `restyle(style)`: modify the current output event.
- `maxloop(count)` / `maxloops(count)`, `loopctl(j, count)`: control template loops dynamically.
- `remember(name, value, decorator=None)`, `recall(name, default=None)`, `remember_if(name, value, condition, decorator=None)`: store and retrieve values. The optional decorator is a Python function mapping a name to a memory key.
- `remember_line`, `remember_syl`, `remember_basesyl`: isolate remembered values by source event, current syllable, or base syllable.

## Limitations and safety

- **Only process trusted subtitles.** Python expressions and code have the permissions of the current process. This is not a sandbox. Template iteration and output limits cannot stop arbitrary Python code from looping forever or performing malicious operations.
- The defaults are 10,000 iterations per template loop and 100,000 output events. The Python API accepts `max_iterations` and `max_output_lines` to change these limits.
- Only ASS v4.00+ is supported, not legacy SSA styles. Extra fields, unknown sections, and attachments are preserved, but byte-for-byte formatting is not guaranteed.
- Layout targets single-line karaoke using the base style. It does not simulate automatic wrapping, event collisions, inline style overrides, `\pos` / `\move`, or drawing geometry. `text_extents` supports `\N` hard breaks; syllable layout is not multiline-aware.
- `text_extents` returns logical advance width, font height, and descent, not visible glyph bounds. It preserves edge spaces and measures braces literally. External leading is always `0`. Pixel-identical results across fonts, platforms, or Aegisub's native font interfaces are not guaranteed.
- No GUI, video/audio processing, Automation plugin interface, or other Aegisub features are included.
