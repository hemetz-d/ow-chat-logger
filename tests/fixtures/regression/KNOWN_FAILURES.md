# Known regression test failures

Last updated: 2026-05-03. Run with `pytest --run-ocr tests/test_regression_screenshots.py`.

Most failures here are **pre-existing** — they were present before the T-26 normalization work and are unrelated to it. Entries for example_25–31 are newly added fixtures that exercise hero-info patterns the parser does not yet support (see T-46) and chat panels with non-default backgrounds (lobby / main menu).

---

### example_04 - two distinct OCR errors on the same player name `Cipe`
- **Channel:** team_lines
- **Issues (two separate bugs):**
  1. `[Cipe]: i die and change` → `[Oipe]: i die and change`: OCR reads the leading capital `C` as `O`. Classic C/O confusion for this font at chat render size.
  2. `[Flea]: cipe dont switch` → `[Flea]: Cipe dont switch`: the original message body has lowercase `cipe`; the OCR returns uppercase `Cipe`. The capitalisation is OCR-introduced, not original.
- **Root cause:** Both errors originate in OCR glyph ambiguity at small sizes. Issue 1 is a bracket-region confusion (`C` ↔ `O`). Issue 2 is independent — the lowercase `c` in message content is being read as `C`, suggesting low confidence on short lowercase glyphs in this font/scale.
- **Note:** Fixing this class of error requires a corpus-based player-name check, post-OCR spell correction, or character-level confidence thresholds — none of which exist yet.

### example_05 - two consecutive messages merged into one
- **Channel:** team_lines
- **Expected two records:** `[Flea]: cipe` and `[Cipe]: YO`
- **Current actual:** `[Flea]: Cipe YO` (single record — boundary detection regressed since the original triage; see T-51)
- **Root cause:** The missing-prefix heuristic does not split this line on the 2026-05-03 `--run-ocr` pass; the `[Cipe]: YO` body is appended in full to the still-open Flea record. Even when the boundary is detected (as it was historically), speaker recovery from the bare `YO` mask is not yet implemented. T-51 covers both — boundary detection consistency across fixtures, and downstream speaker recovery.
- **Related task:** T-51 (missing-prefix continuation across speakers).
- **See also:** example_13 (same root cause class).

### example_09 - line missing from actual entirely
- **Channel:** team_lines
- **Missing:** `[marcyl7]: :)`
- **Root cause:** In the raw OCR output the line appears as `[marcyl 7];` — two problems are visible: (1) a spurious space splits the player name into `marcyl` and `7`, and (2) the colon after the closing bracket is read as a semicolon `;` (the latter is now corrected by `_OCR_CHAR_MAP`, so the live failure is the spurious-space split). The `:)` body is also short enough that T-49's threshold may apply — verify with raw box dump whether the body is detected at all.
- **Related tasks:** T-30 (team color masking quality), T-49 (short-body threshold review).

### example_11 - line missing from actual entirely + split-line artefact
- **Channel:** all_lines
- **Missing:** `[A7X]: gg`
- **Present:** `[vhl]: ggwp` (same channel, passes)
- **Root cause (two separate issues):**
  1. **Split in raw data:** Even `[vhl]: ggwp` — which ultimately passes — appears as two separate bounding boxes in the raw OCR output rather than one. `reconstruct_lines` successfully recombines them, but it shows the OCR detection here is fragile.
  2. **Missing detection:** `[A7X]: gg` is entirely absent from the raw OCR. The 2-character `gg` body strongly suggests T-49's short-body threshold is filtering the mask region before OCR runs; the missing prefix is a secondary effect.
- **Related tasks:** T-49 (short-body threshold), T-30 (mask-threshold problem for this frame).

### example_12 - line missing from actual entirely
- **Channel:** team_lines
- **Missing:** `[A7X]: sup dawgs`
- **Root cause:** The line is absent from raw OCR entirely — the mask never isolates it. The background in this screenshot is a strong blue that is visually very similar to the blue team-chat text color. The HSV range used to mask team messages cannot distinguish the text from the background at this color/brightness combination, so the contour is never found and OCR has nothing to run on.
- **Related task:** T-30 (team color masking quality)

### example_13 - two consecutive messages merged into one
- **Channel:** team_lines
- **Expected two records:** `[A7X]: sup dawgs` and `[A7X]: xdd`
- **Current actual:** `[A7X]: sup dawgs xdd` (single record on the 2026-05-03 `--run-ocr` pass — boundary detection regressed since the original triage; same shape as ex_05)
- **Root cause:** The missing-prefix heuristic does not split this line on the current pass. T-51 covers boundary detection consistency and downstream speaker recovery.
- **Related task:** T-51 (missing-prefix continuation across speakers).
- **See also:** example_05 (same root cause class).

### example_14 - multi-line garbage bleed on two messages
- **Channel:** team_lines
- **Affected messages:**
  - `[Omphalode]: speak better` → actual: `[Omphalode]: speak better o`
  - `[Omphalode]: u 12?` → actual: `[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child`
  - `[A7X]: i check on your mom more often` → partially present in raw lines but lost in parsed output
- **Root cause:** Extremely difficult screenshot: blue team-chat text on a blue background with additional noise pixels. Two compounding problems:
  1. `[A7X]: i check on your mom more often` is partially detectable in raw lines, but the fragment is garbled enough that it fails prefix matching and is absorbed as continuation into the Omphalode record (T-51 territory).
  2. Pink text `Odin's Fav Child` is being read from a player-portrait panel that overlaps the chat crop region (T-54 territory).
- **Related tasks:** T-54 (UI panel bleed — addresses the `Odin's Fav Child` injection); T-51 (missing-prefix continuation — addresses the absorbed `i check on your mom more often`); T-30 (broader blue-on-blue mask quality — the underlying detection gap).

### example_17 - player-name garble + warning text still glued onto message
- **Channel:** all_lines
- **Expected:** `[A7X]: gg`
- **Actual:** `[A7Xl•.]: gg Warning! You're voting to ban your teammate's preferred hero.`
- **Root cause (two parts, both still live despite T-27 and T-28 landing):**
  1. **Player-name artefact:** OCR reads stray pixels adjacent to the closing bracket as extra characters inside the player name token (`A7X` → `A7Xl•.`). Same root-cause class as the trailing-`l` / `I` cleanup in T-15 / T-16, but the suffix here is multi-character noise (`l•.`) that the existing `ocr_fix_closing_bracket` heuristic does not strip. Fixing this class generally needs OCR character-level confidence or a corpus-based player-name check (same blocker as T-17).
  2. **Warning text bleed survives T-27 / T-28:** T-27 added the hero-ban warning string to `SYSTEM_PATTERNS` and T-28 capped continuation by vertical gap, yet `--run-ocr` (2026-05-03) still emits the warning as message body. The most likely reason: the warning is merged with the `gg` line at the OCR / `reconstruct_lines` stage (same y-band cluster), so `classify_line` sees a single concatenated line, matches `STANDARD_PATTERN` first, and `SYSTEM_REGEX` never gets a chance — system detection only runs as a per-line classification, not a sub-string scrub of an already-classified standard line. **Tracked as T-47.**

### example_18 - message content truncated
- **Channel:** team_lines
- **Expected:** `[Brummer]: guys........... 2-2-2 pls`
- **Actual:** `[Brummer]: guys........... 2`
- **Root cause:** The line is already truncated in the raw OCR data — only `[Brummer]; guys........... 2` is present (note also the semicolon instead of colon on the closing bracket, a minor OCR artefact). The remainder `-2-2 pls` is absent from raw data entirely, meaning the crop or mask clips the right-hand portion of this line before OCR runs. Since `2` alone satisfies `"2".isdigit() == True` it would normally be filtered, but here it is appended to the `guys...........` token via the buffer before the digit check fires — giving the truncated but plausible-looking result.
- **Related task:** T-52 (right-edge body truncation on long messages — same shape on ex_25 confirms it is systemic).

### example_22 - all_lines emits unrelated content from the team channel
- **Channel:** all_lines
- **Expected:** `[A7X]: ich gärtnere im busch deiner muter`, `[A7X]: xd`
- **Actual (`--run-ocr`, 2026-05-03):** `[Kastelg]: hi gooners`, `[AN]: what is this`
- **Root cause:** The actual emits content that on screen is in **team chat**, not all chat — so the all-chat mask is picking up team-coloured pixels (or the team mask is leaking into the all-chat detection path). Player-name OCR drift on top: `A7X` → `AN`. Two distinct issues:
  1. **Channel cross-contamination** — the bigger of the two; needs the per-channel mask debug images on this fixture to determine whether the team mask's HSV upper edge is creeping into the all-chat band, or whether `crop_to_screen_region` is feeding the wrong slice to the all-chat OCR pass.
  2. **Player-name OCR drift** — the kind of artefact T-15 / T-16 / T-17 already document for trailing characters; here it is `7X` → `N` mid-name, which is a different class.
- **Related task:** T-53 (channel cross-contamination — direct integration target). Overlaps with T-30 (mask quality) and T-34 (HSV-config propagation).

### example_23 - two consecutive all-chat messages merged into one
- **Channel:** all_lines
- **Expected:** `[Power]: this is overwatch goodbye`, `[A7X]: epic!`
- **Actual (`--run-ocr`, 2026-05-03):** single record `[Power]: this is overwatch goodbye epicl`
- **Root cause:** Same shape as example_05 / example_13 (continuation across speakers). The `[A7X]:` prefix for the second message is dropped by OCR, so the `epic!` body has no detectable prefix and is appended to the still-open `Power` record. The trailing `!` is also misread as `l`. T-28's vertical-gap guard does not help here because the two messages are tightly stacked.
- **Related tasks:** T-51 (continuation merge — primary fix); T-48 (`!`→`l` end-of-body correction — addresses the secondary OCR drift).

### example_24 - same merge as example_23, separate capture
- **Channel:** all_lines
- **Expected / Actual:** identical to example_23 above.
- **Root cause:** Same as example_23 — kept as a second fixture so a future fix can be validated against more than one capture of the bug.
- **Related tasks:** T-51, T-48 (same as example_23).

### example_25 - lobby chat: truncated body, missing line, caret OCR
- **Channel:** team_lines (lobby "group" chat)
- **Expected:** `[A7X]: gg bot mimi`, `[Aerotex]: free`, `[MimiChan]: you^^`
- **Actual (`--run-ocr`, 2026-05-03):** `[A7X]: gg`, `[MimiChan]: youÅA`
- **Root cause (three distinct issues):**
  1. **Body truncation:** `[A7X]: gg bot mimi` → `[A7X]: gg`. The trailing `bot mimi` is lost between OCR and the parser. Likely same right-edge-clip class as ex_18.
  2. **Line entirely missing:** `[Aerotex]: free` is absent from both `team_lines` and `all_lines` actual. Either short-body threshold gating or lobby chat-name colour falling outside the HSV band.
  3. **Caret-pair misread:** `you^^` → `youÅA`. New OCR character-class drift not in `_OCR_CHAR_MAP` today.
- **Related tasks:** T-52 (issue 1, right-edge truncation); T-49 (issue 2, short-body threshold) and T-30 (issue 2 alternative cause — lobby mask coverage); T-48 (issue 3, caret-pair correction). The predicted "endorsement leak" from the pre-OCR draft of this entry did not materialize — endorsement lines are correctly filtered today; T-50 anchors the system pattern explicitly anyway.

### example_26 - lobby chat: 3 of 5 expected lines missing
- **Channel:** team_lines (lobby)
- **Expected:** `[Akamé]: gg`, `[MimiChan]: gg`, `[Hichamdhakkr]: gg`, `[A7X]: gg bot mimi`, `[Aerotex]: free`
- **Actual (`--run-ocr`, 2026-05-03):** `[Akamé]: gg`, `[A7X]: gg bot mimi` (only 2 of 5)
- **Root cause:** Three contiguous short lines (`[MimiChan]: gg`, `[Hichamdhakkr]: gg`, `[Aerotex]: free`) are dropped while the lines above and below them are detected. Tightly-packed chat scrollback with 2-character message bodies (`gg`) is the common factor — the same `min_mask_nonzero_pixels_for_ocr` floor that probably drops `[Aerotex]: free` in example_25 likely drops the `gg` lines here too. The whisper line at the top (`Akamé (Sigma) to FlameHawk (Mercy): Hello!`) and the standard hero greet on line 2 (`FlameHawk (Mercy): Hello!`) are correctly **not** in chat output today (routed to system / hero respectively) — the T-46 hero-info gap is documented in T-46's task entry, not here.
- **Related tasks:** T-49 (short-body threshold — primary fix); T-30 (mask coverage on lobby panel — alternative/compounding cause); T-46 captures the hero-info wastage on the same screenshot.

### example_27 - lobby chat: continuation merge across speakers + multiple OCR drifts
- **Channel:** team_lines (lobby)
- **Expected:** `[A7X]: bot mimi what is too much?`, `[MimiChan]: why bot .....`, `[A7X]: for fun!`, `[MimiChan]: okay^^`, `[A7X]: thank you!`
- **Actual (`--run-ocr`, 2026-05-03):** `[A7X]: bot mimi what is too much?`, `[MimiOhan]: why bot for fun!`, `[MimiChan]: okayÅA`, `[A7X]: thank youl`
- **Root cause (four distinct issues):**
  1. **Continuation merge across speakers** (same class as ex_05 / ex_13 / ex_23 / ex_24): `[MimiChan]: why bot .....` and `[A7X]: for fun!` collapse to `[MimiOhan]: why bot for fun!`. The trailing `.....` of the first message is lost (likely sub-confidence dots) and the `[A7X]:` prefix of the second is dropped, so it falls through as continuation onto the still-open MimiChan record.
  2. **Player-name `C` → `O`** drift on the merged line (`MimiChan` → `MimiOhan`) — same C/O glyph ambiguity as ex_04.
  3. **Caret-pair misread** `^^` → `ÅA` — same as ex_25 issue 3.
  4. **Message-body `!` → `l`** on the last line (`thank you!` → `thank youl`) — same artefact class as the trailing-bracket misread in T-15 / T-16, here in message-body content.
- **Related tasks:** ex_05 / ex_13 / ex_23 / ex_24 (continuation merge family); T-46 documents the wasted hero info (`A7X switched to Genji (was Ana)`, `Hichamdhakkr (Soldier: 76): Hello!`) on the same screenshot.

### example_28 - lobby chat: line entirely missing + OCR drifts
- **Channel:** team_lines (lobby)
- **Expected:** `[MimiChan]: 3 healer ? its to much !`, `[Aerotex]: dude need cass ult for 1 supp`
- **Actual (`--run-ocr`, 2026-05-03):** `[MimiOhan]: 3 healer ? its to much I` (only 1 of 2)
- **Root cause:**
  1. **Line entirely missing:** `[Aerotex]: dude need cass ult for 1 supp` is absent. Same suspected cause as ex_25 / ex_26 for the missing Aerotex line — colour or mask-threshold gap.
  2. **`MimiChan` → `MimiOhan`** — same C/O drift as ex_27.
  3. **`!` → `I`** at end of body — same trailing-`!` artefact class as ex_27 issue 4 (here `I` instead of `l`).
- **Related tasks:** T-30 (mask gap on Aerotex line); T-46 documents the wasted hero info on the same screenshot — three hero-bearing lines are correctly filtered (the switch and two whispers, including the nested-parens whisper that is T-46's hardest single-frame test).

### example_31 - main-menu chat: short message body dropped
- **Channel:** team_lines (main-menu group chat)
- **Expected:** `[Microwave]: hello teamings`, `[Joebar79]: hello`, `[Makiko]: hey`, `[Microwave]: joe biden wake up`, `[Joebar79]: gl`, `[Joebar79]: =)`
- **Actual (`--run-ocr`, 2026-05-03):** all lines present **except** `[Joebar79]: =)`
- **Root cause:** The 2-character body `=)` is not detected. Most likely the same `min_mask_nonzero_pixels_for_ocr` floor that drops short bodies elsewhere (ex_25 `[Aerotex]: free`, ex_26 `gg` lines) — the `=)` glyphs after masking simply do not clear the threshold. Note that the `_OCR_CHAR_MAP` rewrite of `=` → `-` is **not** the cause here (the line never reaches `classify_line`); the expected JSON keeps the user-typed ground truth `=)` so the regression remains true to what was said in-chat. Predicted main-menu masking concerns from the pre-OCR draft of this entry did NOT materialize — the team mask catches this panel correctly.
- **Related tasks:** T-30 (mask threshold review for short bodies — same root concern as ex_25 / ex_26 / ex_28). The standard hero greet `Lougian (Zenyatta): Hello!` is correctly routed away from chat lines today; T-46 covers its hero-log emission.

---

## How to investigate a failure

1. Add a temporary `print` to `extract_chat_lines` or `collect_screenshot_messages` to dump the raw OCR box list and the classified lines for the specific screenshot.
2. Compare the raw box coordinates against the expected chat region to see if boxes are being dropped or merged incorrectly.
3. Check whether the problem is in OCR detection (boxes missing), line reconstruction (`reconstruct_lines` Y-merge), parsing (`classify_line`), or buffering (`MessageBuffer.feed`).
