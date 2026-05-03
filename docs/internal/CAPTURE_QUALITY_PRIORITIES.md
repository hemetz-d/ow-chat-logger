# Capture Quality Priorities

Derived from the 2026-05-03 `--analyze` pass over all 32 regression fixtures (16 failing after the ex_26 correction). Each entry is an **error class** observed in `tests/fixtures/regression/KNOWN_FAILURES.md`, ordered easiest → hardest by implementation effort.

This is a separate working list from `TASKS.md` — `TASKS.md` tracks specific T-tickets, this file tracks the *failure classes themselves* and the order they should be tackled to drive the regression suite to green.

Effort scale: **XS** (config tweak / single-line) · **S** (small focused fix, ≤1 day) · **M** (multi-file, ≤3 days) · **L** (substantial, ≤1 week with iteration) · **XL** (research, no clear path)

Risk scale: **LOW** (well-bounded, easy to revert) · **MED** (could regress unrelated fixtures) · **HIGH** (architectural, broad blast radius)

---

## Quick-reference matrix

| # | Error class | Effort | Risk | Fixtures fixed | Existing task |
|---|---|---|---|---|---|
| **Tier 1 — Quick wins** ||||||
| 1 | Anchor-count floor: allow heuristic with anchor=1 + stricter probe | XS | LOW | ex_23, ex_24 | T-51 (sub-cause) |
| 2 | System patterns: `^You endorsed `, `^Music selected is ` | XS | LOW | (preventive) | T-50 |
| **Tier 2 — Small focused fixes** ||||||
| 3 | OCR character corrections: `ÅA`→`^^`, end-of-body `!`→`l`/`I` | S | LOW | ex_23, _24, _25, _27, _28 (drift parts) | T-48 |
| 4 | `y_merge_threshold` tuning + within-line reconstruction | S | MED | ex_25 (split) | none |
| 5 | Lower `min_mask_nonzero_pixels_for_ocr` (+ post-OCR confidence) | S | MED | enables short-body detection (paired with #13) | T-49 |
| 6 | ex_18 right-edge mask gap investigation | S | LOW | ex_18, possibly ex_25 partial | T-30 (re-scoped) |
| **Tier 3 — Multi-file work** ||||||
| 7 | Hero detection broadening (whisper + switch) | M | MED | (additive — no failure fixes; unlocks dozens of hero records) | T-46 |
| 8 | UI panel spatial exclusion | M | LOW | ex_14 (panel bleed part) | T-54 (re-scoped) |
| 9 | HSV-band tightening for orange backgrounds | M | MED | ex_22 + noise reduction across in-game fixtures | T-53 |
| 10 | Speaker recovery via mask-region OCR re-run | M | MED | ex_05, ex_13, ex_27 (when boundary works) | T-51 (phase 2) |
| **Tier 4 — Substantial** ||||||
| 11 | Blue-on-blue mask saturation (morphology + thresholding rework) | L | HIGH | ex_09, ex_12, ex_14 partial, ex_22 partial | T-30 |
| 12 | Player-name corpus check / spell correction | L | HIGH | ex_04, ex_17, ex_22, ex_27, ex_28 player-name parts | T-17 (deferred) |
| **Tier 5 — Research / no clear path** ||||||
| 13 | OCR engine short-symbol dropout (`=)`, `:)`, `gg`) | XL | — | ex_09 partial, ex_11, ex_31 | none |
| 14 | OCR non-determinism on boundary detection | XL | — | ex_05, ex_13, ex_17, ex_27 (run-to-run jitter) | none |
| 15 | Body case drift (lowercase → uppercase on first char) | XL | — | ex_04, ex_05 (body parts) | T-17 (folded) |

**Cumulative projection:**
- After Tier 1: **2 fewer failing tests** (ex_23, ex_24).
- After Tier 1 + Tier 2: **3-5 fewer failing tests** depending on how cleanly #3 / #4 / #6 land.
- After Tier 1 + 2 + 3: **8-10 fewer failing tests** (ex_05, _13, _14, _22, _23, _24 fully or mostly resolved).
- After Tier 4: **most player-name and mask-saturation failures resolved** — likely down to 2-4 remaining failures in Tier 5 territory.

---

## Tier 1 — Quick wins

### #1 · Anchor-count floor: allow heuristic with `anchor_count=1` + stricter probe density
**Effort:** XS · **Risk:** LOW · **Fixtures fixed:** ex_23, ex_24 (currently locked out of missing-prefix recovery)

Today the missing-prefix heuristic refuses to fire when `anchor_count < missing_prefix_min_anchor_lines (=2)`. Sparse all-chat captures (only one prefix-bearing line in the channel) are blind to second-message prefix loss. ex_23 and ex_24 both have exactly this shape: `[Power]: this is overwatch goodbye` followed by `epicl` with no detectable prefix → merged because `anchor_count=1` and probing is skipped (`probe_area=0`).

**Fix:** Lower the floor to 1 BUT compensate by tightening the probe density requirement (`missing_prefix_min_span_density: 0.12` → `0.20`). With only one anchor, body_start_range derivation is less reliable, so the probe needs to be more confident before splitting.

**First step:** Add a unit test in `tests/test_buffer.py` that exercises `anchor_count=1` with a synthetic prefix mask of varying densities; confirm the new threshold gates correctly.

**What it fixes when done:** ex_23 and ex_24 split correctly; remaining failure on those fixtures is the secondary `!`→`l` drift handled by #3.

---

### #2 · System patterns: `^You endorsed `, `^Music selected is `
**Effort:** XS · **Risk:** LOW · **Fixtures fixed:** none currently failing (preventive)

ex_25's `You endorsed FlameHawk!` and the `Music selected is Kicks (was Any)` line near ex_29 are not in `SYSTEM_PATTERNS` today. They happen to land between unrelated chat speakers and so don't cause visible breakage — but they're at risk of being parsed as continuation onto the previous record on a slightly different scrollback.

`Music selected is X (was Y)` shares the `(was Y)` shape with hero-switch announcements; **must land before T-46** to prevent the new `HERO_SWITCH_PATTERN` from misfiring on it.

**Fix:** Add two anchored patterns to `parser.SYSTEM_PATTERNS`. Two-line change, one unit test.

---

## Tier 2 — Small focused fixes

### #3 · OCR character corrections: caret pair + end-of-body `!`
**Effort:** S · **Risk:** LOW · **Fixtures fixed:** partial ex_23, _24, _25, _27, _28

Three OCR drift classes uncovered by `--analyze`:
- **Caret pair `^^` → `ÅA`** (ex_25 `you^^`→`youÅA`, ex_27 `okay^^`→`okayÅA`). String-level reverse map: `ÅA`→`^^` applied after `_OCR_CHAR_MAP`.
- **End-of-body `!` → `l`** (ex_27 `thank you!`→`thank youl`, ex_23/24 `epic!`→`epicl`). Apply when body ends in `l` or `I` and second-to-last char is in `[a-z!?.]`.
- **End-of-body `!` → `I`** (ex_28 `much !`→`much I`). Same shape as `!`→`l` variant.

Must NOT fire on legitimate body content (`lol`, `I`, names ending in `l`/`I`). Negative test cases mandatory.

**First step:** Add `_OCR_PAIR_MAP = {"ÅA": "^^"}` applied via `.replace` after `_OCR_CHAR_MAP`. Add `_fix_body_trailing_punct(text)` helper for end-of-body corrections, only invoked from `normalize_finished_message` on completed records (not raw lines).

**What it fixes when done:** ex_27/28 body-text reads cleanly; ex_23/24 still fail until #1 lands too. ex_25 still fails on the line-reconstruction split (#4).

---

### #4 · `y_merge_threshold` tuning + within-line reconstruction
**Effort:** S · **Risk:** MED · **Fixtures fixed:** ex_25

ex_25's `[A7X]: gg bot mimi` splits because OCR boxes for `mimi` (y=1348), `bot` (y=1357), and `[A7Xl:` (y=1362) span exactly 14 px — the current `y_merge_threshold`. The boundary case forces a split into `'bot mimi'` (orphaned continuation, discarded) and `'[A7Xl: gg'` (parses as `[A7X]: gg`).

**Fix options (pick one — DO NOT bundle):**
- **(a)** Bump `y_merge_threshold: 14` → `16`. Trivial, fixes ex_25, but risks merging unrelated lines on tightly-packed scrollbacks.
- **(b)** Make threshold proportional to detected line height (currently constant). Robust but more work.
- **(c)** Add hysteresis: boxes within 14 px always merge; 14-20 px merge only if x-spans overlap or are adjacent (no significant horizontal gap). Best correctness but most complex.

**First step:** Run all 32 fixtures with `y_merge_threshold=16` and diff the `--analyze` output against current state. If no regressions, ship (a). Otherwise pursue (c).

---

### #5 · Lower `min_mask_nonzero_pixels_for_ocr` + add post-OCR confidence gate
**Effort:** S · **Risk:** MED · **Fixtures fixed:** none alone (paired with #13)

The current floor (24 px) drops some legitimate short bodies before OCR runs. Lowering it to 8-12 lets short content reach the engine, but we also need to filter resulting noise — pair with a post-OCR confidence threshold (e.g. drop OCR boxes with conf < 0.5 OR text length 1 with no surrounding context).

**Why "none alone":** for fixtures like ex_31 (`=)`), ex_11 (`gg`), ex_09 (`:)`), the mask already passes the threshold (we verified ex_31 has 1088 body-region pixels) — the **OCR engine** drops the text, not the mask gate. So this fix alone won't fix those tests; it pairs with #13's engine work.

**First step:** Drop floor to 12. Run full regression suite + sweep `--analyze` for new noise lines that should be filtered.

---

### #6 · ex_18 right-edge mask gap investigation
**Effort:** S · **Risk:** LOW · **Fixtures fixed:** ex_18, possibly ex_25 partial

`--analyze` confirmed ex_18's `[Brummer]: guys........... 2-2-2 pls` truncates to `2` at the OCR layer despite 189 px of unused horizontal space inside `screen_region`. The mask itself is failing on `-2-2 pls`. Hyphens and digits should mask cleanly in the team band — needs the `team_mask.png` for this fixture inspected to see whether the mask is empty in that region (mask gap) or non-empty but missed by OCR.

**First step:** View `Output/analyze/ex_18/team_mask.png` and zoom on x≈845..1300, y≈558..630 (the `-2-2 pls` region). Two outcomes:
- Mask empty → text colour falls outside team band on the right portion (could be fade or shadow); fix is HSV widening on V dimension or local contrast adjustment.
- Mask present but OCR missed it → engine-side issue similar to #13.

**What it fixes when done:** ex_18, and possibly informs whether ex_25's `bot mimi` truncation (#4) shares a root cause.

---

## Tier 3 — Multi-file work

### #7 · Hero detection broadening (whisper + switch)
**Effort:** M · **Risk:** MED · **Fixtures fixed:** none currently failing (additive)

T-46 in `TASKS.md` already has the full design. From the analyze pass, the value is bigger than I'd estimated: hidden hero info exists in `--analyze` raw lines on ex_04, _05, _09, _11, _17, _22, _23, _24, _27, _28, _29, _30 — every one of those fixtures would emit hero records the hero log doesn't see today. Do this even though it doesn't fix any failing chat tests; the value is in unlocking the hero-log integration tests that currently can't be written.

**First step:** Implement `WHISPER_HERO_PATTERN` and `HERO_SWITCH_PATTERN` per T-46's spec. Land #2 first (system patterns) so `Music selected is X (was Y)` doesn't false-positive on the switch matcher.

---

### #8 · UI panel spatial exclusion
**Effort:** M · **Risk:** LOW · **Fixtures fixed:** ex_14 (panel bleed part)

T-54 re-scoped: the panel bleed in ex_14 is teal/cyan inside the team band, not pink, so hue-rejection won't help. Spatial exclusion is the only viable angle.

**First step:** Identify the player-portrait panel's bounding box in ex_14's chat capture region. Add `chat_region_exclusions` config key (list of `[x, y, w, h]`). Subtract those rectangles from the mask after thresholding.

**Risk note:** if the panel position varies across game modes, a static rectangle will miss some cases. Acceptable for ex_14; revisit if more bleed shapes appear elsewhere.

---

### #9 · HSV-band tightening for orange backgrounds
**Effort:** M · **Risk:** MED · **Fixtures fixed:** ex_22 (chat content recovery), reduces noise across in-game fixtures

ex_22's all_mask is **2,676,230** nonzero pixels (40× normal) because the wood-paneled walls fall inside H 0-20. T-53 covers this. Other in-game fixtures (ex_29, ex_30, ex_24) show the same 50k-260k range of false-positive all-mask area.

**First step:** Tighten S/V floors on the all band (currently `[0,150,100]–[20,255,255]`). The actual chat-text orange has S>200 typically; raising the S floor from 150 to 200 should kill most background paneling without losing chat. Verify against ex_19/_20/_21/_23/_24 which currently pass on the all channel.

**Pairs with T-35:** the chat-color preset work has already done the hue palette analysis; reuse it here.

---

### #10 · Speaker recovery via mask-region OCR re-run (T-51 phase 2)
**Effort:** M · **Risk:** MED · **Fixtures fixed:** ex_05, ex_13, ex_27 (when boundary detection works)

When the missing-prefix heuristic detects a boundary, currently the recovered record is `[unknown]:`. Phase 2 re-runs OCR on the prefix mask region (with relaxed thresholds — smaller min-area, no allowlist filter) to extract the actual player name.

**First step:** Implement `recover_prefix_text(mask, line_y, prefix_x_range)` that crops the mask, upscales further, runs OCR with relaxed config, and returns either a valid bracketed name or `None`. Wire into `MessageBuffer.feed`'s missing-prefix path.

**Risk:** prefix region may have insufficient text content even after re-scaling. The `[unknown]` fallback stays as a safety net.

---

## Tier 4 — Substantial

### #11 · Blue-on-blue mask saturation rework (T-30 broad work)
**Effort:** L · **Risk:** HIGH · **Fixtures fixed:** ex_09, ex_12, partial ex_14, partial ex_22

Four fixtures show the same pattern: team_mask in the **1M-2.3M nonzero pixel** range, raw OCR returns nothing useful. The mask captures everything (text and background indistinguishable in HSV space), so contour detection has no shape to work with.

**Approach options (likely needs combination):**
- (a) **Adaptive thresholding:** use local contrast within the chat region instead of global HSV bands.
- (b) **Edge detection assist:** combine HSV mask with Canny edges; only keep mask pixels that are also near an edge.
- (c) **Color-delta from background:** sample background colour from a known non-chat region (e.g. top-right corner of the chat box), reject mask pixels within Δ of that colour.
- (d) **Tighter S/V floors specifically when team mask area exceeds N%.** Threshold-on-threshold.

**First step:** Pick one fixture (ex_12 — cleanest case, only 1 missing line) and prototype each option in a notebook. Pick the one that recovers `[A7X]: sup dawgs` without regressing ex_06 / _07 / _08 (high-mask passing fixtures).

**Risk:** any mask change risks regressing the 13 currently-passing fixtures. Per-fixture diff testing is mandatory.

---

### #12 · Player-name corpus check / spell correction
**Effort:** L · **Risk:** HIGH · **Fixtures fixed:** ex_04, ex_17, ex_22, ex_27, ex_28 (player-name parts)

T-17 was deferred originally. The `--analyze` pass shows 5 fixtures hit player-name OCR drifts (`Cipe`→`Oipe`, `MimiChan`→`MimiOhan`, `A7X`→`AN`, `A7X`→`A7Xl•.`). A sliding corpus of recently-seen player names — built from previously-correct detections in the session — would let post-OCR correction catch these drifts.

**Approach:**
- Maintain a per-session corpus of player names seen with high-confidence detections.
- After parsing each line, check if the detected player name has high edit-distance to a corpus entry (Levenshtein < 2 or 25% of name length).
- If so, replace with the corpus entry.

**Risk:** false corrections turn `A7Xl•.` into `A7X` correctly but might also turn `Daniel` into `Daniel-but-different-letter` if both exist. Needs careful threshold + a "do not auto-correct" list for ambiguous cases.

**First step:** Define the data structure (in-memory dict, persisted to `chat_log.sqlite`?). Decide threshold. Prototype on the 5 affected fixtures.

---

## Tier 5 — Research / no clear path

### #13 · OCR engine short-symbol dropout
**Effort:** XL · **Affected:** ex_09 partial (`:)`), ex_11 (`gg`), ex_31 (`=)`)

Both Windows OCR and easyocr drop short isolated symbol/letter tokens. We verified `=)` is missing from both engines on ex_31 with the mask intact. No clean fix available without:
- (a) Trying a third OCR engine (PaddleOCR, RapidOCR, Tesseract with custom config).
- (b) Pre-processing to inject letter-context (artificially extend the body region with neighbouring `:` or `]` from the prefix to make OCR treat it as a continuation).
- (c) Post-processing: detect "prefix-only line with mask body coverage" and re-run OCR on the body with different scale/padding.

All three are experimental. Document and accept until either a new OCR backend is evaluated or the gap becomes unacceptable.

---

### #14 · OCR non-determinism on boundary detection
**Effort:** XL · **Affected:** ex_05, _13, _17, _27 (boundary detection regime flips run-to-run)

Same input image, different OCR runs return slightly different y-coordinates for the same boxes, which flips the missing-prefix heuristic between "boundary detected" and "boundary missed". Engine-internal — not addressable from our pipeline alone.

**Mitigations to consider:**
- Run OCR multiple times and take consensus (expensive — 2-3× per frame).
- Switch to a deterministic engine (most modern OCR engines aren't fully deterministic).
- Loosen the heuristic's thresholds to be tolerant of small y-coord shifts.

The third option overlaps with #1 and may be the practical move once #1 lands.

---

### #15 · Body case drift (lowercase first char → uppercase)
**Effort:** XL · **Affected:** ex_04, ex_05 (body parts)

`cipe` reads as `Cipe` in body content. Same low-confidence-glyph class as the player-name C/O drift but on body text. Without character-level confidence from the OCR engine, this needs the same corpus/spell-check machinery as #12 — and corpora for *body content* are much harder to build than for player names (open vocabulary).

Likely folded into #12's corpus work, or accepted as a permanent minor drift.

---

## Maintenance notes

- Re-run `--analyze` on every fixture after each tier lands; the analyze artefacts in `Output/analyze/ex_*/` are the ground-truth source for these priorities.
- Update this file's "Cumulative projection" as fixtures move out of the failing set.
- New observed failure classes (from new fixtures) should be added in their effort tier with an entry similar in shape to the existing ones.
- This file is for ordering and decision-making; per-fixture details stay in `KNOWN_FAILURES.md`, per-task implementation specs stay in `TASKS.md`.
