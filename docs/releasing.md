# Build and release

`.github/workflows/release.yml` runs on pull requests, pushes to `main`, version tags, and manual dispatches. It:

1. Builds and checks a source distribution, installs it, and runs the tests and CLI outside the source tree.
2. Builds CPython 3.12, 3.13, and 3.14 wheels from that source distribution for Linux x86-64 and Windows x64.
3. Repairs native dependencies with auditwheel on Linux and delvewheel on Windows, then tests each installed wheel outside the source tree.
4. Uploads the source distribution and wheels as workflow artifacts.
5. Publishes all artifacts to PyPI only for a successful `vVERSION` tag push. Pull requests, branch pushes, and manual runs never publish.

The tag must exactly match the version in `pyproject.toml`. For example, version `0.1.0` requires tag `v0.1.0`. A version mismatch fails before building a release. PyPI versions cannot be overwritten.

## One-time PyPI setup

Configure a [Trusted Publisher](https://docs.pypi.org/trusted-publishers/) for the `kara-templater` project, or a pending publisher before its first release:

- Owner and repository: this repository's GitHub owner and name.
- Workflow filename: `release.yml`.
- Environment: `pypi`.

Create the `pypi` environment in the GitHub repository settings. Restrict deployments to version tags and optionally require a reviewer. The publish job receives `id-token: write` only; no PyPI API token or repository secret is needed. The package name must be available to your PyPI account.

## Release checklist

1. Update the version in `pyproject.toml` and commit the release changes.
2. Ensure the main-branch workflow has passed.
3. Create a matching `vVERSION` tag on the intended commit and publish that tag to GitHub through your normal release process.
4. Approve the `pypi` deployment if required and inspect the workflow and PyPI files.

## Native builds

Linux uses the bundled metrics-patched libass with Autotools and Fontconfig. Unicode automatic line breaking is disabled on both platforms because template layout does not support automatic wrapping; explicit hard breaks still work. Release wheels use the manylinux 2.28 image. Its native dependencies and a basic test font are installed inside the container.

Windows follows libass's [UCRT64 Meson CI](https://github.com/libass/libass/blob/master/.github/workflows/meson.yml): MSYS2 supplies GCC, pkg-config, NASM, and shared native dependencies. The setuptools build command extracts and patches libass, stages `native/meson.build` and its sources, and lets Meson build the entire extension against the exact build interpreter. This avoids mixing MinGW and MSVC compilation within the extension. Fontconfig is disabled; DirectWrite/GDI provides system font discovery.

`tools/collect_licenses.py` copies the build environment's native license directory into the distributions before wheel construction. Copied license files are ignored by Git. Wheels bundle only the DLLs/shared objects selected by the repair tool, not the build environment or fonts.

For local wheel builds, install `cibuildwheel==4.2.1` and run it from the repository root. Linux requires Docker or Podman; Windows requires the UCRT64 dependencies and PATH setup from the README. Select a single ABI with `CIBW_BUILD` when debugging. To use Podman on Linux, set `CIBW_CONTAINER_ENGINE=podman`.

```sh
python -m cibuildwheel --platform linux --output-dir wheelhouse
```

On Linux, run source-tree tests after building the extension:

```sh
python setup.py build_ext --inplace
python -m unittest discover -s tests -v
```

On Windows, test a repaired, installed wheel instead, from outside the checkout, so the extension is loaded with its bundled DLLs.
