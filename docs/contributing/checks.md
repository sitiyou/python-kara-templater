# Checks and documentation

Run linting, type checking, tests, documentation checks, and visual previews before opening a pull request. Every code change must pass Ruff, ty, and the relevant test suites.

## Standard check suite

From the checkout root, after installing the package and `checks` dependency group:

```sh
uv run ruff check .
uv run ty check
uv run python -m pytest
uv run python -m tools.check_scene_types
uv run python -m tools.check_docs
```

Ruff and ty are pinned in [pyproject.toml](../../pyproject.toml). Public functions and methods require complete parameter and return annotations, and public type inference must not leak `Any` or `Unknown` (verified by `tests/test_typing.py` and `tests/typing/`).

`tools.check_scene_types` runs negative typing fixtures that must fail with an `invalid-argument-type` diagnostic. A broken import is not accepted as evidence that a type contract works.

## Choosing a test run

Use `uv run python -m pytest` during day-to-day work. Its default `testpaths` in [pyproject.toml](../../pyproject.toml) exercise ASS parsing, fonts, lyric sources, structured lyrics, progress curves, lyric layout, orchestration, the CLI preset, effect parameters, raster compositing, and GPU scenes. Pass a file or node ID to focus on one feature.

Before a release or large refactor, run the full suite:

```sh
uv run python -m pytest tests
```

An explicit directory overrides `testpaths` and runs every regression, example, typing, and documentation test.

### Writing effective tests

Test retained behavior: source and owner preservation, timing and transforms, shape selection, material semantics, diagnostics, budgets, deterministic seeking, and rendered output where it matters. Use focused independent references for geometry and color checks. Store test baselines under `tests/fixtures/` and test fonts with their license files under `tests/fonts/`.

Documentation tests (`tests/test_documentation.py`) execute complete author-facing scripts directly. Avoid coupling tests to historical plans, incidental headings, or implementation snapshots. When you replace a public interface, migrate behavior checks to the replacement and remove tests whose only purpose was the discarded syntax.

## Arch package checks

The [AUR package check script](https://aur.archlinux.org/cgit/aur.git/tree/check-core.sh?h=python-kara-templater) installs the built wheel outside the source tree and runs the default core test suite plus CLI and Hook export checks inside a 30-second wall-clock budget (after native compilation finishes). A timeout fails the package build.

| Test group | What it verifies | Where it runs |
| --- | --- | --- |
| Package core | Font selection and native shaping, ASS timing import, structured ruby and cue placement, row allocation, CPU raster round trip, seekable GPU draw preparation, installed CLI, and standalone Hook export | AUR |
| Rendering regressions | Curve accuracy between frames, pixel coverage of sweeps and outlines, combinations of effects, clocks, and fonts, and real Hook playback when Vulkan is available | Upstream suite |
| Developer and release checks | Documentation scripts and links, public typing, standalone native metrics, wheel metadata, and bundled libraries | Upstream tests and release tooling |

To reassess runtime cost before a release, profile the full suite against an installed wheel:

```sh
python -m pytest tests --durations=30 --junitxml=timings.xml
```

Inspect both the slowest individual cases and the sum of case times per module; the effect catalog can be expensive in aggregate even when single presets finish quickly.

## Reference and links

The [API reference](../reference/README.md) is committed Markdown generated from `kara_templater.__all__`, runtime signatures, dataclass fields, and English docstrings. Regenerate and check it whenever you change a public contract:

```sh
uv run python -m tools.generate_reference
uv run python -m tools.generate_reference --check
```

`tools.check_docs` verifies:

- Local file links and Markdown heading anchors across `README.md`, `skills/kara-templater/SKILL.md`, and `docs/`.
- Bilingual parity between English pages in `docs/` and Chinese counterparts in `docs/zh-cn/` (excluding the generated English-only `docs/reference/`).
- Python syntax in every non-reference `python` code block.
- Exact match between committed `docs/reference/*.md` files and `tools.generate_reference`.

`tools.check_docs` also runs against installed package sources during isolated wheel checks. Signatures alone are never enough: document units, state composition, defaults, exceptions, and limits in the owning API docstring and user guide.

## Visual previews

For shader changes, check the scene in WebGL 2 with `scene.preview()` and render the `.hook` over the intended background with FFmpeg. If a gallery demo changes, also scrub its browser preview. [Preview and export](../output/README.md) · [Play and render a Hook](../output/hook.md) · [Documentation site](documentation-site.md)

### ASS gallery GIFs

`tools.render_gallery` compiles `examples/scene_cues.py` to ASS, rasterizes events with the package CPU preview, and streams frames to FFmpeg to produce an animated GIF:

```sh
uv run python -m tools.render_gallery --case word-backgrounds
```

Run it from a checkout with FFmpeg and the `checks` dependencies installed. It writes the exported ASS, copied preview fonts, and a SHA-256 provenance `report.json` under `build/gallery/`, and updates `docs/examples/assets/word-backgrounds.gif`. Pass `--output` or `--assets` for local experiments without overwriting tracked media (`--width`, `--fps`, and `--duration` are also configurable). Historical GIFs from the retired sampled ASS exporter are not regenerated by this tool.

### ASS playback and seek validation

For continuous-playback and seek checks of a fixed ASS example through FFmpeg's `ass` filter (`libass`):

```sh
uv run python -m tools.validate_scene_core --scene cues build/preview-cues
```

`--scene` accepts `cues` (default) or `native-tween`. The tool writes the exported ASS, a timestamped contact sheet PNG, and a JSON report comparing continuous 50 fps playback against fresh seeks into the requested ignored `build/` directory. It checks one fixed example in the configured preview environment rather than proving identical rendering in every player.

For Studio frame comparisons, match the measured font em on both renderers before registering images at rest, and keep one fixed registration for the line; see [Choose and register fonts](../guides/fonts.md). Track only curated preview media under `docs/examples/assets/` and keep generated reports under `build/`.

## Next steps

- [Write and build the documentation site](documentation-site.md)
- [Build and validate a release](releasing.md)
- [Architecture](architecture.md)
