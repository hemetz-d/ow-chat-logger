# ow-chat-logger

OCR-based Overwatch chat logger. Captures periodic screenshots, isolates chat text by color channel, runs OCR, and writes deduplicated messages to CSV.

```
Screenshot (pyautogui)
        |
        v
  HSV Color Filter
  +-----------+   +-----------+
  | BLUE mask |   |ORANGE mask|
  | (team)    |   | (all)     |
  +-----------+   +-----------+
        |               |
        v               v
  Upscale + morphological steps  (per-profile)
        |               |
        v               v
  OCR Backend  (pluggable: Windows / EasyOCR / Tesseract)
        |               |
        v               v
  Line reconstruct (Y-merge, height filter)
        |               |
        v               v
  Parse + normalize (classify, fix OCR typos)
        |               |
        v               v
  MessageBuffer (handle continuations per screenshot)
        |               |
        +-------+-------+
                |
                v
       Dedup (LRU, 1000-entry window)
                |
                v
     chat_log.csv / hero_log.csv
```

---

## Modes

### Live logger (default)

Runs two threads: one captures screenshots at a configurable interval, the other processes frames through the OCR pipeline.

```bash
python -m ow_chat_logger
python -m ow_chat_logger --ocr-profile easyocr_master_baseline
```

With performance metrics written to CSV:

```bash
python -m ow_chat_logger --metrics
python -m ow_chat_logger --metrics --metrics-interval 5 --metrics-log-path perf.csv
```

Output files (default: `%APPDATA%\ow-chat-logger\`):

```
chat_log.csv              timestamp | player | message | channel
hero_log.csv              timestamp | player | hero     | channel
crash.log                 exception tracebacks
performance_metrics.csv   timing, frame counts, duty cycle  (if --metrics)
```

### Analyze mode

Runs the pipeline against a saved screenshot without capturing anything. Useful for tuning HSV ranges and OCR thresholds offline. Produces intermediate mask images for each processing step.

```bash
python -m ow_chat_logger analyze --image path/to/screenshot.png
python -m ow_chat_logger analyze --image screenshot.png --ocr-profile easyocr_master_baseline --output-dir ./debug --config overrides.json
```

Output:

```
<output-dir>/
  original.png                  cropped capture region
  team_01_raw_threshold.png     raw HSV mask
  team_02_upscaled.png          after upscaling
  team_03_after_close.png       after morphological close  (high_quality_ocr only)
  team_04_after_open.png        after morphological open   (high_quality_ocr only)
  all_*.png                     same steps for all-chat channel
  report.json                   effective config, raw OCR lines, parsed messages
```

### Benchmark mode

Runs all configured OCR profiles against regression fixtures and ranks them by accuracy and speed.

```bash
python -m ow_chat_logger benchmark
python -m ow_chat_logger benchmark --profiles windows_default easyocr_master_baseline
python -m ow_chat_logger benchmark --fixtures tests/fixtures/regression --json-out results.json --csv-out results.csv
```

Outputs a ranked summary to stdout:

```
OCR benchmark summary:
  windows_default (windows):            7/7 exact matches, p50 total 42.10 ms
  easyocr_master_baseline (easyocr):    6/7 exact matches, p50 total 380.22 ms
  tesseract_default (tesseract):        unavailable
```

---

## OCR Profiles

Three built-in profiles are available. The active profile controls the OCR engine, image preprocessing steps, and HSV color ranges.

| Profile | Engine | Notes |
|---------|--------|-------|
| `windows_default` | Windows OCR (WinRT) | Default. Fast, no extra install needed on Windows. |
| `easyocr_master_baseline` | EasyOCR | Requires `pip install ow-chat-logger[easyocr]`. GPU optional. |
| `tesseract_default` | Tesseract | Requires Tesseract installed and on PATH. |

Select a profile at runtime with `--ocr-profile <name>` in any mode. To change the default permanently, set `ocr.default_profile` in your user config.

---

## Configuration

User config is loaded from `%APPDATA%\ow-chat-logger\config.json` (Windows) or `~/.ow-chat-logger/config.json`. Missing keys fall back to defaults. Override the path with `OW_CHAT_LOGGER_CONFIG`.

`config_template.json` documents all available keys and the full profile structure.

Key pipeline parameters (per profile under `ocr.profiles.<name>.pipeline`):

| Key | Effect |
|-----|--------|
| `screen_region` | Capture region `[x, y, w, h]` in pixels |
| `scale_factor` | Upscale factor before OCR |
| `high_quality_ocr` | Enables extra morphological steps and component filtering |
| `y_merge_threshold` | Max Y distance (px) to merge OCR boxes into one line |
| `min_ocr_box_height` | Filter boxes shorter than this (noise rejection) |
| `team_hsv_lower/upper` | HSV bounds for team chat color (blue) |
| `all_hsv_lower/upper` | HSV bounds for all-chat color (orange) |

Top-level settings:

| Key | Default | Effect |
|-----|---------|--------|
| `capture_interval` | `2.0` | Seconds between screenshots |
| `max_remembered` | `1000` | Deduplication window size |
| `ocr.default_profile` | `windows_default` | Active profile when no `--ocr-profile` flag is given |

---

## Installation

```bash
pip install -e ".[dev]"
```

With EasyOCR support:

```bash
pip install -e ".[dev,easyocr]"
```

Core dependencies: `opencv-python`, `pyautogui`, `numpy`, `pillow`, `psutil`
Windows OCR requires: `winrt-runtime` (included in `requirements.txt`)

---

## Tests

```bash
pytest
```

Unit tests cover parser, buffer, dedup, pipeline, image processing, logger, metrics, config, CLI, analysis, and benchmark.

OCR regression tests (slow, require an active OCR backend):

```bash
pytest --run-ocr tests/test_regression_screenshots.py
```

To run OCR regression against a non-default backend profile:

```bash
pytest --run-ocr --ocr-profile easyocr_master_baseline tests/test_regression_screenshots.py
```

Add regression fixtures as `tests/fixtures/regression/<name>.png` + `<name>.expected.json`. See the fixture README for the JSON format and per-fixture config overrides.

---

## Standalone EXE (Windows)

```powershell
.\build_exe.ps1
```

Uses Nuitka. Entry point: `packaging/nuitka_entry.py`.
