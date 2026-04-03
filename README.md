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
  Upscale 3x + morphological close
        |               |
        v               v
       EasyOCR (GPU / CPU fallback)
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
```

With performance metrics written to CSV:

```bash
python -m ow_chat_logger --metrics
python -m ow_chat_logger --metrics --metrics-interval 5 --metrics-log-path perf.csv
```

Output files (default: `%APPDATA%\ow-chat-logger\`):

```
chat_log.csv          timestamp | player | message | channel
hero_log.csv          timestamp | player | hero     | channel
crash.log             exception tracebacks
performance_metrics.csv   timing, frame counts, duty cycle  (if --metrics)
```

### Analyze mode

Runs the pipeline against a saved screenshot without capturing anything. Useful for tuning HSV ranges and OCR thresholds offline.

```bash
python -m ow_chat_logger analyze --image path/to/screenshot.png
python -m ow_chat_logger analyze --image screenshot.png --output-dir ./debug --config overrides.json
```

Output:

```
<output-dir>/
  original.png      cropped capture region
  team_mask.png     blue (team) HSV mask
  all_mask.png      orange (all) HSV mask
  report.json       effective config, raw OCR lines, parsed messages
```

---

## Configuration

User config is loaded from `%APPDATA%\ow-chat-logger\config.json` (Windows) or `~/.ow-chat-logger/config.json`. Missing keys fall back to defaults. Override the path with `OW_CHAT_LOGGER_CONFIG`.

`config_template.json` documents all available keys. Key tuning parameters:

| Key | Default | Effect |
|-----|---------|--------|
| `screen_region` | `[50, 400, 500, 600]` | Capture region `[x, y, w, h]` in pixels |
| `scale_factor` | `3` | Upscale before OCR (higher = slower, more accurate) |
| `confidence_threshold` | `0.7` | Minimum OCR confidence to keep a box |
| `y_merge_threshold` | `18` | Max Y distance (px) to merge boxes into one line |
| `min_ocr_box_height` | `60` | Filter boxes shorter than this (noise rejection) |
| `capture_interval` | `2.0` | Seconds between screenshots |
| `team_hsv_lower/upper` | blue range | HSV bounds for team chat color |
| `all_hsv_lower/upper` | orange range | HSV bounds for all-chat color |
| `use_gpu` | `true` | Use GPU for EasyOCR; falls back to CPU automatically |
| `languages` | `["en", "de"]` | EasyOCR language models to load |
| `max_remembered` | `1000` | Deduplication window size |

---

## Installation

```bash
pip install -e ".[dev]"
```

Requires: `easyocr`, `opencv-python`, `pyautogui`, `numpy`, `pillow`, `psutil`

---

## Tests

```bash
pytest
```

Unit tests cover parser, buffer, dedup, pipeline, image processing, logger, metrics, config, CLI, and analysis mode.

OCR regression tests (slow, require GPU/CPU OCR):

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
