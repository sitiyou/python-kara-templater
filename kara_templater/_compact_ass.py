"""Lower simple catalog lyrics to native ASS karaoke for compact playback."""

from dataclasses import replace
from math import ceil, floor
from urllib.parse import quote

from .ass import Document, Line
from .composition import Color
from .import_ass import source_prefix
from .orchestration import LinePlan, LyricScene
from .scene import NativeEvent, Scene
from .scene_animation import VisualState
from .scene_lyrics import _reading_intervals
from .scene_output import SceneBudget, _color, _number
from .scene_text import DocumentLayout

type _Knots = tuple[tuple[float, float], ...]


def _karaoke_clock(on: int, off: int, distance: float, width: float) -> int:
    return on + round((off - on) * min(1, max(0, distance / width)))


def _mix(a: Color, b: Color, weight: float) -> Color:
    return Color(
        round(a.red + (b.red - a.red) * weight),
        round(a.green + (b.green - a.green) * weight),
        round(a.blue + (b.blue - a.blue) * weight),
    )


def _wipe_clip(
    offsets: tuple[float | None, float | None],
    on: int,
    off: int,
    left: float,
    right: float,
    ink_left: float,
    ink_right: float,
    wipe: bool,
    knots: _Knots,
) -> str:
    """Complementary native rectangular clips, including ink outside the advance."""

    def rect(x: float) -> str:
        a, b = offsets
        x1 = -65536 if a is None else round(x + a)
        x2 = 65536 if b is None else round(x + b)
        return rf"\clip({x1},-65536,{x2},65536)"

    first, last = floor(min(left, ink_left)), ceil(max(right, ink_right))
    if not wipe or off == on:
        return rect(last) if on == 0 else rect(first) + rf"\t({on},{on},{rect(last)})"
    travel = (rect(first) + rf"\t({max(0, on - 20)},{on},{rect(round(left))})"
              if on else rect(round(left)))
    previous = on
    for t, progress in knots:
        ms = on + round((off - on) * t)
        boundary = rect(round(left + (right - left) * progress))
        if ms == 0:
            # ASS interprets a transform ending at zero relative to the event end.
            travel = boundary
        else:
            travel += rf"\t({previous},{ms},{boundary})"
        previous = ms
    return travel + rf"\t({off},{off + 20},{rect(last)})"


def _events(plan: LinePlan, original: Line) -> tuple[Line, ...] | None:
    line = plan.line
    paint = line._karaoke_paint
    body = line.layout.body
    curves: dict[int, _Knots] = {}
    if line.layout.ruby:
        if paint is None or paint.sung_outline is None:
            return None
        for unit in line.layout.lyrics.units:
            spans = unit._body_singing()
            if len(spans) == 1 and (duration := spans[0].end - spans[0].start) > 0:
                curves[unit.start] = tuple(((s.end - spans[0].start) / duration, b)
                                           for s, _, b in unit._body_parts())
        body = replace(
            body,
            singing=tuple(
                span
                for unit in line.layout.lyrics.units
                for span in unit._body_singing()
            ),
        )
    rows: list[Line] = []
    layouts = [body]
    if paint:
        for reading in line.layout.ruby:
            unit = line.layout.lyrics.units[reading.unit_index]
            layouts.append(replace(reading.layout, singing=_reading_intervals(reading, unit, wipe=paint.wipe)))
    for layout in layouts:
        result = _layout_events(plan, original, layout, curves if layout is body else {})
        if result is None:
            return None
        rows.extend(result)
    return tuple(rows)


def _layout_events(
    plan: LinePlan, original: Line, body: DocumentLayout, curves: dict[int, _Knots]
) -> tuple[Line, ...] | None:
    line = plan.line
    paint = line._karaoke_paint
    if (
        paint is None
        or not body.characters
        or any(m.offset and m.placement == "inline" for m in body.source.cues)
        or len({r.appearance for r in body.source.runs}) != 1
        or line.state != VisualState(position=line.state.position)
    ):
        return None
    text = body.source.text
    if any(c in text for c in "\n\\{}"):
        return None
    start = round(line.lifetime.start * 100)
    end = round(line.lifetime.end * 100)
    cursor = start
    offset = 0
    pieces = []
    positioned: list[tuple[str, VisualState]] = []
    dual = paint.sung_outline is not None
    split = dual or body._studio_spacing or any(c._gap_shift for c in body.characters)
    for span in body.singing:
        if span.start_offset == span.end_offset:
            continue
        on, off = round(span.start * 100), round(span.end * 100)
        if span.start_offset != offset or on < cursor or off > end:
            return None
        if not paint.wipe:
            on = off
        if cursor < on:
            pieces.append(rf"{{\k{on - cursor}}}")
        tag = "kf" if paint.wipe else "k"
        pieces.append(rf"{{\{tag}{off - on}}}" + text[offset : span.end_offset])
        if split:
            clusters = [
                c
                for c in body.characters
                if offset <= c.start and c.end <= span.end_offset
            ]
            if (
                not clusters
                or clusters[0].start != offset
                or clusters[-1].end != span.end_offset
            ):
                return None
            for i, c in enumerate(clusters):
                if c.object.text.isspace():
                    continue
                extent = body._sweep_bounds(offset, span.end_offset, c)
                if not extent.width:
                    return None
                if dual:
                    ink = c.ink_bounds or c.bounds
                    dx = line.state.position.x
                    pad = c.object.state.border + abs(c.object.state.shadow.x) + 2
                    width = paint.feather if paint.wipe and off > on else 0
                    steps = min(8, ceil(width / 3))
                    boundaries = (
                        [width * (j / steps - 0.5) for j in range(steps + 1)]
                        if steps
                        else [0.0]
                    )
                    edges = [None, *boundaries, None]
                    for j, offsets in enumerate(zip(edges, edges[1:], strict=False)):
                        clip = _wipe_clip(
                            offsets,
                            (on - start) * 10,
                            (off - start) * 10,
                            extent.left + dx,
                            extent.right + dx,
                            min(ink.left + dx - pad, extent.left + dx) - width / 2,
                            max(ink.right + dx + pad, extent.right + dx) + width / 2,
                            paint.wipe,
                            curves.get(offset, ((1, 1),)),
                        )
                        fraction = (
                            1.0
                            if j == 0
                            else 0.0
                            if j > steps
                            else 1 - (j - 0.5) / steps
                        )
                        weight = fraction * fraction * (3 - 2 * fraction)
                        fill = _mix(paint.unsung, paint.sung, weight)
                        outline = _mix(
                            paint.unsung_outline or c.object.state.outline,
                            paint.sung_outline or c.object.state.outline,
                            weight,
                        )
                        overrides = rf"{{{clip}\1c{_color(fill)}\3c{_color(outline)}}}"
                        positioned.append((overrides + c.object.text, c.object.state))
                    continue
                left = c.bounds.left - extent.left
                right = extent.width
                if i + 1 < len(clusters):
                    after = clusters[i + 1]
                    right = (
                        after.bounds.left
                        - after._gap_shift
                        + c._gap_shift
                        - extent.left
                    )
                begin = (
                    _karaoke_clock(on, off, left, extent.width) if paint.wipe else on
                )
                finish = (
                    _karaoke_clock(on, off, right, extent.width) if paint.wipe else off
                )
                timed = (
                    rf"{{\k{begin - start}}}{{\{tag}{finish - begin}}}" + c.object.text
                )
                positioned.append((timed, c.object.state))
        cursor, offset = off, span.end_offset
    if offset != len(text):
        return None
    glyph = body.characters[0].object

    def event(content: str, state: VisualState) -> Line:
        pos = line.state.position + state.position
        prefix = (
            rf"{{\an7\q2\pos({_number(pos.x)},{_number(pos.y)})"
            rf"\fn{glyph.font}\fs{_number(glyph.font_size)}\b{int(glyph.bold)}\i{int(glyph.italic)}"
            rf"\fe{glyph.encoding}\fsp{_number(glyph.spacing)}"
            rf"\fscx{_number(100 * state.scale.x)}\fscy{_number(100 * state.scale.y)}"
            rf"\bord{_number(state.border)}\xshad{_number(state.shadow.x)}\yshad{_number(state.shadow.y)}"
            rf"\1c{_color(paint.sung)}\2c{_color(paint.unsung)}\3c{_color(paint.unsung_outline or state.outline)}"
            rf"\fad({round(1000 * paint.entry)},{round(1000 * paint.exit)})}}"
        )
        return replace(
            original,
            comment=False,
            effect=plan.source.effect,
            start_time=start * 10,
            end_time=end * 10,
            text=prefix + content,
        )

    if split:
        return tuple(event(content, state) for content, state in positioned)
    return (event("".join(pieces), glyph.state),)


def compact_document(scene: LyricScene, budget: SceneBudget) -> Document:
    output = Scene(
        scene.document, owner=scene.owner, replace_records=set(scene.replace_records)
    )
    plans = {id(plan.line): plan for plan in scene.plans}
    for obj in scene.objects:
        plan = plans.get(id(obj))
        if plan is None:
            output.add(obj)
            continue
        index = plan.source.record_index
        original = (
            Line(style=plan.source.style)
            if index is None
            else scene.document.records[index]
        )
        assert isinstance(original, Line)
        rows = _events(plan, original)
        if rows is None:
            output.add(obj)
            continue
        for i, row in enumerate(rows):
            output.add(
                NativeEvent(
                    id=f"{plan.line.id}/compact:{i}", event=row, origin=plan.line.origin
                )
            )
        cues = {target.node_id for target in plan.line.query("cue")}
        children = tuple(child for child in plan.line.children if child.id in cues)
        if children:
            output.add(
                replace(
                    plan.line,
                    id=plan.line.id + "/inline",
                    children=children,
                    animations=(),
                )
            )
    doc = output.compile(native_tweens=True, budget=budget).document
    prefixes = (
        source_prefix(scene.owner),
        f"kara:scene:v1:{quote(scene.owner, safe='')}:",
    )
    doc.records = [
        r
        for r in doc.records
        if not (isinstance(r, Line) and r.comment and r.effect.startswith(prefixes))
    ]
    return doc
