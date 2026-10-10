# TETRA LEAGUE construction review — 0.20.0

Research and implementation review, 10 October 2026. Baseline: [0.19.1](https://github.com/Shightrox/Scifica-Tetrio-ai-bot/tree/v0.19.1).

The objective is more useful attack per placement while retaining an escape route. Speed alone cannot repair a planner that spends T pieces as filler, discards preparation before seeing its payoff, or sends its shallow answer before its construction search finishes.

## Rules used for this review

The authority for League rules is the game's [official patch-note data](https://tetr.io/about/patchnotes/notes.json), also presented on the [patch-notes page](https://tetr.io/about/patchnotes/). Relevant changes are BETA 1.2.0 (16 August 2024), 1.3.0 (22 September 2024), and 1.5.0 (18 January 2025):

- Season 2 uses B2B charging. The regular B2B addition is one; displayed B2B x4 starts a four-line Surge. Breaking the chain releases the charge in three packets.
- All clears add five garbage and qualify for B2B.
- A quad or spin that removes garbage gets a flat additional line outside multipliers.
- Immobile non-T spins preserve/build B2B; the later All-Mini+ change also recognizes immobile T placements without three corners as minis.
- Opening double cancellation and clutch clears affect real matches. Quick Play's cancellation-sickness changes must not be imported into League.

Scifica still estimates damage. It does not simulate incoming cancellation, packet timing, opening double cancellation, clutch spawning, opponent behavior, or room overrides. A projected attack is not net garbage delivered. The existing mini reward approximation has not been certified against game replays.

## Tactical source review

These are principles extracted from author-written guides, not a claim that Scifica now contains every pictured setup. The implementation column describes our engineering choices.

| Topic and primary guide | Tactical lesson | Consequence for Scifica |
| --- | --- | --- |
| [Donation — FOUR](https://four.lol/mid-game/donation/) | Temporary cover can create an attack if the clear restores access. Repeated donations can also spoil the field. | Evaluate a T-slot's entry and the board after its clear, with a visible T dependency. Do not reward arbitrary buried holes. |
| [Skimming — FOUR](https://four.lol/mid-game/skimming/) | Sacrificing an attack can improve the next field; a missing T can make abandonment correct. | Low-field B2B-breaking skims get a modest cost; rescue and garbage evacuation remain exempt. The guide's general line-delay argument is not used as a League rule. |
| [STMB cave — FOUR](https://four.lol/methods/stmb/) | Several pieces can supply a TSD overhang; the surrounding surface determines which construction works. | Preserve distinct preparation branches instead of requiring one named roof pattern. Six different roof builders are regression-tested. |
| [Kaidan — FOUR](https://four.lol/methods/kaidan/) | Stair-shaped surfaces and S/Z props can become TSDs; parity and the following surface matter. | Search the actual board and queue. A local shape alone is insufficient proof of an attack. |
| [Parapet — FOUR](https://four.lol/methods/parapet/) | A J/L donation can attack while preserving a lower well. Missing support pieces can force a skim. | Retain HOLD alternatives and judge post-clear garbage access. No permanent commitment to a pictured setup. |
| [Fractal — FOUR](https://four.lol/methods/fractal/) | A second TSD can be prepared while waiting for T; roof placement controls the continuation. | A longer known-queue search can value two attacks. The new heuristic credits one useful slot, not an unlimited stack of hypothetical future T pieces. |
| [T-spin triple — FOUR](https://four.lol/methods/tspin-triple/) | A triple needs an entrance and cleanup; multiple triples can leave substantial construction debt. | Existing native TST routes remain eligible, but there is no unconditional triple/tower bonus or new double-TST template book. |
| [LST stacking — FOUR](https://four.lol/stacking/lst/) | Alternating roofs depend on the available S/Z/J/L pieces and the shape left by the previous clear. | Preserve queue-dependent surface alternatives. A short construction search can discover local fragments; it does not implement an indefinite LST loop. |
| [Tetris stacking — FOUR](https://four.lol/stacking/tetris/) | Quads remove height and can recycle clean garbage; the pieces needed to finish the well matter. | Keep the existing known-I well credit and strong evacuation scoring. Do not replace every quad with a T-spin. |
| [TKI — FOUR](https://four.lol/openers/tki/) | Early-I starts support quick, relatively low TSDs with several continuation options. | A future opener library should be keyed by actual order and safe exits. This release improves general construction first; it does not claim a TKI book. |
| [MKO — FOUR](https://four.lol/openers/mko/) | Early J/L order enables alternatives such as TSD or PC, with different resulting surfaces. | Compare a verified PC with the full strategic alternative. Never treat a published conditional PC percentage as our bot's success probability. |
| [4-wide — FOUR](https://four.lol/stacking/4-wide/) | Residual shape and piece order sustain a clear chain; the guide discusses a different damage context. | Keep explicit consecutive-clear search. Do not adopt a universal 4-wide policy or optimize combo length as a substitute for damage. |
| [Perfect clear — Hard Drop](https://harddrop.com/wiki/Perfect_clear) | Emptying the entire field is an exact geometric condition. | Keep the independent PC proof and exact board/queue validation; an attractive partial layout is not a promised PC. |

The original [Cold Clear 2 evaluator](https://github.com/MinusKelvin/cold-clear-2/blob/main/src/bot/freestyle.rs) is useful algorithmic context: it distinguishes move reward from field value, accounts for T expenditure, and examines T-slot structure instead of treating every covered cell identically. Scifica's new JavaScript search is an independent implementation; no Cold Clear code, trained weights, or runtime dependency was imported.

The game author's [2019 garbage-design article](https://blog.osk.sh/post.php?p=5df9463f716867.05060790&s=a) explains the historical motivation for combining strong clears with combos. It is design context, not the source of current League constants.

Our conclusion: prioritize reachable TSD/quad/B2B sequences and their exits, use PCs when actually proved, and evaluate chains by estimated output and remaining field. Large combo counts or impressive towers alone are poor objectives.

## What the code review found

| Finding in 0.19.1 | Practical effect | Change |
| --- | --- | --- |
| Controller normally allowed only 40 ms before accepting the shallow answer | Deeper construction could finish after the first move was already committed | Native League planning receives a bounded 550 ms allowance on an observed, safe piece with more than six cells of landing clearance. A final answer is accepted immediately. Falling frames do not restart the deadline. |
| Six roots, then three variants per root | Preparation and HOLD branches could disappear before their T arrived | New global beam of 24 distinct states, a per-root quota, and four competitive preparation slots. |
| Shape-only T-slot credit | Three corners could look valuable even behind an inaccessible roof | Ready slots require a native rotation route and a simulated useful clear. |
| Hole costs reject useful cover, while broad shape bonuses can reward bad cover | Both missed donations and speculative construction debt | Queue-backed slot credit accounts for holes removed by the hypothetical T clear and rejects worsening garbage access. |
| T filler and cheap B2B-breaking skims | Valuable resources spent for little immediate benefit | Modest costs outside rescue, garbage extraction, actual full spins, PCs and Surge releases. |
| PC compared against the shallow alternative | A locally attractive PC could bypass a better construction sequence | Compare against completed League refinement. |
| Cancelled speculative work could occupy the worker ahead of changed positions | A larger budget would worsen stale-work delays | Cooperative cancellation between expansions; latest request restarts even after A → B → A changes. |
| Internal B2B count was treated as its displayed index | Surge was credited one difficult clear too early and one line too high | Convert difficult-clear count to displayed index before evaluating Surge; panel combo/B2B labels use displayed indices too. |

The capture and rotation systems retain their existing feedback checks. The emergency policy from 0.19.1 remains ahead of construction. Four visible garbage rows, height thirteen, garbage at height eleven, and serious burial/hole debt still trigger survival. Attack bonuses cannot reactivate halfway through an emergency search merely because a hypothetical later board is lower.

## How the new search works

`league-search.cjs` runs in the warm background worker when native Attack priority is enabled and the observed root is outside survival. It expands complete breadth layers, up to six actual placements and a nominal 450 ms budget. An individual expansion can overrun that boundary. Roots always use native routes; future T/held-T pieces and fields with cavities do too. Clean non-T future construction uses straight landings to spend more of the budget on useful alternatives.

Each node includes the field, actual remaining preview, HOLD, combo and B2B. Equivalent occupied/garbage fields with the same continuation state are deduplicated. Cumulative move rewards are discounted by 0.9 per placement; field value is added once at the leaf. Final selection also uses estimated attack per searched placement. Interrupted layers are discarded so a partly expanded layer does not unfairly favor roots examined first. Reaching the end of the known queue ends that branch; unseen pieces are never invented.

Ready T-slot credit requires a T in available HOLD or the next four preview positions, three-corner full-spin geometry, a supported placement, completed relevant rows, and an executable spin entrance. The credit falls with T distance. Simulating the clear must not add holes or worsen access to garbage. Incomplete two-corner shapes receive only a smaller heuristic allowance on low-hole fields; they are not presented as verified attacks. This is intentionally a limited recognizer, not an exhaustive inventory of TSTs or chained templates.

One regression position, bottom four rows only:

```text
active L, NEXT T I O S Z, HOLD disabled

Before       After building the roof
..........   .......L..
..........   .....LLL..
JJJ...JJJJ   JJJ...JJJJ
JJJJ.JJJJJ   JJJJ.JJJJJ
```

The planner preserves the L preparation, then finds a real T-spin double. The remaining L does not bury a hole. Equivalent tests cover O, I, S, Z and J roofs, a mirrored field, a T saved in HOLD, and an inaccessible roof that must receive no ready-spin proof. When a held T can immediately perfect-clear the original field, that PC correctly wins over forcing a more elaborate TSD.

The 550 ms controller allowance is a ceiling for initial refinement, not a fixed delay between all pieces or keys. Cached final answers bypass it. Low clearance and survival retain the short path. The worker still emits shallow advice promptly for display and fallback. The existing PC and consecutive-clear proof searches retain their separate budgets. Speed and Dynamic tempo settings continue to govern input independently.

## Measured comparison

Results are recorded in [the complete benchmark data](benchmarks/league-v0.20.0.json). The comparison uses the exact 0.19.1 commit, four seeded seven-bag streams, five previews, HOLD, and 80 placements per stream in each of two conditions. The garbage condition starts with six rows and raises two more every nine placements. Every chosen native route is replayed and its result checked. Both versions' outputs use the same corrected attack estimator.

| Metric | 0.19.1 | 0.20.0 |
| --- | ---: | ---: |
| Clean start, estimated attack / 320 placements | 113 | 186 |
| Rising garbage, estimated attack / 320 placements | 133 | 152 |
| Total estimated attack per placement | 0.384 | 0.528 |
| Full T-spin clears | 3 | 23 |
| All spin clears, including minis | 10 | 33 |
| Quads | 9 | 12 |
| Perfect clears | 12 | 9 |
| HOLD exchanges | 197 | 198 |
| Garbage rows removed | 88 | 84 |
| Completed placements | 640 | 640 |
| Runs that topped out | 0 / 8 | 0 / 8 |
| Highest field, clean / garbage | 7 / 15 | 7 / 9 |
| Mean planning time | 131 ms | 362 ms |

Estimated attack increased 65% from clean starts and 14% with this garbage schedule; combined improvement was 37%. Mean planning took 2.76 times as long. Per-run new-search p95 was 480–493 ms. These measurements include the strategy passes, not capture or execution. Lower key tempo was not used to produce the difference.

There are regressions: clean seed 7 sent 39 versus 40 estimated lines; garbage seed 19 sent 31 versus 32. The new planner removed two fewer garbage rows on each of garbage seeds 7 and 19, and made fewer PCs overall. On garbage seed 7 its maximum field rose from seven to nine rows. It therefore cannot be described as universally better at evacuation or every type of attack. Existing emergency regression fixtures still pass.

This is a planner comparison, not a League win-rate test. It waits for refinement and replans each placement; it does not reuse the live worker's PC/clear-chain proof cache. All search passes compete, whereas the live worker can keep a winning PC proof without running the clear-chain pass. It excludes vision errors, gravity timing, input latency, an opponent, and garbage cancellation. Garbage arrives on a placement schedule, not a wall-clock schedule, so spending longer thinking does not attract extra garbage in this test. Time budgets make decisions sensitive to host load. The first three seeds informed exploratory work; seed 83 was added for this longer check. Results for every seed, including regressions, are retained. Raw `maxCombo` and `maxB2B` fields count consecutive clears and difficult clears respectively; the displayed indices are one lower.

Reproduce from a full Git checkout containing the baseline commit:

```powershell
node scripts/benchmark_league.cjs work/league-results.json
```

## Validation and remaining priorities

Automated coverage includes construction-route replay, unavailable/held T, inaccessible slots, known-queue limits, cancellation, Surge indexing, bounded controller waiting, and immediate survival execution. Existing SRS+/180, direct-drop preference, emergency downstack, HOLD acknowledgement, round restart, capture and window tests remain required. The packaged EXE also executes an L-roof → TSD construction with its bundled Node and new module, while autopilot remains disarmed.

The next substantial improvements require more than larger heuristic constants:

1. **Observe incoming garbage and opponent pressure.** Then compare send-now, cancel-now and short-delay attacks using actual packet deadlines. Current code cannot honestly infer these from our settled grid alone.
2. **Replay-verified damage and timing model.** Validate minis, opening cancellation, Surge packet splitting and clutch behavior against recorded game events. Then measure net attack, survival and matches, not only estimated gross damage.
3. **Longer construction planning.** Typed setup continuations, abandonment conditions and bag-aware uncertainty could support multi-T structures without pretending an unseen piece is known. Current six-placement search cannot reliably plan an entire multi-bag system.
4. **Conditional opener library.** TKI/MKO and PC alternatives should include queue constraints, native paths, fallback exits and incoming-garbage invalidation. A diagram-matching library without those checks would repeat the old tower failures.
5. **Learn and validate evaluator weights on held-out suites.** Use wider boards/queues and adversarial garbage schedules, including timing. This release uses hand-tuned weights and a small transparent comparison; it does not establish general tactical superiority.
