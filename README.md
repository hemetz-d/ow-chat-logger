# ow-chat-logger

Windows-only OCR-based Overwatch chat logger focused on local runtime capture, parsing, and tuning.

## Run

```bash
python -m ow_chat_logger
```

This build uses the built-in Windows OCR APIs through WinRT.

Select a different OCR profile at runtime:

```bash
python -m ow_chat_logger --ocr-profile easyocr_master_baseline
```

Enable runtime performance metrics:

```bash
python -m ow_chat_logger --metrics --metrics-interval 5
```

Optional metrics flags:
- `--metrics-interval <seconds>` to control summary frequency
- `--metrics-log-path <path>` to write metrics CSV to a custom file

## Tests

```bash
pip install -e ".[dev]"
pytest
```

- **Unit tests** (default): parser, buffer, dedup, pipeline mocks, image reconstruction, config helpers.
- **OCR screenshot regression** (optional): add `tests/fixtures/regression/<name>.png` + `<name>.expected.json`, then run:

```bash
pytest --run-ocr tests/test_regression_screenshots.py
```

To run OCR regression against a non-default backend profile:

```bash
pytest --run-ocr --ocr-profile easyocr_master_baseline tests/test_regression_screenshots.py
```

See `tests/fixtures/regression/README.md` for the JSON format and `config_overrides`.

## OCR Profiles
- `windows_default`: current WinRT OCR implementation.
- `easyocr_master_baseline`: preserved EasyOCR-style baseline matching the old `master` defaults.
- `tesseract_default`: optional Tesseract profile for side-by-side comparisons.

Profile settings live under `ocr.default_profile` and `ocr.profiles` in config.

Legacy flat OCR keys are still accepted and mapped onto the default Windows profile.

## Optional Backends
Install optional OCR engines as needed:

```bash
pip install -e ".[dev,easyocr]"
pip install -e ".[dev,tesseract]"
```

## OCR Calibration
Use the supported analyze mode to inspect OCR output for a saved screenshot:

```bash
python -m ow_chat_logger analyze --image path\to\screenshot.png
```

Optional flags:
- `--output-dir <path>` to control where masks and the JSON report are written
- `--config <path>` to layer JSON config overrides onto the normal runtime config for that analysis run
- `--ocr-profile <name>` to analyze with a specific OCR profile

## OCR Benchmarking
Benchmark one or more OCR profiles against the screenshot regression fixtures:

```bash
python -m ow_chat_logger benchmark --profiles windows_default easyocr_master_baseline tesseract_default --json-out benchmark.json --csv-out benchmark.csv
```

Optional flags:
- `--fixtures <path>` to point at a different regression fixture directory
- `--benchmark-config <path>` to layer JSON config overrides onto the benchmark run
- `--profiles <name> [<name> ...]` to benchmark a specific profile subset

## Quality Tuning
Adjust each profile's `pipeline` and `settings` blocks independently so Windows OCR, EasyOCR, and Tesseract can be tuned and benchmarked side by side without maintaining parallel branches.
