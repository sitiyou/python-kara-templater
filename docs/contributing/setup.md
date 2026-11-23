# Development setup

The project uses Python 3.12 or later and a C++ extension linked to FreeType, HarfBuzz, FriBidi and Fontconfig. Installing the library from source builds that extension. A
matching repaired wheel avoids the native build toolchain on the destination.

## Linux

A source build needs a C/C++ toolchain, Python headers, pkg-config, and development headers for FreeType, HarfBuzz, FriBidi, Fontconfig,
and libpng. For a Debian/Ubuntu environment with Python 3.12+:

```sh
sudo apt install build-essential python3-dev python3-venv pkg-config libfreetype-dev libharfbuzz-dev libfribidi-dev \
  libfontconfig-dev libpng-dev fonts-dejavu-core
```

For Arch Linux:

```sh
sudo pacman -S --needed base-devel python python-pip pkgconf freetype2 harfbuzz fribidi fontconfig libpng ttf-dejavu
```

Package names vary by OS version. The dependency names above describe the
libraries the build checks through pkg-config.

From the checkout root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Linux wheel builds target manylinux 2.28 on x86-64. Native runtime libraries
remain dynamically linked: install FreeType, HarfBuzz, FriBidi, Fontconfig,
libpng, and the C++ runtime on the host. These builds require glibc >=2.28 and
do not target musl/Alpine. Python package installation does not supply OS packages.

## Windows

Use x64 CPython and the MSYS2 UCRT64 toolchain. In UCRT64:

```sh
pacman -Syu
pacman -S --needed patch mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-fontconfig \
  mingw-w64-ucrt-x86_64-freetype mingw-w64-ucrt-x86_64-harfbuzz \
  mingw-w64-ucrt-x86_64-fribidi
```

Complete a requested shell restart/update before building. In PowerShell at the
checkout root, adjust the MSYS2 path if necessary:

```powershell
$env:Path = "C:\msys64\ucrt64\bin;C:\msys64\usr\bin;$env:Path"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install delvewheel
python -m pip wheel . --no-deps --wheel-dir dist
python -m delvewheel repair --strip --no-mangle libharfbuzz-0.dll --wheel-dir wheelhouse (Get-ChildItem dist\*.whl).FullName
python -m pip install --no-index --find-links wheelhouse kara-templater
```

Windows repair bundles selected DLLs. Test the repaired installed wheel outside
the checkout, with the build-toolchain directories removed from PATH. Font
selection uses Fontconfig and explicitly registered font files.

## Check tools and previews

The checks dependency group pins Ruff and ty and includes pytest, Pillow,
setuptools, and fontTools. With uv available:

```sh
uv sync --group checks
uv run ruff check .
uv run ty check
uv run python -m pytest
```

The default pytest command runs the core suite. Run `uv run python -m pytest tests`
for the complete suite.

Alternatively, with pip supporting dependency groups:

```sh
python -m pip install --group checks
```

For source-tree tests after a non-editable installation, build the native
extension in place with `python setup.py build_ext --inplace`. For installed-wheel
checks, use the isolated workflow in [release builds](releasing.md).

Gallery video encoding uses FFmpeg. Optional player-comparison tools that explicitly test FFmpeg’s ASS filter require that filter in the external player build.
Provide the same fonts to the metrics renderer and FFmpeg/player. See
[fonts and preview](../guides/fonts-and-preview.md).

## GPU video rendering

Install FFmpeg with the libplacebo filter and a working Vulkan driver. The hook
exporter uses the normal project environment. Verify the filter with
`ffmpeg -hide_banner -h filter=libplacebo`. See [GPU rendering](../guides/gpu-rendering.md).
