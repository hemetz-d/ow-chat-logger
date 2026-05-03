# Known regression test failures

Last updated: 2026-05-03. Run with `pytest --run-ocr tests/test_regression_screenshots.py`.

Most failures here are **pre-existing** — they were present before the T-26 normalization work and are unrelated to it. Entries for example_25–31 are newly added fixtures that exercise hero-info patterns the parser does not yet support (see T-46) and chat panels with non-default backgrounds (lobby / main menu).

---

### example_04 - C/O player-name drift + body case drift
- **Channel:** team_lines (all_lines passes 100%)
- **Issues (two OCR drift classes, both confirmed via `--analyze`, 2026-05-03):**
  1. `[Cipe]: i die and change` → `[Oipe]: i die and change`: OCR reads the leading capital `C` as `O`. Classic C/O confusion for this font at chat render size — same class as ex_27's `MimiChan`→`MimiOhan` and ex_28's `MimiChan`→`MimiOhan`.
  2. `[Flea]: cipe dont switch` → `[Flea]: Cipe dont switch`: lowercase `c` in body read as uppercase `C`. Independent low-confidence drift on short lowercase glyphs.
- **Root cause:** OCR glyph ambiguity at chat-render scale. Both classes need a corpus-based player-name check (T-17 deferred) or character-level confidence thresholds — neither exists yet.
- **Hidden hero info for T-46:** team raw includes `'Cipe switched to Orisa (was Sigma).'` → 2 hero records (`Cipe→Orisa`, `Cipe→Sigma`) when T-46 lands.

### example_05 - missing-prefix split works in analyze, fails in pytest
- **Channel:** team_lines (all_lines passes 100%)
- **Expected two records:** `[Flea]: cipe` and `[Cipe]: YO`
- **Actual (OCR-run-dependent — both observed):**
  - `pytest --run-ocr`: `[Flea]: Cipe YO` (single record — boundary detection failed)
  - `--analyze` (2026-05-03): `[Flea]: Cipe`, `[unknown]: YO` (boundary detected — anchor=3, has_missing=True, probe density 0.30; speaker recovery missing)
- **Root cause:** Two classes, both real.
  1. **OCR non-determinism on boundary detection** (same pattern as ex_13, ex_17, ex_27): the missing-prefix heuristic fires correctly when OCR returns `YO` cleanly as a separate raw line; merges when OCR groups the boxes differently. The body-case drift (`cipe` → `Cipe`) is consistent across runs.
  2. **Speaker recovery never works**: even when the heuristic splits the line, the recovered speaker is `[unknown]` not `[Cipe]`. T-51 covers both.
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

### example_13 - missing-prefix split works in analyze, fails in pytest
- **Channel:** team_lines (all_lines passes 100%)
- **Expected two records:** `[A7X]: sup dawgs` and `[A7X]: xdd`
- **Actual (OCR-run-dependent — both observed):**
  - `pytest --run-ocr`: `[A7X]: sup dawgs xdd` (single record — boundary detection failed)
  - `--analyze` (2026-05-03): `[A7X]: sup dawgs`, `[unknown]: xdd` (boundary detected — anchor=4, has_missing=True for line 2; speaker recovery missing)
- **Root cause:** Same OCR non-determinism as ex_05 / ex_27. T-51 covers both boundary consistency and speaker recovery.
- **Related task:** T-51.
- **See also:** example_05 (same root cause class).

### example_14 - multi-line garbage bleed on two messages
- **Channel:** team_lines
- **Affected messages:**
  - `[Omphalode]: speak better` → actual: `[Omphalode]: speak better o`
  - `[Omphalode]: u 12?` → actual: `[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child`
  - `[A7X]: i check on your mom more often` → partially present in raw lines but lost in parsed output
- **Root cause (`--analyze`, 2026-05-03):** team_mask is **1,185,282 nonzero pixels** (massive over-coverage). All-mask is empty. Three compounding issues:
  1. **`[A7X]: i check on your mom more often` garbled to `'your mom mor o'`:** OCR detects a partial fragment with no prefix box. It falls through as `category=continuation` and merges onto the open Omphalode record. T-51 territory (missing-prefix recovery), but the fragment may be too damaged to recover the player even with the heuristic working.
  2. **Stray `'o'` on raw line 3:** appended onto `[Omphalode]: speak better` → `[Omphalode]: speak better o`. Single-character mask artefact.
  3. **`Odin's Fav Child` panel bleed:** the player-portrait panel's text appears in TEAM mask, not all mask — meaning the panel renders with hue components inside H 96-118 (likely a teal/cyan accent rather than pure pink). **T-54's original "reject pink hue" angle does NOT apply here** — the offending pixels are inside the team band. The fix needs to be **spatial exclusion** of the player-portrait region from the chat crop, not hue rejection. T-54 description has been updated to reflect this.
- **Related tasks:** T-51 (continuation merge); T-54 (UI panel bleed — re-scoped to spatial exclusion); T-30 (broader mask-coverage tightening).

### example_17 - player-name garble (warning bleed is non-deterministic)
- **Channel:** all_lines
- **Expected:** `[A7X]: gg`
- **Actual (OCR-run-dependent — both observed):**
  - `pytest --run-ocr` (2026-05-03): `[A7Xl•.]: gg Warning! You're voting to ban your teammate's preferred hero.` (warning bleeds in)
  - `--analyze` (2026-05-03): `[A7Xl�.]: gg` (warning correctly filtered, no bleed)
- **Root cause:** Two distinct issues, only one persistent.
  1. **Player-name artefact (persistent):** OCR reads stray pixels adjacent to the closing bracket as extra characters inside the player name token (`A7X` → `A7Xl•.`/`A7Xl�.`). Same root-cause class as the trailing-`l` / `I` cleanup in T-15 / T-16, but the suffix here is multi-character noise that the existing `ocr_fix_closing_bracket` heuristic does not strip. Fixing this class generally needs OCR character-level confidence or a corpus-based player-name check (same blocker as T-17).
  2. **Warning text bleed (non-deterministic):** T-27 (warning in `SYSTEM_PATTERNS`) only matches when OCR returns the full warning as ONE line. In this fixture OCR splits the warning across two raw lines (`"Warning! You're voting to ban your teammate's"` + `"preferred hero."`) because the chat-panel width forces a wrap, so the per-line `SYSTEM_REGEX.search` no longer matches either half. T-28 (max vertical gap for continuation) catches the bleed when the y-gap between `gg` and the warning is large enough — in the `--analyze` run it was 207 px (over the ≈140-160 threshold), preventing the bleed. The pytest run must have had different OCR y-coordinates that fell under the threshold. So T-27 + T-28 both work as designed; they happen to fully cover this fixture in some runs and miss in others, depending on OCR's y-precision and reconstruction. **T-47 was filed assuming this was a per-line system-pattern scrub gap; the actual gap is OCR-engine non-determinism on the same input. Re-scope or close T-47 — the per-line logic is sound; the data into it is jittery.**
- **Hidden hero info for T-46 on this fixture:** team channel has `A7X (Ana) to Rizzmaser303 (Orisa); Hello!` (whisper, 2 hero records) and `clutches4fun (Ashe); Hello!` (greet, 1 record).

### example_18 - message content truncated (mask gap, NOT crop boundary)
- **Channel:** team_lines
- **Expected:** `[Brummer]: guys........... 2-2-2 pls`
- **Actual:** `[Brummer]: guys........... 2`
- **Root cause (`--analyze`, 2026-05-03):** OCR returns `[Brummer]; guys........... 2` with the rightmost box (`2`) ending at x=845 in upscaled coords (~x=291 in screen-region coords). The default `screen_region` width is 400 — there are 189 px of unused horizontal space to the right of the truncation point, so this is **NOT a crop-boundary clip** as the pre-`--analyze` triage assumed. The mask itself is failing to capture `-2-2 pls` despite ample room. Hyphens and digits should mask cleanly in the team band; needs the `team_mask.png` for this fixture inspected to see whether the mask is empty in that region (mask gap) or non-empty but missed by OCR (engine drop similar to ex_31's symbol-dropout).
- **Related task:** T-52 framing was wrong (this is not the same class as ex_25 line-reconstruction split). Closest fit is T-30 (mask quality) — needs a separate sub-investigation. Document and revisit once the team_mask is inspected.

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
- **Actual (`--run-ocr`, 2026-05-03):** single record `[Power]: this is overwatch goodbye epicl`
- **Root cause (confirmed via `--analyze`, 2026-05-03):** OCR returns `[Power]; this is overwatch goodbye` and `epicl` as **two separate raw lines** (y=862 and y=982 — gap of 120 px, well beyond `y_merge_threshold`). The merge happens not in OCR but in the parser: `epicl` has no prefix box, so it falls through as `category=continuation` and is appended to the still-open Power record. The missing-prefix heuristic SHOULD split it, but **`anchor_count=1` on the all channel** (the channel has only one prefix-bearing line — `[Power]:`; `[Match]:` is filtered by `IGNORED_SENDERS` before counting). The heuristic requires `missing_prefix_min_anchor_lines: 2` to compute `body_start_range`, so probing is skipped (`probe_area=0`) and the recovery never triggers. The trailing `!` → `l` drift on `epicl` is a secondary OCR class.
- **Related tasks:** T-51 (continuation merge — specifically the anchor-count floor blocking sparse-channel detection is the live blocker here); T-48 (`!`→`l` end-of-body correction — addresses the secondary OCR drift).

### example_24 - same merge as example_23, separate capture
- **Channel:** all_lines
- **Expected / Actual:** identical to example_23 above.
- **Root cause:** Same as example_23 (anchor-count floor blocks recovery; confirmed via `--analyze`). Kept as a second fixture so a future fix can be validated against more than one capture of the bug.
- **Related tasks:** T-51, T-48 (same as example_23). T-46 will additionally extract hero info from the team channel's whispers (`bmf→Moira`, `Zacama→Anran`, `GodOfTheGapped→Domina`) — currently filtered as system, surfaced by `--analyze` as low-hanging hero records.

### example_25 - lobby chat: line-reconstruction split + caret OCR drift
- **Channel:** team_lines + all_lines (the lobby renders different speakers in different colour bands; same pattern as ex_26 / ex_28)
- **Expected:** `[A7X]: gg bot mimi`, `[MimiChan]: you^^` (team) + `[Aerotex]: free` (all)
- **Actual (`--analyze`, 2026-05-03):** `[A7X]: gg`, `[MimiChan]: you�A` (team) + `[Aerotex]: free` (all, correctly captured)
- **Root cause:** Two real issues on the team channel; the all channel passes.
  1. **Line-reconstruction split** (NOT right-edge truncation): OCR returns `bot`, `mimi`, and `[A7Xl: gg` as separate boxes whose y-coordinates span the full `y_merge_threshold=14` window (mimi @ y=1348, bot @ y=1357, prefix @ y=1362). `reconstruct_lines` splits them into two raw lines: `'bot mimi'` (no prefix → falls through as continuation onto an empty buffer → discarded) and `'[A7Xl: gg'` (parses correctly to `[A7X]: gg` via T-15/T-16's missing-closing-bracket recovery). The trailing `bot mimi` is silently dropped. **Pre-`--analyze` triage flagged this as right-edge clip (T-52); that diagnosis was wrong.** No existing task covers this within-line reconstruction split — boundary is exactly at the threshold so even a small bump (15 or 16) would likely fix this fixture, but tightening risks merging genuinely separate lines elsewhere.
  2. **Caret-pair misread** `you^^` → `you�A` (the `Å` rendered with replacement char in some encodings). Same as ex_27. T-48 covers this.
- **Note:** Pre-`--analyze` triage incorrectly listed `[Aerotex]: free` as missing and misclassified the truncation. Both errors were artefacts of the regression test's first-channel-fail short-circuit hiding the all_lines content. Expected.json corrected on 2026-05-03 (moved Aerotex to all_lines, dropped the body-truncation framing). Endorsement lines (`Endorsement Received!`, `You endorsed X!`) are correctly filtered today; T-50 anchors the system patterns explicitly anyway.
- **Related tasks:** T-48 (caret correction). No task covers the line-reconstruction split — kept here as documented limitation.

### example_27 - lobby chat: continuation merge + multiple OCR drifts (non-deterministic)
- **Channel:** team_lines (lobby)
- **Expected:** `[A7X]: bot mimi what is too much?`, `[MimiChan]: why bot .....`, `[A7X]: for fun!`, `[MimiChan]: okay^^`, `[A7X]: thank you!`
- **Actual:** OCR is **non-deterministic** between runs on this fixture. Two observed regimes:
  - `pytest --run-ocr` (2026-05-03): 4 lines — `[A7X]: bot mimi what is too much?`, `[MimiOhan]: why bot for fun!` (merged), `[MimiChan]: okayÅA`, `[A7X]: thank youl`. Boundary detection fails on the why-bot/for-fun split.
  - `--analyze` (2026-05-03): 5 lines — same first line, then `[MimiOhan]: why bot`, `[unknown]: for fun!` (split, speaker not recovered), `[MimiChan]: okayÅA`, `[A7X]: thank youl`. Boundary detection succeeds; speaker recovery still missing.
- **Root cause (four issues, all real regardless of which regime fires):**
  1. **Continuation merge across speakers** (same class as ex_05 / ex_13 / ex_23 / ex_24): `[A7X]:` prefix on `for fun!` is dropped by OCR, so the body either merges into the previous record (boundary failure) or splits into `[unknown]` (boundary succeeds). T-51 covers both — boundary consistency and downstream speaker recovery.
  2. **Player-name `C` → `O`** drift on line 2 only (`MimiChan` → `MimiOhan`) — same C/O glyph ambiguity as ex_04. The same `MimiChan` reads correctly on line 4 in both regimes — drift is per-occurrence, not per-fixture. T-17 (deferred) territory.
  3. **Caret-pair misread** `^^` → `ÅA` (rendered as `�A` in the report due to encoding) — same as ex_25 issue 3. Mask captures the carets fine; OCR fails to recognize the glyph pair.
  4. **Message-body `!` → `l`** on the last line (`thank you!` → `thank youl`) — same artefact class as the trailing-bracket misread in T-15 / T-16, here in message-body content.
- **`--analyze` corroboration:** trailing `.....` on line 2 is lost in raw OCR (sub-confidence dots, not in any OCR box). The `A7X switched to Genii (was Ana)` switch line **also** carries a `Genji` → `Genii` OCR drift, mirroring the `Freja`→`Freia` drift seen in ex_30 — same hero-canonicalization concern noted in T-46.
- **Related tasks:** T-51 (continuation merge — primary, both regimes); T-48 (caret + end-of-body `!`→`l`); T-17 deferred (player-name C/O drift). T-46 documents the wasted hero info on the same screenshot.

### example_28 - lobby chat: OCR drifts on MimiChan line
- **Channel:** team_lines (lobby) + all_lines (Aerotex is genuinely all-chat by colour)
- **Expected:** `[MimiChan]: 3 healer ? its to much !` (team) + `[Aerotex]: dude need cass ult for 1 supp` (all)
- **Actual (`--analyze` + `--run-ocr`, 2026-05-03):** `[MimiOhan]: 3 healer ? its to much I` (team) + `[Aerotex]: dude need cass ult for 1 supp` (all, correctly captured)
- **Root cause:** Two OCR drifts on the team line; no mask gaps, no missing lines, no channel mix-up.
  1. **`MimiChan` → `MimiOhan`** — C/O drift inside player name; same class as ex_27 and ex_04. Player-name spell-correction territory; remains under T-17 (deferred) as a corpus-based-name-check requirement.
  2. **`!` → `I`** at end of body — same trailing-`!` artefact class as ex_27 (which read `l` instead of `I` for the same character). T-48 covers the end-of-body trailing-`!` correction.
- **Note:** The pre-`--analyze` triage in this entry incorrectly listed `[Aerotex]: dude need cass ult for 1 supp` as missing. The line is genuinely all-chat (orange/red HSV band) and is captured correctly today; the original expected.json wrongly placed it in `team_lines`, and the regression test masked the all_lines mismatch because `pytest.fail` on the team channel short-circuits the all-channel assertion. Expected.json corrected on 2026-05-03 to reflect the true channel.
- **Related tasks:** T-48 (end-of-body `!`→`I` correction). T-46 documents the wasted hero info on the same screenshot — three hero-bearing lines are correctly filtered (the switch and two whispers, including the nested-parens whisper that is T-46's hardest single-frame test).

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
