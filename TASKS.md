# Tasks

Derived from the senior design review (2026-04-03), updated 2026-04-03 after OCR modularisation branch review.
Each task has a severity, location, description, and tracked state.

Severity: **bug** | **structural** | **smell**
State: `open` | `in-progress` | `review` | `done`

---

## Bugs

### T-01 · Y-anchor drift in `reconstruct_lines`
- **Severity:** bug
- **State:** `done`
- **File:** `src/ow_chat_logger/image_processing.py:110`
- **Completed:** 2026-04-03

`current_y` is set to the first box's Y when a new group starts and is never updated while accumulating that group. With `y_merge_threshold=18`, boxes at y=`[0, 15, 30]` produce two groups instead of one: the box at y=30 is compared against y=0 (diff=30 > 18) rather than the most-recent anchor y=15. Real-world OCR on upscaled text regularly returns boxes with gradual Y drift, causing premature line splits.

**Fix direction:** Update `current_y` to the last-seen Y value after each merge, making it a sliding anchor rather than a group-start anchor.

**Test surface:** `tests/test_image_processing.py` — add a case with three boxes showing gradual Y drift within the merge threshold.

---

### T-02 · `HERO_PATTERN` too greedy
- **Severity:** bug
- **State:** `open`
- **File:** `src/ow_chat_logger/parser.py:9`
- **Completed:** —

The hero pattern `^(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)...` has no bracket requirement on the player name. Any OCR fragment of the form `word (word)` — including partial system messages that slip past `SYSTEM_REGEX` — is silently classified as a hero line. Continuation lines that happen to contain parentheses are also affected.

**Fix direction:** Tighten the pattern. At minimum add a negative assertion to prevent matching lines that start with `[`. Add a guard so a parenthetical in chat content (e.g. `"lol (you wish)"`) doesn't promote to hero.

**Test surface:** `tests/test_parser.py` — add cases for: parenthetical chat content classified as continuation, partial system message not promoted to hero.

---

### T-03 · `r"channels"` bare substring in system patterns
- **Severity:** bug
- **State:** `open`
- **File:** `src/ow_chat_logger/parser.py:29`
- **Completed:** —

The pattern `r"channels"` in `SYSTEM_PATTERNS` is a bare substring match with no anchoring or word boundary. Any player chat message containing the word "channels" is silently dropped as a system message.

**Fix direction:** Replace with a more specific pattern scoped to the actual system message context, or remove it and rely solely on the Aho-Corasick fragment matcher which already handles the longer form.

**Test surface:** `tests/test_parser.py` — add a case where a player message contains "channels" and is correctly classified as `standard`, not `system`.

---

## Structural Issues

### T-04 · `LazyConfig` write path is not thread-safe
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/config.py:187`
- **Completed:** —

`LazyConfig.__setitem__` mutates the shared `_cached_config` dict in place — and now also writes into nested profile dicts — with no lock. The `MutableMapping` interface makes this look safe. While no current production code path writes to `CONFIG` from a worker thread, the interface invites it. A concurrent read (from the processing worker) overlapping with a write is a silent data race on plain dicts.

**Fix direction:** Either (a) make `LazyConfig` read-only after startup by removing `__setitem__`/`__delitem__` and narrowing to `Mapping`, or (b) add a `threading.RLock` around all mutations and the cache-population path. Option (a) is safer and reflects actual usage.

**Test surface:** `tests/test_config_helpers.py` — verify the interface contract; if narrowed, ensure test setup via `reset_config()` still works.

---

### T-06 · Redundant `crop_to_screen_region` call on every live frame
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/pipeline.py:95`
- **Completed:** —

`extract_chat_debug_data` always calls `crop_to_screen_region`, but live captures are already cropped to `screen_region` by `pyautogui.screenshot(region=...)`. The bounds check prevents double-cropping but runs on every frame unnecessarily. This also creates a misleading dual-purpose function where callers must know whether their input is pre-cropped or full-screen.

**Fix direction:** Add a `pre_cropped: bool = False` parameter to `extract_chat_debug_data` and skip the crop step in the live path. Analyze and benchmark paths pass full screenshots and still benefit from the crop.

**Test surface:** `tests/test_pipeline.py` — add a case confirming the live path skips cropping when `pre_cropped=True`.

---

### T-07 · `DEFAULT_ALLOWLIST` hardcoded for EN+DE regardless of language config
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr/easyocr_backend.py:7`
- **Completed:** —

The default allowlist contains German umlauts (`üäöÜÄÖ`) hardcoded. While the allowlist is now overridable per-profile via `settings.allowlist`, the default still silently mismatches for users with other language configs (e.g. `["en", "fr"]` gets no French characters). The same hardcoded string appears in the Tesseract profile settings in `config.py:116`.

**Fix direction:** Define per-language character additions and build `DEFAULT_ALLOWLIST` dynamically from the configured languages, or at minimum document the limitation clearly and add a config-level override example.

**Test surface:** Validate that a profile with `["en", "fr"]` languages can specify an appropriate allowlist via `settings.allowlist`.

---

### T-08 · Shutdown race: buffer flush after non-guaranteed thread join
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/live_runtime.py:308-318`
- **Completed:** —

After `processing_thread.join(timeout=1.0)`, `flush_buffers` runs immediately on the main thread. If the processing worker did not exit within 1s, both threads can access `team_buffer` / `all_buffer` concurrently. `MessageBuffer` has no locking.

**Fix direction:** After `stop_event.set()`, join the processing thread without a timeout (the worker will exit once `stop_event` is set and the queue drains), or check `processing_thread.is_alive()` before calling `flush_buffers` and log a warning if it's still running.

**Test surface:** `tests/test_live_runtime.py` — validate that the processing thread has exited before flush is called.

---

### T-12 · `ResolvedOCRProfile` is frozen but contains mutable dicts
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr/base.py:21`
- **Completed:** —

`ResolvedOCRProfile` is declared `@dataclass(frozen=True)` but its `pipeline: dict` and `settings: dict` fields are plain mutable dicts. `frozen=True` only prevents field reassignment — it does not prevent content mutation. Any caller can do `profile.pipeline["scale_factor"] = 999` and silently corrupt shared state. `resolve_ocr_profile` uses `deepcopy` when building the profile, but callers are not protected afterwards.

**Fix direction:** Use `types.MappingProxyType` for `pipeline` and `settings` fields to make them genuinely read-only at runtime, or replace the frozen dataclass with a regular class that copies on access.

**Test surface:** `tests/test_config_helpers.py` — add a test verifying that mutation of `profile.pipeline` is either prevented or does not affect subsequent pipeline calls.

---

### T-13 · `_benchmark_case` redundantly resolves profile per fixture
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/benchmark.py:91`
- **Completed:** —

`run_benchmark` resolves `profile = resolve_ocr_profile(config, profile_name)` before the fixture loop and builds the backend from it. Then `_benchmark_case` calls `resolve_ocr_profile(config, profile_name)` again internally for the same profile name. `resolve_ocr_profile` performs a `deepcopy` of pipeline and settings on every call — this runs once per fixture, per profile, needlessly.

**Fix direction:** Pass the already-resolved `ResolvedOCRProfile` into `_benchmark_case` as a parameter rather than re-resolving it internally.

**Test surface:** `tests/test_benchmark.py` — verify the case function uses the passed profile without re-resolving.

---

### T-14 · `ocr_engine.py` legacy shim monkey-patches a module-level function in `__init__`
- **Severity:** structural
- **State:** `open`
- **File:** `src/ow_chat_logger/ocr_engine.py:20`
- **Completed:** —

`OCREngine.__init__` temporarily replaces `_windows._import_winrt_modules` with a local reference, calls `super().__init__()`, then restores the original. This pattern is not thread-safe: if two `OCREngine` instances are constructed concurrently, one thread's restore will overwrite the other's patch mid-construction. It appears to be a workaround for test isolation, but it pollutes production code with test machinery.

**Fix direction:** Investigate why the patch is needed and address the root cause. If it's purely for test mocking, use `unittest.mock.patch` in tests rather than patching in the constructor. Remove the monkey-patch from production code.

**Test surface:** `tests/test_ocr_engine.py` — verify the legacy `OCREngine` constructs correctly without the monkey-patch.

---

## Smells

### T-10 · Dead commented-out code in `image_processing.py`
- **Severity:** smell
- **State:** `open`
- **File:** `src/ow_chat_logger/image_processing.py:90-99`
- **Completed:** —

An old `INTER_NEAREST` version of `clean_mask` lives as a comment block below the new `clean_mask` wrapper. It's unreachable and undocumented as an alternative.

**Fix direction:** Delete it. The new `clean_mask_steps` with `INTER_NEAREST` is already the active implementation; the comment is stale.

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-11 · CLI `--metrics` flag can only force-on, not force-off
- **Severity:** smell
- **State:** `open`
- **File:** `src/ow_chat_logger/main.py:84`
- **Completed:** —

`--metrics` sets `metrics_enabled_override=True`. Absence passes `None`, deferring to config. There is no way to force-disable metrics from the CLI when `metrics_enabled: true` is set in user config.

**Fix direction:** Use `BooleanOptionalAction` (Python 3.9+) or add `--no-metrics` to allow explicit force-off. Update `create_metrics_collector` to accept `False` as a disable override.

**Test surface:** `tests/test_cli.py` — add a case for `--no-metrics` overriding config-enabled metrics.

---

## Completed

### T-05 · `OCREngine` stored thresholds that were never used
- **Severity:** structural
- **State:** `done`
- **Completed:** 2026-04-03

Resolved by the OCR modularisation. Each backend now owns its thresholds as instance state (e.g. `EasyOCRBackend.confidence_threshold`). The pipeline calls `ocr.run(mask)` with no threshold arguments — backends consume their own settings. The old dual-ownership problem is gone.

### T-09 · `OCREngine` had no swappable interface
- **Severity:** structural
- **State:** `done`
- **Completed:** 2026-04-03

Resolved by the OCR modularisation. `base.py` defines `OCRBackend` (Protocol) and `BaseOCRBackend` (ABC with `@abstractmethod run()`). Three backends implement it: `WindowsOCRBackend`, `EasyOCRBackend`, `TesseractOCRBackend`. `registry.py` provides `build_ocr_backend(profile)` factory. `ocr_engine.py` is now a thin legacy shim wrapping the Windows backend.

---

## Completion Tracking

| ID | Title | Severity | State | Completed |
|----|-------|----------|-------|-----------|
| T-01 | Y-anchor drift in `reconstruct_lines` | bug | `done` | 2026-04-03 |
| T-02 | `HERO_PATTERN` too greedy | bug | `open` | — |
| T-03 | `r"channels"` bare substring | bug | `open` | — |
| T-04 | `LazyConfig` write not thread-safe | structural | `open` | — |
| T-05 | `OCREngine` dead threshold attributes | structural | `done` | 2026-04-03 |
| T-06 | Redundant crop on every live frame | structural | `open` | — |
| T-07 | `DEFAULT_ALLOWLIST` ignores language config | structural | `open` | — |
| T-08 | Shutdown race on buffer flush | structural | `open` | — |
| T-09 | `OCREngine` has no swappable interface | structural | `done` | 2026-04-03 |
| T-10 | Dead commented-out code | smell | `open` | — |
| T-11 | CLI `--metrics` asymmetric flag | smell | `open` | — |
| T-12 | `ResolvedOCRProfile` mutable dict fields in frozen dataclass | structural | `open` | — |
| T-13 | `_benchmark_case` redundantly re-resolves profile per fixture | structural | `open` | — |
| T-14 | `ocr_engine.py` monkey-patches module function in `__init__` | structural | `open` | — |
