# ASS Python templates

The template frontend preserves the v0.1-style workflow:

```text
input ASS -> Document -> explicit template execution -> Scene -> standard ASS
```

It is independent of the Track authoring layer. Ordinary Document parsing does
not run templates. Engine.to_scene prepares composable NativeEvents, allowing
template output and custom objects to share Scene compilation and budgets.

## Execute explicitly

```python
from kara_templater import Document, apply_templates

source = Document.load("input.ass")
output = apply_templates(source)
output.save("output.ass")
```

For composition, call `Engine().to_scene(source)`, add your Scene objects, and
compile. Use `kara-templater input.ass output.ass --templates` for the CLI. A
stable owner identifies generated content when applying again.

## Template input

Templates are Comment events whose Effect field starts with template or code.
Modifiers select line, syllable, character, ruby, loop, style, and text-retention
behavior. Text templates expand $variables and !Python expressions!; code
comments and expression helpers run in the template context. This is the
project's Python template dialect, not an Aegisub Lua interpreter.

Template execution is an explicit Python execution step; use trusted template
input. It is not triggered by ordinary file loading or new authoring APIs.
The resulting Dialogue uses standard ASS tags rather than a runtime Python DSL.

Template line/syllable contexts expose millisecond timing, layout, colors, and
helper functions. The preserved preprocess and split_karaoke helpers retain
this frontend's source semantics, including ruby and repeated highlights.
The general Scene lifetime model uses seconds and requires positive lifetimes;
NativeEvent retains already-lowered template timing without forcing it into a
visual object's lifetime model.

See [scene_legacy.py](../../examples/scene_legacy.py) for a complete fixed
composition and the [template API reference](../reference/README.md) for the
public entry points. Invalid modifiers, malformed templates, and missing context
produce TemplateError with event information.

## Modes and modifiers

The first Effect token is `template` for a text declaration or `code` for Python
statements. Code defaults to once; text defaults to syl. A text template normally
appends the selected source text after its expanded declaration.

| Modifier | Behavior |
| --- | --- |
| `once` | Execute code once before source lines; code only |
| `line` | Apply in line context; named text fragments may share one line template |
| `pre-line` | Provide a text prefix before line/syllable expansion; text only |
| `syl`, `furi` | Select source syllables or readings |
| `char` | Expand using the preserved per-character template handling |
| `all` | Remove the template event's source-style restriction |
| `repeat N`, `loop N` | Repeat with the j/maxj iteration context |
| `notext` | Suppress automatic source-text append |
| `keeptags` | Retain the selected source override text when appending |
| `noblank` | Skip empty/blank selected text without changing source timing |
| `multi` | Expand repeated highlight intervals separately |
| `fx NAME` | Restrict to a selected inline-effect name |
| `fxgroup NAME` | Skip when the corresponding fxgroup dictionary value is False |

A text line template cannot combine line with syllable/reading modes. Invalid
combinations and missing modifier arguments raise TemplateError.

## Context and helpers

`$lstart`, `$lend`, `$ldur`, and line geometry variables expose line context;
`$sstart`, `$send`, `$sdur`, and syllable geometry expose the selected syllable.
Geometry is in script pixels. Syllable timing is relative to the original line;
line timing is absolute milliseconds. Code/expression context also includes
line, orgline, syl, basesyl, meta, styles, text_extents, math, random, and tenv.

| Helper | Purpose |
| --- | --- |
| `retime(mode, addstart=0, addend=0)` | Set the generated event interval; offsets are milliseconds, except sylpct offsets are percentages |
| `relayer(layer)` | Change the output layer |
| `restyle(name)` | Select an existing output style |
| `maxloop(count)`, `maxloops(count)` | Set maxj for the current repeated expansion |
| `loopctl(j, count)` | Set the current loop counter and limit |
| `remember(name, value, decorator=None)` | Store shared or decorated scope memory and return the value |
| `recall(name, default=None)` | Read stored memory with an optional default |
| `remember_if(...)` | Store only when the supplied condition is true |
| `remember_line`, `remember_syl`, `remember_basesyl` | Store values scoped to the corresponding context object |

retime modes are line, preline, postline, syl, presyl, postsyl, start2syl,
syl2end, sylpct, set, and abs. set/abs use absolute offsets from zero; the
syllable-relative modes require a current syllable. Helpers that modify the
output return an empty string so they can be used inside !expressions!.
Remember/recall helpers instead return their values.

For example, a Comment with Effect `template syl noblank` and this Text places
its automatically appended syllable at the measured center and uses that
syllable's singing interval:

```text
{\an5\pos($scenter,$smiddle)}!retime('syl', 0, 0)!
```

Engine iteration/output limits and SceneBudget bound template generation.
Repeated execution with a stable owner replaces that owner's generated events.
