# Raster previews

Raster preview capability errors and display windows in absolute milliseconds.

Related guides: [Play and render a Hook](../output/hook.md) · [All public symbols](README.md#symbol-index)

## Contents

**Classes:** [`DisplayWindow`](#displaywindow) · [`OutputCapabilityError`](#outputcapabilityerror)

## DisplayWindow

*dataclass* · [Source](../../kara_templater/_raster.py#L43)

An absolute millisecond visibility interval independent of lyric timing.

Animation padding changes this window rather than lyric segment clocks.

```python
DisplayWindow(
    start_ms: int,
    end_ms: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `int` | `required` |
| `end_ms` | `int` | `required` |

## OutputCapabilityError

*exception* · [Source](../../kara_templater/_raster.py#L17)

An output failure with optional source and absolute-time context.

```python
OutputCapabilityError(
    message: str,
    *,
    origin: EventOrigin | None = None,
    time_ms: float | None = None,
)
```
