# Contribute

Set up a local build, verify changes, and navigate the kara-templater codebase. Start here before editing library modules, documentation, or release configuration.

## Quick check

Install the package and check tools using [Set up a development environment](setup.md). From the checkout root, confirm your environment passes linting, type checking, core tests, and documentation checks:

```sh
uv run ruff check .
uv run ty check
uv run python -m pytest
uv run python -m tools.check_scene_types
uv run python -m tools.check_docs
```

## Verify visual changes

When you change an effect or rendering path, export a short representative lyric as a Hook and inspect both sides of every timing boundary the change touches. For example, check before and after a note handoff whenever you modify karaoke sweeps. Add a focused regression test if the existing suite does not cover that boundary. See [Checks and documentation](checks.md) for test selection and preview commands.

## Contributor map

| Goal | Guide |
| --- | --- |
| Install Python, C++, Rust, and font prerequisites | [Set up a development environment](setup.md) |
| Find where lyrics, scenes, and exporters live | [Architecture](architecture.md) |
| Run checks, tests, reference generation, and previews | [Checks and documentation](checks.md) |
| Write bilingual docs, add gallery demos, and build the site | [Write and build the documentation site](documentation-site.md) |
| Build wheels, run isolated checks, and publish a release | [Build and validate a release](releasing.md) |

## Next steps

- [Set up a development environment](setup.md)
- [Architecture](architecture.md)
- [Checks and documentation](checks.md)
