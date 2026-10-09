# Native SRS+ and 180° turns

Version 0.18.0 uses TETR.IO's default SRS+ rotation model for the Windows pilot. A half turn is a single **A** tap with its own ordered kick trials, not two X or Z taps. **180 key** can be changed in the panel or set to **Off**. It must match the game's binding. I-piece quarter turns use SRS+'s symmetric trial order, including rotations after a verified soft drop.

## Sources and coordinates

The [official mechanics FAQ](https://tetrio.github.io/faq/mechanics.html#srs) points to rotation references. The [TETR.IO issue discussing SRS+](https://github.com/tetrio/issues/issues/506) includes the original published I table and examples of differences from SRS. Numeric trials were cross-checked against the basic-rotation coordinates in [torchlight's rotation implementation](https://gist.github.com/torchlight/1832786cf053daa51bf188110b764090). These are rule data; Scifica's search and controller implementation are independent.

The engine's board y grows downwards; the kick constants use positive y upwards. A trial is applied as `(x + dx, y - dy)`. Rotations are 0 / 1 / 2 / 3 = spawn / right / reverse / left. The first collision-free trial wins; changing the order changes reachable routes.

For half turns, JLSTZ use six ordered trials per transition; I uses only two axis trials. O rotations are omitted because they do not change its occupied cells. Half-turn kick index four does not inherit the quarter-turn T-spin fin-kick promotion. Standard SRS remains available to legacy sandbox calls; native requests explicitly select SRS+.

## Evidence before the next key

Routes include a target pose after every action. Soft drop must reach its supported checkpoint. A rotation must produce the checkpoint's occupied cells, allowing subsequent unobstructed gravity; a matching normalized silhouette alone is insufficient. If the surface or kick differs, the pilot discards the route and replans.

I/S/Z have visually identical pairs of orientations with different rotation origins. A confirmed spawn or turn establishes the orientation; subsequent pixel fits retain it rather than silently returning to the first matching shape. Focus loss, capture reset and stop discard this evidence. At an unknown mid-piece start, the pilot can slide/drop or use HOLD without assuming an unobserved orientation.

Some I/S/Z half turns produce no visible movement, or exactly the same pixels as ordinary falling. The mathematical rotation function supports those kicks, but native route search excludes them: their success cannot be distinguished from an ignored key with the available evidence. This is a deliberate limit of screen-only control. Gravity, lock delay and manual interference still make real gameplay less deterministic than the planner.

## Validation

- A J single under a two-block roof is reachable with a half turn and unreachable with quarter turns alone.
- An I single through a narrow entrance is reachable with the SRS+ trial order and absent with the previous SRS-only route set.
- Every route returned on both fixtures is replayed through movement and lock checks.
- Pixel-reader/controller integration completes both routes with instantaneous and incremental soft drop, and recovers without hard-dropping when the final turn is ignored.
- Regression tests cover I kick preference, I-only half-turn trials, spin classification, symmetric pose tracking, gravity false acknowledgements, disabled half turns and cache invalidation.
- The packaged EXE smoke test exercises both new routes through its bundled engine and checks the saved key binding.

This adds reachable actions; it does not guarantee more attack on every queue. Custom SRS-X/ARS/other room kick tables and arbitrary mid-air stopping are outside this model.
