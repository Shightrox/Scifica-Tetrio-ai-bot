# Attack priority

Enabled by default in the desktop pilot. It favors estimated garbage output over low-value skimming, while keeping the existing survival switch. The speed slider still controls key tempo independently.

## What changed in 0.16.0

- **Proved perfect clears.** A separate search uses the visible active piece, up to five NEXT pieces and available HOLD. It can find a four-to-six-piece finish outside the ordinary beam. It never assumes the next unseen bag or promises a fixed opener will work.
- **Keep the continuation.** A proved plan survives a new spawn, newly revealed queue tails and a confirmed HOLD. Every move is rerouted from the observed position. Changed board cells, known queue order, HOLD availability or chain state invalidate reuse.
- **Prefer efficient attacks.** Candidate sequences gain weight for estimated garbage and attack per piece. Successive singles now receive a combo-floor estimate, rather than always being treated as zero damage. Quads, PCs, B2B retention and Surge release remain part of the approximate attack model.
- **Avoid competing I dependencies.** Additional deep, narrow wells receive a penalty. An open attack well is useful only while the rest of the field stays playable. B2B reserves are capped and valued once at the search leaf, so empty stacking does not repeatedly collect a bonus.
- **Keep a fast answer.** The shallow result is emitted independently. A persistent worker performs PC search and ordinary refinement; the input controller keeps its existing 40 ms refinement allowance, or 20 ms under survival pressure.

In 0.16.0 the ordinary pressure beam covered four placements, with six root candidates and width three. **0.17.0 extends native pressure to six placements and adds grounded spins and consecutive-clear continuation search.** PC search still has a 24 ms / 12,000-state budget and considers fields up to six rows high. Root enumeration and final SRS replay add overhead. A timeout means the budget was used, not that no PC exists. Disabling the setting restores the balanced three-placement beam and disables dedicated PC/chain passes. [0.17.0 changes and comparison](spins-and-chains.md).

The status line shows `PC / 4 pieces · ~6 attack` for a verified sequence, or `PRESSURE` with its current tactical intent. This is an estimate for the searched sequence, not a success probability or the net garbage received by an opponent.

## A reachable four-piece example

This position is included in `tests/pc-cases.json`. Only its bottom four rows are shown; `.` means empty.

```text
active J   NEXT I Z L O S   HOLD empty

....ZT...I
...ZZTT..I
OO.ZLTSS.I
OOLLLSS..I
```

The proved sequence places J, clears one row with I, holds Z to use L for another row, then clears the final two rows with O. All four landings are checked using the same movement engine as the controller. The three-piece search cannot see the final PC from this state.

## Comparison with 0.15.2

Both planners receive identical seeded seven-bag streams, five previews, empty initial HOLD and the same fixed garbage schedule. Each condition has six runs of 100 placed pieces. Every returned route is replayed and checked. Both outputs are scored with the **same current attack estimator**; these numbers are not actual multiplayer telemetry.

| Condition, 600 pieces each | 0.15.2 | 0.16.0, Attack priority |
| --- | ---: | ---: |
| Clean start: estimated attack | 120 | 226 |
| Clean start: perfect clears | 4 | 25 |
| Clean start: completed placements | 600 | 600 |
| Rising garbage: estimated attack | 219 | 247 |
| Rising garbage: perfect clears | 1 | 3 |
| Rising garbage: completed placements | 600 | 600 |

The garbage condition starts with eight rows, then raises two rows every seven placements. Incoming rows invalidate any cached PC continuation. Two of the six garbage streams produced slightly less estimated attack in the new version; this is not a universal improvement on every queue.

The clean-start attack estimate improved by about 88%; under this garbage schedule, about 13%. The simulations wait for refinement and do not model capture errors, key latency, finite-speed gravity, incoming attack cancellation, an opponent, or custom room multipliers. A live pilot may use its earlier result when the refinement budget expires. Search timing and occasionally the chosen route can vary with CPU load because PC search is time-bounded.

[Raw results, including every seed and planner timing](benchmarks/pressure-v0.16.0.json). Reproduce from a full Git checkout containing the baseline commit:

```powershell
node scripts/benchmark_pressure.cjs work/pressure-results.json
```

## Research and limits

[Hard Drop: Perfect clear](https://harddrop.com/wiki/Perfect_clear) motivates explicit whole-field completion, rather than only rewarding a low stack. [Perfect Clear Opener](https://harddrop.com/wiki/Perfect_Clear_Opener) shows why a setup's success depends on piece order and alternatives. Scifica proves a visible-queue finish instead of blindly following an opener diagram.

[Tetris stacking](https://harddrop.com/wiki/Tetris_stacking) discusses preserving an open well, accommodating upcoming pieces, and avoiding several columns that all need an I. [Combo](https://harddrop.com/wiki/Combo) motivates evaluating consecutive clears as a sequence. The damage rules of other games are not treated as TETR.IO rules.

The [official TETR.IO patch notes](https://tetr.io/about/patchnotes/) for BETA 1.2.0 describe Season 2's B2B charging/Surge and five-garbage all clears; the [official JSON source](https://tetr.io/about/patchnotes/notes.json) is available when the page's dynamic contents do not load. Scifica's model remains approximate, especially for room overrides, cancellation and modifiers. The displayed attack is not a claim of exact outgoing damage.

Since 0.18.0, native actions also include I-piece SRS+ tucks and TETR.IO's separate 180-degree kick tables. Version 0.19.0 favors direct-drop routes over unnecessary surface descents and includes the flat one-line garbage-clear bonus for quads/spins introduced in BETA 1.3.0. This bonus is outside the combo multiplier. T-spin/immobile-mini rewards remain estimates. Arbitrary mid-air stops and named spin opener templates remain unsupported. The dedicated PC pass still uses straight-drop routes. Survival takes priority on a high or heavily buried field; attack incentives can resume after the danger is removed.

Native ordinary refinement now has a 140 ms pressure / 90 ms balance budget, checked between node expansions. Only completed depth layers are compared; the last expansion can overrun the budget. The six-placement horizon is a maximum, not a guarantee on every machine. PC and consecutive-clear passes keep their separate budgets. [Reliability changes](reliability-v0.19.0.md).
