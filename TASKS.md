# Tasks

Derived from the senior design review (2026-04-03), updated 2026-04-05 after focused codebase review.
Each task has a severity, location, description, and tracked state.

Severity: **bug** | **structural** | **smell**
State: 🔴 `open` | 🟡 `in-progress` | 🔵 `review` | 🟢 `done` | ⚫ `deferred`

---

## Completion Tracking

| ID | Title | Severity | State | Completed |
|----|-------|----------|-------|-----------|
| T-06 | Redundant crop on every live frame | structural | 🟢 `done` | 2026-04-06 |
| T-26 | OCR character-pair ambiguity: `,`/`.` and `=`/`-` | smell | 🟢 `done` | 2026-04-06 |
| T-08 | Shutdown race on buffer flush | structural | 🔴 `open` | — |
| T-10 | Dead commented-out code | smell | 🔴 `open` | — |
| T-11 | CLI `--metrics` asymmetric flag | smell | 🔴 `open` | — |
| T-12 | `ResolvedOCRProfile` mutable dict fields in frozen dataclass | structural | 🔴 `open` | — |
| T-13 | `_benchmark_case` redundantly re-resolves profile per fixture | structural | 🔴 `open` | — |
| T-14 | `ocr_engine.py` monkey-patches module function in `__init__` | structural | 🔴 `open` | — |
| T-20 | Save debug screenshot when a parsing anomaly is detected | structural | 🔴 `open` | — |
| T-21 | `SYSTEM_PATTERNS` redundant `.*` prefixes | smell | 🔴 `open` | — |
| T-22 | `_effective_scale_factor` computed twice per resize | smell | 🔴 `open` | — |
| T-25 | Inline error-case dict in `run_benchmark` duplicates `_unavailable_case` | smell | 🔴 `open` | — |
| T-27 | Add hero-ban vote warning to `SYSTEM_PATTERNS` | smell | 🔵 `review` | — |
| T-28 | Prevent continuation across large vertical gap | structural | 🔴 `open` | — |
| T-29 | Filter sub-height OCR bounding boxes | bug | 🟢 `done` | 2026-04-06 |
| T-30 | Improve team-chat color masking for blue-on-blue scenarios | structural | 🔴 `open` | — |
| T-01 | Y-anchor drift in `reconstruct_lines` | bug | 🟢 `done` | 2026-04-03 |
| T-02 | `HERO_PATTERN` too greedy | bug | 🟢 `done` | 2026-04-03 |
| T-03 | `r"channels"` bare substring | bug | 🟢 `done` | 2026-04-03 |
| T-04 | `LazyConfig` write not thread-safe | structural | 🟢 `done` | 2026-04-03 |
| T-05 | `OCREngine` dead threshold attributes | structural | 🟢 `done` | 2026-04-03 |
| T-09 | `OCREngine` has no swappable interface | structural | 🟢 `done` | 2026-04-03 |
| T-15 | Trailing `l:` in player prefix should normalize to closing bracket | bug | 🟢 `done` | 2026-04-03 |
| T-16 | Capital `I` closing-bracket OCR suffix not covered by T-15 | bug | 🟢 `done` | 2026-04-03 |
| T-18 | `\|` → `I` substitution in `normalize()` corrupts `l`-as-pipe in message content | bug | 🟢 `done` | 2026-04-03 |
| T-19 | Multi-error lines (no bracket + spaces in name + `l:` suffix) fall through to continuation | bug | 🟢 `done` | 2026-04-03 |
| T-07 | `DEFAULT_ALLOWLIST` ignores language config | structural | ⚫ `deferred` | — |
| T-17 | T-15 false positive: legitimate names ending in `l` stripped when bracket is missing | bug | ⚫ `deferred` | — |


---

## Bugs

## Structural Issues

### T-06 · Redundant `crop_to_screen_region` call on every live frame
- **Severity:** structural
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/pipeline.py:95`
- **Completed:** 2026-04-06

`extract_chat_debug_data` always calls `crop_to_screen_region`, but live captures are already cropped to `screen_region` by `pyautogui.screenshot(region=...)`. The bounds check prevents double-cropping but runs on every frame unnecessarily. This also creates a misleading dual-purpose function where callers must know whether their input is pre-cropped or full-screen.

**Fix direction:** Add a `pre_cropped: bool = False` parameter to `extract_chat_debug_data` and skip the crop step in the live path. Analyze and benchmark paths pass full screenshots and still benefit from the crop.

**Test surface:** `tests/test_pipeline.py` — add a case confirming the live path skips cropping when `pre_cropped=True`.

---

### T-08 · Shutdown race: buffer flush after non-guaranteed thread join
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/live_runtime.py:308-318`
- **Completed:** —

After `processing_thread.join(timeout=1.0)`, `flush_buffers` runs immediately on the main thread. If the processing worker did not exit within 1s, both threads can access `team_buffer` / `all_buffer` concurrently. `MessageBuffer` has no locking.

**Fix direction:** After `stop_event.set()`, join the processing thread without a timeout (the worker will exit once `stop_event` is set and the queue drains), or check `processing_thread.is_alive()` before calling `flush_buffers` and log a warning if it's still running.

**Test surface:** `tests/test_live_runtime.py` — validate that the processing thread has exited before flush is called.

---

### T-12 · `ResolvedOCRProfile` is frozen but contains mutable dicts
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/ocr/base.py:21`
- **Completed:** —

`ResolvedOCRProfile` is declared `@dataclass(frozen=True)` but its `pipeline: dict` and `settings: dict` fields are plain mutable dicts. `frozen=True` only prevents field reassignment — it does not prevent content mutation. Any caller can do `profile.pipeline["scale_factor"] = 999` and silently corrupt shared state. `resolve_ocr_profile` uses `deepcopy` when building the profile, but callers are not protected afterwards.

**Fix direction:** Use `types.MappingProxyType` for `pipeline` and `settings` fields to make them genuinely read-only at runtime, or replace the frozen dataclass with a regular class that copies on access.

**Test surface:** `tests/test_config_helpers.py` — add a test verifying that mutation of `profile.pipeline` is either prevented or does not affect subsequent pipeline calls.

---

### T-13 · `_benchmark_case` redundantly resolves profile per fixture
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/benchmark.py:91`
- **Completed:** —

`run_benchmark` resolves `profile = resolve_ocr_profile(config, profile_name)` before the fixture loop and builds the backend from it. Then `_benchmark_case` calls `resolve_ocr_profile(config, profile_name)` again internally for the same profile name. `resolve_ocr_profile` performs a `deepcopy` of pipeline and settings on every call — this runs once per fixture, per profile, needlessly.

**Fix direction:** Pass the already-resolved `ResolvedOCRProfile` into `_benchmark_case` as a parameter rather than re-resolving it internally.

**Test surface:** `tests/test_benchmark.py` — verify the case function uses the passed profile without re-resolving.

---

### T-14 · `ocr_engine.py` legacy shim monkey-patches a module-level function in `__init__`
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/ocr_engine.py:20`
- **Completed:** —

`OCREngine.__init__` temporarily replaces `_windows._import_winrt_modules` with a local reference, calls `super().__init__()`, then restores the original. This pattern is not thread-safe: if two `OCREngine` instances are constructed concurrently, one thread's restore will overwrite the other's patch mid-construction. It appears to be a workaround for test isolation, but it pollutes production code with test machinery.

**Fix direction:** Investigate why the patch is needed and address the root cause. If it's purely for test mocking, use `unittest.mock.patch` in tests rather than patching in the constructor. Remove the monkey-patch from production code.

**Test surface:** `tests/test_ocr_engine.py` — verify the legacy `OCREngine` constructs correctly without the monkey-patch.

---

### T-20 · Save debug screenshot when a parsing anomaly is detected
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/pipeline.py`, `src/ow_chat_logger/live_runtime.py`
- **Completed:** —

When the OCR pipeline produces a suspicious result — e.g. a line falls through to `continuation` instead of matching a standard pattern, a player name is stripped by the `ocr_fix_closing_bracket_l` heuristic, or an empty OCR result is returned for a non-blank mask — there is currently no capture of the frame that caused it. Diagnosing these cases requires reproducing the exact screen state, which is often impossible after the fact.

**Fix direction:** Define an anomaly predicate (callable, configurable) that receives the `extract_chat_debug_data` return dict and returns `True` when the frame is considered anomalous. When triggered, save the cropped RGB image (and optionally the team/all masks) to a configurable directory (e.g. `debug_screenshots/`) with a timestamp filename. Wire the predicate into the live runtime loop after `extract_chat_lines`. Keep the save path and the predicate out of the hot path when not triggered.

**Test surface:** `tests/test_pipeline.py` — add a test that invokes the anomaly predicate with a synthetic debug dict containing a `continuation`-only parse result and confirms a file is written to a temp directory.

---

## Smells

### T-10 · Dead commented-out code in `image_processing.py`
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py:90-99`
- **Completed:** —

An old `INTER_NEAREST` version of `clean_mask` lives as a comment block below the new `clean_mask` wrapper. It's unreachable and undocumented as an alternative.

**Fix direction:** Delete it. The new `clean_mask_steps` with `INTER_NEAREST` is already the active implementation; the comment is stale.

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-11 · CLI `--metrics` flag can only force-on, not force-off
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/main.py:84`
- **Completed:** —

`--metrics` sets `metrics_enabled_override=True`. Absence passes `None`, deferring to config. There is no way to force-disable metrics from the CLI when `metrics_enabled: true` is set in user config.

**Fix direction:** Use `BooleanOptionalAction` (Python 3.9+) or add `--no-metrics` to allow explicit force-off. Update `create_metrics_collector` to accept `False` as a disable override.

**Test surface:** `tests/test_cli.py` — add a case for `--no-metrics` overriding config-enabled metrics.

---

### T-21 · `SYSTEM_PATTERNS` contains redundant `.*` prefixes
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/parser.py:34-47`
- **Completed:** —

All 14 entries in `SYSTEM_PATTERNS` use a `.*` prefix (e.g. `r".*left the game"`). `SYSTEM_REGEX` is compiled and searched via `SYSTEM_REGEX.search(line)`, which already scans the full string — the `.*` prefix is always redundant and makes the patterns harder to read.

**Fix direction:** Remove the `.*` from all pattern strings in `SYSTEM_PATTERNS`. No behavioral change.

**Test surface:** No new tests needed. Verify existing parser tests still pass.

---

### T-22 · `_effective_scale_factor` computed twice per resize call
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py:63-68`
- **Completed:** —

`clean_mask_steps` calls `_effective_scale_factor(cfg)` twice — once for `fx` and once for `fy` — in the same `cv2.resize` call. The function is deterministic for a given `cfg`, so this is safe but wasteful and inconsistent (if the function ever became non-deterministic, fx and fy could diverge).

**Fix direction:** Assign the result to a local variable once, then use it for both `fx` and `fy`.

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-26 · OCR character-pair ambiguity: `,`/`.` and `=`/`-`

- **Severity:** smell
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/parser.py:50`, `tests/fixtures/regression/example_6.expected.json`
- **Completed:** 2026-04-06

OCR regularly confuses two visually similar character pairs in message content:
- `,` ↔ `.` (comma vs period)
- `=` ↔ `-` (equals vs minus)

This causes two separate problems:

1. **Dedup false negatives.** The same message captured on two consecutive frames may be logged twice if OCR produces different characters each time. `DuplicateFilter` uses a raw string key, so `"hello."` and `"hello,"` are treated as distinct messages.

2. **Regression test fragility.** `_assert_channel_lines_match` compares exact strings; a test whose expected JSON was written with `.` will fail if OCR returns `,` for the same screenshot, or vice versa.

**Options considered:**

- **A — Test-only normalization** (`_norm_line` in `test_regression_screenshots.py`): canonicalize the pairs inside `_assert_channel_lines_match` before comparing. Regression tests become tolerant; production behavior is untouched; no expected JSON files need updating. Most surgical for the test problem.
- **B — Parser-level normalization** (`parser.normalize()`): pick one canonical character per pair (e.g. `.` and `-`) before parsing. Dedup and tests are both fixed; expected JSON files must use the canonical form; logs show canonical chars instead of raw OCR.
- **C — Dedup-key normalization only**: apply a normalization function to the key passed to `DuplicateFilter.is_new`. Fixes dedup false negatives; regression tests remain fragile unless combined with A.
- **D — Both A and C**: each problem fixed at the appropriate layer (test comparison tolerance + dedup key normalization) without mutating logged output.

**Recommended fix direction:** Option D. Apply key normalization at the `chat_dedup` / `hero_dedup` call sites in `message_processing.py`, and extend `_norm_line` in `test_regression_screenshots.py` to canonicalize the two pairs. No production output is changed; both failure modes are addressed.

**Test surface:** `tests/test_regression_screenshots.py` (tolerance in comparison), `tests/test_deduplication.py` (verify that messages differing only in `,`/`.` or `=`/`-` are deduplicated as one).

---

### T-27 · Add hero-ban vote warning to `SYSTEM_PATTERNS`
- **Severity:** smell
- **State:** 🔵 `review`
- **File:** `src/ow_chat_logger/parser.py:34-47`
- **Completed:** —

The in-game hero-ban vote notification `Warning! You're voting to ban your teammate's preferred hero.` is not listed in `SYSTEM_PATTERNS`. When OCR picks it up (e.g. when the notification renders over the chat region) it falls through to continuation and is appended to the last open player message instead of being dropped.

**Fix direction:** Add `r"Warning! You're voting to ban your teammate's preferred hero"` to `SYSTEM_PATTERNS`. Remove the redundant `.*` prefix per T-21.

**Test surface:** `tests/test_parser.py` — add a case verifying that a line containing the warning string is classified as a system message and not returned as player content.

---

### T-28 · Prevent continuation across large vertical gap
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/pipeline.py` / `src/ow_chat_logger/message_processing.py`
- **Completed:** —

The continuation buffer appends any unrecognised OCR fragment to the last open player record regardless of how far below (in Y coordinates) the fragment appears relative to the message it is continuing. In example_17, a system-notification line two visual rows below the `[A7X]: gg` message — with a team-chat line in between — is appended to the `gg` record. A maximum vertical distance threshold would prevent bleed from spatially distant lines.

**Fix direction:** Track the Y coordinate of the last line fed to the buffer. When a new fragment arrives as a continuation candidate, check the vertical distance from the previous line's Y. If the gap exceeds a configurable threshold (e.g. 2 × average line height, or a fixed pixel value relative to the crop height), discard the fragment rather than appending it. The threshold should be configurable in the OCR profile.

**Test surface:** `tests/test_message_processing.py` — add a case where a continuation fragment arrives with a Y coordinate far below the open record and verify it is discarded.

---

### T-30 · Improve team-chat color masking for blue-on-blue scenarios
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py` (team mask logic)
- **Completed:** —

In several screenshots (example_09, example_12, example_14) the team-chat text color is a blue shade very similar to the background. The current HSV mask cannot distinguish text from background at this color/brightness combination, so lines are never isolated and OCR produces nothing. Example_14 also shows pink panel text (`Odin's Fav Child`) bleeding into the team-chat crop, suggesting the mask accepts too broad a hue range.

**Fix direction:** Investigate the HSV ranges used for the team mask and compare against the failing screenshots. Consider: (a) widening the lightness range to catch slightly darker blue text; (b) adding a morphological close step before contour detection to bridge near-background-colored text; (c) adding a reject pass for out-of-range hues (e.g. pink/red) that are clearly not team-chat. This is a research-first task — inspect the debug mask images for example_09, example_12, and example_14 before changing thresholds.

**Test surface:** `tests/test_regression_screenshots.py` — example_09, example_12, and example_14 are the direct regression targets.

---

### T-25 · Inline error-case dict in `run_benchmark` duplicates `_unavailable_case` structure
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/benchmark.py:288-319`
- **Completed:** —

The `except Exception` branch in `run_benchmark` builds a 30-line inline dict that is structurally identical to the return value of `_unavailable_case`, differing only in `status: "error"`. This duplication means any schema change to benchmark result rows must be applied in two places. The error-case dict is also missing some fields relative to `_unavailable_case` (e.g. `fixture_path`, `expected_path` are present in `_unavailable_case` but the inline dict uses `str(png_path.resolve())` directly).

**Fix direction:** Extract an `_error_case(*, png_path, expected_path, profile_name, engine_id, message)` helper following the same signature pattern as `_unavailable_case`, with `status="error"`.

**Test surface:** `tests/test_benchmark.py` — verify error-case rows have the same schema as unavailable-case rows.

---

## Completed and Deferred

### T-29 · Filter sub-height OCR bounding boxes
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/image_processing.py` (`reconstruct_lines`)
- **Completed:** 2026-04-06

Replaced the scale-dependent absolute `min_ocr_box_height` threshold with a single relative `min_box_height_fraction` (0.55): any reconstructed line whose tallest bounding box is below 55% of the median line height in the same OCR result is discarded. This fixed the `enekleA` garbage token appended to example_02 (clipped line at h=36 vs median 68; 36/68=53% < 55%).

---

### T-01 · Y-anchor drift in `reconstruct_lines`
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/image_processing.py:110`
- **Completed:** 2026-04-03

`current_y` is set to the first box's Y when a new group starts and is never updated while accumulating that group. With `y_merge_threshold=18`, boxes at y=`[0, 15, 30]` produce two groups instead of one: the box at y=30 is compared against y=0 (diff=30 > 18) rather than the most-recent anchor y=15. Real-world OCR on upscaled text regularly returns boxes with gradual Y drift, causing premature line splits.

**Fix direction:** Update `current_y` to the last-seen Y value after each merge, making it a sliding anchor rather than a group-start anchor.

---

### T-02 · `HERO_PATTERN` too greedy
- **Severity:** bug
- **File:** `src/ow_chat_logger/parser.py:9`
- **State:** 🟢 `done`
- **Completed:** 2026-04-03

The hero pattern `^(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)...` has no bracket requirement on the player name. Any OCR fragment of the form `word (word)` — including partial system messages that slip past `SYSTEM_REGEX` — is silently classified as a hero line. Continuation lines that happen to contain parentheses are also affected.

---

### T-03 · `r"channels"` bare substring in system patterns
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/parser.py:29`
- **Completed:** 2026-04-03

The pattern `r"channels"` in `SYSTEM_PATTERNS` is a bare substring match with no anchoring or word boundary. Any player chat message containing the word "channels" is silently dropped as a system message.

---

### T-04 · `LazyConfig` write path is not thread-safe
- **Severity:** structural
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/config.py:187`
- **Completed:** 2026-04-03

`LazyConfig.__setitem__` mutated the shared `_cached_config` dict in place with no lock.

---

### T-05 · `OCREngine` stored thresholds that were never used
- **Severity:** structural
- **State:** 🟢 `done`
- **Completed:** 2026-04-03

Resolved by the OCR modularisation. Each backend now owns its thresholds as instance state.

---

### T-09 · `OCREngine` had no swappable interface
- **Severity:** structural
- **State:** 🟢 `done`
- **Completed:** 2026-04-03

Resolved by the OCR modularisation. `base.py` defines `OCRBackend` (Protocol) and `BaseOCRBackend` (ABC with `@abstractmethod run()`). Three backends implement it. `registry.py` provides `build_ocr_backend(profile)` factory. `ocr_engine.py` is now a thin legacy shim.

---

### T-15 · Trailing `l:` in player prefix should normalize to closing bracket
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/message_processing.py:18`
- **Completed:** 2026-04-03

OCR sometimes reads the closing bracket as lowercase `l`, producing `[A7Xl: hello` instead of `[A7X]: hello`.

---

### T-16 · Capital `I` closing-bracket OCR suffix not covered by T-15
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/parser.py:121`, `src/ow_chat_logger/message_processing.py:24`
- **Completed:** 2026-04-03

Extended the flag condition and strip to cover capital `I` as a second OCR variant of `]`.

---

### T-18 · `|` → `I` substitution in `normalize()` corrupts lowercase `l` in message content
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/parser.py:79`
- **Completed:** 2026-04-03

Moved the `|` → `I` substitution out of the pre-parse `normalize()` so it only applies to the extracted player token.

---

### T-19 · Multi-error OCR lines fall through to continuation
- **Severity:** bug
- **State:** 🟢 `done`
- **File:** `src/ow_chat_logger/parser.py:113`
- **Completed:** 2026-04-03

Added `NO_BRACKET_SPACED_NAME_PATTERN` to handle the case where both brackets are missing, the player name has spaces, and `]` is misread as `l` or `I`.

---

### T-07 · `DEFAULT_ALLOWLIST` hardcoded for EN+DE regardless of language config
- **Severity:** structural
- **State:** ⚫ `deferred`
- **File:** `src/ow_chat_logger/ocr/easyocr_backend.py:7`
- **Completed:** —

Default allowlist contains German umlauts hardcoded; mismatches for other language configs. Deferred until a clean per-language character-set registry approach is designed.

---

### T-17 · T-15 fix creates false positive for legitimate player names ending in `l`
- **Severity:** bug
- **State:** ⚫ `deferred`
- **File:** `src/ow_chat_logger/message_processing.py:24`, `src/ow_chat_logger/parser.py:121`
- **Completed:** —

The `ocr_fix_closing_bracket` guard fires for players whose names legitimately end in `l` (e.g. `Daniel`, `Nathaniel`). Tradeoff accepted — the heuristic is correct far more often than it fires falsely. Deferred until OCR character-level confidence or a corpus-based player name check is available.
