# Set up a development environment

Install the native libraries, Rust toolchain, and Python check tools required to build kara-templater from source. Use this guide when working from a repository checkout instead of a prebuilt wheel.

## Prerequisites

Building from source requires Python 3.12 or later, a C++17 compiler, and Cargo with Rust 1.87 or later:

- **Native text extension** (`kara_templater._text_native`): links against FreeType, HarfBuzz, FriBidi, and Fontconfig (`libpng` is also required by FreeType/Pillow builds).
- **Bundled WGSL translator** (`_kara_wgsl`): compiled from the locked Rust crate in `native/wgsl/` to validate WGSL materials and translate them to GLSL for browser preview and shader playback.

Repaired wheels already bundle `_kara_wgsl` and the compiled extension so downstream users do not need a C++ or Rust toolchain.

## Linux

Install a C/C++ toolchain, Python headers, `pkg-config`, the native development libraries, and preview fonts.

On Debian or Ubuntu:

```sh
sudo apt install build-essential python3-dev python3-venv pkg-config \
  libfreetype-dev libharfbuzz-dev libfribidi-dev libfontconfig-dev \
  libpng-dev fonts-dejavu-core fonts-noto-cjk
```

On Arch Linux:

```sh
sudo pacman -S --needed base-devel python python-pip pkgconf \
  freetype2 harfbuzz fribidi fontconfig libpng ttf-dejavu noto-fonts-cjk
```

Install Rust 1.87 or later with `rustup` so Cargo is on `PATH` (for example, `rustup default 1.87.0`). Package names vary by distribution; `setup.py` locates `freetype2`, `harfbuzz`, `fribidi`, and `fontconfig` through `pkg-config`.

From the checkout root, build and install into a virtual environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

> [!NOTE]
> Published Linux wheels target `manylinux_2_28` on x86-64 (`glibc >= 2.28`, not musl/Alpine) and keep FreeType, HarfBuzz, FriBidi, Fontconfig, `libpng`, and the C++ runtime dynamically linked. Install those host packages separately when using a wheel on Linux.

## Windows

Use x64 CPython and the MSYS2 UCRT64 toolchain. In an MSYS2 UCRT64 shell:

```sh
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-fontconfig \
  mingw-w64-ucrt-x86_64-freetype mingw-w64-ucrt-x86_64-harfbuzz \
  mingw-w64-ucrt-x86_64-fribidi
```

Complete any requested shell restart before building. Meson and Ninja are installed automatically by the build backend in [pyproject.toml](../../pyproject.toml).

In PowerShell at the checkout root (adjust the MSYS2 path if needed):

```powershell
$env:Path = "C:\msys64\ucrt64\bin;C:\msys64\usr\bin;$env:Path"
rustup toolchain install 1.87.0-x86_64-pc-windows-gnu
$env:RUSTUP_TOOLCHAIN = "1.87.0-x86_64-pc-windows-gnu"
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = "gcc"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install delvewheel
python -m pip wheel . --no-deps --wheel-dir dist
python -m delvewheel repair --strip --no-mangle libharfbuzz-0.dll --wheel-dir wheelhouse (Get-ChildItem dist\*.whl).FullName
python -m pip install --no-index --find-links wheelhouse kara-templater
```

`delvewheel` bundles the required runtime DLLs into the repaired wheel. Verify an installed wheel outside the checkout with MSYS2 directories removed from `PATH`. Font selection on Windows uses Fontconfig and explicitly registered font files.

## Check tools and editable rebuilds

The `checks` dependency group in [pyproject.toml](../../pyproject.toml) pins Ruff and ty and installs `pytest`, `Pillow`, `setuptools`, and `fontTools`. With `uv`:

```sh
uv sync --group checks
uv run ruff check .
uv run ty check
uv run python -m pytest
```

With `pip`:

```sh
python -m pip install --group checks
```

The plain `pytest` command runs the fast core suite. Run `uv run python -m pytest tests` to run every regression, example, and documentation test.

After editing `native/metrics.cpp` or `native/wgsl/` in a non-editable install, rebuild the native artifacts in place with `python setup.py build_ext --inplace`. For installed-wheel checks outside the source tree, follow [Build and validate a release](releasing.md).

## Video playback and preview tools

To render or inspect Hook output, install FFmpeg with the `libplacebo` filter and a working Vulkan driver, then confirm filter support:

```sh
ffmpeg -hide_banner -h filter=libplacebo
```

Hook export itself needs only the normal Python environment; see [Play and render a Hook](../output/hook.md) for rendering commands.

Gallery GIF encoding (`tools.render_gallery`) uses FFmpeg. Continuous ASS seek validation (`tools.validate_scene_core`) also requires FFmpeg's `ass` filter. Provide the same fonts to native measurement and external players; see [Choose and register fonts](../guides/fonts.md).

## Next steps

- [Checks and documentation](checks.md)
- [Architecture](architecture.md)
- [Write and build the documentation site](documentation-site.md)
