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
| T-30 | Improve team-chat color masking for blue-on-blue scenarios | structural | 🔴 `open` | — |
| T-32 | Stale "Related tasks" references in `KNOWN_FAILURES.md` | smell | 🔴 `open` | — |
| T-33 | Undocumented regression failures for example_22/23/24 | smell | 🔴 `open` | — |
| T-34 | Verify GUI chat-color settings propagate to all detection paths | structural | 🔵 `review` | — |
| T-35 | Expose in-game chat color options as presets for team/all chat | structural | 🔴 `open` | — |
| T-36 | Capture regression screenshot fixtures for every chat-color preset | structural | 🔴 `open` | — |
| T-39 | Extend build to produce a Windows installer | structural | 🔴 `open` | — |
| T-40 | In-app update check / auto-updater for installed builds | structural | 🔴 `open` | — |
| T-45 | Export chat history as plain `.txt` and `.csv` from the GUI | structural | 🟢 `done` | 2026-05-03 |
| T-43 | Search the persisted chat log for players and past messages | structural | 🟢 `done` | 2026-04-20 |
| T-25 | Inline error-case dict in `run_benchmark` duplicates `_unavailable_case` | smell | 🟢 `done` | 2026-04-20 |
| T-10 | Dead commented-out code | smell | 🟢 `done` | 2026-04-20 |
| T-21 | `SYSTEM_PATTERNS` redundant `.*` prefixes | smell | 🟢 `done` | 2026-04-20 |
| T-22 | `_effective_scale_factor` computed twice per resize | smell | 🟢 `done` | 2026-04-20 |
| T-42 | Re-resolve OCR profile on config change during a live session | structural | 🟢 `done` | 2026-04-18 |
| T-38 | Detect "message contains embedded chat prefix" as a debug-snap anomaly | structural | 🟢 `done` | 2026-04-18 |
| T-44 | Hide the console window for the packaged GUI exe | structural | 🟢 `done` | 2026-04-18 |
| T-41 | Set up CI for PRs (tests + lint on GitHub Actions) | structural | 🟢 `done` | 2026-04-18 |
| T-11 | CLI `--metrics` asymmetric flag | smell | 🟢 `done` | 2026-04-18 |
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

Overwatch ships a fixed palette of chat colors the user can pick in-game. The same 13-color palette is shared between team and all chat; the in-game UI flags "BLUE" as the **friendly default** and "RED" as the **enemy default**, but the full list is selectable for either channel. Today our GUI forces the user to hand-tune raw HSV tuples, which is a poor UX and a frequent source of "detection stopped working" reports when the in-game color is changed. We should ship a preset per in-game color option so the user selects "Team: <color name>" / "All: <color name>" and the corresponding HSV range is applied.

**In-game palette (13 entries, exact labels as shown in Overwatch settings):**

Hex values are eyedropped from the Overwatch settings-dropdown swatches — UI-chip centres, not rendered chat-text samples (T-36 is still the source of truth for final HSV ranges, since rendered text has AA and saturation spread the chips do not). OpenCV HSV uses H 0–179, S/V 0–255.

| # | In-game label | Role | Hex | OpenCV HSV centre |
|---|---|---|---|---|
| 1 | `YELLOW` | — | `#ffff00` | (30, 255, 255) |
| 2 | `LIME GREEN` | — | `#ccff00` | (36, 255, 255) |
| 3 | `NEON BLUE` | — | `#00ffff` | (90, 255, 255) |
| 4 | `AQUA` | — | `#523fff` | (123, 192, 255) |
| 5 | `TAWNY` | — | `#d45800` | (12, 255, 212) |
| 6 | `ORANGE` | — | `#d47900` | (17, 255, 212) |
| 7 | `MAGENTA` | — | `#de20de` | (150, 218, 222) |
| 8 | `BLUE` | **friendly default** | `#00beff` | (98, 255, 255) |
| 9 | `RED` | **enemy default** | `#ef2f52` | (175, 205, 239) |
| 10 | `GOLD` | — | `#ffd700` | (25, 255, 255) |
| 11 | `GREEN` | — | `#00ab84` | (83, 255, 171) |
| 12 | `PINK` | — | `#ff6ec7` | (162, 145, 255) |
| 13 | `PURPLE` | — | `#800080` | (150, 255, 128) |

The row order above matches the order shown in the Overwatch settings dropdown and is the order the preset dropdown should preserve.

Two centres collide at H=150 (`MAGENTA` vs `PURPLE`), separated by saturation/value — `MAGENTA` (218, 222) is a hot pink-purple, `PURPLE` (255, 128) is a dark saturated violet. Their HSV ranges must be disambiguated on **V** (and secondarily **S**), not on **H** alone; a hue-only preset would collapse them into one.

**Verification of current defaults against this palette:**
- **Team default** `team_hsv_lower=[96,190,90]`, `team_hsv_upper=[118,255,255]` — band H 96–118. The actual `BLUE (friendly default)` centre is **H=98**, which sits at the very bottom edge of the band; the upper bound (118) sits only 5 units below `AQUA` at H=123, so the current team band is biased toward indigo/violet-blue and risks aliasing with `AQUA` once both are presets. Re-centre around H=98 (e.g. H 90–106) with the preset migration. The `easyocr` profile uses [84,90,90]–[112,255,255] (H 84–112) which is centred more accurately on H=98 but has the same upper-edge risk.
- **All-chat default** `all_hsv_lower=[0,150,100]`, `all_hsv_upper=[20,255,255]` — band H 0–20. **The actual `RED (enemy default)` centre is H=175, at the opposite end of the hue wheel from our band.** OpenCV hue wraps at 179→0, so H=175 and H=0 are only 4 units apart in angular distance, which is why anti-aliased pixel spill across the wrap makes detection "work" today — but the current band is actually closer in hue to `ORANGE` (H=17) and `TAWNY` (H=12) than to the real `RED`. The correct band is `[170,150,100]–[179,255,255]`, or a split range covering both sides of the wrap (`H∈[0,5] ∪ [170,179]`) to catch AA spill. This explains the intermittent "detection stopped working" reports when users switch to any other palette entry: today's band is catching `RED` semi-accidentally via hue wrap and catches `ORANGE`/`TAWNY` directly, so only those three colors appear to work. The `easyocr` profile [0,100,100]–[20,255,255] has the same problem.
- **Naming smell to fix alongside this task:** [image_processing.py:21-29](src/ow_chat_logger/image_processing.py:21) still names the mask variables `blue_*` / `orange_*` and comments them as `BLUE (team)` / `ORANGE (all)`. Once "all chat" can be any of 13 colors, that naming becomes actively misleading — rename to `team_mask` / `all_mask` (or `team_*` / `all_*`) as part of this task, not a separate smell.

**Fix direction:** (a) Encode the 13-entry palette above in a single registry module (e.g. `src/ow_chat_logger/chat_color_presets.py`), preserving row order as the dropdown order; the same registry is reused for both team and all chat channels (one palette, not two). (b) Derive an HSV lower/upper range per color from a reference screenshot (see T-36) — the swatch hues in the "Rough hue (visual)" column above are a sanity check, not ground truth. (c) Store the presets in a single module (e.g. `src/ow_chat_logger/chat_color_presets.py`) keyed by channel + color name. (d) Replace the current "TEAM CHAT COLOR (HSV)" / "ALL CHAT COLOR (HSV)" sections in the settings panel (currently six raw integer entries per channel — the "color picker" the user sees today) with a single custom dropdown menu per channel, each offering exactly the in-game palette entries as items. The dropdown should render a small color swatch next to each name so the user picks by recognizing the in-game color, not by typing HSV numbers. Selection writes the four HSV keys from the preset registry. (e) Remove the raw HSV entry rows from the Advanced section too — the user should not be able to enter arbitrary HSV tuples from the UI; detection must track Overwatch's fixed palette and nothing else. Power users who still want raw tuples can edit `config.json` directly. (f) When the loaded config HSV ranges match a preset, reflect that preset name in the dropdown; if they do not match any preset (e.g. hand-edited config), show a read-only "Custom (edit config.json)" entry so the state is legible without offering a path to diverge further from the UI.

**UI notes:**
- CustomTkinter's `CTkOptionMenu` does not support per-item swatches natively; expect to build a small custom widget (frame + swatch + label + popup) or use `CTkComboBox` with a disabled entry and a custom dropdown. Either is acceptable — the hard requirement is "no free-form HSV entry, only the finite preset list is selectable".
- Do NOT use `tkinter.colorchooser` / the Windows system color picker anywhere in this flow. The target values come from Overwatch's palette, not arbitrary RGB the user might pick.

**Test surface:** new `tests/test_chat_color_presets.py` — assert every preset has a valid H∈[0,179], S∈[0,255], V∈[0,255] range with lower < upper per channel; assert selecting a preset writes all four keys; assert loading a config whose values match a preset round-trips to that preset name; assert loading a config whose values do NOT match any preset surfaces as "Custom" and the dropdown does not silently snap to a nearby preset.

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

### T-43 · Search the persisted chat log for players and past messages
- **Severity:** structural
- **State:** 🔴 `open`
- **File:** new `src/ow_chat_logger/log_search.py` (pure search over CSVs), new `src/ow_chat_logger/gui/search_panel.py` (results UI), `src/ow_chat_logger/gui/feed_panel.py` (clickable player names), `src/ow_chat_logger/gui/app.py` (entry point + keybind + click→history wiring), `src/ow_chat_logger/config.py` (reuse `get_app_paths().chat_log` / `.hero_log`)
- **Completed:** —

A single Overwatch match is short and the live feed fits comfortably in memory — a user already sees and remembers what is on screen, so filtering the live rows adds little value. What is actually valuable is recalling a specific player's past lines or a keyword from an earlier session, across the history that persists to `%APPDATA%/ow-chat-logger/chat_log.csv` and `hero_log.csv`. Today that history is reachable only via "Open Logs", which dumps the user into a folder of CSVs — there is no in-app search over it. This task adds that search, plus a click-to-history affordance so clicking a player's name in the live feed opens every known line and hero pick for that exact player. It explicitly does **not** add filtering to the live feed panel; the live feed stays as-is.

**Data shape:** `MessageLogger` (`src/ow_chat_logger/logger.py`) writes one append-only CSV per stream: `chat_log.csv` rows are `[timestamp, player, text, chat_type]`, `hero_log.csv` rows are `[timestamp, player, text]` (the hero name is in `text`). No rotation — both files grow for the lifetime of the install, potentially tens of thousands of rows. The live session has one of these files open for append under `MessageLogger._lock`; the search path must read a second, independent file handle (readers do not need the lock — csv append with explicit flush is safe to interleave with a reader, and a search occasionally missing the very latest line is acceptable).

**Fix direction:**
- (a) **Pure search core** — new `src/ow_chat_logger/log_search.py` exposing two entry points with zero GUI dependencies:
  - `search_logs(query, *, chat_log_path, hero_log_path, channel_filter=None, limit=500) -> SearchResultSet` — free-text case-insensitive substring match against player **or** message text.
  - `history_for_player(player, *, chat_log_path, hero_log_path, limit=1000) -> SearchResultSet` — **exact** case-insensitive match on the player column only (clicking "Chiaki" must not pull in "Chiaki123"). Returns every chat line and every hero pick for that player. The split is deliberate: the click flow wants exact equality, the free-text flow wants substring — one function doing both would need mode flags and a test matrix that doesn't pay for itself.
  - Shared return type: `SearchResultSet(results: list[SearchResult], truncated: bool)`. `SearchResult` is a dataclass `timestamp, player, text, source` with `source ∈ {"team", "all", "hero"}`. Both functions stream the CSVs with `csv.reader`, collect matches, sort newest-first, cap at `limit`, set `truncated=True` if the raw hit count exceeded `limit`. No pandas, no pre-loading.
- (b) **Search panel UI** — new `src/ow_chat_logger/gui/search_panel.py` defining a `SearchPanel(CTkToplevel)` modal with two modes selected by constructor argument:
  - **Free-text mode** (`initial_player=None`): top bar with a `CTkEntry` (placeholder `Search player or message…`) plus a `CTkSegmentedButton` channel filter (`All`, `Team`, `All chat`, `Hero`). Typing is debounced ~150 ms before running `search_logs`.
  - **Player-focused mode** (`initial_player="Chiaki"`): top bar replaces the free-text entry with a focus chip reading `Showing history for Chiaki ×`. Clicking the `×` drops the player filter and reverts to free-text mode (entry becomes editable, chip disappears). Runs `history_for_player` on open; no debounce needed since it's a single query on open.
  - Body is a `CTkScrollableFrame` of compact result rows. Result row format: `[timestamp muted] [channel dot] [player bold] [message, secondary]` — reuse the dot color convention and `T.CHAT_HERO` color for hero source so the visual language matches the feed. Footer shows `N results` / `N results (limit reached — refine query)` when truncated. Escape closes; Enter on a populated free-text entry is a no-op (search is already live via debounce).
- (c) **Click-to-history from the live feed** — make the player `CTkLabel` in `feed_panel.MessageRow` and `feed_panel.HeroRow` click-targets:
  - On `<Enter>`: cursor switches to `"hand2"`, player text gains a faint underline (construct the font with `underline=True` in a hover-only font, or toggle `font=` on hover).
  - On `<Button-1>`: fires a `FeedPanel.on_player_click(player: str)` callback passed in at construction. `OWChatLoggerApp` wires this callback to open `SearchPanel(initial_player=player)`.
  - Trim and skip empty/placeholder player strings (`""`, `"—"`) — clicking those should be a no-op, not open an empty-history modal.
  - The clickable affordance applies only to the player name, not the whole row (row hover already has its own highlight; conflating the two would be noisy).
- (d) **Entry points for free-text search** — wire a search icon button into the feed panel header (right side, left of the message count pill). Reuse the `search` glyph in `icons.py`. Click → open `SearchPanel()` in free-text mode. Bind `Ctrl+F` at the main window (`app.py`) to the same open-or-focus action. Do not add a search input inline in the feed header — search is not a live-feed operation.
- (e) **Path resolution** — every query reads `get_app_paths().chat_log` and `get_app_paths().hero_log` fresh. Missing files mean an empty source (return an empty `SearchResultSet`). Do not cache file content — users often search mid-session and expect recent lines to show up, including for their own hero picks just made.
- (f) **No writes, safe reads** — the search path never opens the CSVs for write. Wrap the per-row loop around `csv.Error` and skip malformed rows silently (count skips in a debug log line, do not surface to the user). Open with `newline=""` and `encoding="utf-8"` to match the writer.

**UI notes:**
- Modal (Toplevel), not a panel split or an overlay on the feed. The feed stays visible underneath; a modal is the minimum disruption for a look-up-and-close flow.
- Results should be selectable text (so the user can copy a username/message), which means using `CTkLabel` with mouse-drag text selection — tk's stock `Label` does not support that. Simplest: render each result as a read-only `CTkEntry` or a flat `tk.Text` line. Accept either; hard requirement is only "user can select and copy".
- When opened from a player click, the modal title bar should read `History · <player>` (or similar) so the window-switcher / Alt-Tab preview is legible; free-text mode keeps the plain `Search` title.
- Do NOT try to jump the live feed to the matched message. History rows predate the current session and no longer exist in the feed; a "jump to" affordance would be misleading.
- Only one `SearchPanel` should be live at a time — if the user clicks a second player while a panel is open, re-target the existing panel (swap to that player's history and raise/focus) rather than stacking Toplevels.

**Test surface:** new `tests/test_log_search.py`
- Fixture: write two tmp CSVs with a known mix of team/all/hero rows (20–30 rows total, varied players and keywords, including unicode, case variants, and OCR-like lookalikes).
- `search_logs`:
  - case-insensitive substring match on player, on message, and on both fields simultaneously;
  - channel filter restricts results to the selected source;
  - newest-first ordering across both files (a recent hero row should come before an older team row);
  - `limit` truncates and `SearchResultSet.truncated is True`;
  - malformed CSV rows are skipped, not fatal;
  - missing log files return an empty `SearchResultSet`, not an exception.
- `history_for_player`:
  - exact match is case-insensitive but rejects substring neighbors (`"Chiaki"` must not match `"Chiaki123"` or `"NotChiaki"`);
  - pulls both chat and hero rows for the target player, newest-first;
  - empty string / whitespace-only player returns an empty result rather than every row;
  - `limit` behaves the same as `search_logs`.

**Not in scope / follow-ups:**
- Regex / whole-word / exact-phrase search modes (free-text side).
- Persistent search history (last N queries remembered across launches).
- Index-backed search (SQLite FTS) — premature until real-world CSV sizes actually become slow; `csv.reader` handles tens of thousands of rows in well under a second on realistic hardware.
- Any live-feed filtering. The earlier draft of this task proposed filtering the live `FeedPanel` rows; that was explicitly dropped in the rework — sessions are short, the visible feed is already small, and live filter adds cost without value.
- Context menu on player click (copy name, mute, favorite). Single left-click opens history; richer actions can land later if there is demand.

---

### T-45 · Export chat history as plain `.txt` and `.csv` from the GUI
- **Severity:** structural
- **State:** 🟢 `done`
- **File:** new `src/ow_chat_logger/log_export.py`, `src/ow_chat_logger/gui/settings_panel.py` (or a new "History" panel), `src/ow_chat_logger/config.py` (`get_app_paths().chat_db`)
- **Completed:** 2026-05-03

When chat history lived in `chat_log.csv` / `hero_log.csv` the user could grep, copy, or share the file directly with any text tool. Moving the canonical store to `chat_log.sqlite` (T-43 follow-up) closes that affordance: the file is opaque outside a SQLite client. We need a first-class export so users can hand history to a teammate, paste it into a bug report, or archive it before wiping the DB.

**Fix direction:**
- (a) **Pure export core** — new `src/ow_chat_logger/log_export.py` with two entry points sharing a single SQLite read pass:
  - `export_to_csv(out_path, *, channel_filter=None, since=None, until=None) -> int` — writes a header row (`timestamp, player, text, source`) plus one row per message in chronological order. Returns the row count written.
  - `export_to_txt(out_path, *, channel_filter=None, since=None, until=None, include_hero=True) -> int` — human-readable rendering: `YYYY-MM-DD HH:MM | TEAM | Alice: hi`, hero rows as `... | HERO | Alice / Mercy`. Same colorless format the console writer uses, minus the ANSI escapes.
  - Both open the DB via `get_app_paths().chat_db` in read-only mode (`uri=True, mode=ro`). No GUI dependencies — these are unit-testable in isolation.
- (b) **GUI wiring** — add an "Export history…" button to the Settings tab (or a dedicated History section). Click opens a small modal: format radio (`.csv` / `.txt`), channel filter (Team / All / Hero / All channels), date range (defaults: all time), then a native save dialog seeded with `chat_history_<YYYYMMDD>.csv`. On success show the existing in-panel toast (`Exported N messages to <path>`).
- (c) **Idempotent / safe** — never modify the DB. Overwrite is fine if the user picks an existing path (the OS save dialog already confirms). If the export fails midway, leave the partial file in place but surface the error in the toast.

**UI notes:**
- Don't add this to the search panel — search is for finding things, export is for moving the whole (filtered) corpus elsewhere. Settings is the natural home alongside "Open Logs" and "Config folder".
- A "share with teammate" workflow is the primary use case → default to `.txt` (readable in any text app, paste-able into Discord) and make `.csv` the second option.
- No streaming progress UI needed for the realistic row counts (tens of thousands max). If exports start blocking the UI noticeably, kick the SQL pass onto a thread and re-check.

**Test surface:** new `tests/test_log_export.py`
- Seed a tmp DB via the same `_seed_db` helper used in `test_log_search.py`.
- `export_to_csv`: header row present; one data row per message; chronological order; channel filter restricts source; round-trip via `csv.reader` matches input.
- `export_to_txt`: timestamp + channel tag + speaker prefix shape per row; hero rows use `/` separator; channel filter excludes correctly; ANSI escapes never present in output.
- Both: empty DB produces a file with header only (CSV) or empty file (TXT) and returns 0; missing DB raises a clean error rather than crashing.

**Not in scope:**
- JSON export — easy to add later if a structured-consumer use case materializes; no current ask.
- Re-import from exported file (would need a separate ingest path; out of scope here, history is append-only at the writer).
- Automated periodic exports / backup-on-quit — manual export only for now.

---

## Smells

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
