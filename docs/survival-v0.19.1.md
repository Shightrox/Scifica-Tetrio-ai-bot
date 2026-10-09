# Garbage evacuation and round recovery — 0.19.1

The 0.19.0 failure was not simply a missing mode switch. Recorded dangerous positions were labelled `survive`, but many executed choices had only one-piece lookahead. The evaluator could keep building over the accessible garbage hole, and deeper branches could regain attack rewards before the emergency was resolved.

## Emergency choices

- Four or more risen garbage rows trigger survival even when their hole is open. Any garbage with a stack at least eleven rows high also triggers it, in addition to the existing height, hole and burial thresholds.
- The first emergency answer considers the current piece and the first known NEXT piece. It retains native tucks for the current move and uses straight-drop future placements for this quick pass. Background refinement includes future tucks.
- Survival scoring stays active throughout that search horizon. Clears, removed garbage, headroom and access to the uppermost garbage hole take priority; combo, B2B, perfect-clear attack rewards and setup banking do not compete with rescue.
- A useful soft-drop tuck receives a smaller input-cost penalty during rescue. Candidates are checked for a playable next spawn earlier, from height twelve.
- Dedicated attack search and stored PC/clear-chain continuations cannot take over an emergency decision. After the observed board is safe, a new search can resume ordinary attack priorities.
- Survival bypasses artificial Speed and Dynamic tempo delays. It still requires fresh frames, focus, movement acknowledgement and exact landing verification. Preferences are not rewritten.

## New rounds

The reader retains the last accepted NEXT queue separately from raw countdown samples. A reset requires an empty observed stack, an unrotated piece in its spawn column, a changed preview that is not an ordinary one-piece shift, and independent empty-HOLD or recent blocking-screen evidence. Three stable observations confirm the reset; gravity may move the piece into the grid during them.

The persistent round ID resets pending DROP/HOLD/soft-drop evidence, recovery, orientation, HOLD availability, chain state and timing before the next search is assembled. Old search replies are discarded. Arming is preserved: an enabled pilot continues; an explicitly stopped pilot stays stopped. A harmless preview-tail change or repeated dark occlusion cannot erase a stack.

## Evidence and limits

`tests/survival-cases.json` contains three stripped board/queue fixtures from failed decisions, without raw logs or account metadata. On the third fixture, the quick answer now clears a roof row, then plans another clear with NEXT to uncover the top garbage hole; the previous choice added height without clearing. Tests also cover a held-I garbage quad, emergency isolation from attack rewards, and an actual solver-process first answer at depth two.

Python regressions cover countdowns that change NEXT before spawn, falling new-round pieces, empty preceding boards, notices after a reset, and pending DROP/HOLD/SD with stale recovery state. A Tk orchestration check verifies that fresh HOLD/chain state enters the search and a delayed old-round answer is ignored. Existing low-stack multi-clear, PC, SRS+/180, tuck and input-recovery checks remain in the suite. Automated input is mocked; these are regression checks, not a live-match win-rate benchmark.

The bot reacts to garbage already visible in the field. Incoming-garbage timers and cancellation are still not simulated. Search remains bounded and can miss a rescue. New-round detection depends on usable field, NEXT and independent reset evidence; a fully obscured frame is not treated as permission to guess.
