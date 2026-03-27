import pytest

from ow_chat_logger.main import main


def test_main_without_args_dispatches_to_live_logger(monkeypatch):
    called = {}

    def fake_run_live_logger(**kwargs):
        called.update(kwargs)
        return 7

    monkeypatch.setattr("ow_chat_logger.main.run_live_logger", fake_run_live_logger)

    assert main([]) == 7
    assert called == {
        "metrics_enabled_override": None,
        "metrics_interval_override": None,
        "metrics_log_path_override": None,
    }


def test_main_metrics_flags_dispatch_to_live_logger(monkeypatch):
    called = {}

    def fake_run_live_logger(**kwargs):
        called.update(kwargs)
        return 13

    monkeypatch.setattr("ow_chat_logger.main.run_live_logger", fake_run_live_logger)

    assert main(["--metrics", "--metrics-interval", "5", "--metrics-log-path", "perf.csv"]) == 13
    assert called == {
        "metrics_enabled_override": True,
        "metrics_interval_override": 5.0,
        "metrics_log_path_override": "perf.csv",
    }


def test_main_analyze_dispatches(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-dispatch")
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"fake")
    called = []

    def fake_run_analyze(args):
        called.append(args.image)
        return 11

    monkeypatch.setattr("ow_chat_logger.main.run_analyze", fake_run_analyze)

    assert main(["analyze", "--image", str(image_path)]) == 11
    assert called == [str(image_path)]


def test_main_analyze_requires_image():
    with pytest.raises(SystemExit):
        main(["analyze"])
