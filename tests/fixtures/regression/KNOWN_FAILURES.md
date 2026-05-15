# Known regression test failures

Last updated: 2026-05-14 (post body_start speaker-recovery + bracket-junk strip
tuning session — see FINDINGS.md). Run with `pytest --run-ocr tests/test_regression_screenshots.py`.

Most failures here are **pre-existing** — they were present before the T-26 normalization work and are unrelated to it. Entries for example_25–31 are newly added fixtures that exercise hero-info patterns the parser does not yet support (see T-46) and chat panels with non-default backgrounds (lobby / main menu).

example_13 and example_17 used to live here; they now pass after the
speaker-recovery (Attempt #4 in FINDINGS.md) and bracket-junk strip
(Attempt #5) changes from 2026-05-14.

---

### example_04 - C/O player-name drift + body case drift
- **Channel:** team_lines (all_lines passes 100%)
- **Issues (two OCR drift classes, both confirmed via `--analyze`, 2026-05-03):**
  1. `[Cipe]: i die and change` → `[Oipe]: i die and change`: OCR reads the leading capital `C` as `O`. Classic C/O confusion for this font at chat render size — same class as ex_27's `MimiChan`→`MimiOhan` and ex_28's `MimiChan`→`MimiOhan`.
  2. `[Flea]: cipe dont switch` → `[Flea]: Cipe dont switch`: lowercase `c` in body read as uppercase `C`. Independent low-confidence drift on short lowercase glyphs.
- **Root cause:** OCR glyph ambiguity at chat-render scale. Both classes need a corpus-based player-name check (T-17 deferred) or character-level confidence thresholds — neither exists yet.
- **Hidden hero info for T-46:** team raw includes `'Cipe switched to Orisa (was Sigma).'` → 2 hero records (`Cipe→Orisa`, `Cipe→Sigma`) when T-46 lands.

### example_05 - speaker recovery + body case drift (boundary now splits correctly)
- **Channel:** team_lines (all_lines passes 100%)
- **Expected two records:** `[Flea]: cipe` and `[Cipe]: YO`
- **Actual (post #1, 2026-05-03):** `[Flea]: Cipe`, `[unknown]: YO` (boundary detection now works after the anchor-count floor fix; remaining diffs are body case drift `cipe`→`Cipe` and missing speaker recovery on `[unknown]`)
- **Root cause (boundary now resolved):** Two remaining classes:
  1. **Speaker recovery missing**: the heuristic splits the line correctly, but the recovered speaker is `[unknown]` not `[Cipe]` — T-51 phase 2 / priority #10 (mask-region OCR re-run on the prefix area).
  2. **Body case drift `cipe` → `Cipe`** — Tier 5 #15 in priorities; needs character-confidence model or corpus check.
- **Note:** Previous entry described OCR non-determinism between pytest and analyze runs. The non-determinism still exists at the OCR-engine level, but with the anchor-count fix the heuristic now fires reliably enough that the test outcome is stable. The earlier "merge" failure regime is gone.
- **Hidden hero info for T-46:** team raw includes `'Flea switched to Wuyang (was Lifeweaver).'` → 2 hero records (`Flea→Wuyang`, `Flea→Lifeweaver`).
- **See also:** example_13 (same root cause class).

### example_09 - blue-on-blue mask saturation + spurious-space player name
- **Channel:** team_lines (all_lines passes 100%)
- **Missing:** `[marcyl7]: :)`
- **Root cause (`--analyze`, 2026-05-03):** team_mask is **1,378,650** nonzero pixels — same massive over-coverage as ex_12 / ex_14 / ex_22 (blue-on-blue scene; mask catches background). Raw OCR returns 8 noisy lines including `'[marcyl 7];'` (just the prefix, no body) and various `A7X (Mei)` voice/whisper lines. Anchor count is **0** for the team channel (none of the noisy raw lines qualifies as a clean prefix anchor), so missing-prefix heuristic can't fire. The `:)` body is silently absent — likely the same OCR engine symbol-only short-token dropout class as ex_31's `=)` (the mask probably has the `:)` pixels but OCR doesn't return text for the symbol pair).
- **Related tasks:** T-30 (team mask saturation on blue-on-blue scenes — primary). The `:)` body absence is the same OCR-engine-limitation class as ex_31 (no task; documented).
- **Hidden hero info for T-46:** `A7X (Mei)` voice lines (multiple), `marcyl 7 (Roadhog)`, `A7X (Mei) to marcyl 7 (Roadhog)` whisper.

### example_11 - `[A7X]: gg` absent from OCR (short-body dropout)
- **Channel:** all_lines (team_lines passes 100% — `[A7X]: what does girltalist mean` correctly captured)
- **Missing:** `[A7X]: gg`
- **Present:** `[vhl]: ggwp` (recovered via two raw boxes `'[vhl];'` + `'ggwp'` joined by buffer continuation — works because the prefix opens an empty record and the body fills it)
- **Root cause (`--analyze`, 2026-05-03):** `[A7X]: gg` is entirely absent from raw OCR — neither the prefix nor the body box appears in either channel's box list. Same OCR-engine-limitation class as ex_31's `=)`: short symbol/letter pair below the engine's detection floor when isolated. The `[vhl]: ggwp` line works because `ggwp` is 4 chars, sufficient for the engine. Anchor count for all channel is **0** (the only "anchor" candidate is the prefix-only `[vhl];`), so missing-prefix heuristic also can't help.
- **Related tasks:** T-49 (short-body threshold) is one possible angle but the underlying issue is the OCR-engine class (same as ex_31). T-30 covers broader mask coverage.
- **Hidden hero info for T-46:** team raw includes `'A7X (Mei); Fall back!'`, `'A7X (Mei); Counting down'` (voice lines — A7X→Mei) and `'FlashR (Lúcio) to Girltalist (Mercy); Hello!'` whisper.

### example_12 - blue-on-blue mask saturation, OCR returns nothing
- **Channel:** team_lines
- **Missing:** `[A7X]: sup dawgs`
- **Root cause (`--analyze`, 2026-05-03):** team_mask is **2,290,286** nonzero pixels (the entire screen-region is essentially masked) but raw OCR is **completely empty**. Mask captures everything; text contours can't be distinguished from the blue background at this color/brightness combination. Same blue-on-blue saturation class as ex_09 / ex_14 / ex_22.
- **Related task:** T-30 (team color masking quality — primary).

### example_14 - `[A7X]: i check on your mom more often` lost in raw OCR
- **Channel:** team_lines
- **Expected missing today (post 2026-05-14 tuning):** `[A7X]: i check on your mom more often`.
- **Previous failure surface (resolved 2026-05-14):**
  - `[Omphalode]: speak better o` (stray 'o' bleed) — fixed by buffer-level
    drop of single-alphanumeric continuations (Attempt #2 in FINDINGS.md).
  - `[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child` (player-portrait
    panel bleed chained onto an open Omphalode record) — fixed by tightening
    `max_continuation_y_gap_factor` 2.0 → 1.5 (Attempt #3 in FINDINGS.md).
    The bleed chain stepped ~1.8× median line-height per jump, just under the
    old 2.0× ceiling; 1.5× breaks the chain at the first jump.
- **Root cause of the remaining miss:** the team_mask is **1,185,282 nonzero
  pixels** (massive over-coverage from a teal/cyan scene element). The
  `[A7X]: i check on your mom more often` line lands inside this overlay
  region; OCR returns only the fragment `'your mom mor o'` for it. That
  fragment is too garbled to match the expected canonical message; even
  recovering the player via the body_start anchor matcher (Attempt #4) would
  not produce a body string that matches the expected one.
- **Related tasks:** T-30 (mask quality on saturated scenes); T-54 (spatial
  exclusion of player-portrait region from chat crop).

### example_18 - OCR engine drops `-2-2 pls` mid-line (NOT a mask gap)
- **Channel:** team_lines
- **Expected:** `[Brummer]: guys........... 2-2-2 pls`
- **Actual:** `[Brummer]: guys........... 2`
- **Root cause (verified 2026-05-14 by writing `team_mask.png` to disk):**
  the team mask shows the **full** `[Brummer]: guys........... 2-2-2 pls`
  string rendered cleanly in white-on-black. The Windows OCR engine
  returns the prefix, `guys...........`, and a single `2` box at
  x=809–845 (upscaled) — then **stops emitting boxes** despite obvious
  text continuing to the right. This is an OCR-engine token-emission
  failure, not a mask issue and not a crop-boundary clip. EasyOCR
  baseline drops it similarly. No pipeline-side tuning recovers a
  segment the OCR backend declined to emit.
- **Related tasks:** none actionable inside this repo's mask /
  reconstruction layer. Workaround would require a second pass with a
  different OCR backend or a different tessellation strategy.

### example_22 - all_mask over-leakage causes duplicate detection + missed lines
- **Channel:** all_lines (team_lines actually passes — confirmed via `--analyze`, 2026-05-03)
- **Expected all_lines:** `[A7X]: ich gärtnere im busch deiner muter`, `[A7X]: xd`
- **Actual all_lines (`--analyze`, 2026-05-03):** `[Kastelg]: hi gooners`, `[AN]: what is this`
- **Root cause (multi-issue):** The screenshot is set in an in-game scene with extensive red/orange wood-paneled walls. The default `all_hsv_lower=[0,150,100]–[20,255,255]` catches that backdrop wholesale: `all_mask` is **2,676,230 nonzero pixels** vs team's **67,888** — 40× over normal. Three downstream effects:
  1. **Duplicate detection of team-chat content:** OCR runs on the over-leaky all-mask, which covers the same spatial regions as the team-chat text. So `[Kastelg]: hi gooners` and `[A7X]: what is this` (both genuinely team-chat) get re-detected by the all-channel pass. The duplicates appear in all_lines with secondary OCR drift (`A7X` → `AN` in this run).
  2. **The actual all-chat content is silently absent:** `[A7X]: ich gärtnere im busch deiner muter` and `[A7X]: xd` are nowhere in either channel's raw OCR. The lines are visible in the screenshot but their chat-text colour appears faded — likely outside the all_hsv saturation/value floors (150/100), or buried in the mask noise.
  3. **`[A7X]` → `[AN]` player-name drift** — secondary OCR artefact, mid-name 7X→N collapse. Different class from T-15/T-16/T-17 trailing-character drift.
- **Related tasks:** T-53 (mask cross-contamination — direct integration target; the mask audit it calls for explains this fixture). T-30 (HSV-band tightening — the wood-panel backdrop is exactly the case T-30's S/V floor review should cover). T-34 (HSV-config propagation — verify any preset change reaches all consumers).

### example_23 - two consecutive all-chat messages merged into one
- **Channel:** all_lines
- **Expected:** `[Power]: this is overwatch goodbye`, `[A7X]: epic!`
- **Actual (post #3, 2026-05-08):** `[Power]: this is overwatch goodbye`, `[unknown]: epic!` — body OCR drift fixed (`epicl`→`epic!`). Only remaining diff is speaker recovery (`[unknown]`→`[A7X]`).
- **Root cause (single remaining class):** Speaker recovery missing — T-51 phase 2 / priority #10.
- **Resolution history:**
  - #1 (T-51 phase 1, 2026-05-03): boundary detection (anchor-count floor + body_start_range relaxation for single-anchor channels) split the merged record correctly. Pre-#1 actual was a single merged record `[Power]: this is overwatch goodbye epicl`.
  - #3 (T-48, 2026-05-08): end-of-body `!`→`l` drift fixed via the chat-interjection whitelist; `[unknown]: epicl` is now `[unknown]: epic!`.

### example_24 - same as example_23, separate capture
- **Channel:** all_lines
- **Expected / Actual (post #3):** identical to example_23 above. Now produces `[Power]: this is overwatch goodbye`, `[unknown]: epic!`. Only remaining failure is speaker recovery (#10).
- **Note:** Kept as a second fixture so a future fix can be validated against more than one capture of the bug.
- **Hidden hero info for T-46:** team channel has `bmf→Moira`, `Zacama→Anran`, `GodOfTheGapped→Domina` whisper records.

### example_25 - lobby chat: caret OCR drift (line-reconstruction split fixed)
- **Channel:** team_lines + all_lines (the lobby renders different speakers in different colour bands; same pattern as ex_26 / ex_28)
- **Expected:** `[A7X]: gg bot mimi`, `[MimiChan]: you^^` (team) + `[Aerotex]: free` (all)
- **Actual (post #4, 2026-05-14):** `[A7X]: gg bot mimi`, `[MimiChan]: you�A` (team) + `[Aerotex]: free` (all). Only remaining diff is the caret-pair body drift `you^^` → `you�A`.
- **Root cause (single remaining class):** **Caret-pair misread** `you^^` → `you�A`. A `_OCR_PAIR_MAP` fix was prototyped under T-48 and then dropped — too narrow (only fires on this player's emoticon style across 2 fixtures) and the precedent of accumulating per-glyph OCR maps is worse than the body-OCR fidelity gain. Documented as a known limitation; revisit once a corpus-based or character-confidence approach is on the table.
- **Resolution history:**
  - #4 (T-55, 2026-05-14): `y_merge_threshold` bumped 14→16 on the `windows_default` profile. OCR previously returned `bot` (y=1348), `mimi` (y=1357), and `[A7Xl: gg` (y=1362) as separate boxes whose span equalled the merge threshold — `reconstruct_lines` split them into two raw lines: `'bot mimi'` (emitted as `[unknown]: bot mimi`) and `'[A7Xl: gg'`. With the widened window all three boxes chain-merge into a single raw line that parses as `[A7X]: gg bot mimi`.
- **Note:** Pre-`--analyze` triage incorrectly listed `[Aerotex]: free` as missing and misclassified the truncation. Both errors were artefacts of the regression test's first-channel-fail short-circuit hiding the all_lines content. Expected.json corrected on 2026-05-03. Endorsement lines (`Endorsement Received!`, `You endorsed X!`) are correctly filtered today; T-50 anchors the system patterns explicitly anyway.
- **Related tasks:** No active task on the caret-pair drift (#3 known limitation).

### example_27 - lobby chat: speaker recovery + player-name + caret drift (trailing-`!` fixed)
- **Channel:** team_lines (lobby)
- **Expected:** `[A7X]: bot mimi what is too much?`, `[MimiChan]: why bot .....`, `[A7X]: for fun!`, `[MimiChan]: okay^^`, `[A7X]: thank you!`
- **Actual (post #3, 2026-05-08):** 5 records — `[A7X]: bot mimi what is too much?`, `[MimiOhan]: why bot`, `[unknown]: for fun!`, `[MimiChan]: okayÅA`, `[A7X]: thank you!`.
- **Root cause (three remaining issues):**
  1. **Speaker recovery missing** — `[unknown]: for fun!` should be `[A7X]: for fun!`. Priority #10.
  2. **Player-name `C` → `O`** drift on line 2 only (`MimiChan` → `MimiOhan`) — same C/O glyph ambiguity as ex_04. The same `MimiChan` reads correctly on line 4 — drift is per-occurrence, not per-fixture. T-17 deferred / priority #12.
  3. **Caret-pair misread** `okay^^` → `okayÅA`. Same shape as ex_25 issue 2; the `_OCR_PAIR_MAP` fix was prototyped under T-48 and dropped on review (per-glyph hardcoded fixes don't scale). No active task.
- **Resolution history:**
  - #1 (T-51 phase 1, 2026-05-03): boundary detection stable across runs (was non-deterministic pre-#1, e.g. `[MimiOhan]: why bot for fun!` as one merged record).
  - #3 (T-48, 2026-05-08): trailing-`l` `thank youl`→`thank you!` fixed via the chat-interjection whitelist.
- **`--analyze` corroboration:** trailing `.....` on line 2 is lost in raw OCR (sub-confidence dots, not in any OCR box). The `A7X switched to Genii (was Ana)` switch line carries a `Genji` → `Genii` OCR drift — same hero-canonicalization concern noted in T-46.

### example_28 - lobby chat: player-name drift (body OCR now fixed)
- **Channel:** team_lines (lobby) + all_lines (Aerotex is genuinely all-chat by colour)
- **Expected:** `[MimiChan]: 3 healer ? its to much !` (team) + `[Aerotex]: dude need cass ult for 1 supp` (all)
- **Actual (post #3, 2026-05-08):** `[MimiOhan]: 3 healer ? its to much !` (team) + `[Aerotex]: dude need cass ult for 1 supp` (all, correctly captured)
- **Root cause (single remaining issue):** **`MimiChan` → `MimiOhan`** — C/O drift inside player name; same class as ex_27 and ex_04. Player-name spell-correction territory; remains under T-17 (deferred) as a corpus-based-name-check requirement / priority #12.
- **Resolution history:**
  - #3 (T-48, 2026-05-08): trailing `I`-after-space body misread fixed via the standalone-`I` rule; `its to much I` is now `its to much !`.
- **Note:** The pre-`--analyze` triage in this entry incorrectly listed `[Aerotex]: dude need cass ult for 1 supp` as missing. The line is genuinely all-chat (orange/red HSV band) and is captured correctly today; the original expected.json wrongly placed it in `team_lines`, and the regression test masked the all_lines mismatch because `pytest.fail` on the team channel short-circuits the all-channel assertion. Expected.json corrected on 2026-05-03 to reflect the true channel.
- **Related tasks:** Priority #12 (player-name corpus / spell-correction). T-46 documents the wasted hero info on the same screenshot — three hero-bearing lines are correctly filtered (the switch and two whispers, including the nested-parens whisper that is T-46's hardest single-frame test).

### example_31 - main-menu chat: OCR engine drops symbol-only short body
- **Channel:** team_lines (main-menu group chat)
- **Expected:** `[Microwave]: hello teamings`, `[Joebar79]: hello`, `[Makiko]: hey`, `[Microwave]: joe biden wake up`, `[Joebar79]: gl`, `[Joebar79]: =)`
- **Actual (`--run-ocr`, 2026-05-03):** all lines present **except** `[Joebar79]: =)`
- **Root cause (per `analyze` run, 2026-05-03):** The mask captures `=)` cleanly — body region for line 6 has 1088 nonzero pixels vs 1600 for the working `gl` body on line 5; both render as obvious 2-character glyphs in `team_mask.png`. The `[Joebar79];` prefix box for line 6 is detected at conf=1.00, but the OCR engine returns **no box at all** for the body region. Final raw line is `'[Joebar79];'` (empty body), which `normalize_finished_message` drops because `not msg`. Cross-checked against the easyocr backend (`--ocr-profile easyocr_master_baseline`) — easyocr drops `=)` too (and additionally drops `gl` and `joe biden wake up`), so this is a class limitation of both supported OCR engines on isolated symbol-only short tokens, not a tunable in our pipeline. The `_OCR_CHAR_MAP` rewrite of `=` → `-` is **not** the cause here; the line never reaches `classify_line`. The expected JSON keeps the user-typed ground truth `=)` so the regression preserves the gap.
- **Not addressed by:** T-49 (mask threshold — mask is intact), T-48 (character corrections — distinct class), T-30 (mask quality — mask is intact). No active task; documented as a known OCR-engine limitation.
- **Note on the rest of the fixture:** The standard hero greet `Lougian (Zenyatta): Hello!` is correctly routed away from chat lines today; T-46 covers its hero-log emission.

---

## How to investigate a failure

1. Add a temporary `print` to `extract_chat_lines` or `collect_screenshot_messages` to dump the raw OCR box list and the classified lines for the specific screenshot.
2. Compare the raw box coordinates against the expected chat region to see if boxes are being dropped or merged incorrectly.
3. Check whether the problem is in OCR detection (boxes missing), line reconstruction (`reconstruct_lines` Y-merge), parsing (`classify_line`), or buffering (`MessageBuffer.feed`).
