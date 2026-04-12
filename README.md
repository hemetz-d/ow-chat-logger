# ow-chat-logger

Windows-only OCR-based Overwatch chat logger.

It captures the chat area, isolates team and all-chat by color, runs OCR, reconstructs lines, and writes deduplicated messages to CSV. The default and best-supported backend is Windows OCR.

## Quick Start

### 1. Install

```bash
pip install -e .
```

Optional OCR backends:

```bash
pip install -e ".[easyocr]"
pip install -e ".[tesseract]"
```

### 2. Create a config file

User config lives at:

- `%APPDATA%\ow-chat-logger\config.json`

You usually only need to set the chat capture region:

```json
{
  "screen_region": [80, 400, 400, 600]
}
```

Use [config_template.json](config_template.json) as the full reference.

### 3. Run the live logger

```bash
python -m ow_chat_logger
```

To use a different OCR profile:

```bash
python -m ow_chat_logger --ocr-profile easyocr_master_baseline
```

## What You Get

By default the app writes files under `%APPDATA%\ow-chat-logger\`:

- `chat_log.csv`
- `hero_log.csv`
- `crash.log`
- `performance_metrics_*.csv` when metrics are enabled
- `analysis\...` folders from `analyze`

## Supported Workflows

### Live Logging

This is the normal mode.

```bash
python -m ow_chat_logger
```

Optional metrics:

```bash
python -m ow_chat_logger --metrics
python -m ow_chat_logger --metrics --metrics-interval 5 --metrics-log-path perf.csv
```

### Analyze A Screenshot

Use this when tuning `screen_region`, HSV ranges, or OCR behavior on a saved image.

```bash
python -m ow_chat_logger analyze --image path/to/screenshot.png
python -m ow_chat_logger analyze --image screenshot.png --output-dir .\\debug
python -m ow_chat_logger analyze --image screenshot.png --ocr-profile easyocr_master_baseline
```

`analyze` writes:

- the cropped source image
- per-channel masks
- intermediate mask-processing steps
- `report.json` with raw OCR lines, parsed lines, timings, and effective config

### Benchmark OCR Profiles

Use this to compare built-in OCR profiles against the regression fixtures.

```bash
python -m ow_chat_logger benchmark
python -m ow_chat_logger benchmark --profiles windows_default easyocr_master_baseline
python -m ow_chat_logger benchmark --json-out results.json --csv-out results.csv
```

## OCR Profiles

Built-in profiles:

- `windows_default`
  Windows OCR via WinRT. Default, fastest, and the primary supported path.
- `easyocr_master_baseline`
  Optional fallback for comparison and tuning.
- `tesseract_default`
  Optional fallback if Tesseract is installed and on `PATH`.

To change the default permanently, set `ocr.default_profile` in your config.

## Config Notes

Most users only need:

- `screen_region`
- `capture_interval`
- `ocr.default_profile`

If you are tuning OCR behavior, the per-profile pipeline settings live under:

- `ocr.profiles.<name>.pipeline`

Useful keys there include:

- `scale_factor`
- `y_merge_threshold`
- `max_continuation_y_gap_factor`
- `min_box_height_fraction`
- `team_hsv_lower` / `team_hsv_upper`
- `all_hsv_lower` / `all_hsv_upper`

Environment overrides:

- `OW_CHAT_LOGGER_CONFIG`
  Use a custom config file path.
- `OW_CHAT_LOG_DIR`
  Override the output directory.

## Tests

Fast test suite:

```bash
pytest
```

OCR screenshot regression suite:

```bash
pytest --run-ocr tests/test_regression_screenshots.py
```

Run the regression suite against a specific backend profile:

```bash
pytest --run-ocr --ocr-profile easyocr_master_baseline tests/test_regression_screenshots.py
```

Fixture format is documented in [tests/fixtures/regression/README.md](tests/fixtures/regression/README.md).

## Standalone Windows Build

```powershell
.\build_exe.ps1
```

This builds a standalone folder app with Nuitka using [packaging/nuitka_entry.py](packaging/nuitka_entry.py).

## Repo Layout

Root files are intentionally kept small and user-facing:

- `README.md`
- `pyproject.toml`
- `config_template.json`
- `build_exe.ps1`
- `src/`
- `tests/`

Internal project-management notes live under [docs/internal/README.md](docs/internal/README.md).
