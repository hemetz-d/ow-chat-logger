# ow-chat-logger

OCR-based Overwatch chat logger focused on local runtime capture, parsing, and tuning.

## Run

```bash
python -m ow_chat_logger
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

See `tests/fixtures/regression/README.md` for the JSON format and `config_overrides`.

## OCR Calibration
Use the supported analyze mode to inspect OCR output for a saved screenshot:

```bash
python -m ow_chat_logger analyze --image path\to\screenshot.png
```

Optional flags:
- `--output-dir <path>` to control where masks and the JSON report are written
- `--config <path>` to layer JSON config overrides onto the normal runtime config for that analysis run
