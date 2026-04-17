from __future__ import annotations

import queue

import customtkinter as ctk

from ow_chat_logger.gui.backend_bridge import BackendBridge, StatusEvent
from ow_chat_logger.gui.feed_panel import FeedPanel
from ow_chat_logger.gui.settings_panel import SettingsPanel


class OWChatLoggerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OW Chat Logger")
        self.geometry("1080x700")
        self.minsize(760, 500)
        self.configure(fg_color="#1a1a2e")
        self._bridge = BackendBridge()
        self._polling = False
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_polling()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_toolbar()
        self._build_content()

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=52, fg_color="#16213e", corner_radius=0)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        ctk.CTkLabel(
            toolbar,
            text="OW Chat Logger",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#5BC8F5",
        ).pack(side="left", padx=16, pady=10)

        self._status_dot = ctk.CTkLabel(
            toolbar, text="●", text_color="#555555", font=ctk.CTkFont(size=16)
        )
        self._status_dot.pack(side="left", padx=(12, 4))
        self._status_label = ctk.CTkLabel(
            toolbar, text="Idle", text_color="#888888", font=ctk.CTkFont(size=12)
        )
        self._status_label.pack(side="left", padx=(0, 16))

        self._stop_btn = ctk.CTkButton(
            toolbar,
            text="Stop",
            width=88,
            height=34,
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="right", padx=(4, 16), pady=9)

        self._start_btn = ctk.CTkButton(
            toolbar,
            text="Start",
            width=88,
            height=34,
            fg_color="#28a745",
            hover_color="#218838",
            command=self._on_start,
        )
        self._start_btn.pack(side="right", padx=4, pady=9)

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=8)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        self._feed_panel = FeedPanel(content)
        self._feed_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self._settings_panel = SettingsPanel(content)
        self._settings_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_start(self) -> None:
        from ow_chat_logger.config import reset_config

        reset_config()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")
        self._set_status("starting", "Starting…")
        self._bridge.start()

    def _on_stop(self) -> None:
        self._stop_btn.configure(state="disabled")
        self._set_status("stopping", "Stopping…")
        self._bridge.stop()

    def _on_close(self) -> None:
        self._polling = False
        self.withdraw()
        self._bridge.stop()
        self.after(600, self.destroy)

    # ── Polling loop ──────────────────────────────────────────────────────────

    def _start_polling(self) -> None:
        self._polling = True
        self._poll()

    def _poll(self) -> None:
        if not self._polling:
            return

        # Drain message feed
        try:
            while True:
                entry = self._bridge.message_queue.get_nowait()
                self._feed_panel.append_message(entry)
        except queue.Empty:
            pass

        # Drain status events
        try:
            while True:
                event = self._bridge.status_queue.get_nowait()
                self._apply_status_event(event)
        except queue.Empty:
            pass

        # Check for worker errors
        exc = self._bridge.drain_error()
        if exc:
            self._apply_status_event(StatusEvent("error", str(exc)))

        self.after(100, self._poll)

    # ── Status helpers ────────────────────────────────────────────────────────

    def _apply_status_event(self, event: StatusEvent) -> None:
        if event.kind == "started":
            self._set_status("running", event.message)
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
        elif event.kind == "stopped":
            self._set_status("idle", "Stopped")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
        elif event.kind == "error":
            msg = event.message[:70] + ("…" if len(event.message) > 70 else "")
            self._set_status("error", f"Error: {msg}")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")

    def _set_status(self, kind: str, text: str) -> None:
        colors = {
            "running": "#28a745",
            "starting": "#f0ad4e",
            "stopping": "#f0ad4e",
            "error": "#dc3545",
            "idle": "#555555",
        }
        color = colors.get(kind, "#888888")
        self._status_dot.configure(text_color=color)
        self._status_label.configure(text=text, text_color=color)


def run_gui() -> int:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = OWChatLoggerApp()
    app.mainloop()
    return 0
