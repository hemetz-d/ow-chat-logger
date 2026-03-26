# Screenshot OCR regression fixtures

Add **pairs** of files in this folder:

| File | Purpose |
|------|--------|
| `my_sample.png` | Full screenshot (or cropped chat region) in **RGB** when saved — use PNG. |
| `my_sample.expected.json` | Expected classified chat lines after masks + EasyOCR + parsing/filtering. |

## Expected JSON format

```json
{
  "team_lines": [
    "[PlayerName] : first line",
    "PlayerName (Hero): hero line"
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

- **`team_lines` / `all_lines`**: Final filtered/classified lines, not raw OCR fragments.
- **`config_overrides`**: Optional. Merged on top of runtime `CONFIG` for that screenshot.

## How to run

```bash
pip install -e ".[dev]"
pytest --run-ocr tests/test_regression_screenshots.py
```

Without `--run-ocr`, OCR tests are skipped.

## Notes

- These tests intentionally reuse the app's parsing/filtering code, so app changes are reflected automatically.
- Leading/trailing whitespace and repeated spaces are normalized in assertions.
