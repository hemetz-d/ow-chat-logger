# Tasks

Derived from the senior design review (2026-04-03). Each task has a severity, location, description, and tracked state.

Severity: **bug** | **structural** | **smell**
State: `open` | `in-progress` | `review` | `done`

---

## Bugs

### T-01 · Y-anchor drift in `reconstruct_lines`
- **Severity:** bug
- **State:** `open`
- **File:** `src/ow_chat_logger/image_processing.py:78`
- **Completed:** —

`current_y` is set to the first box's Y when a new group starts and is never updated while accumulating that group. With `y_merge_threshold=18`, boxes at y=`[0, 15, 30]` produce two groups instead of one: the box at y=30 is compared against y=0 (diff=30 > 18) rather than the most-recent anchor y=15. Real-world OCR on upscaled text regularly returns boxes with gradual Y drift, causing premature line splits.

**Fix direction:** Update `current_y` to the last-seen Y value after each merge, making it a sliding anchor rather than a group-start anchor.

**Test surface:** `tests/test_image_processing.py` — add a case with three boxes showing gradual Y drift within the merge threshold.

---

### T-02 · `HERO_PATTERN` too greedy
- **Severity:** bug
- **State:** `open`
- **File:** `src/ow_chat_logger/parser.py:9`
- **Completed:** —

The hero pattern `^(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)...` has no bracket requirement on the player name. Any OCR fragment of the form `word (word)` — including partial system messages that slip past `SYSTEM_REGEX` — is silently classified as a hero line. Continuation lines that happen to contain parentheses (e.g. `"lol (you wish)")`) are also affected.

**Fix direction:** Tighten the pattern. At minimum require the match to look like a known structure (e.g. player name followed immediately by `(HeroName)` with no leading bracket). Add a negative assertion to prevent matching lines that start with `[`.

**Test surface:** `tests/test_parser.py` — add cases for: parenthetical chat content classified as continuation, partial system message not promoted to hero.

---

### T-03 · `r"channels"` bare substring in system patterns
- **Severity:** bug
- **State:** `open`
- **File:** `src/ow_chat_logger/parser.py:29`
- **Completed:** —

The pattern `r"channels"` in `SYSTEM_PATTERNS` is a bare substring match with no anchoring or word boundary. Any player chat message containing the word "channels" is silently dropped as a system message.

**Fix direction:** Replace with a more specific pattern scoped to the actual system message context (e.g. `r"press \w+ to access voice channels"` or merge it into the Aho-Corasick fragment matcher which already handles the longer form).

**Test surface:** `tests/test_parser.py` — add a case where a player message contains "channels" and is correctly classified as `standard`, not `system`.

---

## Structural Issues

### T-04 · `LazyConfig` write path is not thread-safe
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/config.py:58`
- **Completed:** —

`LazyConfig.__setitem__` and `__delitem__` mutate the shared `_cached_config` dict in place with no lock. The `MutableMapping` interface makes this look safe to callers. While no current code path writes to `CONFIG` from a worker thread, the interface invites it. A concurrent read (from the processing worker) overlapping with a write (from any future path) is a silent data race on a plain dict.

**Fix direction:** Either (a) make `LazyConfig` read-only after startup by removing `__setitem__`/`__delitem__` and narrowing the interface to `Mapping`, or (b) add a `threading.Lock` around all mutations and the cache-population path. Option (a) is safer and reflects actual usage.

**Test surface:** `tests/test_config_helpers.py` — verify the interface contract; if narrowed, verify that existing test setup via `reset_config()` still works.

---

### T-05 · `OCREngine` stores thresholds that are never used
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr_engine.py:12`
- **Completed:** —

`self.confidence_threshold` and `self.text_threshold` are set at init time but the pipeline always passes them explicitly as overrides in every `run()` call. The instance defaults only activate if a caller passes `None`, which never happens in any current code path. The attributes are dead weight that implies a usage contract that doesn't exist.

**Fix direction:** Either remove the instance attributes and require thresholds to always be passed to `run()`, or invert it: remove the overrides from `run()` and rely on instance state. Pick one ownership model, not both.

**Test surface:** `tests/test_pipeline.py` — validate that thresholds flow through correctly after the refactor.

---

### T-06 · Redundant `crop_to_screen_region` call on every live frame
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/pipeline.py:73`
- **Completed:** —

`extract_chat_debug_data` always calls `crop_to_screen_region`, but live captures are already cropped to `screen_region` by `pyautogui.screenshot(region=...)`. The bounds check in `crop_to_screen_region` prevents double-cropping, but it runs on every frame unnecessarily. More importantly, this creates a misleading dual-purpose function: callers must understand whether their input is pre-cropped or full-screen.

**Fix direction:** Add a `pre_cropped: bool = False` parameter to `extract_chat_debug_data` and skip the crop step in live mode. The analyze and regression paths pass full screenshots and still benefit from the crop.

**Test surface:** `tests/test_pipeline.py` — add a case that confirms the live path skips cropping when `pre_cropped=True`.

---

### T-07 · `OCR_ALLOWLIST` doesn't adapt to `languages` config
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr_engine.py:3`
- **Completed:** —

The allowlist is hardcoded with German umlauts (`üäöÜÄÖ`) regardless of the `languages` config. A user who sets `languages: ["en", "fr"]` gets no French characters (é, è, ê, à, ç) but retains unused German ones. The allowlist and language config are silently inconsistent.

**Fix direction:** Define per-language character sets and build the allowlist dynamically from the configured languages. Keep the base ASCII set as always-included.

**Test surface:** `tests/test_pipeline.py` or a new `tests/test_ocr_engine.py` — verify allowlist content for different language combinations.

---

### T-08 · Shutdown race: buffer flush after non-guaranteed thread join
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/live_runtime.py:291-302`
- **Completed:** —

After `processing_thread.join(timeout=1.0)`, `flush_buffers` runs immediately on the main thread. If the processing worker didn't exit within 1s, both threads can access `team_buffer` / `all_buffer` concurrently. `MessageBuffer` has no locking. The logger mutex protects the file, but the buffer state machine is unprotected.

**Fix direction:** After `stop_event.set()`, wait for `processing_thread` to finish (no timeout, or a longer/logged timeout) before calling `flush_buffers`. Alternatively, if a hard timeout is needed, check `processing_thread.is_alive()` before flushing.

**Test surface:** `tests/test_live_runtime.py` — add a test that validates the processing thread has exited before flush is called.

---

### T-09 · This branch: `OCREngine` has no swappable interface
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr_engine.py`
- **Completed:** —

The current branch aims to enable comparison between OCR engines, but `OCREngine` imports `easyocr` at module level and has EasyOCR baked directly into the constructor. There is no abstract base class, `Protocol`, or factory. Engine swappability is implied by the class name but not enforced by any interface contract.

**Fix direction:** Define a `Protocol` (or ABC) for an OCR engine with a `run(mask, *, confidence_threshold, text_threshold) -> list` signature. Rename the current class to `EasyOCREngine`. Add a factory or registry so the engine can be selected by config. This is the prerequisite for comparison harness work.

**Test surface:** New or updated `tests/test_ocr_engine.py` — validate that `EasyOCREngine` satisfies the protocol; add a stub engine to confirm the pipeline accepts any conforming engine.

---

## Smells

### T-10 · Dead commented-out code in `image_processing.py`
- **Severity:** smell
- **State:** `open`
- **File:** `src/ow_chat_logger/image_processing.py:50-59`
- **Completed:** —

An old `INTER_NEAREST` version of `clean_mask` lives as a comment block. It's not reachable, not documented as an alternative, and not behind a config toggle.

**Fix direction:** Delete it. If the `INTER_NEAREST` approach is worth preserving as an option, expose it via a config key (e.g. `mask_interpolation: "cubic" | "nearest"`).

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-11 · CLI `--metrics` flag can only force-on, not force-off
- **Severity:** smell
- **State:** `open`
- **File:** `src/ow_chat_logger/main.py:47`
- **Completed:** —

`--metrics` sets `metrics_enabled_override=True`. Absence passes `None`, which defers to the config file. There is no way to force-disable metrics from the CLI when `metrics_enabled: true` is set in the user config. The flag is asymmetric.

**Fix direction:** Use a `BooleanOptionalAction` (Python 3.9+) or add `--no-metrics` to allow explicit force-off. Update `create_metrics_collector` to accept `False` as a disable override.

**Test surface:** `tests/test_cli.py` — add a case for `--no-metrics` overriding config-enabled metrics.

---

## Completion Tracking

| ID | Title | Severity | State | Completed |
|----|-------|----------|-------|-----------|
| T-01 | Y-anchor drift in `reconstruct_lines` | bug | `open` | — |
| T-02 | `HERO_PATTERN` too greedy | bug | `open` | — |
| T-03 | `r"channels"` bare substring | bug | `open` | — |
| T-04 | `LazyConfig` write not thread-safe | structural | `open` | — |
| T-05 | `OCREngine` dead threshold attributes | structural | `open` | — |
| T-06 | Redundant crop on every live frame | structural | `open` | — |
| T-07 | `OCR_ALLOWLIST` ignores language config | structural | `open` | — |
| T-08 | Shutdown race on buffer flush | structural | `open` | — |
| T-09 | `OCREngine` has no swappable interface | structural | `open` | — |
| T-10 | Dead commented-out code | smell | `open` | — |
| T-11 | CLI `--metrics` asymmetric flag | smell | `open` | — |
