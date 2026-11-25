# Build and validate a release

Build source distributions and repaired wheels, verify an installed wheel outside the checkout, and publish tagged releases to PyPI. Follow this guide when preparing a release or changing packaging and native dependencies.

## Release workflow overview

The workflow in `.github/workflows/release.yml` runs four jobs:

1. **`quality`**: lints and type-checks with the pinned Ruff and ty versions.
2. **`sdist`**: checks that a tag matches `pyproject.toml`, builds the source archive, runs `twine check --strict`, installs the archive outside the checkout, and runs the full `pytest tests` suite plus CLI Hook export.
3. **`wheels`**: builds repaired CPython 3.12–3.15 wheels for Linux x86-64 (`manylinux_2_28`) and Windows AMD64 with `cibuildwheel`, tests them, and checks wheel metadata.
4. **`publish`**: uploads artifacts to PyPI using Trusted Publishing, restricted to `v*` version tags.

A local tag or `pyproject.toml` version edit alone does not publish a release.

## Build locally and update notices

After installing the native build prerequisites in [Set up a development environment](setup.md), build into a fresh output directory so old artifacts do not mix:

```sh
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

The source distribution includes Python and native C++/Rust sources, dependency license notices, documentation and preview media, examples, skills, tests, and test fonts (configured in `MANIFEST.in`). It must not depend on `.dev/` or `build/`. Fonts have separate licenses and are not bundled into runtime wheels.

Native dependency notices live in `vendor/runtime-licenses/README.md` for Windows runtime DLLs and `vendor/runtime-licenses/wgsl/LICENSES.txt` for the bundled WGSL translator's locked Rust crates. Builds include these files directly without scanning the host; update them manually whenever you change native dependencies, the Windows DLL bundle, or `native/wgsl/Cargo.lock`.

## Platform wheel repair

- **Linux**: wheels target `manylinux_2_28` on x86-64 using `auditwheel repair --plat manylinux_2_28_x86_64 --only-plat`. Host-linked system libraries (`libharfbuzz`, `libfribidi`, `libfontconfig`, `libfreetype`, `libglib-2.0`, `libgraphite2`, `libexpat`, `libz`, `libbz2`, `libpng16`, `libbrotli*`, and `libpcre2-8`) are deliberately excluded. Inspect the final wheel tags and document host runtime requirements; do not advertise an older manylinux floor.
- **Windows**: builds use MSYS2 UCRT64, Meson, and `delvewheel repair --strip --no-mangle libharfbuzz-0.dll`. `libharfbuzz-0.dll` stays unmangled because of its FreeType dependency cycle; other bundled DLLs are name-mangled. CI runs runtime checks inside `cibuildwheel` (`pytest tests/test_wgsl_material.py` and CLI Hook export) and inspects each wheel for `_text_native.<abi>-win_amd64.pyd`, `_kara_wgsl.exe`, and `libharfbuzz-0.dll`. On a local Windows machine, verify DLL loading in a clean environment with UCRT64 and MSYS2 directories removed from `PATH`.

Review the fixed native dependency notices whenever you change repair flags or bundled libraries.

## Isolated distribution verification

Build a wheel from the source archive, then validate both artifacts against a clean virtual environment with `uv` installed:

```sh
uv run python -m tools.validate_distribution path/to/source.tar.gz path/to/package.whl build/distribution-check --python python3.12
```

The output directory must not already exist. `tools.validate_distribution` performs these checks:

1. Verifies wheel tags (Linux wheels must advertise only `manylinux_2_28_x86_64`), checks that `_text_native` and `_kara_wgsl` (`_kara_wgsl.exe` on Windows) are present, and confirms every `.py`, `.pyi`, and `py.typed` file matches the source archive byte-for-byte. On Windows, only the exact recognized `delvewheel` DLL bootstrap in `kara_templater/__init__.py` is stripped before comparison; arbitrary edits inside repair markers fail.
2. Creates a fresh virtual environment, installs the wheel, copies `tests/`, `examples/`, `tools/`, `docs/`, and `skills/` without `kara_templater/`, and confirms imports load from the installed wheel.
3. Runs `pytest tests`, `ty check tests/typing`, `tools.check_scene_types`, six runnable ASS and Hook examples, and four CLI workflows (default Hook, `--ass`, `--effect` builder, and `--effect` tracks).
4. Checks output formats and writes logs plus `distribution-validation.json` under `build/`.

Keep current verification reports separate from earlier runs; never cite an older snapshot as verification of modified code.

## Publish deliberately

Update `project.version` in [pyproject.toml](../../pyproject.toml) and ensure CI passes on `main`. Push a tag matching `vVERSION` exactly; the `sdist` job rejects mismatched tags. Publishing uses the `pypi` GitHub environment and PyPI Trusted Publishing, which must be configured in repository and environment settings beforehand. Branch pushes and branch-targeted manual runs never publish, and existing PyPI versions cannot be replaced.

> [!WARNING]
> Editing documentation, running local checks, or building test wheels does not require a release. Do not push version tags or trigger publication during routine maintenance.

## Next steps

- [Set up a development environment](setup.md)
- [Checks and documentation](checks.md)
- [Third-party sources](../../THIRD_PARTY.md)
