# Objects, groups, and coordinates

A Scene combines a Document with TextObject, PathObject, ObjectGroup, and
already-lowered AssDialogue values. Visual objects are dataclasses: use
`dataclasses.replace` to create an edited value and `scene.add(...)` to compose it.
Object identities must be unique within a Scene, including group descendants.

## State and coordinates

VisualState contains position, scale, rotation, skew, opacity, fill, outline,
border, blur, and shadow. Distances use script pixels in Document PlayRes; angles
use degrees and opacity uses 0 through 1. Screen x increases rightward and y
downward. TextObject.alignment follows the ASS 1–9 alignment convention.

A group's children use local coordinates. Parent transforms compose with child
transforms, so putting a background and its text in one group makes both follow
the group. A group's origin is the pivot of its transform; grouping does not
silently recenter children. Author local geometry around the intended pivot.
`VectorPath.rectangle` starts at (0, 0); a circle is centered around the origin.

Text positions are alignment anchors. Layout boxes, glyph outlines, and blurred
ink bounds describe different things. A border or glow does not enlarge the
text's advance. Use measured range backgrounds or path bounds for the task at
hand, rather than estimating text width from character count.

## Lifetimes and copies

Lifetime is an absolute, half-open interval `[start, end)` in seconds, with
`0 <= start < end`. A child's visibility is also clipped by ancestor lifetimes.
An AnimationClip starts relative to its owning object's birth.

`object.copy(id=..., delay=..., offset=...)` makes a reusable variant. Group
copies remap descendant identities and internal references. Keep identities
unique when adding original and copied objects. A delayed copy preserves its
local animation clock. External coverage bindings are keyed by identity and
must be remapped if their objects are renamed or copied.

To query a node with parent transforms and references applied, use the Scene's
`evaluator()`. Calling an object's `at(time)` evaluates its own local animation;
it is not a substitute for world-space evaluation of an entire hierarchy.

## Native ASS and lowering

AssDialogue inserts an already-lowered Dialogue into the same compilation
pipeline. It preserves its ASS text and timing, including events with zero duration. Source origins remain
available on the node and output result.

Rotations, mirroring, and skew can require geometry lowering. Some text
transforms become glyph paths instead of font-rendered text. Inspect AssObjectReport
strategy and geometry budgets to understand the resulting cost. Clip spaces and
shared masks are explained in [geometry](geometry.md).

Group opacity multiplies each drawing layer. For post-composite alpha over the
whole group, explicitly choose [raster or coverage composition](materials.md).
