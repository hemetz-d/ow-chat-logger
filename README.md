# OW Chat Logger

A Windows-only OCR-based Overwatch chat logger with a GUI built in CustomTkinter.

It captures the Overwatch chat region, isolates team and all-chat by color, runs
OCR on each channel, parses player + message + hero-pick events, deduplicates
across frames, and writes everything to a single indexed SQLite database. The
GUI streams the live feed in real time and lets you search history across every
session you've ever recorded.

The default and best-supported OCR backend is **Windows OCR** (WinRT). EasyOCR
and Tesseract are available as optional fallbacks.

---

## At a glance

The GUI ships in three tabs — **Live Feed**, **Search**, and **Settings** — with
a configurable accent system (8 presets) that propagates through every surface.

- **Live Feed** — incoming messages with channel-colored dots, a "NEW" badge
  on fresh rows, and a side panel that opens with the player's full history
  when you click their name.
- **Search** — virtualized `tk.Text` results over the entire SQLite store,
  with channel + time-window filters and inline match highlighting.
- **Settings** — region picker, capture-interval presets (Slow / Normal /
  Fast / Custom), accent picker, and an Advanced section for raw HSV / OCR
  pipeline tuning.

> Screenshot conventions are documented under
> [docs/screenshots/](docs/screenshots/) — captures are dropped into that
> folder and surfaced inline here once available.

---

## Quick Start

### Install

```bash
pip install -e .
```

Optional OCR backends:

```bash
pip install -e ".[easyocr]"
pip install -e ".[tesseract]"
```

Requires Python 3.14+ on Windows. The GUI uses CustomTkinter; the OCR pipeline
ships with a WinRT-backed default, so a clean install on Windows works without
extra OCR setup.

### First run (GUI)

```bash
python -m ow_chat_logger --gui
```

On first launch the **Live Feed** tab shows an onboarding panel reflecting your
current capture region, interval, and chat colors. Hit **Start** in the toolbar
to begin capturing; the recording chip turns green and rows stream in.

To configure capture without leaving the app, switch to the **Settings** tab —
region picker, capture-interval presets (Slow / Normal / Fast / Custom), accent
colors, and an Advanced section for raw HSV / OCR-pipeline tuning.

### First run (headless CLI)

```bash
python -m ow_chat_logger
```

Same OCR pipeline as the GUI, but writes only to the SQLite store and prints
colorized lines to stdout. Useful for scripting / running on a second machine /
debugging without the GUI overhead.

### Configuration

User config lives at `%APPDATA%\ow-chat-logger\config.json`. You usually only
need:

```json
{
  "screen_region": [80, 400, 400, 600],
  "capture_interval": 2.0
}
```

See [config_template.json](config_template.json) for the full reference. The
GUI's Settings tab covers everything an end user normally touches.

---

## Where things live

After install everything is anchored under `%APPDATA%\ow-chat-logger\`:

```
%APPDATA%\ow-chat-logger\
├── config.json              user overrides (GUI also writes here)
├── chat_log.sqlite          canonical chat + hero history (one DB per install)
├── chat_log.sqlite-wal      SQLite WAL sidecar
├── chat_log.sqlite-shm      SQLite shared-memory sidecar
├── crash.log                uncaught exceptions before / during GUI start
├── update_check.json        cached update-check timestamp (when added)
└── dev/
    ├── debug_snaps/         saved frames when a parsing anomaly is detected
    └── analysis/<ts>/       per-run output of `ow-chat-logger analyze`
```

There is no longer an "OW Chat Logger Data" folder beside the exe — every
artefact lives in appdata so backup / cleanup is one folder.

`OW_CHAT_LOG_DIR` still redirects ad-hoc scratch output (performance metrics
CSVs) for power users / tests, but the chat DB always anchors to appdata.

---

## Architecture

```
                        ┌───────────────────────┐
                        │   Overwatch window    │
                        └───────────┬───────────┘
                                    │  pyautogui screenshot @ capture_interval
                                    ▼
   ┌──────────────────────────────────────────────────────────┐
   │  pipeline.py                                             │
   │   crop  →  HSV mask (team / all)  →  morphological clean │
   │            ↓                                             │
   │           OCR engine (Windows / EasyOCR / Tesseract)     │
   │            ↓                                             │
   │           parser.py  →  reconstruct lines, hero events   │
   │            ↓                                             │
   │           deduplication.py  →  drop frame-to-frame dupes │
   └──────────┬───────────────────────────────────────────────┘
              │ FeedEntry events
              ▼
   ┌──────────────────────────────────┐    ┌──────────────────────────┐
   │  logger.py (MessageLogger)       │    │  GUI backend_bridge.py   │
   │   INSERT into chat_log.sqlite    │    │   queue → main thread    │
   │   (one row per event, source ∈   │    │                          │
   │    {team, all, hero})            │    │   FeedPanel renders rows │
   └──────────────────┬───────────────┘    │   SearchView queries DB  │
                      │                    └──────────────────────────┘
                      ▼
              ┌────────────────────────┐
              │   chat_log.sqlite      │  ←── SearchView reads here too
              │   (WAL, indexed on     │      (cached read-only conn)
              │    player_lc, source,  │
              │    timestamp DESC)     │
              └────────────────────────┘
```

### Components

| Module | Role |
|---|---|
| `pipeline.py` | Orchestrates one capture frame: crop → mask → OCR → parse → dedupe. |
| `image_processing.py` | HSV masking and morphological cleanup per channel. |
| `ocr/` | Pluggable OCR backends. `windows`, `easyocr`, `tesseract` profiles in [config.py](src/ow_chat_logger/config.py). |
| `parser.py` / `message_processing.py` | Reconstruct chat lines from OCR boxes; handle player-prefix recovery and continuation-line merging. |
| `matcher.py` / `hero_roster.py` | Detect hero-pick events from system messages. |
| `deduplication.py` | Suppress identical lines that recur across consecutive frames. |
| `logger.py` | `MessageLogger` — thread-safe SQLite INSERT for chat + hero rows. |
| `_chat_db.py` | Schema + `open_db(path)` helper. WAL mode, indexed on `player_lc` / `source` / `timestamp`. |
| `log_search.py` | Pure search core. `search_logs(...)` and `history_for_player(...)` over the SQLite store with parameterized `LIKE ESCAPE` queries. |
| `live_runtime.py` | Headless CLI loop. Owns the capture timer + `MessageLogger` lifecycle. |
| `analysis.py` / `benchmark.py` | Offline tools: pipeline against a saved screenshot, or compare OCR profiles against the regression fixtures. |
| `gui/` | CustomTkinter UI (see below). |

### GUI module map

| Module | Role |
|---|---|
| `gui/app.py` | `OWChatLoggerApp` — main window, toolbar, status bar, accent application, polling loop. |
| `gui/main_tabs.py` | Live Feed / Search / Settings tab switcher (segmented control in the toolbar). |
| `gui/feed_panel.py` | Live feed with player side panel + onboarding side panel. |
| `gui/search_panel.py` | Virtualized search results in a single `tk.Text` widget with per-row tags. |
| `gui/settings_panel.py` | In-tab settings (no modal Toplevels). Sticky save / reset footer. |
| `gui/backend_bridge.py` | Thread-safe queue between the live runtime and the Tk main loop. |
| `gui/region_picker.py` | Click-and-drag region selector overlay for screen capture. |
| `gui/theme.py` | Color tokens, accent palette (8 presets), font helpers, chrome-style application. |
| `gui/config_io.py` | Read / write `config.json` for GUI-driven setting changes. |

### Database schema

One table covers chat and hero events; rows are discriminated by `source`:

```sql
CREATE TABLE messages (
  id          INTEGER PRIMARY KEY,
  timestamp   TEXT NOT NULL,
  player      TEXT NOT NULL,
  player_lc   TEXT NOT NULL,                 -- LOWER(player), indexed
  text        TEXT NOT NULL,                 -- chat body, or hero name when source='hero'
  text_lc     TEXT NOT NULL,                 -- LOWER(text), used for LIKE searches
  source      TEXT NOT NULL CHECK (source IN ('team','all','hero'))
);
CREATE INDEX idx_player_lc ON messages (player_lc);
CREATE INDEX idx_source    ON messages (source);
CREATE INDEX idx_timestamp ON messages (timestamp DESC);

PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
```

WAL mode lets the live writer and the GUI's read-only search connection coexist
without locking each other out.

---

## CLI

```bash
python -m ow_chat_logger --help
```

| Subcommand | Purpose |
|---|---|
| _(default)_ | Run the live logger (headless). |
| `--gui` | Launch the GUI. |
| `analyze --image <path>` | Run the OCR pipeline against one screenshot; dumps masks + a `report.json` with raw + parsed lines and effective config under `%APPDATA%\ow-chat-logger\dev\analysis\<ts>\`. |
| `benchmark` | Compare OCR profiles against the regression fixtures. `--profiles`, `--json-out`, `--csv-out`. |

Live-run flags:

```bash
python -m ow_chat_logger --metrics                           # enable metrics
python -m ow_chat_logger --metrics --metrics-interval 5      # rollup every 5s
python -m ow_chat_logger --ocr-profile easyocr_master_baseline
```

---

## OCR profiles

Built-in:

| Name | Engine | Notes |
|---|---|---|
| `windows_default` | Windows OCR (WinRT) | Default, fastest, primary supported path. |
| `easyocr_master_baseline` | EasyOCR | Comparison + tuning fallback. Requires `pip install -e ".[easyocr]"`. |
| `tesseract_default` | Tesseract | Fallback if Tesseract is on `PATH`. Requires `pip install -e ".[tesseract]"`. |

Change the default permanently in `config.json`:

```json
{ "ocr": { "default_profile": "easyocr_master_baseline" } }
```

Per-profile pipeline knobs live under `ocr.profiles.<name>.pipeline` — common
ones: `scale_factor`, `y_merge_threshold`, `team_hsv_lower` / `team_hsv_upper`,
`all_hsv_lower` / `all_hsv_upper`, `min_box_height_fraction`. The Settings →
Advanced section in the GUI covers the same keys with a friendlier surface.

---

## Tests

```bash
pytest                                                        # fast suite (~3s)
pytest --run-ocr tests/test_regression_screenshots.py         # OCR fixtures
pytest --run-ocr --ocr-profile easyocr_master_baseline tests/test_regression_screenshots.py
```

Fixture format is documented in
[tests/fixtures/regression/README.md](tests/fixtures/regression/README.md).

---

## Standalone Windows build

```powershell
.\build_exe.ps1
```

Builds a Nuitka standalone folder via [packaging/nuitka_entry.py](packaging/nuitka_entry.py).
The packaged exe is console-less by default (`--windows-console-mode=attach`):

- Double-clicking from Explorer opens only the GUI window — no terminal.
- CLI subcommands (`ow-chat-logger.exe analyze ...`, `benchmark ...`) still
  print to the parent console when launched from `cmd` / `powershell`.
- Uncaught exceptions before the GUI mainloop land in
  `%APPDATA%\ow-chat-logger\crash.log`.

---

## Environment overrides

| Env var | Effect |
|---|---|
| `OW_CHAT_LOGGER_CONFIG` | Use a custom `config.json` path. |
| `OW_CHAT_LOG_DIR` | Redirect ad-hoc scratch output (metrics CSVs, "Open Logs" target). The canonical chat DB always stays in appdata. |

---

## Repo layout

```
.
├── README.md
├── pyproject.toml
├── config_template.json
├── build_exe.ps1
├── src/ow_chat_logger/      capture / OCR / parsing / SQLite / CLI
│   └── gui/                 CustomTkinter GUI (Live / Search / Settings)
├── tests/                   pytest suite + regression screenshot fixtures
├── docs/
│   ├── screenshots/         GUI screenshots referenced from this README
│   └── internal/            project-management notes (TASKS, ITERATE)
└── packaging/               Nuitka entry point for the Windows build
```

Internal project-management notes live under
[docs/internal/README.md](docs/internal/README.md).
