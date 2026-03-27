import csv
from pathlib import Path
from uuid import uuid4

from ow_chat_logger.metrics import PerformanceMetrics


def _local_tmp_dir(name: str) -> Path:
    path = Path("tests") / "_test_log_dir" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_performance_metrics_writes_csv_summary():
    metrics_path = _local_tmp_dir("metrics-summary") / "performance_metrics.csv"
    metrics = PerformanceMetrics(
        metrics_path,
        interval_seconds=10.0,
        capture_interval=2.0,
        use_gpu=False,
        screen_region=(1, 2, 3, 4),
    )

    metrics.record_capture(0.010, dropped_frames=1)
    metrics.record_processed_frame(
        preprocess_seconds=0.020,
        ocr_seconds=0.030,
        parse_seconds=0.040,
        total_seconds=0.090,
        team_skipped=True,
        all_skipped=False,
        team_boxes=2,
        all_boxes=3,
        team_lines=1,
        all_lines=2,
    )
    metrics.record_logged_message("standard")
    metrics.record_logged_message("hero")
    assert metrics.flush_if_due(force=True) is True
    metrics.close()

    rows = list(csv.DictReader(metrics_path.open("r", encoding="utf-8")))
    assert len(rows) == 1
    first = rows[0]
    assert first["frames_captured"] == "1"
    assert first["frames_processed"] == "1"
    assert first["frames_dropped"] == "1"
    assert first["ocr_skipped_team"] == "1"
    assert first["ocr_skipped_all"] == "0"
    assert first["ocr_skipped_total"] == "1"
    assert first["ocr_boxes_total"] == "5"
    assert first["lines_total"] == "3"
    assert first["chat_messages_logged"] == "1"
    assert first["hero_messages_logged"] == "1"
    assert first["screen_region"] == "[1, 2, 3, 4]"


def test_performance_metrics_final_close_flushes_partial_interval():
    metrics_path = _local_tmp_dir("metrics-close") / "close_flush.csv"
    metrics = PerformanceMetrics(
        metrics_path,
        interval_seconds=60.0,
        capture_interval=2.0,
        use_gpu=True,
        screen_region=(50, 400, 500, 600),
    )

    metrics.record_capture(0.005)
    metrics.close()

    rows = list(csv.DictReader(metrics_path.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["frames_captured"] == "1"


def test_performance_metrics_handles_missing_psutil(monkeypatch):
    metrics_path = _local_tmp_dir("metrics-no-psutil") / "no_psutil.csv"
    monkeypatch.setattr("ow_chat_logger.metrics.psutil", None)

    metrics = PerformanceMetrics(
        metrics_path,
        interval_seconds=1.0,
        capture_interval=2.0,
        use_gpu=False,
        screen_region=(0, 0, 1, 1),
    )

    metrics.record_capture(0.001)
    metrics.flush_if_due(force=True)
    metrics.close()

    rows = list(csv.DictReader(metrics_path.open("r", encoding="utf-8")))
    assert rows[0]["cpu_percent"] == ""
    assert rows[0]["rss_mb"] == ""
