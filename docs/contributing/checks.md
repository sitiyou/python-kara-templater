# Checks and documentation

Run checks from the checkout root after installing the package and check tools:

```sh
uv run ruff check .
uv run ty check
uv run python -m pytest
uv run python -m tools.check_scene_types
uv run python -m tools.check_docs
```

Ruff and ty are pinned in pyproject.toml. Public functions and methods need full
parameter/return annotations, and public inference must not expose Any/Unknown.
Typing fixtures include valid custom extensions and deliberately rejected calls.
The negative extension checker requires an argument-contract error; a broken
import is not evidence that a type contract works.

## Effective tests

Test retained behavior: source/owner preservation, timing and transforms, shape
selection, material semantics, diagnostics, budgets, deterministic seeking, and
actual output where necessary. Use focused independent references for meaningful
geometry/color checks. Keep baselines under tests/fixtures and font resources
with their licenses under tests/fonts.

Documentation tests execute complete author-facing scripts. Avoid coupling tests
to historical plans, incidental heading text, or implementation snapshots.
When an interface is removed, migrate useful behavior checks to its replacement
and remove tests whose only purpose was the discarded declaration syntax.

## Arch package checks

The [AUR package's core check](https://aur.archlinux.org/cgit/aur.git/tree/check-core.sh?h=python-kara-templater)
installs the built wheel outside the source tree. Its 30-second wall-clock budget
includes environment setup, pytest startup and both output commands. A timeout
fails the build. Native compilation runs before this budget starts.

| Test group | What it verifies | Where it runs |
| --- | --- | --- |
| Package core | Font selection and native shaping, ASS timing import, structured ruby and cue placement, row allocation, libass raster round trip, seekable GPU draw preparation, installed CLI and standalone hook export | AUR |
| Rendering regressions | Curve accuracy between frames, pixel coverage of sweeps and outlines, combinations of effects, clocks and fonts, actual hook playback when Vulkan is available | Upstream suite |
| Developer and release checks | Documentation scripts and links, public typing, native source-cache invalidation, wheel metadata and bundled libraries | Upstream tests and release tooling |

The upstream suite also exercises the core behaviors. AUR selects individual
test IDs so adding an effect or a parameter combination does not silently
increase package build time. Keep one representative case per package failure
mode. For example, the installed CLI smoke checks the entry point once. CLI
regressions for repeated exports and ownership still belong upstream.

To reassess cost on a new release, run the full installed-package suite with
`python -m pytest tests --durations=30 --junitxml=timings.xml`. Inspect both
the slowest cases and the sum of case times per module. The effect catalog can
be costly in aggregate even when each preset finishes quickly.

## Reference and links

The API reference is committed Markdown for GitHub reading. Its generator derives
signatures, fields, and public members from the final code and docstrings.
Regenerate after changing a public contract and inspect the resulting prose and
links:

```sh
uv run python -m tools.generate_reference
uv run python -m tools.generate_reference --check
```

`tools.check_docs` checks local file/heading links, non-reference Python snippet
syntax, and exact generated reference content. It also works against installed
package source during isolated distribution tests.
Signatures alone are insufficient: document units, state composition, defaults,
exceptions, and supported limits in the owning API/guide.

## Visual previews

```sh
uv run python -m tools.render_gallery
uv run python -m tools.validate_scene_core --scene sweep build/preview-sweep
```

The gallery saves actual ASS before rendering the tracked GIFs. Its ignored report
records source/ASS/GIF hashes and fonts. Full visual validators write reports and
artifacts to an explicit ignored build directory. Include only curated preview
media in user documentation, not iterative validation histories.

See [release builds](releasing.md) for clean-source and installed-package checks.


For Studio frame comparisons, match the measured font em on both renderers
before registering images at rest. Use one fixed registration for the line.
For sampled ASS also compare against the reference at the emitted interval’s
midpoint. A separate comparison at the playback timestamp measures the
visible sampling error. See [font sizing](../guides/fonts-and-preview.md#match-a-karaoke-studio-font-size).
