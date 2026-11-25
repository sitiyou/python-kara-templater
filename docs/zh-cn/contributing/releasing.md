# 构建与验证发布包

构建源码分发包与修复后的 Wheel、在源码树之外验证已安装的 Wheel，并将带标签的版本发布到 PyPI。准备发版或修改打包配置与原生依赖时，请按本页操作。

## 发布流水线概览

`.github/workflows/release.yml` 工作流包含四个阶段：

1. **`quality`**：使用锁定版本的 Ruff 和 ty 执行代码风格与类型检查。
2. **`sdist`**：核对标签与 `pyproject.toml` 版本号一致，构建源码压缩包并运行 `twine check --strict`，随后在源码树外安装源码包，运行完整 `pytest tests` 套件和命令行 Hook 导出检查。
3. **`wheels`**：通过 `cibuildwheel` 为 Linux x86-64（`manylinux_2_28`）和 Windows AMD64 构建 CPython 3.12–3.15 修复版 Wheel，执行测试并校验元数据。
4. **`publish`**：通过 PyPI Trusted Publishing 上传分发产物，仅限 `v*` 版本标签触发。

仅在本地打标签或修改 `pyproject.toml` 中的版本号不会触发发布。

## 本地构建与更新许可声明

按[配置开发环境](setup.md)装好原生构建依赖后，在干净的输出目录中构建，避免混入旧产物：

```sh
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

源码分发包由 `MANIFEST.in` 控制，包含 Python 与 C++/Rust 源码、依赖许可声明、离线预览所需的 HTML 与 JavaScript、文档与预览媒体、示例、技能文件、测试与测试字体，且不得依赖 `.dev/` 或 `build/`。字体受独立许可约束，不会自动打入运行时 Wheel。

原生依赖许可快照存放在 `vendor/runtime-licenses/README.md`（Windows 运行时 DLL）和 `vendor/runtime-licenses/wgsl/LICENSES.txt`（内置 WGSL 翻译器的锁定 Rust 依赖）。构建过程直接复制这些静态文件而不会扫描宿主环境；每当更换原生依赖、调整 Windows DLL 打包清单或更新 `native/wgsl/Cargo.lock` 时，都必须手动同步这些声明。

## 平台 Wheel 修复

- **Linux**：面向 x86-64 `manylinux_2_28`，使用 `auditwheel repair --plat manylinux_2_28_x86_64 --only-plat`。系统动态链接库（`libharfbuzz`、`libfribidi`、`libfontconfig`、`libfreetype`、`libglib-2.0`、`libgraphite2`、`libexpat`、`libz`、`libbz2`、`libpng16`、`libbrotli*`、`libpcre2-8`）均刻意排除在外。发布前需检查最终 Wheel 标签并记录宿主运行库要求，切勿宣称更早的 manylinux 兼容基线。
- **Windows**：使用 MSYS2 UCRT64、Meson 和 `delvewheel repair --strip --no-mangle libharfbuzz-0.dll`。由于与 FreeType 存在循环依赖，`libharfbuzz-0.dll` 保持原名不做重整，其余打包 DLL 会进行名称重整。CI 会在 `cibuildwheel` 中对每个 Windows Wheel 运行 `pytest tests/test_wgsl_material.py` 与命令行 Hook 导出测试，并检查包内是否包含 `_text_native.<abi>-win_amd64.pyd`、`_kara_wgsl.exe` 和 `libharfbuzz-0.dll`。在本地 Windows 主机上测试时，还应在移除 UCRT64 和 MSYS2 路径的干净 `PATH` 环境下确认 DLL 加载正常。

调整修复参数或打包库清单时，请同步核对静态原生依赖许可声明。

## 隔离分发包验证

先从源码包构建 Wheel，再在安装了 `uv` 的环境中对两者执行隔离验证：

```sh
uv run python -m tools.validate_distribution path/to/source.tar.gz path/to/package.whl build/distribution-check --python python3.12
```

输出目录必须尚未存在。`tools.validate_distribution` 会依次执行以下校验：

1. 检查 Wheel 标签（Linux Wheel 只能声明 `manylinux_2_28_x86_64`），核对 `_text_native` 与 `_kara_wgsl`（Windows 下为 `_kara_wgsl.exe`）存在，并逐字节比对所有 `.py`、`.pyi` 和 `py.typed` 与源码包一致。Windows 下仅剥离 `kara_templater/__init__.py` 中精确匹配的 `delvewheel` DLL 引导代码，修复标记内的任意改动都会被拒绝。
2. 新建干净的虚拟环境并安装该 Wheel，只复制 `tests/`、`examples/`、`tools/`、`docs/` 和 `skills/`（不复制 `kara_templater/` 源码目录），确认导入来自虚拟环境中的已安装包。
3. 运行完整 `pytest tests`、`ty check tests/typing`、`tools.check_scene_types`、六个可运行的 ASS 与 Hook 示例，以及四条命令行工作流（默认 Hook、`--ass`、`--effect` 构建函数、`--effect` 轨道声明）。
4. 校验输出格式，并把运行日志和 `distribution-validation.json` 写入 `build/`。

请把当前版本的验证报告与旧记录区分开，切勿用早期快照证明修改后的代码已经通过验证。

## 审慎发布

更新 [pyproject.toml](../../../pyproject.toml) 中的 `project.version`，确认 `main` 分支上的 CI 全部通过，然后推送与 `vVERSION` 完全一致的标签（不匹配的标签会被 `sdist` 任务拦截）。发布依赖事先配置好的 GitHub `pypi` 环境和 PyPI Trusted Publishing。普通分支推送和针对分支的手动运行都不会发布，且 PyPI 上已发布的版本号无法覆盖。

> [!WARNING]
> 修改文档、本地校验或构建测试 Wheel 都不需要发版。日常维护期间请勿推送版本标签或触发发布流程。

## 下一步

- [配置开发环境](setup.md)
- [检查与文档验证](checks.md)
- [第三方源码与许可](../../../THIRD_PARTY.md)
