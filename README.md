# Run main xd
TODO
- release executable for noobs
- make better in every way

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
## Building Executable
The project uses Nuitka to build a standalone executable.

### Prerequisites
- Python 3.10+
- Microsoft Visual Studio Build Tools with C++ workload (for Nuitka compilation on Windows)

### Running PowerShell Build
`powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`

This will:
1. Install the project and packaging dependencies, including Nuitka
2. Build the executable with Nuitka from the package-aware launcher
