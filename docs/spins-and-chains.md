# Spins, clear chains and HOLD in 0.17.0

The previous native controller could only move and rotate before a hard drop. It could not execute the covered-slot placements shown by an unrestricted Tetris search. It also disabled HOLD when a white header/frame made an empty slot look unknown.

## What changes

- **HOLD evidence:** read emptiness from the slot interior; retain the outgoing piece after a confirmed exchange even when the slot becomes grey or occluded. An unconfirmed HOLD cannot establish that fact. Capture resets discard it.
- **Surface tucks:** search and execute `move/rotate -> Down to a verified surface -> rotate/slide -> hard drop`. Repeated short Down taps accommodate different soft-drop speeds. Only observed pixels acknowledge a descent. Failed or changed motion triggers replanning.
- **Spin value:** native routes track the last rotation and kick. Three-corner T-spins, front-corner minis and immobile minis affect the approximate B2B/attack model. A cached landing retains this classification only if a new route actually produces it.
- **Stronger preparation:** known upcoming T shapes can give a capped terminal bonus to supported T slots. Available I wells and B2B reserves gain more weight; survival remains the override.
- **Longer continuation:** native attack search covers up to six known placements; a separate bounded pass looks for consecutive clears. There is no four-clear combo cap. Verified chains survive new NEXT tails and HOLD; incoming garbage invalidates the old field assumptions.
- **Use late computation:** emit a quick answer and a two-placement intermediate result while the deeper worker runs. One deeper update may replace a route near spawn after key confirmation. Newly revealed queue tails can reuse matching known-prefix analysis. No route switching occurs inside an active tuck.

While finishing a tuck, base pacing, Dynamic tempo and cosmetic extra moves are bypassed to reduce lock-delay risk. All focus, fresh-frame and landing guards remain. The required soft-drop binding is **Down**.

## Validation and comparison

The pixel/controller integration test performs a T-spin double through the actual reader and mocked keys, both with instantaneous descent and three-cell descent steps. Fault tests cover ignored Down, a missed low rotation, focus loss and changed surfaces; no blind final drop is sent. The solver tests replay surface routes, verify HOLD entry, reject spin-less cache replacements and find a six-clear synthetic chain without assuming unknown pieces.

The small offline comparison uses three seeded seven-bag streams, 60 placements each, for clean starts and fixed rising garbage. Both versions have five previews and available HOLD. It waits for full refinement and replays every returned route; it does not simulate capture/input mistakes, an opponent, finite gravity, cancellation or room modifiers. Both outputs use the same attack estimator.

| 180 placements per condition | 0.16.1 | 0.17.0 |
| --- | ---: | ---: |
| Clean: estimated attack | 77 | 85 |
| Clean: quads | 3 | 8 |
| Clean: spin clears | 0 | 3 |
| Clean: perfect clears | 9 | 5 |
| Rising garbage: estimated attack | 84 | 87 |
| Rising garbage: longest clear chain | 6 | 9 |
| Rising garbage: spin clears | 0 | 3 |
| Completed placements, both conditions | 360 | 360 |

One clean stream sends less estimated attack (28 -> 22). The result is a strategy tradeoff, not a universal improvement or a guarantee of live-game performance. HOLD is selected 135 times across the new planner's 360 placements; visual HOLD availability is tested separately.

Deeper computation costs more: the recorded refined search means range from roughly 66 to 111 ms in the new version. It runs in the worker; the separate moving-position IPC check observed native first-answer p50/p95 around 2/3 ms on the development machine. Native fixture capture remained around 58 FPS; final answers can arrive over 200 ms after capture. These measure different parts of the pipeline and are not latency promises.

[Raw results](benchmarks/tucks-v0.17.0.json). Reproduce from a full checkout containing v0.16.1:

```powershell
node scripts/benchmark_tucks.cjs work/tucks-results.json
```

## Rules and scope

The [official TETR.IO patch notes](https://tetr.io/about/patchnotes/notes.json) describe All-Mini in BETA 1.2.0 and the cornerless immobile-T mini addition in BETA 1.5.0. Scifica approximates All-Mini+; custom rules and exact outgoing damage remain outside its model.

Supported native tucks use 90-degree SRS kicks for T/J/L/S/Z; O can slide. **I-piece SRS+ tucks, 180-degree rotations, arbitrary mid-air stopping and named opener templates are not implemented.** The PC pass still searches straight-drop finishes. Surface verification reduces execution risk but does not simulate every gravity or lock-reset rule.
