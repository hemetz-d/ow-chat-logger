from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import CONFIG, get_app_paths, reset_config, resolve_ocr_profile
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.live_runtime import (
    LatestFrameQueue,
    capture_worker,
    close_loggers,
    processing_worker,
)
from ow_chat_logger.logger import MessageLogger
from ow_chat_logger.message_processing import flush_buffers
from ow_chat_logger.ocr import build_ocr_backend


@dataclass
class FeedEntry:
    timestamp: str
    category: str  # "standard" | "hero"
    chat_type: str  # "team" | "all" | ""
    player: str
    text: str


@dataclass
class StatusEvent:
    kind: str  # "started" | "stopped" | "error" | "info"
    message: str


class GUIAwareMessageLogger(MessageLogger):
    def __init__(self, *args: Any, gui_queue: queue.Queue | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._gui_queue = gui_queue

    def log(self, timestamp: str, player: str, text: str, chat_type: str | None = None) -> None:
        super().log(timestamp, player, text, chat_type)
        if self._gui_queue is None:
            return
        entry = FeedEntry(
            timestamp=timestamp,
            category="hero" if self.print_mode == "hero" else "standard",
            chat_type=chat_type or "",
            player=player,
            text=text,
        )
        try:
            self._gui_queue.put_nowait(entry)
        except queue.Full:
            pass


class BackendBridge:
    def __init__(self) -> None:
        self.message_queue: queue.Queue[FeedEntry] = queue.Queue(maxsize=500)
        self.status_queue: queue.Queue[StatusEvent] = queue.Queue(maxsize=50)
        self._stop_event: threading.Event | None = None
        self._capture_thread: threading.Thread | None = None
        self._processing_thread: threading.Thread | None = None
        self._chat_logger: GUIAwareMessageLogger | None = None
        self._hero_logger: GUIAwareMessageLogger | None = None
        self._team_buffer: MessageBuffer | None = None
        self._all_buffer: MessageBuffer | None = None
        self._chat_dedup: DuplicateFilter | None = None
        self._hero_dedup: DuplicateFilter | None = None
        self._error_queue: queue.Queue = queue.Queue()
        self._frame_queue: LatestFrameQueue | None = None
        self._reload_event: threading.Event | None = None
        self._reload_notice: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=10)
        self._cleanup_lock = threading.Lock()
        self._cleanup_started = False

    def is_running(self) -> bool:
        return self._stop_event is not None and not self._stop_event.is_set()

    def start(self, ocr_profile_override: str | None = None) -> None:
        if self.is_running():
            return

        self._cleanup_started = False

        try:
            profile = resolve_ocr_profile(dict(CONFIG), ocr_profile_override)
            ocr = build_ocr_backend(profile)
        except Exception as exc:
            self.status_queue.put(StatusEvent("error", str(exc)))
            return

        paths = get_app_paths()
        self._chat_logger = GUIAwareMessageLogger(
            str(paths.chat_log),
            print_messages=False,
            gui_queue=self.message_queue,
        )
        self._hero_logger = GUIAwareMessageLogger(
            str(paths.hero_log),
            print_messages=False,
            print_mode="hero",
            include_chat_type=False,
            gui_queue=self.message_queue,
        )
        self._team_buffer = MessageBuffer()
        self._all_buffer = MessageBuffer()
        self._chat_dedup = DuplicateFilter(CONFIG["max_remembered"])
        self._hero_dedup = DuplicateFilter(CONFIG["max_remembered"])
        self._stop_event = threading.Event()
        self._error_queue = queue.Queue()
        self._frame_queue = LatestFrameQueue()
        self._reload_event = threading.Event()

        self._capture_thread = threading.Thread(
            target=capture_worker,
            args=(self._frame_queue, self._stop_event, self._error_queue),
            name="gui-capture",
            daemon=True,
        )
        self._processing_thread = threading.Thread(
            target=processing_worker,
            args=(self._frame_queue, self._stop_event, self._error_queue),
            kwargs={
                "ocr": ocr,
                "ocr_profile": profile,
                "team_buffer": self._team_buffer,
                "all_buffer": self._all_buffer,
                "chat_dedup": self._chat_dedup,
                "hero_dedup": self._hero_dedup,
                "chat_logger": self._chat_logger,
                "hero_logger": self._hero_logger,
                "reload_event": self._reload_event,
                "reload_notice": self._reload_notice,
            },
            name="gui-processing",
            daemon=True,
        )
        self._capture_thread.start()
        self._processing_thread.start()
        self.status_queue.put(StatusEvent("started", f"Logging — profile: {profile.name}"))

    def reload_config(self) -> None:
        """Invalidate the config cache and signal the live pipeline to re-resolve.

        Safe to call when no session is running — becomes a no-op after the cache reset.
        """
        reset_config()
        if self._reload_event is not None and self.is_running():
            self._reload_event.set()

    def drain_reload_notice(self) -> StatusEvent | None:
        try:
            kind, message = self._reload_notice.get_nowait()
        except queue.Empty:
            return None
        return StatusEvent(kind=kind, message=message)

    def stop(self) -> None:
        if self._stop_event is None:
            return
        self._stop_event.set()
        with self._cleanup_lock:
            if self._cleanup_started:
                return
            self._cleanup_started = True
        cleanup = threading.Thread(target=self._cleanup, daemon=True, name="gui-cleanup")
        cleanup.start()

    def drain_error(self) -> Exception | None:
        try:
            exc = self._error_queue.get_nowait()
            # Threads stopped themselves — trigger cleanup if not already running
            if self._stop_event is not None:
                self._stop_event.set()
                with self._cleanup_lock:
                    if not self._cleanup_started:
                        self._cleanup_started = True
                        cleanup = threading.Thread(
                            target=self._cleanup, daemon=True, name="gui-error-cleanup"
                        )
                        cleanup.start()
            return exc
        except queue.Empty:
            return None

    def _cleanup(self) -> None:
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)

        if self._team_buffer and self._all_buffer:
            flush_buffers(
                self._team_buffer,
                self._all_buffer,
                chat_dedup=self._chat_dedup,
                hero_dedup=self._hero_dedup,
                chat_logger=self._chat_logger,
                hero_logger=self._hero_logger,
            )

        if self._chat_logger:
            self._chat_logger.flush()
        if self._hero_logger:
            self._hero_logger.flush()
        close_loggers(
            *([self._chat_logger] if self._chat_logger else []),
            *([self._hero_logger] if self._hero_logger else []),
        )
        self.status_queue.put(StatusEvent("stopped", "Logging stopped."))
