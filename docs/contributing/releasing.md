# Build and validate a release

The release workflow in .github/workflows/release.yml checks source quality,
builds a source distribution, tests an installed package outside the checkout,
and builds repaired CPython 3.12–3.14 wheels for Linux x86-64 and Windows AMD64.
It uploads artifacts and has a separate publishing job restricted to version tags.
A local tag or pyproject version alone does not prove publication.

## Build locally

After installing native build prerequisites:

```sh
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

Use a fresh output directory to avoid mixing old artifacts. The source archive
includes library/native sources, bundled patches/licenses, current docs/media,
examples, and required tests/fixtures. It must not require .dev or previous build
outputs. Fonts have separate licenses and are not automatically bundled in wheels.

Native dependency notices are fixed files under vendor/runtime-licenses and are
included directly in source/wheel metadata. Builds do not scan the host. Review
the recorded versions and update the snapshots manually when changing native
dependencies or the Windows DLL bundle. Linux host-linked libraries remain external.

Native source caches are keyed by archive, ordered patches, binding/build files,
platform, and Python ABI. Failed patch application does not publish a partial
source cache. The extension is relinked against the selected cache.

## Platform repair

Linux wheels use manylinux 2.28 and auditwheel with --only-plat. Several native
libraries are deliberately external; inspect the final wheel tags/dependencies
and document host runtime requirements. Do not add an older manylinux claim
solely because a repair tool can emit an additional tag.

Windows uses UCRT64/Meson and delvewheel. Repair leaves libharfbuzz-0.dll unmangled
because of its FreeType dependency cycle; other selected DLLs are name-mangled.
Test without UCRT/MSYS build-toolchain directories on PATH so bundled dependency
loading is actually exercised. Wine can test Windows ABI artifacts but does not
replace a native Windows host for platform/rendering claims.

Review the fixed native dependency notices alongside dependency/repair changes.

## Isolated distribution verification

Build a wheel from the source archive, then use the distribution validator with
the actual filenames and interpreter for that version/platform:

```sh
python -m tools.validate_distribution path/to/source.tar.gz path/to/package.whl build/distribution-check --python python3.12
```

The output directory must not already exist. The validator compares wheel source
files with the archive, checks native and typing assets/tags, installs a fresh
environment, and copies tests/examples/tools/docs without copying the library
source directory. It exercises installed-package tests, public typing, examples,
and the preset, Track and Scene builder CLI workflows, recording artifact hashes and logs under build/.

Windows comparison recognizes only the expected complete delvewheel bootstrap,
then compares original source bytes. Arbitrary source edits inside repair
markers are not accepted. Distinguish current verification from old reports;
never describe an earlier source snapshot as a run of changed code.

## Publish deliberately

Update the project version and ensure intended CI checks pass. A publish tag must
exactly match vVERSION for pyproject.toml. The workflow uses the pypi GitHub
environment and PyPI Trusted Publishing. Configure repository/environment policy
before publishing. Branch pushes and branch-targeted manual runs do not publish;
a matching version-tag run may publish. Existing PyPI versions cannot be replaced.

Creating docs, running local validation, or building artifacts does not itself
require a release. Do not push tags or publish as part of routine documentation
maintenance.
