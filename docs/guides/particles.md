# Particles, copies, echoes, and following

Particle effects create ordinary Scene objects. An Emission gives a stable ID
and birth time; emit_particles calls a ParticleFactory with ParticleContext.
The factory chooses geometry, lifetime, appearance, and animation and returns
an object or group. See the sakura example for a complete editable petal factory.

## Reproducible variation

Use a fixed seed and named channels such as `context.uniform("size", low, high)`.
Random values are keyed by seed, emission ID, and channel. Adding a new random
property does not advance an unrelated property's random stream. Avoid global
random draws inside animation callbacks: evaluation may seek, repeat, or visit
objects in a different order.

Changing a seed deliberately changes variation. Preserve emission IDs when you
want stable particles across a configuration edit. Give the factory an explicit
particle lifetime instead of tying visibility to a source lyric's duration.

## Three different time relationships

| Relationship | Interface | Behavior |
| --- | --- | --- |
| Capture at birth | Emission/factory and emission-source lookup | Read the source once at birth; particle then moves independently |
| Follow continuously | FollowObject or ReferenceFunction | Evaluate the referenced object's world state at the requested time |
| Reuse earlier motion | echoes or delayed copies/references | Draw a delayed historical appearance with explicit spacing/opacity |

Use Scene.evaluator() for world-space queries across parent groups. References
receive absolute Scene seconds, and their lookup function uses that same clock.
Material and geometry callbacks instead use object-local seconds.
References
declare their dependencies; unknown IDs or dependency cycles produce contextual
errors. Keep callback output deterministic for arbitrary seeks.

`copy` and echoes preserve local clocks and make distinct identities. Group
copies remap references within the copied hierarchy. External material and
coverage maps remain keyed by ID and need explicit remapping.

Particle count, lifetime overlap, geometry detail, color bands, and echoes all
contribute to compilation and playback cost. Plan emission density with
SceneBudget.max_active and event/byte limits; a visually small petal can still
have expensive geometry or glow. Read [compilation](compilation.md) before
increasing a dense effect's limits.
