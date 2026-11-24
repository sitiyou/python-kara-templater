# Raster previews

Raster preview capability errors and display windows in absolute milliseconds.

[All public symbols](README.md#symbol-index)

## Contents

- [DisplayWindow](#displaywindow)
- [OutputCapabilityError](#outputcapabilityerror)

## DisplayWindow

An absolute millisecond visibility interval independent of lyric timing.

Animation padding changes this window rather than lyric segment clocks.

[Source](../../kara_templater/_raster.py#L43)

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

An output failure with optional source and absolute-time context.

[Source](../../kara_templater/_raster.py#L17)

```python
OutputCapabilityError(
    message: str,
    *,
    origin: EventOrigin | None = None,
    time_ms: float | None = None,
)
```
