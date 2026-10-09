# Route and state reliability — 0.19.0

This release fixes reproduced failures from the 0.18.1 review. The Windows pilot keeps its existing controls and saved tempo settings.

## Rotation before descent

Native routing uses a stable Dijkstra queue, ordered first by the number of intermediate surface descents, then by weighted movement cost. Terminal descent is executed with Space and is free in this route comparison. A route with the same landing and clear classification therefore prefers a direct approach when one exists. Stable ties favor early turns. Surface distance and grounded input contribute additional cost to tactical evaluation; these are heuristics, not measured milliseconds or a full lock-delay simulator.

One reproduced I-piece case previously returned:

```text
before: Down → Z → Z → Z → Space
after:  Z → Left × 4 → Space
```

The fixture is in `tests/review-regressions.cjs`. Ordinary T half turns use A near spawn. The J roof entry still requires its true 180 kick, and the narrow I entry still uses SRS+ after descent. Spin and ordinary-clear landings remain separate: a direct path cannot inherit a spin's attack reward. Zero-line rotations receive no separate spin reward.

Each rotation checkpoint carries its ordered kick trials. The controller checks the first legal trial again against current pixels before pressing a key. If gravity changed the winning kick, it replans first. After a confirmed move, a non-spin placement already on its target drop column may finish immediately with Space.

## Board and piece transitions

- **Natural lock:** a lock/clear plus NEXT transition, or a verified same-type respawn, releases the HOLD lockout even when Space was never sent. The controller simulates the previous piece's landing and allows aligned garbage afterward. A queue tail or garbage rise alone is insufficient. Normal clears update combo/B2B conservatively; an unobserved spin is not credited.
- **NEXT tails:** revealing or hiding trailing previews does not cancel a pending input or erase known I/S/Z orientation. A conflict in known order still invalidates it.
- **Identical HOLD:** a held copy of the active type can restore spawn position and escape a pocket. It is excluded at the unchanged spawn. The controller requires an observed position reset; unchanged pixels cannot acknowledge an ignored Shift.
- **Occlusion:** an unexplained changed stack stays untrusted even after many identical frames. Visible legal lock/clear/garbage evidence can reconcile it. Fresh-round acquisition requires a stable empty field and spawn, a different known preview, plus independently empty HOLD or a preceding game screen. Selecting the field again remains an explicit reset for unsupported transitions.

## Search continuity

An unreachable cached result no longer prevents fresh deep search. A result using a shorter NEXT prefix is provisional while the expanded queue is searched. Fully proved PC/clear-chain continuations can still be reused. Rebased route cost is updated, and losing cached alternatives triggers refinement.

Ordinary refinement completes whole depth layers before committing their scores. Pressure allows 140 ms and balance 90 ms, checked between expansions; initial enumeration and the last expansion may exceed those budgets. This keeps first and last root candidates at a comparable searched horizon. PC and consecutive-clear searches retain their separate limits.

The background thread restarts after an error, unexpected exit or a three-second stall. A separate process watchdog handles an unresponsive search process. A dedicated writer sends only the latest queued request, so pipe backpressure cannot stall Tk or key-release handling. Logging also writes on a separate thread.

The default versus estimate now includes the **flat +1** for a quad/spin clearing garbage, outside combo multiplication, as described in the [official BETA 1.3.0 patch notes](https://tetr.io/about/patchnotes/notes.json). Clearing more garbage rows does not multiply this bonus. Custom room formulas and incoming cancellation remain outside this estimator.

## Offline diagnostics

`autoplay-events.log` now uses versioned schema 2. State changes include the observed board/pose, NEXT/HOLD, chain, pending action, selected route, search stage and tempo settings. Up to three rotating files of approximately 8 MB each are retained locally. No screenshots, usernames or window titles are added to these snapshots; nothing is uploaded.

```powershell
node scripts/replay_trace.cjs "$env:LOCALAPPDATA/Scifica/autoplay-events.log"
```

The tool counts events and replays distinct recorded advice through movement, checkpoints and lock/clear validation. It never sends input. It reports malformed/unreachable routes with log line numbers. This is deterministic replay of recorded search snapshots, not reconstruction of hidden pixels, a recording of every rendered frame, or proof that the game accepted a key. Logs from older schemas are skipped.

## Validation and remaining work

Regressions cover direct-drop dominance, early A, genuine SRS+/180 tucks, changed kick order after gravity, repeated dark occlusion, new-round acquisition, identical HOLD with an ignored Shift, natural locks, repeated NEXT types, harmless tails, longer-queue refinement and a forcibly terminated real worker. Existing fault replay, notification, input-watchdog and window checks remain part of CI. Packaged verification runs with isolated settings and no game input.

This release does not add incoming-garbage meter/timer recognition, a complete gravity/lock-delay simulator, an opponent model, learned evaluation or an alternative search engine. Those remain separate architectural work. The routing and deadline fixes are not a claim of a higher multiplayer win rate or guaranteed attack improvement on every queue.
