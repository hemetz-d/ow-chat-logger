# OW Chat Logger

A Windows-only Overwatch chat logger with a CustomTkinter GUI. It watches the
chat region, runs OCR per channel (team / all / hero picks), and writes every
event to a single SQLite database you can search across all your sessions.

## At a glance

The GUI ships in three tabs with a configurable accent system:

- **Live Feed** — incoming messages with channel-colored dots, a "NEW" badge
  on fresh rows, and a side panel that opens with a player's full history
  when you click their name.
- **Search** — virtualized results over your entire history, with channel +
  time-window filters and inline match highlighting.
- **Settings** — region picker, capture-interval presets, accent picker, and
  an Advanced section for HSV / OCR tuning.

> Screenshot conventions are documented under
> [docs/screenshots/](docs/screenshots/).

## Install

```bash
pip install -e .
```

Requires Python 3.14+ on Windows. The default OCR backend is Windows OCR
(WinRT), which works out of the box on a clean install. EasyOCR and Tesseract
are optional fallbacks (`pip install -e ".[easyocr]"` / `".[tesseract]"`).

## Run

```bash
python -m ow_chat_logger --gui     # GUI (recommended)
python -m ow_chat_logger           # headless CLI
```

On first launch the GUI's Live Feed tab walks you through the capture region
and interval. Hit **Start** in the toolbar to begin recording.

## Configuration

User config lives at `%APPDATA%\ow-chat-logger\config.json`. The Settings tab
covers everything an end user normally touches; if you want to hand-edit, see
[config_template.json](config_template.json) for the full reference.

## Where files live

Everything lives under `%APPDATA%\ow-chat-logger\`:

- `chat_log.sqlite` — your full chat + hero history (one DB per install)
- `config.json` — user overrides
- `crash.log` — uncaught exceptions
- `dev/` — debug snapshots and `analyze` output

## OCR profiles

Three are built in: `windows_default` (default, fastest), `easyocr_master_baseline`,
and `tesseract_default`. Switch the default in `config.json` under
`ocr.default_profile`, or tune one in Settings → Advanced.

## CLI extras

```bash
python -m ow_chat_logger analyze --image screenshot.png   # debug a single frame
python -m ow_chat_logger benchmark                        # compare OCR profiles
```

## Tests + build

```bash
pytest                            # fast suite
.\build_exe.ps1                   # standalone Windows exe via Nuitka
```

## Going deeper

Architecture overview, module breakdown, database schema, and the open task
backlog all live in [docs/internal/](docs/internal/).
