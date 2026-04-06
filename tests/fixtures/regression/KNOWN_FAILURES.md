# Known regression test failures

Last updated: 2026-04-06. Run with `pytest --run-ocr tests/test_regression_screenshots.py`.

These failures are **pre-existing** — they were present before the T-26 normalization work and are unrelated to it. They are grouped by failure class so an agent working on them can attack one class at a time.

---

## Class A · Line missing from actual entirely

OCR either did not detect the line at all, or the parsed message was silently dropped by a filter.

### example_9 — `[marcyl7]: :)`
- **Channel:** team_lines
- **Missing:** `[marcyl7]: :)`
- **Root cause candidate:** The message content is just `:)` (2 chars). The `msg.isdigit()` filter doesn't explain it, but very short emoji-like tokens may fall below OCR confidence or the line may not survive `reconstruct_lines` grouping. Worth checking raw OCR output from this screenshot.

### example_11 — `[A7X]: gg`
- **Channel:** all_lines
- **Missing:** `[A7X]: gg`
- **Present:** `[vhl]: ggwp` (same channel, passes)
- **Root cause candidate:** `gg` is 2 chars. If OCR reads the line with low confidence and the bounding box doesn't survive `reconstruct_lines`, the line is never fed to the parser. Alternatively the message `gg` is a digit-check false negative (not digits, so it passes) — more likely an OCR detection gap.

### example_12 — `[A7X]: sup dawgs`
- **Channel:** team_lines
- **Missing:** `[A7X]: sup dawgs`
- **Root cause candidate:** Screenshot contains only one team message. If the chat region mask produces no contours for that line, the whole line is absent from OCR output. The team HSV range may not highlight this particular frame's text colour.

---

## Class B · Two consecutive messages merged into one

The buffer treats a new player's next line as a continuation of the previous message. This means the second line has no clearly parsed bracket prefix and `buffer.feed()` interprets it as continuation text.

### example_13 — `[A7X]: sup dawgs` + `[A7X]: xdd` → `[A7X]: sup dawgs xdd`
- **Channel:** team_lines
- **Expected two records:** `[A7X]: sup dawgs` and `[A7X]: xdd`
- **Actual one record:** `[A7X]: sup dawgs xdd`
- **Root cause:** OCR reads `[A7X]: xdd` without its brackets — probably `A7X]: xdd` or `A7X xdd` — which fails all player-prefix patterns and lands in `continuation`. The buffer appends it to the in-flight A7X message.

### example_5 — `[Flea]: cipe` + `[Cipe]: YO` → `[Flea]: Cipe YO`
- **Channel:** team_lines
- **Expected two records:** `[Flea]: cipe` and `[Cipe]: YO`
- **Actual one record:** `[Flea]: Cipe YO`
- **Root cause:** Same as example_13. The `[Cipe]: YO` line loses its brackets in OCR, becomes `Cipe YO` or similar, falls to continuation, and is appended to the Flea message. Note the capital `C` in `Cipe` — the capitalisation is preserved from the raw OCR fragment that became a continuation.

---

## Class C · Trailing OCR garbage appended to message content

Text from adjacent UI elements (scorecard, system notifications, hero names) leaks into the chat region and OCR picks it up as a continuation of the last real message.

### example_2 — `[MrHenderson]: you guys suck baalls enekleA`
- **Channel:** all_lines
- **Expected:** `[MrHenderson]: you guys suck baalls`
- **Actual:** `[MrHenderson]: you guys suck baalls enekleA`
- **Root cause:** The token `enekleA` is continuation text from something rendered below or beside the chat box — likely a player name or UI label that bleeds into the mask region after the last real message line.

### example_14 — multi-line garbage bleed on two messages
- **Channel:** team_lines
- **Affected messages:**
  - `[Omphalode]: speak better` → actual: `[Omphalode]: speak better o`
  - `[Omphalode]: u 12?` → actual: `[Omphalode]: u 12? your mom mor o O[RDK/I Odin's Fav Child`
  - `[A7X]: i check on your mom more often` → entirely missing
- **Root cause:** A large block of UI text (appears to be a player tag `O[RDK/I Odin's Fav Child`) is being read by OCR from somewhere outside the pure chat lines — possibly the team/player panel that overlaps the chat region in this screenshot. The garbage is long enough to swallow the remaining real messages: the A7X line is consumed as part of the Omphalode continuation rather than starting a new record.

### example_17 — system notification bleed into player message
- **Channel:** all_lines
- **Expected:** `[A7X]: gg`
- **Actual:** `[A7Xl…]: gg Warning! You're voting to ban your teammate's preferred hero. -3.1`
- **Root cause (two parts):**
  1. Player name: `A7X` gains a garbled suffix (`l…` or similar) — OCR is reading stray pixels next to the closing bracket as extra characters inside the player name.
  2. Message content: The string `Warning! You're voting to ban your teammate's preferred hero. -3.1` is the in-game hero-ban vote notification rendered over the chat. The chat region crop includes enough of the notification area that OCR reads it as a continuation line appended to the `gg` message.

---

## Class D · Character-level confusion in player name

### example_4 — `Cipe` read as `Oipe`
- **Channel:** team_lines
- **Expected:** `[Cipe]: i die and change`
- **Actual:** `[Oipe]: i die and change`
- **Root cause:** OCR reads the capital `C` as `O`. This is a classic Windows OCR / EasyOCR confusion for certain fonts at small sizes. The player name `Cipe` also appears in a message body (`[Flea]: cipe dont switch`) where casing differs from the actual (`[Flea]: Cipe dont switch`) — the capitalisation in the message body comes from how the continuation fragment was fed to the buffer.
- **Note:** Fixing this class requires either a corpus-based player-name check, post-OCR spell correction, or a character-level confidence threshold — none of which exist yet.

---

## Class E · Message content truncated

### example_18 — `[Brummer]: guys........... 2-2-2 pls` truncated to `[Brummer]: guys........... 2`
- **Channel:** team_lines
- **Expected:** `[Brummer]: guys........... 2-2-2 pls`
- **Actual:** `[Brummer]: guys........... 2`
- **Root cause candidate:** OCR reads the message across two bounding boxes. The first box gives `[Brummer]: guys...........` and the second box contains `2`. The remaining `-2-2 pls` is either on a third box that falls outside the Y-merge threshold (and is dropped), or the `-` confuses something downstream. Since `2` alone passes the `msg.isdigit()` filter (`"2".isdigit() == True`) it would normally be filtered — but here it is present in the output, suggesting the `2` is being appended to `guys...........` via the buffer before the digit check fires, then `-2-2 pls` arrives as a separate fragment that starts a new partial message which is never flushed. Needs raw OCR output inspection to confirm.

---

## How to investigate a failure

1. Add a temporary `print` to `extract_chat_lines` or `collect_screenshot_messages` to dump the raw OCR box list and the classified lines for the specific screenshot.
2. Compare the raw box coordinates against the expected chat region to see if boxes are being dropped or merged incorrectly.
3. Check whether the problem is in OCR detection (boxes missing), line reconstruction (`reconstruct_lines` Y-merge), parsing (`classify_line`), or buffering (`MessageBuffer.feed`).
