import csv
import json
import math
import time
from pathlib import Path
from threading import Lock

try:
    import psutil
except Exception:  # pragma: no cover - graceful runtime fallback
    psutil = None


_CSV_FIELDS = [
    "timestamp",
    "ocr_profile",
    "ocr_engine",
    "interval_seconds",
    "capture_interval_config",
    "screen_region",
    "frames_captured",
    "frames_processed",
    "frames_dropped",
    "processing_busy_seconds",
    "duty_cycle_percent",
    "capture_ms_avg",
    "capture_ms_p50",
    "capture_ms_p95",
    "preprocess_ms_avg",
    "preprocess_ms_p50",
    "preprocess_ms_p95",
    "ocr_ms_avg",
    "ocr_ms_p50",
    "ocr_ms_p95",
    "parse_ms_avg",
    "parse_ms_p50",
    "parse_ms_p95",
    "total_frame_ms_avg",
    "total_frame_ms_p50",
    "total_frame_ms_p95",
    "cpu_percent",
    "rss_mb",
    "ocr_skipped_team",
    "ocr_skipped_all",
    "ocr_skipped_total",
    "ocr_boxes_team",
    "ocr_boxes_all",
    "ocr_boxes_total",
    "lines_team",
    "lines_all",
    "lines_total",
    "chat_messages_logged",
    "hero_messages_logged",
]


def _mean_ms(samples: list[float]) -> str:
    if not samples:
        return ""
    return f"{sum(samples) * 1000.0 / len(samples):.3f}"


def _percentile_ms(samples: list[float], percentile: float) -> str:
    if not samples:
        return ""

    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return f"{ordered[index] * 1000.0:.3f}"


class PerformanceMetrics:
    """Collect low-overhead periodic runtime summaries for the live logger."""

    def __init__(
        self,
        file_path: str | Path,
        *,
        interval_seconds: float,
        capture_interval: float,
        screen_region,
        ocr_profile_name: str = "",
        ocr_engine_id: str = "",
    ) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.interval_seconds = max(float(interval_seconds), 0.1)
        self.capture_interval = float(capture_interval)
        self.screen_region = list(screen_region)
        self.ocr_profile_name = ocr_profile_name
        self.ocr_engine_id = ocr_engine_id
        self._lock = Lock()
        self._file = self.file_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=_CSV_FIELDS)
        if self.file_path.stat().st_size == 0:
            self._writer.writeheader()
            self._file.flush()

        self._process = None
        if psutil is not None:
            try:
                self._process = psutil.Process()
                self._process.cpu_percent(None)
            except Exception:
                self._process = None

        self._reset_interval(start_time=time.monotonic())

    def _reset_interval(self, *, start_time: float) -> None:
        self._interval_start = start_time
        self._capture_samples: list[float] = []
        self._preprocess_samples: list[float] = []
        self._ocr_samples: list[float] = []
        self._parse_samples: list[float] = []
        self._total_samples: list[float] = []
        self._frames_captured = 0
        self._frames_processed = 0
        self._frames_dropped = 0
        self._processing_busy_seconds = 0.0
        self._ocr_boxes_team = 0
        self._ocr_boxes_all = 0
        self._ocr_skipped_team = 0
        self._ocr_skipped_all = 0
        self._lines_team = 0
        self._lines_all = 0
        self._chat_messages_logged = 0
        self._hero_messages_logged = 0

    def record_capture(self, duration_seconds: float, *, dropped_frames: int = 0) -> None:
        with self._lock:
            self._frames_captured += 1
            self._frames_dropped += max(int(dropped_frames), 0)
            self._capture_samples.append(duration_seconds)

    def record_processed_frame(
        self,
        *,
        preprocess_seconds: float,
        ocr_seconds: float,
        parse_seconds: float,
        total_seconds: float,
        team_skipped: bool,
        all_skipped: bool,
        team_boxes: int,
        all_boxes: int,
        team_lines: int,
        all_lines: int,
        ocr_profile_name: str = "",
        ocr_engine_id: str = "",
    ) -> None:
        with self._lock:
            if ocr_profile_name:
                self.ocr_profile_name = ocr_profile_name
            if ocr_engine_id:
                self.ocr_engine_id = ocr_engine_id
            self._frames_processed += 1
            self._processing_busy_seconds += total_seconds
            self._preprocess_samples.append(preprocess_seconds)
            self._ocr_samples.append(ocr_seconds)
            self._parse_samples.append(parse_seconds)
            self._total_samples.append(total_seconds)
            self._ocr_skipped_team += int(bool(team_skipped))
            self._ocr_skipped_all += int(bool(all_skipped))
            self._ocr_boxes_team += int(team_boxes)
            self._ocr_boxes_all += int(all_boxes)
            self._lines_team += int(team_lines)
            self._lines_all += int(all_lines)

    def record_logged_message(self, category: str) -> None:
        with self._lock:
            if category == "standard":
                self._chat_messages_logged += 1
            elif category == "hero":
                self._hero_messages_logged += 1

    def flush_if_due(self, *, force: bool = False) -> bool:
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._interval_start
            has_data = any(
                [
                    self._frames_captured,
                    self._frames_processed,
                    self._frames_dropped,
                    self._chat_messages_logged,
                    self._hero_messages_logged,
                    self._capture_samples,
                    self._preprocess_samples,
                    self._ocr_samples,
                    self._parse_samples,
                    self._total_samples,
                    self._ocr_skipped_team,
                    self._ocr_skipped_all,
                ]
            )
            if not force and elapsed < self.interval_seconds:
                return False
            if not has_data:
                return False

            self._writer.writerow(self._build_row(elapsed))
            self._file.flush()
            self._reset_interval(start_time=now)
            return True

    def _build_row(self, elapsed: float) -> dict[str, str | int | float | bool]:
        cpu_percent = ""
        rss_mb = ""
        if self._process is not None:
            try:
                cpu_percent = f"{self._process.cpu_percent(None):.2f}"
                rss_mb = f"{self._process.memory_info().rss / (1024 * 1024):.2f}"
            except Exception:
                cpu_percent = ""
                rss_mb = ""

        duty_cycle = 0.0
        if elapsed > 0:
            duty_cycle = (self._processing_busy_seconds / elapsed) * 100.0

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ocr_profile": self.ocr_profile_name,
            "ocr_engine": self.ocr_engine_id,
            "interval_seconds": f"{elapsed:.3f}",
            "capture_interval_config": f"{self.capture_interval:.3f}",
            "screen_region": json.dumps(self.screen_region),
            "frames_captured": self._frames_captured,
            "frames_processed": self._frames_processed,
            "frames_dropped": self._frames_dropped,
            "processing_busy_seconds": f"{self._processing_busy_seconds:.3f}",
            "duty_cycle_percent": f"{duty_cycle:.2f}",
            "capture_ms_avg": _mean_ms(self._capture_samples),
            "capture_ms_p50": _percentile_ms(self._capture_samples, 0.50),
            "capture_ms_p95": _percentile_ms(self._capture_samples, 0.95),
            "preprocess_ms_avg": _mean_ms(self._preprocess_samples),
            "preprocess_ms_p50": _percentile_ms(self._preprocess_samples, 0.50),
            "preprocess_ms_p95": _percentile_ms(self._preprocess_samples, 0.95),
            "ocr_ms_avg": _mean_ms(self._ocr_samples),
            "ocr_ms_p50": _percentile_ms(self._ocr_samples, 0.50),
            "ocr_ms_p95": _percentile_ms(self._ocr_samples, 0.95),
            "parse_ms_avg": _mean_ms(self._parse_samples),
            "parse_ms_p50": _percentile_ms(self._parse_samples, 0.50),
            "parse_ms_p95": _percentile_ms(self._parse_samples, 0.95),
            "total_frame_ms_avg": _mean_ms(self._total_samples),
            "total_frame_ms_p50": _percentile_ms(self._total_samples, 0.50),
            "total_frame_ms_p95": _percentile_ms(self._total_samples, 0.95),
            "cpu_percent": cpu_percent,
            "rss_mb": rss_mb,
            "ocr_skipped_team": self._ocr_skipped_team,
            "ocr_skipped_all": self._ocr_skipped_all,
            "ocr_skipped_total": self._ocr_skipped_team + self._ocr_skipped_all,
            "ocr_boxes_team": self._ocr_boxes_team,
            "ocr_boxes_all": self._ocr_boxes_all,
            "ocr_boxes_total": self._ocr_boxes_team + self._ocr_boxes_all,
            "lines_team": self._lines_team,
            "lines_all": self._lines_all,
            "lines_total": self._lines_team + self._lines_all,
            "chat_messages_logged": self._chat_messages_logged,
            "hero_messages_logged": self._hero_messages_logged,
        }

    def close(self) -> None:
        self.flush_if_due(force=True)
        with self._lock:
            self._file.close()
