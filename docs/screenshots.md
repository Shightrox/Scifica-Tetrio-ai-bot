# Screenshot provenance

- `images/result-original.png`: user-supplied screenshot published byte-for-byte, without editing. SHA-256: `f718d684e9dce9d78d9e5e0ccefe035ed3d46bb829e8ef1e29dfa654a141e017`.
- `images/gameplay-overlay.png`: user-supplied gameplay screenshot retouched using the built-in imagegen tool (not the CLI). The user requested replacing the nickname with `scifica` and reconstructing the capture-excluded overlay. This is an edited illustration; fine text and other small details can differ from the original screenshot.

The four landing cells were selected by running the project's visual reader and solver on the supplied board with HOLD disabled. The J-piece target occupies zero-indexed cells (7,18), (8,18), (9,18), (9,19). The original grid bounds were x=521, y=85, width=228, height=458. The published illustration is not a raw capture of the overlay or a performance measurement.

## Final edit prompt

```text
Edit this screenshot minimally, keeping its full composition and ALL panel text, numbers, game blocks and background unchanged. Do not redraw or improve the interface; this is a screenshot edit, not a new illustration. Replace only NITROXUY under the center of the playing field with lowercase "scifica", in the same small dark font. Keep 775 below.
Add Scifica's thin muted-green rectangular outline following the exact outer edge of the black 10x20 playing grid, and faint dashed vertical extensions upward at its left and right edges.
Add four hollow mint outlined squares, with hairline pale inner outlines, for the purple J piece's landing target. Precisely: the rightmost three cells on the SECOND row from the BOTTOM, plus the rightmost cell on the BOTTOM row. The three target squares must be directly to the RIGHT of the single purple block that sits one row above the base purple row. The fourth target square must be directly to the RIGHT of the rightmost purple block on the bottom row. The bottom edge of that fourth square is just above the light frame with the player nickname. These are empty cells beside the purple stack, not the empty row above it. Leave a little gap between the outlines and cell edges. No fills, arrows, paths, new captions, changed game blocks, or other edits. Keep the original low-resolution screenshot look and original aspect ratio.
```
