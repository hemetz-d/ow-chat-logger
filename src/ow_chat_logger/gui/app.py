from __future__ import annotations

import colorsys
import queue
import tkinter as tk
import tkinter.colorchooser as colorchooser

import customtkinter as ctk

from ow_chat_logger.gui.backend_bridge import BackendBridge, StatusEvent
from ow_chat_logger.gui.config_io import (
    load_ui_config,
    open_log_folder,
    save_ui_config,
)
from ow_chat_logger.gui.feed_panel import FeedPanel
from ow_chat_logger.gui.settings_panel import SettingsPanel

# ── Color helpers (OpenCV HSV: H∈[0,180], S∈[0,255], V∈[0,255]) ─────────────

def _hsv_bounds_to_hex(lower: list[int], upper: list[int]) -> str:
    h = ((lower[0] + upper[0]) / 2) / 180.0
    s = ((lower[1] + upper[1]) / 2) / 255.0
    v = upper[2] / 255.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _hex_to_hsv_bounds(hex_color: str, hue_tol: int = 14) -> tuple[list[int], list[int]]:
    hx = hex_color.lstrip("#")
    r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h_ocv = int(h * 180)
    s_ocv = int(s * 255)
    lower = [max(0, h_ocv - hue_tol), max(0, s_ocv - 80), 50]
    upper = [min(180, h_ocv + hue_tol), 255, 255]
    return lower, upper


# ── Main application window ───────────────────────────────────────────────────

class OWChatLoggerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OW Chat Logger")
        self.geometry("900x640")
        self.minsize(600, 400)
        self.configure(fg_color="#1a1a2e")
        self._bridge = BackendBridge()
        self._polling = False
        self._settings_window: ctk.CTkToplevel | None = None
        self._swatches: dict[str, ctk.CTkButton] = {}
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_polling()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_toolbar()
        self._build_feed()
        self._build_bottom_bar()

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
        self._status_label.pack(side="left")

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

    def _build_feed(self) -> None:
        self._feed_panel = FeedPanel(self)
        self._feed_panel.pack(fill="both", expand=True, padx=0, pady=0)

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=52, fg_color="#16213e", corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # Thin separator line at top of bar
        ctk.CTkFrame(bar, height=1, fg_color="#0f3460", corner_radius=0).pack(
            fill="x", side="top"
        )

        # Color swatches
        ctk.CTkLabel(
            bar, text="Chat colors:", text_color="#888888", font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=(14, 6), pady=10)

        cfg = load_ui_config()
        for chat_key, label, fallback in (
            ("team", "Team", "#5BC8F5"),
            ("all", "All", "#FFAA00"),
        ):
            ctk.CTkLabel(
                bar, text=label, text_color="#aaaaaa", font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=(0, 4))

            try:
                hex_color = _hsv_bounds_to_hex(
                    cfg[f"{chat_key}_hsv_lower"], cfg[f"{chat_key}_hsv_upper"]
                )
            except Exception:
                hex_color = fallback

            swatch = ctk.CTkButton(
                bar,
                text="",
                width=40,
                height=26,
                corner_radius=4,
                fg_color=hex_color,
                hover_color=hex_color,
                command=lambda k=chat_key: self._pick_color(k),
            )
            swatch.pack(side="left", padx=(0, 12))
            self._swatches[chat_key] = swatch

        # Separator
        ctk.CTkFrame(bar, width=1, fg_color="#0f3460", corner_radius=0).pack(
            side="left", fill="y", padx=4, pady=10
        )

        # Log folder
        ctk.CTkButton(
            bar,
            text="Open Logs ↗",
            width=100,
            height=30,
            fg_color="#1a3a5c",
            hover_color="#1a4a8a",
            font=ctk.CTkFont(size=11),
            command=open_log_folder,
        ).pack(side="left", padx=(8, 4))

        # Settings gear — right-aligned
        ctk.CTkButton(
            bar,
            text="⚙  Settings",
            width=100,
            height=30,
            fg_color="#2a2a3e",
            hover_color="#3a3a52",
            font=ctk.CTkFont(size=11),
            command=self._open_settings_modal,
        ).pack(side="right", padx=(4, 14))

    # ── Color picker ──────────────────────────────────────────────────────────

    def _pick_color(self, chat_key: str) -> None:
        current_hex = self._swatches[chat_key].cget("fg_color")
        result = colorchooser.askcolor(
            color=current_hex,
            title=f"Choose {chat_key.title()} Chat color",
            parent=self,
        )
        if not (result and result[1]):
            return
        hex_color: str = result[1]
        lower, upper = _hex_to_hsv_bounds(hex_color)
        save_ui_config({
            f"{chat_key}_hsv_lower": lower,
            f"{chat_key}_hsv_upper": upper,
        })
        from ow_chat_logger.config import reset_config
        reset_config()
        self._swatches[chat_key].configure(fg_color=hex_color, hover_color=hex_color)

    def _refresh_swatches(self) -> None:
        """Recompute swatch colors from saved config (called after settings modal save)."""
        cfg = load_ui_config()
        for chat_key in ("team", "all"):
            try:
                hex_color = _hsv_bounds_to_hex(
                    cfg[f"{chat_key}_hsv_lower"], cfg[f"{chat_key}_hsv_upper"]
                )
                self._swatches[chat_key].configure(
                    fg_color=hex_color, hover_color=hex_color
                )
            except Exception:
                pass

    # ── Settings modal ────────────────────────────────────────────────────────

    def _open_settings_modal(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus()
            return

        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("460x580")
        win.minsize(400, 400)
        win.configure(fg_color="#1a1a2e")
        win.transient(self)

        header = ctk.CTkFrame(win, height=40, fg_color="#16213e", corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#5BC8F5",
        ).pack(side="left", padx=14, pady=8)

        panel = SettingsPanel(win, on_save=self._refresh_swatches)
        panel.pack(fill="both", expand=True)

        self._settings_window = win

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

        try:
            while True:
                self._feed_panel.append_message(self._bridge.message_queue.get_nowait())
        except queue.Empty:
            pass

        try:
            while True:
                self._apply_status_event(self._bridge.status_queue.get_nowait())
        except queue.Empty:
            pass

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
        color = {
            "running": "#28a745",
            "starting": "#f0ad4e",
            "stopping": "#f0ad4e",
            "error": "#dc3545",
            "idle": "#555555",
        }.get(kind, "#888888")
        self._status_dot.configure(text_color=color)
        self._status_label.configure(text=text, text_color=color)


def run_gui() -> int:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = OWChatLoggerApp()
    app.mainloop()
    return 0
