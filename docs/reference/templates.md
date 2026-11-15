# Python templates

The explicit ASS Python-template frontend and preserved millisecond preprocessing contexts. Ordinary Document loading does not execute templates. See [templates](../guides/templates.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Engine](#engine)
- [LegacyLine](#legacyline)
- [LegacySyllable](#legacysyllable)
- [TemplateError](#templateerror)
- [apply_templates](#apply_templates)
- [preprocess](#preprocess)
- [split_karaoke](#split_karaoke)

## Engine

The explicit Python ASS-template frontend.

to_scene prepares source-mapped NativeEvents; apply compiles them while
retaining template helper and preprocessing behavior.

[Source](../../kara_templater/engine.py#L293)

```python
Engine(
    *,
    max_iterations: int = 10000,
    max_output_lines: int = 100000,
    video_size: tuple[int, int] | None = None,
    owner: str = 'legacy-templates',
    budget: SceneBudget | None = None,
)
```

### Engine.apply

Execute templates and compile their Scene to a new Document with the configured budget.

```python
Engine.apply(
    document: Document,
) -> Document
```

### Engine.to_scene

Execute trusted legacy templates explicitly and return a composable scene.

```python
Engine.to_scene(
    document: Document,
) -> Scene
```

## LegacyLine

Line carrying the v0.1.0 preprocessing attributes (times in milliseconds).

[Source](../../kara_templater/_legacy_layout.py#L54)

```python
LegacyLine(
    text: str = '',
    start_time: float = 0,
    end_time: float = 0,
    style: str = 'Default',
    actor: str = '',
    layer: int = 0,
    margin_l: int = 0,
    margin_r: int = 0,
    margin_v: int = 0,
    effect: str = '',
    comment: bool = False,
    fields: dict[str, str] = _HAS_DEFAULT_FACTORY_CLASS(),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `str` | `''` |
| `start_time` | `float` | `0` |
| `end_time` | `float` | `0` |
| `style` | `str` | `'Default'` |
| `actor` | `str` | `''` |
| `layer` | `int` | `0` |
| `margin_l` | `int` | `0` |
| `margin_r` | `int` | `0` |
| `margin_v` | `int` | `0` |
| `effect` | `str` | `''` |
| `comment` | `bool` | `False` |
| `fields` | `dict[str, str]` | `dict()` |

### LegacyLine.margin_b

Template-facing bottom-margin alias using the event vertical margin.

Type: `int`.

### LegacyLine.margin_t

Template-facing top-margin alias using the event vertical margin.

Type: `int`.

### LegacyLine.serialize

Serialize this Dialogue or Comment in its preserved event field order.

```python
LegacyLine.serialize() -> str
```

## LegacySyllable

Template syllable or reading context with millisecond timing, measured text bounds, source links, and repeated highlights.

These fields retain the explicit Python-template frontend semantics.

[Source](../../kara_templater/_legacy_layout.py#L19)

Supports standard dict construction and attribute access to stored keys.

Example: `LegacySyllable(res_x=1280, res_y=720)`.

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `res_x` | `int` | `instance attribute` |
| `res_y` | `int` | `instance attribute` |
| `video_x_correct_factor` | `float` | `instance attribute` |
| `text` | `str` | `instance attribute` |
| `text_stripped` | `str` | `instance attribute` |
| `text_spacestripped` | `str` | `instance attribute` |
| `prespace` | `str` | `instance attribute` |
| `postspace` | `str` | `instance attribute` |
| `tag` | `str` | `instance attribute` |
| `start_time` | `float` | `instance attribute` |
| `end_time` | `float` | `instance attribute` |
| `duration` | `float` | `instance attribute` |
| `kdur` | `float` | `instance attribute` |
| `i` | `int` | `instance attribute` |
| `inline_fx` | `str` | `instance attribute` |
| `highlights` | `list[LegacyHighlight]` | `instance attribute` |
| `furi` | `list[LegacySyllable]` | `instance attribute` |
| `isfuri` | `bool` | `instance attribute` |
| `isbreak` | `bool` | `instance attribute` |
| `spillback` | `bool` | `instance attribute` |
| `syl` | `LegacySyllable` | `instance attribute` |
| `line` | `LegacyLine` | `instance attribute` |
| `style` | `Style` | `instance attribute` |
| `width` | `float` | `instance attribute` |
| `height` | `float` | `instance attribute` |
| `left` | `float` | `instance attribute` |
| `center` | `float` | `instance attribute` |
| `right` | `float` | `instance attribute` |
| `prespacewidth` | `float` | `instance attribute` |
| `postspacewidth` | `float` | `instance attribute` |

## TemplateError

A malformed or invalid Python-template declaration with event context.

It is raised during explicit template parsing or execution, not ordinary
Document loading.

[Source](../../kara_templater/engine.py#L22)

Construction: `TemplateError(*args)` using the inherited exception constructor.

## apply_templates

Apply trusted v0.1.0 Python templates through the shared ASS compiler.

[Source](../../kara_templater/engine.py#L684)

```python
apply_templates(
    document: Document,
    *,
    max_iterations: int = 10000,
    max_output_lines: int = 100000,
    video_size: tuple[int, int] | None = None,
    owner: str = 'legacy-templates',
    budget: SceneBudget | None = None,
) -> Document
```

## preprocess

Mutate the existing event, adding the historical typed layout view.

LegacyLine adds no slots or constructor state; promotion retains identity for
templates that store references to the source or its syllables.

[Source](../../kara_templater/_legacy_layout.py#L259)

```python
preprocess(
    source: Line,
    styles: dict[str, Style],
    meta: Record,
) -> LegacyLine
```

## split_karaoke

Split template text into its syllable and ruby contexts using the preserved karaoke notation.

Timing values in the resulting contexts are milliseconds.

[Source](../../kara_templater/_legacy_layout.py#L143)

```python
split_karaoke(
    text: str,
) -> tuple[list[LegacySyllable], list[LegacySyllable]]
```
