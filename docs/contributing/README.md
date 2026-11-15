# Contributing

Keep the public authoring API typed, the examples readable, and the output
standard ASS. User documentation is English Markdown for direct GitHub reading.

- [Development setup](setup.md): native dependencies and installation.
- [Architecture](architecture.md): Document, frontends, Scene, and output semantics.
- [Checks and documentation](checks.md): tests, typing, reference generation, and previews.
- [Release builds](releasing.md): source archives, native wheels, and isolated validation.

Use ordinary functions and typed values for extension APIs. Public interfaces
must not leak Any/Unknown. Every new output strategy needs explicit semantics,
resource limits, and relevant behavior checks. Keep timing, source provenance,
and visual output distinct when designing a change.

Process plans, implementation logs, and generated verification reports belong
under ignored development/output paths. Track concise user contracts, meaningful
test fixtures, required fonts/licenses, and these long-lived contributor guides.
