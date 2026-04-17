# Tasks

Internal backlog and cleanup notes.

Derived from the senior design review (2026-04-03), updated 2026-04-17 after full codebase re-verification.
Each task has a severity, location, description, and tracked state.

Severity: **bug** | **structural** | **smell**
State: 🔴 `open` | 🟡 `in-progress` | 🔵 `review` | 🟢 `done` | ⚫ `deferred`

---

## Completion Tracking

| ID | Title | Severity | State | Completed |
|----|-------|----------|-------|-----------|
| T-10 | Dead commented-out code | smell | 🔴 `open` | — |
| T-11 | CLI `--metrics` asymmetric flag | smell | 🔴 `open` | — |
| T-21 | `SYSTEM_PATTERNS` redundant `.*` prefixes | smell | 🔴 `open` | — |
| T-22 | `_effective_scale_factor` computed twice per resize | smell | 🔴 `open` | — |
| T-25 | Inline error-case dict in `run_benchmark` duplicates `_unavailable_case` | smell | 🔴 `open` | — |
| T-30 | Improve team-chat color masking for blue-on-blue scenarios | structural | 🔴 `open` | — |
| T-32 | Stale "Related tasks" references in `KNOWN_FAILURES.md` | smell | 🔴 `open` | — |
| T-33 | Undocumented regression failures for example_22/23/24 | smell | 🔴 `open` | — |
| T-34 | Verify GUI chat-color settings propagate to all detection paths | structural | 🔵 `review` | — |
| T-42 | Re-resolve OCR profile on config change during a live session | structural | 🔴 `open` | — |
| T-35 | Expose in-game chat color options as presets for team/all chat | structural | 🔴 `open` | — |
| T-36 | Capture regression screenshot fixtures for every chat-color preset | structural | 🔴 `open` | — |
| T-38 | Detect "message contains embedded chat prefix" as a debug-snap anomaly | structural | 🔴 `open` | — |
| T-39 | Extend build to produce a Windows installer | structural | 🔴 `open` | — |
| T-40 | In-app update check / auto-updater for installed builds | structural | 🔴 `open` | — |
| T-41 | Set up CI for PRs (tests + lint on GitHub Actions) | structural | 🔴 `open` | — |
| T-43 | In-GUI search for players and old messages | structural | 🔴 `open` | — |
| T-14 | `ocr_engine.py` monkey-patches module function in `__init__` | structural | 🟢 `done` | 2026-04-17 |
| T-37 | Move `debug_snaps/` and `analysis/` out of user `log_dir` | structural | 🟢 `done` | 2026-04-17 |
| T-20 | Save debug screenshot when a parsing anomaly is detected | structural | 🟢 `done` | 2026-04-17 |
| T-31 | Duplicate frame-processing block in `live_runtime.py` | structural | 🟢 `done` | 2026-04-17 |
| T-07 | `DEFAULT_ALLOWLIST` ignores language config | structural | ⚫ `deferred` | — |
| T-17 | T-15 false positive: legitimate names ending in `l` stripped when bracket is missing | bug | ⚫ `deferred` | — |
| T-01 | Y-anchor drift in `reconstruct_lines` | bug | 🟢 `done` | 2026-04-03 |
| T-02 | `HERO_PATTERN` too greedy | bug | 🟢 `done` | 2026-04-03 |
| T-03 | `r"channels"` bare substring | bug | 🟢 `done` | 2026-04-03 |
| T-04 | `LazyConfig` write not thread-safe | structural | 🟢 `done` | 2026-04-03 |
| T-05 | `OCREngine` dead threshold attributes | structural | 🟢 `done` | 2026-04-03 |
| T-06 | Redundant crop on every live frame | structural | 🟢 `done` | 2026-04-06 |
| T-08 | Shutdown race on buffer flush | structural | 🟢 `done` | 2026-04-17 |
| T-09 | `OCREngine` has no swappable interface | structural | 🟢 `done` | 2026-04-03 |
| T-12 | `ResolvedOCRProfile` mutable dict fields in frozen dataclass | structural | 🟢 `done` | 2026-04-17 |
| T-13 | `_benchmark_case` redundantly re-resolves profile per fixture | structural | 🟢 `done` | 2026-04-17 |
| T-15 | Trailing `l:` in player prefix should normalize to closing bracket | bug | 🟢 `done` | 2026-04-03 |
| T-16 | Capital `I` closing-bracket OCR suffix not covered by T-15 | bug | 🟢 `done` | 2026-04-03 |
| T-18 | `\|` → `I` substitution in `normalize()` corrupts `l`-as-pipe in message content | bug | 🟢 `done` | 2026-04-03 |
| T-19 | Multi-error lines (no bracket + spaces in name + `l:` suffix) fall through to continuation | bug | 🟢 `done` | 2026-04-03 |
| T-26 | OCR character-pair ambiguity: `,`/`.` and `=`/`-` | smell | 🟢 `done` | 2026-04-06 |
| T-27 | Add hero-ban vote warning to `SYSTEM_PATTERNS` | smell | 🟢 `done` | 2026-04-06 |
| T-28 | Prevent continuation across large vertical gap | structural | 🟢 `done` | 2026-04-06 |
| T-29 | Filter sub-height OCR bounding boxes | bug | 🟢 `done` | 2026-04-06 |

Detailed entries for completed tasks are not repeated below; see git history (commit messages reference the task ID, e.g. `fix(T-01): …`) for the fix and rationale.

---

## Bugs

*No open bugs.*

---

## Structural Issues

### T-30 · Improve team-chat color masking for blue-on-blue scenarios
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py` (team mask logic)
- **Completed:** —

In several screenshots (example_09, example_12, example_14) the team-chat text color is a blue shade very similar to the background. The current HSV mask cannot distinguish text from background at this color/brightness combination, so lines are never isolated and OCR produces nothing. Example_14 also shows pink panel text (`Odin's Fav Child`) bleeding into the team-chat crop, suggesting the mask accepts too broad a hue range.

**Fix direction:** Investigate the HSV ranges used for the team mask and compare against the failing screenshots. Consider: (a) widening the lightness range to catch slightly darker blue text; (b) adding a morphological close step before contour detection to bridge near-background-colored text; (c) adding a reject pass for out-of-range hues (e.g. pink/red) that are clearly not team-chat. This is a research-first task — inspect the debug mask images for example_09, example_12, and example_14 before changing thresholds.

**Test surface:** `tests/test_regression_screenshots.py` — example_09, example_12, and example_14 are the direct regression targets.

---

### T-34 · Verify GUI chat-color settings propagate to all detection paths
- **Severity:** structural
- **State:** 🔵 `review`
- **File:** `src/ow_chat_logger/gui/settings_panel.py:131-137`, `src/ow_chat_logger/gui/config_io.py`, `src/ow_chat_logger/image_processing.py`
- **Completed:** —

The settings panel exposes `team_hsv_lower/upper` and `all_hsv_lower/upper` entries, but there is no automated coverage that proves a change written from the GUI actually reaches every downstream mask/detection call. If a future refactor introduces a second copy of the HSV range (e.g. cached at import time, read from a stale dict, or bypassed on a fallback path) the GUI edit will silently no-op and regressions will only surface in manual play-testing.

**Fix direction:** (a) Audit every consumer of the four HSV keys and list them in the task body — team mask, all mask, any debug-mask rendering, and any live-runtime path that may hold a pre-resolved copy. (b) Add a regression test that mutates the four HSV keys in CONFIG to a synthetic non-default range, runs a frame through `extract_chat_debug_data` plus the live-runtime path, and asserts the produced masks reflect the new range (e.g. a pixel that is inside the new range but outside the default passes through). (c) If any consumer caches the range at import or profile-resolve time, either invalidate on config change or document the reload requirement and add a test that fails loudly if the cache is stale.

**Test surface:** new `tests/test_color_config_propagation.py` — parametrize over the four HSV keys; existing `tests/test_gui_config_io.py` (if present) for the GUI → config round-trip.

---

### T-35 · Expose in-game chat color options as presets for team and all chat
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/gui/settings_panel.py:131-137`, `src/ow_chat_logger/gui/config_io.py`
- **Completed:** —

Overwatch ships a fixed palette of chat colors the user can pick in-game (team and all chat each have their own palette). Today the GUI forces the user to hand-tune raw HSV tuples, which is a poor UX and a frequent source of "detection stopped working" reports when the in-game color is changed. We should ship a preset per in-game color option so the user selects "Team: <color name>" / "All: <color name>" and the corresponding HSV range is applied.

**Fix direction:** (a) Enumerate the full set of in-game chat color options for team chat and for all chat (source of truth: Overwatch settings UI — list each color name exactly as it appears in-game). (b) Derive an HSV lower/upper range per color from a reference screenshot (see T-36). (c) Store the presets in a single module (e.g. `src/ow_chat_logger/chat_color_presets.py`) keyed by channel + color name. (d) Add two `CTkOptionMenu`s to the settings panel ("Team chat color" / "All chat color") whose selection writes the four HSV keys. (e) Keep the raw HSV entries available under the existing Advanced pattern (see `feedback_settings_ux.md`) so power users can still override. (f) When the loaded config HSV ranges match a preset, reflect that preset name in the dropdown; otherwise show "Custom".

**Test surface:** new `tests/test_chat_color_presets.py` — assert every preset has a valid H∈[0,179], S∈[0,255], V∈[0,255] range with lower < upper per channel; assert selecting a preset writes all four keys; assert loading a config whose values match a preset round-trips to that preset name.

**Depends on:** T-36 (the preset HSV ranges must be derived from real screenshots, not guessed).

---

### T-36 · Capture regression screenshot fixtures for every chat-color preset
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `tests/fixtures/regression/`, `tests/test_regression_screenshots.py`
- **Completed:** —

For T-35 to be trustworthy we need one real screenshot per in-game chat color (team and all) so we can (a) derive each preset's HSV range from ground truth and (b) guard against a preset silently breaking on a future masking change. The current regression corpus covers only a handful of colors — most presets have zero coverage.

**Fix direction:** (a) For each color in the in-game team-chat palette, capture a screenshot with at least one team-chat message visible and save as `tests/fixtures/regression/preset_team_<color>.png` plus a matching `.expected.json`. (b) Repeat for each all-chat color as `preset_all_<color>.png`. (c) Use short, unambiguous message content (no special OCR hazards — avoid `l`/`I` ambiguity, no hero-name parsing edge cases) so a failure clearly indicates a color/masking problem rather than a parser bug. (d) Extend the regression runner (or add a parametrized sibling test) that, given the preset registry from T-35, asserts each `preset_*_<color>.png` produces the expected lines using that preset's HSV range. (e) Document the capture procedure in `tests/fixtures/regression/README.md` so future in-game palette additions can be covered by the same process.

**Test surface:** `tests/test_regression_screenshots.py` (or a new `tests/test_chat_color_preset_screenshots.py` if parametrization gets awkward).

**Depends on:** blocks T-35 completion — presets should not merge without corresponding fixtures.

---

### T-38 · Detect "message contains embedded chat prefix" as a debug-snap anomaly
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/debug_snaps.py`, `src/ow_chat_logger/live_runtime.py`
- **Completed:** —

Observed in a live game: a single record was emitted as `Joebar: J: hello [Makiko] hey`, which is clearly two chat messages (`Joebar: hello` and `Makiko: hey`) merged into one record during Y-anchor grouping / continuation merge. Neither T-20 predicate catches this — bboxes produced lines, and every character is in the allowed set. The signal is structural: a parsed `msg` that itself contains a `LINE_PATTERN`-like prefix (`[Makiko] hey` / `Makiko: hey`) implies two lines were welded together upstream.

**Fix direction:** (a) Add `message_contains_embedded_prefix(record, *, prefix_regex)` predicate to `debug_snaps.py` that searches `record["msg"]` for a second chat-line prefix match (re-using `LINE_PATTERN` or a dedicated regex). (b) Wire it into `processing_worker` alongside the two existing predicates, with reason `"embedded_prefix"` and details including the matched span. (c) Add unit tests covering the Joebar example, bracketed-name variants, and a negative case where a username appears inside a legitimate message (e.g. `"tell @Joebar hi"`). (d) Separately, once snaps confirm the root cause, open a follow-up task to fix the actual merge (reconstruction or continuation-gap logic).

**Test surface:** `tests/test_debug_snaps.py` — predicate unit tests; eventual root-cause fix will need a regression fixture.

---

### T-39 · Extend build to produce a Windows installer
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `build_exe.ps1`, new installer spec (e.g. `installer/ow-chat-logger.iss` or `installer/ow-chat-logger.wxs`), CI workflow if/when added
- **Completed:** —

Today `build_exe.ps1` produces a Nuitka standalone folder under `dist/` — good for local dev, but a release-grade distribution needs a single `.exe` installer the user can double-click. Without one, first-run UX is "download a zip, extract somewhere, find the exe, pin it manually", which is a non-starter for non-technical users and blocks any future signed/auto-updating release flow.

**Fix direction:**
- (a) Pick a toolchain. Candidates:
  - **Inno Setup** (`iscc`, free, script-driven `.iss`, simplest, widely used for Nuitka/PyInstaller outputs) — recommended default.
  - **WiX Toolset** (`.wxs`, produces `.msi`, better for enterprise/GPO deployment, steeper learning curve).
  - **NSIS** (`.nsi`, free, works but less ergonomic than Inno).
- (b) Add an `installer/` directory with the spec (`ow-chat-logger.iss` for Inno Setup) covering: app name, version (pulled from `pyproject.toml`), publisher, install dir default (`%LOCALAPPDATA%\Programs\OW Chat Logger`), Start Menu shortcut, optional desktop shortcut, uninstaller entry.
- (c) Extend `build_exe.ps1` with a post-Nuitka step that invokes the installer compiler on the `dist/` output and drops `OWChatLogger-Setup-<version>.exe` into `dist/installer/`. Gate behind a flag (e.g. `-Installer` switch) so the default dev flow still produces just the folder.
- (d) Decide on handling for `%APPDATA%\ow-chat-logger\config.json` — installer must NOT overwrite it if present; uninstaller must NOT delete user data by default (offer a checkbox). Include the `dev/` subtree (T-37 target) in the "leave on uninstall" rule.
- (e) Document the build flow in the README (prereq: install Inno Setup, add `iscc` to PATH) and note version bump procedure.
- (f) Non-goal for this task: code signing (separate follow-up — needs a cert and a KMS/HSM story), auto-update (needs an update server), CI automation (add once GitHub Actions or equivalent lands).

**Test surface:** manual — build the installer, run it on a clean Windows user account, verify:
- install completes without admin elevation where possible,
- Start Menu shortcut launches the app,
- app writes `config.json` / `dev/debug_snaps/` to `%APPDATA%` as expected,
- uninstall removes installed files but preserves user config and `dev/` artefacts,
- reinstall over an existing install does not clobber user data.

### T-40 · In-app update check / auto-updater for installed builds
- **Severity:** structural
- **State:** 🔴 `open`
- **Priority:** low
- **File:** new `src/ow_chat_logger/updater.py`, GUI integration in `src/ow_chat_logger/gui/app.py`, installer spec (T-39) for upgrade-in-place support
- **Completed:** —

Once the app ships via a Windows installer (T-39), users who installed an older version need a way to learn about and pull newer releases without manually re-downloading. Without this, released versions silently rot on user machines and bug fixes never reach the people who hit them.

**Fix direction:** Two separable deliverables; ship either one first.

- **(a) Passive update check (minimum viable):**
  - On app start (or on an explicit "Check for updates" button), fetch the latest release metadata from GitHub Releases (`GET https://api.github.com/repos/<owner>/<repo>/releases/latest`) and compare `tag_name` against the running app's version (pulled from `pyproject.toml` / baked in at Nuitka build time).
  - If newer, show a non-blocking banner in the GUI with a "Download" button linking to the release asset.
  - Rate-limit: one check per 24 h max, cached in `appdata_dir/update_check.json` (respects user offline, avoids GitHub API pressure).
  - Opt-out via a settings toggle `updates_check_on_start` (default `true` for installed builds, `false` for dev runs detected via `is_packaged_windows_run()`).
- **(b) Auto-updater (stretch):**
  - Download the new installer to a temp dir, verify signature / SHA256 against the release asset's checksum, launch it with `/SILENT` (Inno Setup) or `/quiet` (MSI), exit the running app so the installer can replace the binaries.
  - Needs T-39 installer to support upgrade-in-place without clobbering `%APPDATA%\ow-chat-logger\config.json` or the `dev/` tree — called out in T-39's fix-direction already.
  - Signing story required before auto-run (see T-39 non-goal on code signing). Until then, (a) is the safe ceiling.

**Design notes / decisions to lock in before coding:**
- Version source of truth: add `__version__` to the package and bake it into the Nuitka build, OR read from a `VERSION` file bundled next to the exe. Need to pick one; `__version__` is cleaner.
- Release channel: stable-only vs. allow-prerelease opt-in. Default stable.
- Offline behavior: a failed check must never block app start — wrap in `try/except`, log quietly, move on.
- Dev run detection: skip the check entirely when not running from an installed location (avoid nagging during development).

**Test surface:** `tests/test_updater.py` — version comparison (semver parsing, pre-release handling), cache TTL honored, network-error path is silent, GUI banner state transitions. Stub the GitHub API response; do not hit the network in tests.

---

### T-42 · Re-resolve OCR profile on config change during a live session
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/live_runtime.py:392`, `src/ow_chat_logger/config.py` (LazyConfig / cache reset), GUI apply path in `src/ow_chat_logger/gui/`
- **Completed:** —

`run_live_logger` resolves the OCR profile once at startup and passes it frozen to every frame (see comment at `live_runtime.py:392`). When the user edits HSV values (or any other `profile.pipeline` key) through the settings panel while a live session is running, the change reaches the config file and `CONFIG` but not the running pipeline — masks keep using the pre-resolved snapshot until the user stops and restarts the logger. Discovered while writing the T-34 propagation tests.

**Fix direction:** (a) Decide the reload boundary — per-frame re-resolution is cheap but spreads cost; a signal-driven reload (GUI "Apply" fires an event the processing worker consumes) is cleaner. (b) Make sure a reload does not reinitialize the OCR backend if the engine/languages did not change (avoid tearing down EasyOCR/Windows OCR on every HSV tweak). (c) Add a regression test that mutates HSV keys mid-session (simulated by invoking a reload hook between two `_process_frame_for_live` calls) and asserts the second frame's mask reflects the new range. (d) Update the T-34 docstring note on `run_live_logger` once this lands.

**Test surface:** `tests/test_live_runtime.py` (or `tests/test_color_config_propagation.py` extension) — assert a reload hook makes a running pipeline pick up new HSV ranges without full restart.

---

### T-41 · Set up CI for PRs (tests + lint on GitHub Actions)
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** new `.github/workflows/ci.yml`, `pyproject.toml` (lint/format tool config if added), follow-up `.github/workflows/build.yml` once T-39 lands
- **Completed:** —

Today there is no automated check on PRs — `pytest` runs only on developer machines, and nothing stops a regression from merging to `master` if the author forgets to run the suite locally. Every new task that adds tests (T-40 updater tests, T-36 regression fixtures, T-31 helper extraction) relies entirely on reviewer discipline. Without CI the test surfaces described elsewhere in this doc are aspirational rather than enforced, and reviewers have no signal beyond reading the diff.

**Fix direction:**
- (a) Add `.github/workflows/ci.yml` triggered on `pull_request` and `push` to `master`. Primary runner: `windows-latest` — the app has Windows-only deps (`winrt-*`, `pywinstyles`) and the target platform is Windows, so Linux runners would need extensive skips to be useful. Matrix across Python 3.10 / 3.11 / 3.12 (current `requires-python = ">=3.10"`). Steps: checkout, `actions/setup-python` with pip cache keyed on `pyproject.toml`, `pip install -e ".[dev]"`, `pytest`.
- (b) Pick a lint/format toolchain and run it as a separate, fast-failing job. Recommended: `ruff check` + `ruff format --check` (single tool, zero-config baseline, no black/flake8/isort sprawl). Land the initial formatting pass in its own PR so this task's CI-enablement PR doesn't also carry a repo-wide reformat.
- (c) Gate merges on green CI — enable branch protection on `master` requiring the `ci` check. This is a GitHub repo settings change, not a code change; call it out in the PR description so the maintainer can flip it after merge.
- (d) Handle optional OCR extras: `easyocr`/`pytesseract` are optional and pull heavy deps (torch, system tesseract). Default CI installs `[dev]` only; any test that requires a real OCR backend should be marked (`@pytest.mark.ocr`) and deferred to an optional, manually-triggered job rather than gating every PR on a multi-GB install.
- (e) Non-goals for this task: code signing, release automation, publishing installers. Those belong with T-39 — once it lands, a follow-up `build.yml` (tag-triggered) can invoke `build_exe.ps1` plus the installer compiler. Keep this task strictly scoped to PR gating.

**Test surface:** the workflow itself — verify on a throwaway PR that (1) a deliberately broken test fails the CI run, (2) a lint violation fails the lint job, (3) the check is green on `master` after merge. No in-repo test changes required; this task is pure infra.

---

### T-43 · In-GUI search for players and old messages
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/gui/feed_panel.py`, `src/ow_chat_logger/gui/app.py`
- **Completed:** —

The live feed now shows many tightly-packed rows in a capped scrollback (`_MAX_ROWS = 500` in `feed_panel.py`). Finding a specific player's past line or a keyword from earlier in the session requires scroll-hunting — there is no in-app search. The persisted log files are reachable only via "Open Logs", which drops the user into a folder of CSVs rather than an in-context search over the running session.

**Fix direction:** (a) Add a `CTkEntry` to the feed panel header with placeholder `Search player or message…`, styled to match existing inputs (`T.R_INPUT`, `T.BG_ELEV`, `T.BORDER_HAIRLINE`), positioned left of the count pill. (b) Track `_filter_text` on `FeedPanel`; on every keystroke walk `self._rows`, `pack_forget()` non-matching entries, and re-pack matches in order. Match predicate: case-insensitive substring in either the entry's `player` or `text` field; for `HeroRow` the hero name (`entry.text`) is already part of the searchable field. (c) Keep the filter sticky across new incoming messages — `append_message` must check the predicate before packing the new row. (d) Hide adjacent date separators that would otherwise float between two filtered-out rows; walk separators in the same pass and skip any that are not sandwiched between two visible message rows. (e) While a filter is active, swap the count pill text from `N` to `N/M` (visible/total) and keep its `T.ACCENT` coloring. (f) Bind `Ctrl+F` at the main window (`app.py`) to focus the feed search entry. (g) Render an `×` clear button inside the entry that resets the filter — add a `close` glyph to `icons.py` if one is not already there.

**UI notes:**
- The search entry belongs in the feed header, not the bottom bar: the bottom bar is for app-wide controls (chat colors, theme, settings) and search is a panel-local tool over the feed contents.
- Preserve auto-scroll behavior: when a filter is active and a new matching message arrives, auto-scroll should still land at the bottom of the filtered view (call the same `_scroll_to_bottom` after filter-aware re-pack).
- Do NOT introduce channel-filter chips in this task — the leading channel dot already gives that affordance and adding chips muddies scope. Note as a follow-up.

**Test surface:** new `tests/test_feed_panel_search.py` — (1) a pure-logic helper that maps a sequence of `FeedEntry` and a filter string to the expected subset of players/messages, exercised without a Tk root; (2) an integration test that instantiates `FeedPanel` inside a hidden `CTk()` root, appends a fixed entry set, sets the filter, and asserts the exact list of visible rows via `winfo_ismapped()` plus the count-pill text format `N/M`. GUI integration tests are slower, so keep them focused on what the pure predicate cannot catch (pack/forget side effects, separator hiding, count-pill state).

**Not in scope / follow-ups to open as separate tasks:**
- Searching across persisted `chat_log.csv` / `hero_log.csv` files. That needs a different UI (results list with timestamps, file-streaming to avoid loading the whole session) and should not be conflated with filtering the live in-memory feed.
- Regex / whole-word search modes.
- Filter by channel (team-only / all-only) via toggle chips.

---

## Smells

### T-10 · Dead commented-out code in `image_processing.py`
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py:91-100`
- **Completed:** —

An old `INTER_NEAREST` version of `clean_mask` lives as a comment block below the new `clean_mask` wrapper. It's unreachable and undocumented as an alternative.

**Fix direction:** Delete it. The new `clean_mask_steps` with `INTER_NEAREST` is already the active implementation; the comment is stale.

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-11 · CLI `--metrics` flag can only force-on, not force-off
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/main.py:11-14`, `src/ow_chat_logger/main.py:84`
- **Completed:** —

`--metrics` sets `metrics_enabled_override=True`. Absence passes `None`, deferring to config. There is no way to force-disable metrics from the CLI when `metrics_enabled: true` is set in user config.

**Fix direction:** Use `BooleanOptionalAction` (Python 3.9+) or add `--no-metrics` to allow explicit force-off. Update `create_metrics_collector` to accept `False` as a disable override.

**Test surface:** `tests/test_cli.py` — add a case for `--no-metrics` overriding config-enabled metrics.

---

### T-21 · `SYSTEM_PATTERNS` contains redundant `.*` prefixes
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/parser.py:33-49`
- **Completed:** —

All but one of the 15 entries in `SYSTEM_PATTERNS` use a `.*` prefix (e.g. `r".*left the game"`). `SYSTEM_REGEX` is compiled and searched via `SYSTEM_REGEX.search(line)`, which already scans the full string — the `.*` prefix is always redundant and makes the patterns harder to read.

**Fix direction:** Remove the `.*` from all pattern strings in `SYSTEM_PATTERNS`. No behavioral change.

**Test surface:** No new tests needed. Verify existing parser tests still pass.

---

### T-22 · `_effective_scale_factor` computed twice per resize call
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/image_processing.py:64-70`
- **Completed:** —

`clean_mask_steps` calls `_effective_scale_factor(cfg)` twice — once for `fx` and once for `fy` — in the same `cv2.resize` call. The function is deterministic for a given `cfg`, so this is safe but wasteful and inconsistent (if the function ever became non-deterministic, fx and fy could diverge).

**Fix direction:** Assign the result to a local variable once, then use it for both `fx` and `fy`.

**Test surface:** No new tests needed. Verify existing image processing tests still pass.

---

### T-25 · Inline error-case dict in `run_benchmark` duplicates `_unavailable_case` structure
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `src/ow_chat_logger/benchmark.py:293-325`
- **Completed:** —

The `except Exception` branch in `run_benchmark` builds a 30-line inline dict that is structurally identical to the return value of `_unavailable_case`, differing only in `status: "error"`. This duplication means any schema change to benchmark result rows must be applied in two places. The error-case dict is also missing some fields relative to `_unavailable_case` (e.g. `fixture_path`, `expected_path` are present in `_unavailable_case` but the inline dict uses `str(png_path.resolve())` directly).

**Fix direction:** Extract an `_error_case(*, png_path, expected_path, profile_name, engine_id, message)` helper following the same signature pattern as `_unavailable_case`, with `status="error"`.

**Test surface:** `tests/test_benchmark.py` — verify error-case rows have the same schema as unavailable-case rows.

---

### T-32 · Stale "Related tasks" references in `KNOWN_FAILURES.md`
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `tests/fixtures/regression/KNOWN_FAILURES.md:64-72`
- **Completed:** —

The example_17 entry lists "Related tasks: T-27 (add hero-ban warning to SYSTEM_PATTERNS), T-28 (max vertical gap for continuation)". Both tasks are now `done` (2026-04-06). The entry must either be removed (if example_17 no longer fails) or updated with the current root cause — the text as written implies those fixes are still pending.

**Fix direction:** Re-run `pytest --run-ocr tests/test_regression_screenshots.py`, compare actual output for example_17 against the expected JSON, and either delete the entry or rewrite the root-cause explanation to reflect what remains after T-27 and T-28 landed.

**Test surface:** The regression suite itself is the test — whatever example_17 now emits is the ground truth for the updated note.

---

### T-33 · Undocumented regression failures for example_22, example_23, example_24
- **Severity:** smell
- **State:** 🔴 `open`
- **File:** `tests/fixtures/regression/KNOWN_FAILURES.md`, `tests/fixtures/regression/example_22.*`, `tests/fixtures/regression/example_23.*`, `tests/fixtures/regression/example_24.*`
- **Completed:** —

`pytest --run-ocr tests/test_regression_screenshots.py` reports 12 failures on master, but `KNOWN_FAILURES.md` only documents 9 of them (04, 05, 09, 11, 12, 13, 14, 17, 18). Three failing examples are undocumented:
- **example_22** (team_lines): expected `[A7X]: ich gärtnere im busch deiner muter` + `[A7X]: xd`, actual emits unrelated `[Kastelg]: hi gooners` + `[AN]: what is this` — suggests either a wrong `expected.json` or a coloring/crop misclassification.
- **example_23** and **example_24** (all_lines): both expect `[Power]: this is overwatch goodbye` followed by `[A7X]: epic!`, actual merges them into a single `[Power]: this is overwatch goodbye epicl` — looks like a missing-prefix / continuation-merge issue similar in shape to example_17.

**Fix direction:** Triage each of the three fixtures. For each, decide whether (a) the expected JSON is wrong and should be updated, (b) it reveals a real bug and should be split off into its own task, or (c) it's a genuine OCR/masking limitation that belongs in `KNOWN_FAILURES.md`.

**Test surface:** `tests/test_regression_screenshots.py` — these three examples.

---

## Deferred

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
- **File:** `src/ow_chat_logger/message_processing.py:25`, `src/ow_chat_logger/parser.py`
- **Completed:** —

The `ocr_fix_closing_bracket` guard fires for players whose names legitimately end in `l` (e.g. `Daniel`, `Nathaniel`). Tradeoff accepted — the heuristic is correct far more often than it fires falsely. Deferred until OCR character-level confidence or a corpus-based player name check is available.
