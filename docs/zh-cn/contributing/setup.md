# 配置开发环境

安装从源码构建 kara-templater 所需的原生库、Rust 工具链和 Python 检查工具。如果你在仓库签出目录中开发，而不是直接安装预构建的 Wheel，请按本页配置环境。

## 前置条件

从源码构建需要 Python 3.12 及以上版本、C++17 编译器，以及 Cargo 和 Rust 1.87 及以上版本：

- **原生文本扩展**（`kara_templater._text_native`）：链接 FreeType、HarfBuzz、FriBidi 和 Fontconfig（构建 FreeType 与 Pillow 时还需要 `libpng`）。
- **内置 WGSL 翻译器**（`_kara_wgsl`）：从 `native/wgsl/` 中的锁定 Rust 工程编译而来，用于 Hook 和浏览器预览的着色器导出。

修复后的 Wheel 已经打包好 `_kara_wgsl` 和编译产物，下游用户无需安装 C++ 或 Rust 工具链。

## Linux 环境

先安装 C/C++ 工具链、Python 头文件、`pkg-config`、原生开发库和预览字体。

Debian 或 Ubuntu：

```sh
sudo apt install build-essential python3-dev python3-venv pkg-config \
  libfreetype-dev libharfbuzz-dev libfribidi-dev libfontconfig-dev \
  libpng-dev fonts-dejavu-core fonts-noto-cjk
```

Arch Linux：

```sh
sudo pacman -S --needed base-devel python python-pip pkgconf \
  freetype2 harfbuzz fribidi fontconfig libpng ttf-dejavu noto-fonts-cjk
```

通过 `rustup` 安装 Rust 1.87 或更高版本，并确保 Cargo 在 `PATH` 中（例如 `rustup default 1.87.0`）。不同发行版的包名可能略有差异，`setup.py` 通过 `pkg-config` 查找 `freetype2`、`harfbuzz`、`fribidi` 和 `fontconfig`。

在仓库根目录创建虚拟环境并安装：

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

> [!NOTE]
> 发布的 Linux Wheel 面向 x86-64 的 `manylinux_2_28`（要求 `glibc >= 2.28`，不支持 musl/Alpine），并且保持 FreeType、HarfBuzz、FriBidi、Fontconfig、`libpng` 和 C++ 运行时动态链接。在 Linux 上使用 Wheel 时，仍需单独安装这些系统库。

## Windows 环境

使用 x64 CPython 和 MSYS2 UCRT64 工具链。在 MSYS2 UCRT64 终端中运行：

```sh
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-fontconfig \
  mingw-w64-ucrt-x86_64-freetype mingw-w64-ucrt-x86_64-harfbuzz \
  mingw-w64-ucrt-x86_64-fribidi
```

如果更新过程中提示重启终端，请先重启再继续。Meson 和 Ninja 会由 [pyproject.toml](../../../pyproject.toml) 中的构建后端自动安装。

随后在仓库根目录打开 PowerShell（如 MSYS2 安装路径不同，请自行调整）：

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

`delvewheel` 会把所需的运行时 DLL 打包进修复后的 Wheel。测试安装好的 Wheel 时，请移出源码目录并从 `PATH` 中移除 MSYS2 路径。Windows 下的字体选择依赖 Fontconfig 以及显式注册的字体文件。

## 检查工具与本地重编译

[pyproject.toml](../../../pyproject.toml) 中的 `checks` 依赖组锁定了 Ruff 和 ty，并包含 `pytest`、`Pillow`、`setuptools` 和 `fontTools`。使用 `uv` 时：

```sh
uv sync --group checks
uv run ruff check .
uv run ty check
uv run python -m pytest
```

也可以用 `pip` 安装该依赖组：

```sh
python -m pip install --group checks
```

不带路径参数运行 `pytest` 只执行核心测试套件。运行 `uv run python -m pytest tests` 则会执行全部回归、示例和文档测试。

在非可编辑安装中修改 `native/metrics.cpp` 或 `native/wgsl/` 后，可用 `python setup.py build_ext --inplace` 就地重新编译原生组件。要在源码树之外验证已安装的 Wheel，请参见[构建与验证发布包](releasing.md)。

## 视频渲染与预览工具

要渲染或检查 Hook 输出，需要安装带 `libplacebo` 滤镜的 FFmpeg 以及可用的 Vulkan 驱动，然后确认滤镜存在：

```sh
ffmpeg -hide_banner -h filter=libplacebo
```

Hook 导出本身只需要正常的 Python 环境，具体渲染命令见[播放与渲染 Hook](../output/hook.md)。

画廊 GIF 编码（`tools.render_gallery`）依赖 FFmpeg，ASS 连续播放与跳转校验（`tools.validate_scene_core`）还需要 FFmpeg 的 `ass` 滤镜。确保原生文本测量与外部播放器使用同一套字体，详见[选择与注册字体](../guides/fonts.md)。

## 下一步

- [检查与文档验证](checks.md)
- [架构概览](architecture.md)
- [编写与构建文档站点](documentation-site.md)
