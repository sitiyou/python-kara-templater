# Scene objects and groups

Build and compose text, vector paths and groups inside a Scene, inspect their world-space state and create reusable copies. Use this guide when adding custom visuals alongside or instead of lyric tracks.

## Build objects and add them to a Scene

A `Scene` wraps a `Document` and holds four kinds of entries: `TextObject`, `PathObject`, `ObjectGroup` and `AssDialogue`. Every object ID must be unique across the entire `Scene`, including descendants inside groups.

```python
from kara_templater import (
    Color,
    Document,
    FadeIn,
    Lifetime,
    ObjectGroup,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)

badge = ObjectGroup(
    id="badge",
    lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(320, 180)),
    children=(
        PathObject(
            id="badge/bg",
            lifetime=Lifetime(0, 3),
            path=VectorPath.rectangle(260, 84),
            state=VisualState(position=Vec2(-130, -42), fill=Color.hex("#2A2245")),
        ),
        TextObject(
            id="badge/label",
            text="Chorus",
            font_size=44,
            alignment=5,
            lifetime=Lifetime(0, 3),
            state=VisualState(fill=Color.hex("#FFE08A")),
        ),
    ),
).animate(FadeIn(), duration=0.4)

scene = Scene(Document.create(width=640, height=360)).add(badge)
scene.export("badge.hook")
```

Keep these practical details in mind when building objects:

- **Immutable values**: Visual objects are frozen dataclasses. Use `dataclasses.replace(...)` or `.animate(...)` to produce modified variants without mutating the original.
- **Literal text**: `TextObject.text` renders literal Unicode. Braces `{}` and backslashes `\` appear as characters rather than ASS override tags, and `\n` inserts a line break.
- **Outline-only and scaled borders**: Set `filled=False` on `TextObject` or `PathObject` to draw only its stroke. By default, border widths stay fixed in script pixels when an object scales; set `scale_border=True` to scale the border along with the shape.

Coordinates use script pixels (document `PlayRes`), angles use clockwise degrees, opacity uses `0..1`, `TextObject.alignment` uses the ASS 1–9 keypad layout, and `Lifetime(start, end)` is a half-open interval in seconds. See [Core concepts](../concepts.md) for the full coordinate and lifetime model.

## Group hierarchies and pivots

An `ObjectGroup` establishes a local coordinate system for its children. Parent transforms (`position`, `scale`, `rotation`, `skew`) compose onto every descendant, so grouping a background plate with its label moves and scales them together.

A group's `(0, 0)` origin is its transform pivot. Grouping never recentres children automatically, so author child geometry around the intended pivot:

- `VectorPath.rectangle(width, height)` starts at `(0, 0)` and extends right and down (offset it by `Vec2(-width / 2, -height / 2)` to centre it, as in the badge above).
- `VectorPath.circle(radius)` is already centred at `(0, 0)`.

Three inheritance rules prevent common surprises:

1. **Lifetimes intersect**: A child is only visible while both its own lifetime and every ancestor's lifetime are active, while its local animation clock still runs from its own `time_origin`.
2. **Opacity multiplies per child**: Group `opacity` multiplies each child drawing independently; it does not flatten the group onto an offscreen buffer first.
3. **Paint is not inherited**: Setting `fill`, `outline` or `material` on an `ObjectGroup` does not recolour its children. Style each child directly.

When sizing backgrounds or aligning decorations to text, remember that `TextObject` positions are alignment anchors, and borders or glows do not enlarge layout advance. Measure actual text bounds with `text_extents`, `outline_text` or `line.layout` instead of estimating width from character counts.

## Copy objects and evaluate world state

Call `copy(id=..., offset=..., delay=...)` on any `TextObject`, `PathObject`, `ObjectGroup` or `LyricLine` to create a shifted variant with a unique ID:

```python
second = badge.copy(id="badge-2", offset=Vec2(0, 100), delay=0.5)
```

A delayed copy shifts both its `lifetime` and any explicit `clock_start`, so local animations play identically at the new time. Copying an `ObjectGroup` automatically renames all descendant IDs and remaps internal `StateReference` links (such as `FollowObject`) inside the copied subtree.

To inspect an object's final world-space state at a given timestamp, use `scene.evaluator()`:

```python
evaluator = scene.evaluator()
world_state = evaluator.at("badge/label", 0.2)
```

`evaluator.at(id, time)` applies parent group transforms and resolves references. Calling `node.at(time)` directly only evaluates that node's own local animation, ignoring parents and references.

## Mix in existing ASS dialogue

Use `AssDialogue(id=..., event=Line(...), origin=...)` to pass an already-authored ASS `Line` straight through the same `Scene` pipeline. It keeps its raw ASS text and timestamps (including zero-duration events) and preserves source origin metadata.

When replacing existing lines from a `Document` during ASS export, call `scene.replace_source(record_index)` so the original record is kept as a `Comment` rather than duplicated.

For ASS export strategies, geometry budgets and `AssObjectReport`, see [Export standard ASS](../output/ass.md).

## Next steps

- Review coordinate spaces, alignment and time units in [Core concepts](../concepts.md).
- Draw custom vector shapes, extrusions and masks in [Shapes, clips and masks](geometry.md).
- Animate objects with clips and timelines in [Animation and timing](animation.md).
- Link objects with delayed copies and references in [Particles, copies and echoes](particles.md).
