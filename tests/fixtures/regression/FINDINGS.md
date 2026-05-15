# Detection findings

Working notes captured while tuning the OCR pipeline against the regression
fixture set. Each section captures what was tried and what was learned so a
future run does not repeat the same experiment.

Baseline (2026-05-14, profile = `windows_default`):
- 16 / 32 fixtures pass.
- 16 known failures, broadly grouped:
  - **Speaker recovery `[unknown]` → `[PLAYER]`** (example_05, 13, 23, 24, 27):
    boundary detection splits the line into a separate record, the
    missing-prefix heuristic fires (`[unknown]: <body>`), but the speaker is
    never recovered.
  - **Player-name C/O drift** (example_04, 27, 28): leading `C` in player
    names misread as `O` (`Cipe`→`Oipe`, `MimiChan`→`MimiOhan`). Pure
    character-level OCR ambiguity at chat-render scale.
  - **Body case drift `cipe`→`Cipe`** (example_04, 05): independent
    character-level drift on short lowercase glyphs.
  - **Mask saturation / scene bleed** (example_09, 12, 14, 22): the chat
    HSV band catches large scene elements (blue-on-blue arenas;
    wood-panel walls for the all band).
  - **Short-body dropout** (example_11, 31): the OCR engine returns no box
    at all for an isolated 2-character body (`gg`, `=)`).
  - **Player-name garble** (example_17): OCR reads `]` plus a few stray
    pixels as multiple characters (`A7X` → `A7Xl•.`).
  - **OCR-engine truncation mid-body** (example_18): mask captures the
    full `[Brummer]: guys........... 2-2-2 pls`, but the Windows OCR
    engine simply does not emit a box for the `-2-2 pls` segment.
    Verified by dumping the team mask — it is intact and the gap is
    purely in OCR output, not the mask. The KNOWN_FAILURES entry's
    "mask gap" framing was wrong.

After this session: 18 / 32 pass (gained example_13 and example_17,
partial improvement on example_14 and example_27).

---

## Useful diagnostic tooling added (2026-05-14)

- `tools/iter_regression.py` — runs every regression fixture through the
  same pipeline as `tests/test_regression_screenshots.py` and prints
  per-fixture missing / unexpected diffs. Faster to iterate than pytest
  because it streams partial output and isn't gated on the `--run-ocr`
  flag's xfail bookkeeping.
- `tools/dump_fixture.py` — prints raw OCR boxes + reconstructed lines
  for named fixtures. Critical when triaging whether a failure is mask
  quality, OCR engine output, or downstream reconstruction.
- `tools/write_masks.py` — writes upscaled team / all masks to disk so
  they can be Read-tool inspected as images. The fastest way to confirm
  whether a missing line is a mask gap (mask is dark) or an OCR engine
  drop (mask is fine, but no boxes returned).

---

## How to interpret a "mask is fine but OCR returns nothing"

The team / all masks are upscaled binary images (white = in-band hue,
black = out-of-band). When the mask clearly shows the expected text but
the OCR backend returns no box for that region, the issue is in the
backend, not in the pipeline. Confirmed instances during this session:

- **example_18**: the team mask shows `[Brummer]: guys........... 2-2-2 pls`
  in full white on black, but the Windows OCR engine returns the prefix,
  `guys...........`, and a single trailing `2` — `-2-2 pls` is silently
  dropped despite the pixels being there.
- **example_31**: the team mask shows `=)` at the same clarity as the
  passing `gl`, but the Windows OCR engine returns no box for that line's
  body. EasyOCR also drops it. Symbol-only short tokens are below both
  engines' detection floor.

Pipeline-side knobs (HSV bands, morphology, component filters,
`min_box_height_fraction`) cannot recover characters the OCR backend
chose not to emit. Reach for them only after confirming the mask is
intact AND a box is returned but garbled.

---

## Attempt #1 — `scale_factor` 4 → 5 (REJECTED, 2026-05-14)

**Hypothesis:** giving the Windows OCR engine 25% more pixels per glyph
would recover short-body dropouts (example_11, 31) and player-name suffix
garble (example_17) without changing character recognition on
already-passing fixtures.

**Result:** 18 / 32 pass (gained 11, 17, 18; lost 07 and changed the
failure modes of 13 and 31). Specifically:
- example_07 regresses: `[PuddingLORD]: 243 level` → `249 level` (digit
  `3` reads as `9` at the larger scale).
- example_13 drifts in the previously-passing portion: `speak better`
  → `spak better`.
- example_31 develops a new drift: `Joebar79` → `Joebar791` and now also
  drops `gl`.

**Conclusion:** the Windows OCR engine's confidence shifts non-uniformly
with scale. Some glyphs improve, others degrade. `3` ↔ `9` at scale 5 is
a strict regression that disqualifies the change. Reverted.

**For future:** if exploring scale-related tuning, do it per-glyph-class
or look at sub-pixel preprocessing instead; bumping the global scale
isn't safe.

---

## Attempt #2 — Drop single-character continuation lines (ACCEPTED, 2026-05-14)

**Hypothesis:** the chat-text mask occasionally picks up stray UI / scene
elements at chat-band colour that OCR reads as a lone glyph. Merging
that lone glyph into the active record via the continuation path
corrupts the body. Filter continuations of length 1 (alphanumeric) at
the buffer level.

**Result:** no fixture flipped to PASS, but example_14's failure surface
strictly shrank (one fewer missing line + one fewer unexpected line —
the spurious `[Omphalode]: speak better o` is gone).

**Implementation note:** initial attempt dropped these lines inside
`_reconstruct` itself, which broke `test_reconstruct_lines_splits_different_rows`
in `test_image_processing.py` — that unit test asserts that single-char
boxes still produce single-char lines (reconstruction is a low-level
function with documented behaviour). The right scope is the buffer's
continuation handler, where the filter is semantically a "this is not a
real chat continuation" decision rather than a reconstruction concern.

**Risk if anything in future grows a 1-char chat body (e.g. someone
typing literally just `k`):** that line will be silently dropped. The
shortest legitimate body in the current corpus is 2 characters (`gg`,
`xd`, `:)`, `=)`).

---

## Attempt #3 — `max_continuation_y_gap_factor` 2.0 → 1.5 (ACCEPTED, 2026-05-14)

**Hypothesis:** the chained bleed in example_14
(`[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child`) walks
down the screen across the player-portrait UI region. Each bleed line
sits ~1.8 × the median chat line-height below the previous one — under
the 2.0× ceiling, so they keep getting merged. Tightening the gap to
1.5× breaks the chain at the first jump.

**Result:** example_14 drops from 3 missing + 2 unexpected lines to
1 missing + 0 unexpected. No regressions in any other fixture (running
both `iter_regression.py` and the full unit-test suite).

**Cross-fixture spot check (manual):**
- example_11 recovery of `[vhl]: ggwp` from `[vhl];` + `ggwp` boxes
  works at 1.5× — those two boxes are on the same physical chat line so
  their y-gap is essentially zero.
- example_17 warning-bleed: the warning sits ~12× the median below
  `[A7X]: gg`, far above either threshold.
- Long passing fixtures (01–03, 06–08, 10, 15–16, 19–21, 26, 29–30):
  intra-message continuations in these fixtures are all from the same
  physical chat line, well under 1.5×.

**Unit test impact:** `test_resolve_ocr_profile_uses_windows_default_profile`
asserts the literal default value. Updated to match.

**For future:** if a fixture needs a wider gap, prefer making the gap
factor a profile-level override (or use the existing
`max_continuation_y_gap_factor` flat override path) rather than walking
this back globally.

---

## Attempt #4 — Speaker recovery by anchor body_start_x matching (ACCEPTED, 2026-05-14)

**Hypothesis:** when the missing-prefix heuristic fires it produces a
record with `player="unknown"`. In ~half of those cases, the
continuation's `first_box_x` aligns precisely with the `body_start_x` of
one specific known anchor. Different player names have visibly different
body-start columns (`[A7X]:` starts the body at x≈257, `[Omphalode]:`
at x≈493 because `]:` lands at a different column for short vs long
names). When the continuation's body_start_x lines up with one anchor
and is far from the others, that anchor's player is the right
attribution — without re-OCRing the prefix region.

**Implementation:** plumb each anchor's player name through
`compute_prefix_evidence_for_lines`, store an `anchor_players` list
alongside `anchor_body_start_xs`. When `has_missing_prefix_evidence`
fires AND ≥2 distinct players speak in the same channel, pick the
anchor whose body_start_x is closest to the continuation's
`first_box_x`, accept it if `dx ≤ 18 px` (≈ one character at
scale_factor=4). Otherwise fall back to `unknown`. The 18 px tolerance
is well under the typical inter-player gap (~100–250 px when name
lengths differ) so misattribution is unlikely.

**Result:**
- example_13 flips XFAIL → PASS — `[unknown]: xdd` becomes `[A7X]: xdd`
  (only A7X and Omphalode speak; xdd at x=257 matches A7X's body_start
  exactly, dx=236 to Omphalode).
- example_27 loses one of three failure cases — `[unknown]: for fun!`
  becomes `[A7X]: for fun!`. Still fails on `MimiOhan` C/O drift and
  caret-pair drift.
- example_05 changes attribution from `[unknown]: YO` to `[Flea]: YO`.
  Both are wrong (expected `[Cipe]: YO`) — this fixture's Cipe never
  appears as an anchor, so no body_start match is possible. Failure
  count unchanged.
- example_23 / 24 unchanged — `epic!` body_start_x of 257 is 68 px from
  Power's 325, well outside the 18 px tolerance, so heuristic
  correctly declines to attribute and stays `[unknown]`.

**Where this DOES NOT help:** any fixture where the expected speaker
never appears as an anchor on the same channel (example_05, 23, 24).
Those need actual prefix-region re-OCR (T-51 phase 2).

**Risk for future fixtures:** if two speakers happen to have nearly
identical body_start_xs (e.g. two short player names of the same
length), the heuristic could pick the wrong one. The
distinct-player count gate (≥2) ensures the heuristic only fires when
there's an actual choice, and the 18 px tolerance is tight enough that
near-collisions are unlikely.

---

## Attempt #5 — Generalize `ocr_fix_closing_bracket` to strip trailing junk (ACCEPTED, 2026-05-14)

**Hypothesis:** the existing `ocr_fix_closing_bracket` correction only
strips a single trailing `l` or `I` from the player token (the
canonical misread of `]`). But OCR sometimes reads `]` as a run of
garbage like `l�.`, `l•.`, `..`, etc. — the trailing run is always
non-alphanumeric punctuation. Strip all trailing non-alnum characters
in the `MISSING_CLOSING_BRACKET_PATTERN` branch before testing the
canonical `l`/`I` rule.

**Implementation:** in `classify_line`, after extracting the player from
`MISSING_CLOSING_BRACKET_PATTERN`, strip trailing non-alphanumeric
characters when the line starts with `[`. Then the existing `l`/`I`
test runs against the cleaned tail and the existing normalize logic
strips that single character if present. Real OW player names never
end in punctuation, so this is a safe widening.

**Result:**
- example_17 flips XFAIL → PASS — `[A7Xl�.]: gg` becomes `[A7X]: gg`.
  The `�.` is stripped (non-alnum); the remaining tail ends in `l` so
  `ocr_fix_closing_bracket` is set and the `l` gets stripped at
  `normalize_finished_message` time.
- No other fixture changes.

**Risk for future fixtures:** a legitimate player name that genuinely
ends in punctuation AND is captured by the missing-closing-bracket
pattern (i.e. OCR also lost the `]`) would now have its trailing
punctuation stripped. OW player-name rules don't allow trailing
punctuation as far as the regression corpus shows, so this is a
non-issue in practice.

---

## Final state (2026-05-14)

- Baseline 16 / 32 → final 18 / 32 PASS.
- Two new passing fixtures: example_13, example_17.
- Partial improvement (not yet passing) on example_14 and example_27.
- No regressions in the 16 previously-passing fixtures or in the
  259-test unit suite.

**Remaining xfail count after this session: 14** (was 16). Cases that
remain are pure character-level OCR drift, OCR-engine token dropouts,
and speaker-recovery cases where no anchor for the expected speaker
exists in the same channel.
