# Screenshot OCR regression fixtures

Add **pairs** of files in this folder:

| File | Purpose |
|------|--------|
| `my_sample.png` | Full screenshot (or cropped chat region) in **RGB** when saved — use PNG. |
| `my_sample.expected.json` | Expected OCR lines after masks + EasyOCR + `reconstruct_lines`. |

## Expected JSON format

```json
{
  "team_lines": [
    "[PlayerName] : first line",
    "continuation text"
  ],
  "all_lines": [
    "[Other] : all chat line"
  ],
  "config_overrides": {
    "confidence_threshold": 0.7,
    "text_threshold": 0.5,
    "scale_factor": 3,
    "y_merge_threshold": 18,
    "team_hsv_lower": [88, 135, 135],
    "team_hsv_upper": [112, 255, 255],
    "all_hsv_lower": [6, 155, 155],
    "all_hsv_upper": [20, 255, 255]
  }
}
```

- **`team_lines` / `all_lines`**: Lists of strings exactly as produced by `ow_chat_logger.pipeline.extract_chat_lines` (one logical line per list entry; continuations are merged only after the buffer in the main app — here you usually store **raw OCR lines** from the pipeline).
- **`config_overrides`**: Optional. Merged on top of your runtime `CONFIG` so you can pin HSV/thresholds for that screenshot when you tune parameters.

## How to run

```bash
pip install -e ".[dev]"
pytest --run-ocr tests/test_regression_screenshots.py
```

Without `--run-ocr`, OCR tests are skipped (fast default CI).

## Updating expectations after a deliberate change

1. Run once and copy failing output from pytest, **or** add a small script that prints `extract_chat_lines(...)`.
2. Paste into `*.expected.json` (keep `config_overrides` in sync with what you want to lock).

## Notes

- EasyOCR output can vary slightly by version/CPU vs GPU. If a test becomes flaky, tighten `config_overrides` (e.g. thresholds) or snapshot fewer lines.
- Trailing/leading whitespace and repeated spaces are **normalized** in the test (single spaces).
