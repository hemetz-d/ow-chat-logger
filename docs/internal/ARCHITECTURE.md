# Architecture

Capture flow, module layout, and the SQLite schema. Pulled out of the
top-level README so the user-facing surface stays short.

## Data flow

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

## Capture pipeline

| Module | Role |
|---|---|
| `pipeline.py` | Orchestrates one capture frame: crop → mask → OCR → parse → dedupe. |
| `image_processing.py` | HSV masking and morphological cleanup per channel. |
| `ocr/` | Pluggable OCR backends. `windows`, `easyocr`, `tesseract` profiles in [config.py](../../src/ow_chat_logger/config.py). |
| `parser.py` / `message_processing.py` | Reconstruct chat lines from OCR boxes; handle player-prefix recovery and continuation-line merging. |
| `matcher.py` / `hero_roster.py` | Detect hero-pick events from system messages. |
| `deduplication.py` | Suppress identical lines that recur across consecutive frames. |
| `logger.py` | `MessageLogger` — thread-safe SQLite INSERT for chat + hero rows. |
| `_chat_db.py` | Schema + `open_db(path)` helper. WAL mode, indexed on `player_lc` / `source` / `timestamp`. |
| `log_search.py` | Pure search core. `search_logs(...)` and `history_for_player(...)` over the SQLite store with parameterized `LIKE ESCAPE` queries. |
| `live_runtime.py` | Headless CLI loop. Owns the capture timer + `MessageLogger` lifecycle. |
| `analysis.py` / `benchmark.py` | Offline tools: pipeline against a saved screenshot, or compare OCR profiles against the regression fixtures. |

## GUI module map

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

## Database schema

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

## Storage layout

Everything is anchored under `%APPDATA%\ow-chat-logger\`:

```
%APPDATA%\ow-chat-logger\
├── config.json              user overrides (GUI also writes here)
├── chat_log.sqlite          canonical chat + hero history
├── chat_log.sqlite-wal      SQLite WAL sidecar
├── chat_log.sqlite-shm      SQLite shared-memory sidecar
├── crash.log                uncaught exceptions before / during GUI start
└── dev/
    ├── debug_snaps/         saved frames when a parsing anomaly is detected
    └── analysis/<ts>/       per-run output of `ow-chat-logger analyze`
```

There is no longer an "OW Chat Logger Data" folder beside the exe.

`OW_CHAT_LOG_DIR` redirects ad-hoc scratch output (performance metrics CSVs)
for power users / tests, but the chat DB always anchors to appdata.
`OW_CHAT_LOGGER_CONFIG` redirects the config file path.
