# How Scifica works

## Capture and evidence

`win_capture.py` reuses DIB buffers for a small screen region. `overlay.py` keeps only the latest captured frame rather than allowing old frames to queue up. Capture, field discovery and JavaScript search run independently of the Tk controls.

The native reader samples a 10 × 20 field plus four rows above it, NEXT to the right and HOLD to the left. `block_vision.py` uses block boundaries and interior color support; a background with the same hue alone is insufficient evidence. `notice_vision.py` identifies fragmented text and helps preserve previously verified cells behind a notification. Unique visible fragments can locate a partly occluded active piece. A completely invisible piece is not assigned a fabricated position.

`overlay_vision.py` maintains a settled-board model. It reconciles observed locks, line clears, preview shifts and aligned garbage rises. An expected own DROP can explain changes under a notice only when visible cells agree. Contradictions outside the mask reject the forecast. HOLD requires stable observations. Repeated unexplained pixels never replace the settled model solely because they persist; a fresh-round reset requires independent spawn/preview and empty-HOLD or game-screen evidence.

`field_geometry.py` prefers a working calibration. A new proposal must include plausible game content and survive two distinct scans. Background calibration does not move or activate the control panel. A capture epoch rejects results from an old region.

## Search

`engine.js` enumerates reachable placements using explicit rotation rules. Native requests use TETR.IO SRS+ for I quarter turns and its separate JLSTZ/I half-turn tables. Legacy sandbox requests default to SRS without half turns. Native routes can move/rotate at spawn, soft-drop onto a surface, then rotate or slide under an overhang, including I tucks. `SD` means descent to a specific supported pose, never an arbitrary mid-air stop. HOLD branches use the held piece or the known queue head, respecting the once-per-piece exchange. [Tables, sources and limitations](rotation-system.md).

`overlay-solver.cjs` stays alive over JSON-lines IPC. It provides a shallow answer, an intermediate two-placement native result, then deeper search (balanced: three pieces, eight roots; native attack priority: six pieces, six roots; beam width three). Legacy straight-drop requests retain four-piece pressure search. Cache identity includes the observed queue, HOLD availability, movement mode and attack setting. A newly revealed queue tail receives provisional analysis of its matching known prefix while the longer queue is refined; conflicting known pieces cannot. Unreachable cached targets cannot suppress a fresh search. The current pose and descent checkpoints are rerouted. Spin classification is part of landing identity, so a straight-drop route cannot inherit an old spin reward. Worker identity and request keys reject stale answers. Ordinary deep search commits only complete depth layers within a 140 ms pressure / 90 ms balance budget, checked between expansions. An expansion can overrun the boundary. Background thread errors/exits restart the worker; a three-second watchdog also detects stalls. A latest-only writer keeps pipe backpressure off the UI thread.

When attack priority is enabled, `perfect-clear.cjs` first attempts a low-field PC over at most six known placements. It uses bottom-up row bitmasks, deduplicated rotations, straight-drop landings, cell-count divisibility and failed-state memoization. Search stops at 12,000 visited states or a 24 ms time budget; root enumeration and final validation add a small amount of work outside that budget. Every found sequence is independently replayed through the ordinary SRS placement engine before it is eligible for selection. If the PC candidate scores worse than the fast alternative, the ordinary deeper search proceeds instead.

PC continuations retain expected boards, active/HOLD pieces, chain state and known queue prefixes. Newly revealed preview tails are allowed; conflicting known pieces are not. Every reused landing is rerouted from the current observed pose. A predicted HOLD has a separate post-exchange continuation, so the replacement piece does not lose the PC plan. Risen garbage, mismatched chains, unavailable HOLD or strategy changes reject reuse. The first answer and input verification stay on their existing paths.

The pilot normally gives a shallow/intermediate result up to 40 ms for refinement. An emergency first answer searches two placements with six roots and beam width two, using native root routes but straight-drop future routes. With two pieces already considered it needs no additional refinement wait; a one-piece survival answer retains a 20 ms allowance. Background search includes future tucks. These are refinement budgets, not promises about total latency. While an observed piece is near spawn, one later, deeper result may replace the route after the pending key has been acknowledged. A tuck already in progress cannot be changed this way.

`attack-search.cjs` additionally searches consecutive clears over at most six known placements, including HOLD, with a 32 ms / 140-node budget. Individual placement enumeration may finish just beyond that time boundary. Its verified continuation uses the same board/queue/HOLD checks as a PC proof. This is a search horizon, not a maximum lifetime combo length.

## AUTO strategy

| Mode | Typical trigger | Priority |
| --- | --- | --- |
| Attack | Low stack and accessible field | Quads, short clear chains, perfect clears, usable future setup |
| Balance | Height at least 9, or growing hole/garbage debt | Keep future opportunities without losing access |
| Survive | Height at least 13, at least 4 garbage rows, any garbage at height 11+, substantial burial, or many holes | Clear the garbage entrance, reduce height and preserve a playable next spawn |

Exact triggers live in `autoPolicy()` in `engine.js`. Every intermediate board is penalized for new holes, burial and dangerous growth. A prepared I-piece well earns setup credit only when an I is known in available HOLD or the short preview. Setup reward is capped at four layers and removed in survival mode. A promising preparation branch can be retained in the beam; it is not rewarded once per search step.

An emergency root keeps survival scoring throughout its search horizon, including hypothetical later boards that would individually qualify for attack. Clears and garbage removal receive direct rewards; height, new holes and cover over the upper garbage entrance receive stronger penalties. Future spawn reachability is checked from height twelve. Input cost matters less so a useful rescue tuck is not rejected for its soft drop. Dedicated PC/attack passes and stored attack continuations are bypassed in survival. This preserves low-stack combo search without allowing it to displace rescue. [Regression evidence](survival-v0.19.1.md).

The evaluator tracks approximate combo/B2B state after verified locks. Consecutive clears can justify a temporary local cost when a reachable continuation removes it. Unmodeled board transitions reset the chain instead of pretending the attack history is known. Native spin detection requires the route to finish in rotation: T uses three occupied corners, its front corners and fifth-kick promotion; other immobile shapes and cornerless immobile T shapes count as minis. The estimate approximates All-Mini+ and does not model custom spin tables or incoming cancellation.

Attack priority adds weight to estimated garbage and attack per searched piece while reducing the incentive to skim low-value singles. The estimate includes a combo floor for successive singles and a flat +1 outside combo multiplication when a quad/spin clears garbage. A capped B2B reserve is valued once at the search leaf; competing narrow wells are penalized because they demand extra I pieces. All of these extra incentives are disabled for a state already in survival mode. They can resume after downstacking removes the danger. See [research and benchmarks](attack-priority.md).

## Closed-loop input

`game_input.py` sends short scan-code taps and renewable Down holds only when the selected TETR.IO window is foreground and no conflicting modifier is held. It schedules key release and tracks only keys it owns. The controller is injected with tap, release and soft-drop sinks, allowing tests to exercise faults without sending real input.

```text
 disarmed --start--> ready --> send action --> verify new frame
                       ^                            |
                       |       confirmed            |
                       +----------------------------+

 missed input / changed field --> discard route --> fresh frames --> replan
 focus lost -------------------> pause -----------> verify on return
 Escape / Stop ----------------> disarmed
```

Movement acknowledgements require actual observed cells, not a NEXT-derived guess. Native rotation checkpoints verify the target cells with unobstructed gravity allowance; ordinary falling cannot acknowledge a symmetric half turn. The pilot preserves confirmed I/S/Z orientation across the reader's visually identical 0/2 or 1/3 representations. Unknown orientation restricts current-piece rotation until spawn or another observation resolves it. HOLD waits for the expected replacement. An identical-piece exchange also requires an observed respawn that ordinary gravity cannot explain. A natural lock independently reconciles board/queue evidence and unlocks HOLD; a harmless preview tail does not reset movement or orientation. Its confirmed outgoing piece is retained through grey/occluded HOLD frames and cleared on capture reset. Empty-slot detection samples the dark interior, excluding the white heading and border. DROP verifies the current landing matches the target, then waits for a new piece plus the resulting field; it does not immediately repeat a drop. Recovery requires three distinct fresh observed frames before proceeding. Repeatedly ineffective moves can select another candidate whose first action differs. Worker crashes restart with backoff while preserving armed state.

Soft drop holds Down until the planned supported pose is observed, then releases it before any following rotation or slide. Only distinct, fresh, verified frames with the same board, piece, generation and reachable surface renew the 120 ms input lease. An independent watchdog checks every 8 ms and releases on expiry, focus/target changes or conflicting modifiers, including when the controller stops ticking. Missing, stale, ambiguous or inferred-only poses release immediately in the controller. Actual downward progress resets a 450 ms stall timeout, allowing a slow but progressing descent to finish. A changed surface, failed descent or missed rotation discards the route; it never skips straight to the final drop. Once descent begins, the remaining tuck actions bypass base pacing and cosmetic timing because they must fit inside the game's lock delay. Movement flourishes are excluded from spin/tuck plans.

A stable Dijkstra queue first minimizes intermediate surface descents, then weighted movement cost, preferring an early rotation on equal cost. Rotation checkpoints carry ordered kick trials; a changed first legal kick after gravity triggers replanning before input. Rotations requiring floor/roof kicks still occur after the necessary descent. Terminal descent steps are removed from execution: a plain placement locks with Space directly from the air. Once its last motion is verified, the final drop bypasses the extra key-spacing delay and a late deeper result cannot redirect the completed route. Exact landing, fresh pixels and focus are still required. Initial planning/thought pacing is unchanged, including a new placement that needs no motion.

The controller pauses on a stale/ambiguous frame, focus loss, a blocking game message, panel overlap or a held modifier. A temporary pause is different from explicit Stop. No screenshot alone can prove the position of a fully hidden piece.

Round detection compares NEXT against the last accepted queue, which countdown frames cannot overwrite. Three observations of an empty field and an unrotated spawn-column piece, a non-shifted new preview, and empty-HOLD or recent blocking-screen evidence trigger a persistent round ID change. Vertical falling does not restart this probe. Before constructing the new search state, orchestration clears pending actions, recovery, pose, HOLD history, chain state and old search replies while preserving whether the pilot is armed. Focus-notice frames also retain the round ID. An explicitly stopped pilot never starts itself.

## Speed and humanization

`preferences.py` validates finite values and writes settings atomically. The panel applies changes live. Autopilot arming and capture geometry are never restored from settings.

Speed limits the interval between ordinary movement taps, after handling acknowledgement and recovery. Survival, a final aligned hard drop and active tuck execution bypass this interval. It never sleeps the capture or search loop. The slider runs from 2 to 29 keys/s, with 30 representing **MAX**, which adds no fixed wait. Humanization can vary the nominal interval by up to ±12%, so it is a target tempo rather than a strict rate limiter.

At an eligible piece's first plan, humanization is the probability of adding a pair such as `Left, Right`. Eligibility requires an observed pose near spawn, a low stack, enough landing clearance, and no recovery or survival pressure. Both taps use the ordinary acknowledgement path. The original route follows only after the return is verified. A board change or failed tap discards the detour and replans. Turning the slider to zero during a pair still allows its pending correction; it does not blindly assume the piece returned.

No search quality is traded for humanization. These controls do not change AUTO's tactical priorities.

Dynamic tempo is an independent 0–100% strength setting, disabled by default. A placement samples one 80–260 ms thought delay (25% chance of another 80–200 ms) and a 0.7–1.3 rhythm factor. Successful taps sample 25–100 ms times that factor, with an 18% chance of another 30–90 ms hesitation. The slider scales both types of delay. Thought and tap deadlines overlap; no `sleep` is introduced. Thought timing starts with the first usable candidate and does not reset when the pose, advice or HOLD changes. A verified lock resets the rhythm for the next placement. Recovery cancels thought timing and the extra tap delay.

Each fresh observation scales the added waits: 35% with six-to-nine cells of landing clearance or a pose below the spawn area; zero at five or fewer cells, any occupied cell in the top eleven rows, survival, inferred-only poses or retries. Once the thought gate opens, it stays open for that placement. Survival bypasses both these waits and the base Speed interval; ordinary pacing returns after rescue without changing preferences. Pending acknowledgements, stale-frame and focus checks always run before pacing. Setting Dynamic tempo to zero releases an existing artificial wait on the next eligible update.

## UI and local data

`panel.py` draws the title bar, square sliders and compact status surface. `window_chrome.py` uses Tk's [borderless window mode](https://www.tcl-lang.org/man/tcl8.7/TkCmd/wm.html) so Tk and Windows agree about the client dimensions. Dragging coalesces pointer positions at an 8 ms interval and calls [SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos) with NOSIZE, NOZORDER and NOACTIVATE. Mouse release flushes the final position. This avoids the old combination of repeated Tk geometry requests and intercepted non-client size messages, which could shrink and corrupt the panel while dragging. Native styles retain the taskbar entry and minimize/restore behavior; minimized controls do not count as field overlap.

The overlay is a separate, non-activating, click-through window excluded from capture. Only explicit setup may initially place the controls away from the field; recalibration leaves their position intact.

`server.py` binds to loopback only. Its launch endpoint checks origin, content type and a custom header. The browser sandbox shares the search engine but uses its own animation and a simpler image reader; it is not the native live-vision pipeline. Native capture frames remain in memory. Local rotating schema-2 logs record controller status, board/pose, pending input and search snapshots, not screenshot files. Logging runs off the UI thread. The offline route replay command and data limits are documented in [0.19.0 reliability notes](reliability-v0.19.0.md).

Main files:

| File | Responsibility |
| --- | --- |
| `overlay.py`, `panel.py` | Orchestration, overlay drawing, desktop controls |
| `window_chrome.py` | Borderless frame, coalesced native dragging, minimize/restore |
| `win_capture.py` | DIB capture, window helpers, exclusion |
| `overlay_vision.py`, `block_vision.py`, `notice_vision.py` | Temporal field reading, block structure, text filtering |
| `field_geometry.py` | Grid proposals and stable calibration |
| `engine.js`, `overlay-solver.cjs` | Reachability, evaluation, lookahead, warm worker |
| `perfect-clear.cjs` | Budgeted bitboard PC search, SRS validation, continuation proof |
| `attack-search.cjs` | Bounded consecutive-clear search and continuation metadata |
| `autoplay.py`, `game_input.py` | Feedback controller and guarded key taps |
| `preferences.py` | Validated local settings |
| `app.js`, `vision.js`, `worker.js` | Browser sandbox and image inspector |
