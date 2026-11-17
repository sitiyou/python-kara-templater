# Inspecting karaoke timing frame by frame

The [eight studies](lyric-studies.md) are informed by reference videos, but a
video is not the source ASS. The following observations separate actual motion
from glow, distinguish different clocks, and correct two early interpretations.
They do not recover an author's original keyframes or easing formula.

## Sampling and uncertainty

The collection clips below are 1280×720 at 24000/1001 frames per second.
Frame numbers are zero-based; times are decoded presentation timestamps rounded
to milliseconds, not requested seek positions. Event onsets can generally only
be bracketed to one source frame, about 42 ms. A thresholded visible edge includes
stroke, blur, compression and fading. It is not an undecorated glyph metric.

## Emphasis can overlap the next singing unit

In [Falling & growing, P47](https://www.bilibili.com/video/BV1cp4y187Hv?p=47),
the first glyph is already on the baseline at frame 0. Its arrival therefore
cannot be measured completely from this clip. The next outlined copy descends
while the first glyph is still expanding.

| Phase | First glyph | Final word |
| --- | --- | --- |
| Approaching copy | Already arrived at 0 s | Descending at 4.421–4.671 s; on baseline near 4.713 s |
| Visible growth | 0–about 0.542 s | About 4.713–5.130/5.214 s |
| Broad maximum/overlap | About 0.542–0.667 s; next glyph already active | About 5.130–5.255 s |
| Release/dissolve | Smaller retained outline evident by about 0.792 s | Dissolving at 5.297–5.589 s |

The two visible growth phases are both around half a second. This is compatible
with a separate decoration clock, but does not prove fixed-duration animation:
the source singing intervals are unavailable and the last word is treated as a
unit. It is especially unsafe to infer duration from character count.

A color-threshold check of the first glyph's left strip, x=285..339 and
y=315..404, finds visible blue bounds expanding from approximately y=340..379
at frame 0 to y=326..393 around frames 13–15 (0.542–0.626 s). Higher thresholds
give tighter bounds. These numbers confirm expansion in the visible image,
**not** a font scale factor. An initial wider measurement region was rejected
because it included the next descending glyph. The release also mixes a fading
large drawing with a smaller retained outline, so a fitted geometric shrink
curve would be unjustified.

For authoring, keep two choices available: source-relative emphasis for the
requested L4TS behavior, and independently timed approach/echo decoration.
`ScalePulse(peak_at=0.42)` is a chosen smooth envelope; 0.42 is not a recovered
constant from P47. A 250 ms note and a 2 s note therefore get different pulse
durations in our source-relative example even though copied decoration can retain
an explicitly authored duration.

## Rising echoes can be close to constant speed

In [Pulse, P135](https://www.bilibili.com/video/BV1cp4y187Hv?p=135), the copies
rise continuously; they are not static offset glyphs that only fade.
For the first leading copy, a fixed x=310..359, y=180..339 region gives:

| Frame | Time (s) | Top visible y, grayscale threshold >200 |
| --- | --- | --- |
| 1 | 0.042 | 335 |
| 2 | 0.083 | 328 |
| 3 | 0.125 | 320 |
| 4 | 0.167 | 313 |
| 5 | 0.209 | 305 |
| 6 | 0.250 | 298 |
| 7 | 0.292 | 291 |
| 8 | 0.334 | 283 |

The fitted slope is about −178 source pixels/s, with a maximum residual below
one pixel. Thresholds 160 and 230 give similar slopes over this interval. After
that, the first copy fades below some thresholds and the measurement jumps to
another drawing; those samples must not be fitted as one trajectory. The final
word shows multiple rising copies and a separate blurred/ring decoration around
4.713–5.339 s.

The study now uses `DriftOut(scale=1, rate=linear_rate)` for rising copies. Its
distance, copy count and duration are illustrative, not an exact reconstruction.
Linear travel is appropriate here; it does not justify using a triangular linear
scale pulse for every singing emphasis.

## A stationary ornament is not a motion trail

In [Rainbow, P70](https://www.bilibili.com/video/BV1cp4y187Hv?p=70), many outlined
glyph copies arrive above the baseline. The dot arch behind them is a separate
ornament. The intensity-weighted center of its top dot stays at approximately
(639.5, 173.4) between sampled frames at 0.501, 1.001, 2.002, 3.003 and 4.004 s.
It cannot be used as evidence that dots were emitted from the moving copies.

The end of the clip contains **two different disappearance orders**:

- Text begins losing its leftmost glyphs around 4.630–4.796 s; progressively
  more text disappears from the left through roughly 5.7 s.
- The arch loses its right side sooner. In equal-sized left and right regions
  above the text, relative dot intensity is approximately 100%/67% at 5.172 s,
  77%/33% at 5.339 s, and 35%/1% at 5.506 s, normalized to 4.421 s.

The regions are x=400..519 and x=760..879, both y=200..319. Intensity is summed
above grayscale 130. Earlier measurements in those regions are contaminated by
incoming glyphs and are not used for the exit comparison. This corrects the
earlier blanket description of “reverse text disappearance”; the uploader's
title alone was insufficient evidence.

[Bezier collection P9](https://www.bilibili.com/video/BV1Ro4y197Lf?p=9) is a
supplemental curved-strand reference: frames around 0.5, 2 and 4 s show colored
arcs and line-like luminous paths. The updated curve study replaces independent
dots with `Ribbon`/`TrailPath`, which grows and retracts connected stroked path
segments. Its clocks and curve control points are chosen illustration parameters;
this does not recover the original template. The supplemental
[stationary-arch example](../../examples/lyric_ornament.py) separately demonstrates
P70’s opposing text/ornament exit order, with explicitly chosen clocks.

## Particle writing has a local preparation phase

In [ParticleWriting, P104](https://www.bilibili.com/video/BV1cp4y187Hv?p=104),
the opening glyph region initially contains turquoise strokes and particles.
White body text becomes evident around frames 8–9 (0.334–0.375 s), and the first
letter is clear around frame 12 (0.501 s). The next letter is becoming readable
around 1.043–1.210 s while particles from the first region persist.

This supports independent particle lifetimes and a local pre-reveal phase. It
does not prove that the author followed true handwriting stroke order or used a
simple horizontal clipping rectangle. Our particle-writing study uses a
horizontal reveal explicitly; it should not be presented as a reconstruction of
the reference's writing path.

## The particle emission area matters

In [Cherry blossoms, P121](https://www.bilibili.com/video/BV1cp4y187Hv?p=121),
petals are already distributed around still-unsung text in the opening frames.
The first character is still readable at 0.417–0.459 s and disappears around
0.501–0.542 s; petals remain and the next character becomes active. This combines
decoration across the line with per-character departure. The updated example
uses `LyricParticles(placement="line")` for this ambient field; the default
front emitter remains useful for shedding from the active sweep. Particle motion
and density are chosen parameters, not measured source settings.

In [Out, P56](https://www.bilibili.com/video/BV1cp4y187Hv?p=56), the emphasized
second character is prominent around 0.501–0.584 s, thins/fades around
0.626–0.709 s, and the next character is prominent by 0.751–0.834 s. Rotating,
blurred drawings coexist with a faint retained baseline. This is a different
ownership policy from removing the original characters at row end. The latter
is supported by the [ぴ song example](https://www.bilibili.com/video/BV1tDpt6HE2R),
where the completed upper row remains stable and then exits left-to-right while
the lower row is already singing. Keep both animation target and time anchor
explicit rather than forcing all scatter variants onto one schedule.

## Ordinary readable styles have independent clocks too

In the [Great Days](https://www.bilibili.com/video/BV1eeWu65ESU) clip around
50.0–50.8 s, the completed upper row remains in place while the lower row's color
front advances. The upper row begins fading around the latter part of that
interval, without a corresponding lower-row fade. The 30 fps local sequence
shows stationary glyph positions through the handoff: no scale pulse is needed
to reproduce its main mechanism.

In [Zzz](https://www.bilibili.com/video/BV1CKWt6LEyj), the lower-row small mark
cluster appears near the first glyph around 48.37 s and moves along the early
singing front through about 48.8 s, across a background change. The full unsung
line is already visible before the cluster appears. This distinguishes front
decoration from the P104 pre-reveal process. The local clip is sampled at 30 fps;
these are visible-frame observations, not source ASS onset timestamps.

The remaining source-to-implementation gaps are recorded rather than hidden by
calling every particle pattern a trail or every emphasis a pulse. The library
must keep timing, appearance and decoration independently composable.
