# Known regression test failures

Last updated: 2026-04-06. Run with `pytest --run-ocr tests/test_regression_screenshots.py`.

These failures are **pre-existing** - they were present before the T-26 normalization work and are unrelated to it.

---

### example_02 - trailing OCR garbage appended to message content
- **Channel:** all_lines
- **Expected:** `[MrHenderson]: you guys suck baalls`
- **Actual:** `[MrHenderson]: you guys suck baalls enekleA`
- **Root cause:** The token `enekleA` comes from a visually cut-off line at the bottom of the chat region — the line occupies approximately half the normal line height because it is clipped by the crop boundary. A full-height line threshold (bounding-box height filter) would discard it before it ever reaches the parser. No such filter currently exists.
- **Related task:** T-29

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
- **Actual one record:** `[Flea]: Cipe YO`
- **Root cause:** The raw OCR detects `Flea: Cipe` and `YO` as separate lines, but the player prefix `[Cipe]:` of the second line is already gone at the OCR stage — likely because the trailing `e` of `Cipe` morphed into an unrecognisable glyph, preventing the bracket group from being read at all. Without a valid prefix, `Cipe YO` is classified as continuation and appended to the Flea record. The capitalised `C` in the continuation fragment is OCR-introduced (same glyph confusion as example_04 issue 2).
- **See also:** example_13 (same root cause class).

### example_09 - line missing from actual entirely
- **Channel:** team_lines
- **Missing:** `[marcyl7]: :)`
- **Root cause:** In the raw OCR output the line appears as `[marcyl 7];` — two problems are visible: (1) a spurious space splits the player name into `marcyl` and `7`, and (2) the colon after the closing bracket is read as a semicolon `;`. Both prevent the player-prefix pattern from matching, so the line falls through continuation with no viable payload and is lost. This is a rough OCR detection issue (more noise than a parser edge case) — the glyph recognition on this particular blue-team-colour rendering is unreliable.
- **Related task:** T-30 (team color masking quality)

### example_11 - line missing from actual entirely + split-line artefact
- **Channel:** all_lines
- **Missing:** `[A7X]: gg`
- **Present:** `[vhl]: ggwp` (same channel, passes)
- **Root cause (two separate issues):**
  1. **Split in raw data:** Even `[vhl]: ggwp` — which ultimately passes — appears as two separate bounding boxes in the raw OCR output rather than one. `reconstruct_lines` successfully recombines them, but it shows the OCR detection here is fragile.
  2. **Missing detection:** `[A7X]: gg` is entirely absent from the raw OCR — it never appears at any stage, not even as a fragment. This is a detection gap, most likely in the color mask (the all-chat region on this screenshot may have very low contrast or a rendering artifact that prevents the line from being isolated).
- **Note:** Both issues concern the same screenshot, suggesting an overall image-quality or mask-threshold problem for this frame.

### example_12 - line missing from actual entirely
- **Channel:** team_lines
- **Missing:** `[A7X]: sup dawgs`
- **Root cause:** The line is absent from raw OCR entirely — the mask never isolates it. The background in this screenshot is a strong blue that is visually very similar to the blue team-chat text color. The HSV range used to mask team messages cannot distinguish the text from the background at this color/brightness combination, so the contour is never found and OCR has nothing to run on.
- **Related task:** T-30 (team color masking quality)

### example_13 - two consecutive messages merged into one
- **Channel:** team_lines
- **Expected two records:** `[A7X]: sup dawgs` and `[A7X]: xdd`
- **Actual one record:** `[A7X]: sup dawgs xdd`
- **Root cause:** The `[A7X]:` prefix of the second message is fully absent from the raw OCR data — it is not misread, it simply does not appear. OCR only produces the bare content `xdd`, which has no prefix and falls to continuation, appending to the in-flight A7X record. Because both messages share the same player name, the merged result looks plausible and gives no parse-time signal that anything went wrong.
- **See also:** example_05 (same root cause class).

### example_14 - multi-line garbage bleed on two messages
- **Channel:** team_lines
- **Affected messages:**
  - `[Omphalode]: speak better` → actual: `[Omphalode]: speak better o`
  - `[Omphalode]: u 12?` → actual: `[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child`
  - `[A7X]: i check on your mom more often` → partially present in raw lines but lost in parsed output
- **Root cause:** Extremely difficult screenshot: blue team-chat text on a blue background with additional noise pixels. Two compounding problems:
  1. `[A7X]: i check on your mom more often` is partially detectable in raw lines, but the fragment is garbled enough that it fails prefix matching and is absorbed as continuation into the Omphalode record.
  2. Pink text `Odin's Fav Child` is being read — likely from a player portrait panel or a kill-feed element that overlaps the chat crop region. This bleeds into the Omphalode message content.
- **Note:** Better color handling (tighter pink/player-panel exclusion from the team mask, or a separate color-keyed reject pass) could address the panel bleed. The blue-on-blue detection gap (same class as example_12) is the harder underlying problem. This case requires specific attention — not a quick fix.
- **Related task:** T-30 (team color masking quality)

### example_17 - system notification bleed into player message
- **Channel:** all_lines
- **Expected:** `[A7X]: gg`
- **Actual:** `[A7Xl•.]: gg Warning! You're voting to ban your teammate's preferred hero. -3.1`
- **Root cause (three parts):**
  1. **Player name artefacts:** `A7X` gains a garbled suffix (`l•.` or similar) — OCR reads stray pixels adjacent to the closing bracket as extra characters inside the player name token.
  2. **Vertical-distance bleed:** The warning text comes from approximately two lines below the `gg` message, with a team-chat line in between. The continuation buffer has no concept of vertical distance, so a distant line can still be appended to an open record. A max-vertical-gap constraint on continuation would prevent this class of bleed.
  3. **Missing system pattern:** `Warning! You're voting to ban your teammate's preferred hero.` is not in `SYSTEM_PATTERNS`. Adding it would cause the warning fragment to be dropped rather than appended as content.
- **Related tasks:** T-27 (add hero-ban warning to SYSTEM_PATTERNS), T-28 (max vertical gap for continuation)

### example_18 - message content truncated
- **Channel:** team_lines
- **Expected:** `[Brummer]: guys........... 2-2-2 pls`
- **Actual:** `[Brummer]: guys........... 2`
- **Root cause:** The line is already truncated in the raw OCR data — only `[Brummer]; guys........... 2` is present (note also the semicolon instead of colon on the closing bracket, a minor OCR artefact). The remainder `-2-2 pls` is absent from raw data entirely, meaning the crop or mask clips the right-hand portion of this line before OCR runs. Since `2` alone satisfies `"2".isdigit() == True` it would normally be filtered, but here it is appended to the `guys...........` token via the buffer before the digit check fires — giving the truncated but plausible-looking result.
- **Note:** The root cause is upstream of the parser (mask or crop cuts off the end of long messages). Needs raw bounding-box inspection to determine whether the clip is in the mask or in `reconstruct_lines`.

---

## How to investigate a failure

1. Add a temporary `print` to `extract_chat_lines` or `collect_screenshot_messages` to dump the raw OCR box list and the classified lines for the specific screenshot.
2. Compare the raw box coordinates against the expected chat region to see if boxes are being dropped or merged incorrectly.
3. Check whether the problem is in OCR detection (boxes missing), line reconstruction (`reconstruct_lines` Y-merge), parsing (`classify_line`), or buffering (`MessageBuffer.feed`).
