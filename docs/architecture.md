# How Scifica works

## Capture and evidence

`win_capture.py` reuses DIB buffers for a small screen region. `overlay.py` keeps only the latest captured frame rather than allowing old frames to queue up. Capture, field discovery and JavaScript search run independently of the Tk controls.

The native reader samples a 10 × 20 field plus four rows above it, NEXT to the right and HOLD to the left. `block_vision.py` uses block boundaries and interior color support; a background with the same hue alone is insufficient evidence. `notice_vision.py` identifies fragmented text and helps preserve previously verified cells behind a notification. Unique visible fragments can locate a partly occluded active piece. A completely invisible piece is not assigned a fabricated position.

`overlay_vision.py` maintains a settled-board model. It reconciles observed locks, line clears, preview shifts and aligned garbage rises. An expected own DROP can explain changes under a notice only when visible cells agree. Contradictions outside the mask reject the forecast. HOLD requires stable observations.

`field_geometry.py` prefers a working calibration. A new proposal must include plausible game content and survive two distinct scans. Background calibration does not move or activate the control panel. A capture epoch rejects results from an old region.

## Search

`engine.js` enumerates reachable placements using SRS rotation kicks. Native requests restrict routes to moves the controller can execute: lateral movement and 90° rotations before hard drop. HOLD branches use the held piece or the known queue head, respecting the once-per-piece exchange.

`overlay-solver.cjs` stays alive over JSON-lines IPC. It provides a shallow answer, then a limited deeper search (normally three pieces, eight root candidates, beam width three). Cached continuations must match the board and queue; the current pose is rerouted rather than assumed unchanged. A worker identity and request key reject stale answers.

The pilot normally gives a shallow result up to 40 ms for refinement, reduced to 20 ms under survival pressure. This is a refinement budget, not a promise about total latency. Verified deep answers can be used immediately.

## AUTO strategy

| Mode | Typical trigger | Priority |
| --- | --- | --- |
| Attack | Low stack and accessible field | Quads, short clear chains, perfect clears, usable future setup |
| Balance | Height at least 9, or growing hole/garbage debt | Keep future opportunities without losing access |
| Survive | Height at least 13, substantial garbage burial, or many holes | Reduce danger and preserve a playable next spawn |

Exact triggers live in `autoPolicy()` in `engine.js`. Every intermediate board is penalized for new holes, burial and dangerous growth. A prepared I-piece well earns setup credit only when an I is known in available HOLD or the short preview. Setup reward is capped at four layers and removed in survival mode. A promising preparation branch can be retained in the beam; it is not rewarded once per search step.

The evaluator tracks approximate combo/B2B state after verified locks. Consecutive clears can justify a temporary local cost when a reachable continuation removes it. Unmodeled board transitions reset the chain instead of pretending the attack history is known. No room-specific attack-cancellation model or spin detector is present.

## Closed-loop input

`game_input.py` sends short scan-code taps only when the selected TETR.IO window is foreground and no conflicting modifier is held. It schedules key release and tracks only keys it owns. The controller is injected with a tap sink, allowing tests to exercise faults without sending real input.

```text
 disarmed --start--> ready --> send one tap --> verify new frame
                       ^                            |
                       |       confirmed            |
                       +----------------------------+

 missed input / changed field --> discard route --> fresh frames --> replan
 focus lost -------------------> pause -----------> verify on return
 Escape / Stop ----------------> disarmed
```

Movement acknowledgements require actual observed cells, not a NEXT-derived guess. HOLD waits for the expected replacement. DROP verifies the current landing matches the target, then waits for a new piece plus the resulting field; it does not immediately repeat a drop. Recovery requires three distinct fresh observed frames before proceeding. Repeatedly ineffective moves can select another candidate whose first action differs. Worker crashes restart with backoff while preserving armed state.

The controller pauses on a stale/ambiguous frame, focus loss, a blocking game message, panel overlap or a held modifier. A temporary pause is different from explicit Stop. No screenshot alone can prove the position of a fully hidden piece.

## Speed and humanization

`preferences.py` validates finite values and writes settings atomically. The panel applies changes live. Autopilot arming and capture geometry are never restored from settings.

Speed limits the interval between taps, after handling acknowledgement and recovery. It never sleeps the capture or search loop. The slider runs from 2 to 29 keys/s, with 30 representing **MAX**, which adds no wait. Humanization can vary the nominal interval by up to ±12%, so it is a target tempo rather than a strict rate limiter.

At an eligible piece's first plan, humanization is the probability of adding a pair such as `Left, Right`. Eligibility requires an observed pose near spawn, a low stack, enough landing clearance, and no recovery or survival pressure. Both taps use the ordinary acknowledgement path. The original route follows only after the return is verified. A board change or failed tap discards the detour and replans. Turning the slider to zero during a pair still allows its pending correction; it does not blindly assume the piece returned.

No search quality is traded for humanization. These controls do not change AUTO's tactical priorities.

## UI and local data

`panel.py` draws the title bar, square sliders and compact status surface. The native window procedure removes non-client framing while keeping normal taskbar/minimize behavior. The overlay is a separate, non-activating, click-through window excluded from capture. Only explicit setup may initially place the controls away from the field; recalibration leaves their position intact.

`server.py` binds to loopback only. Its launch endpoint checks origin, content type and a custom header. The browser sandbox shares the search engine but uses its own animation and a simpler image reader; it is not the native live-vision pipeline. Native capture frames remain in memory. Local rotating logs record controller status, not screenshot files.

Main files:

| File | Responsibility |
| --- | --- |
| `overlay.py`, `panel.py` | Orchestration, overlay drawing, desktop controls |
| `win_capture.py` | DIB capture, window helpers, exclusion |
| `overlay_vision.py`, `block_vision.py`, `notice_vision.py` | Temporal field reading, block structure, text filtering |
| `field_geometry.py` | Grid proposals and stable calibration |
| `engine.js`, `overlay-solver.cjs` | Reachability, evaluation, lookahead, warm worker |
| `autoplay.py`, `game_input.py` | Feedback controller and guarded key taps |
| `preferences.py` | Validated local settings |
| `app.js`, `vision.js`, `worker.js` | Browser sandbox and image inspector |
