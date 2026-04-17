from __future__ import annotations

import colorsys
import queue
import tkinter as tk
import tkinter.colorchooser as colorchooser

import customtkinter as ctk

from ow_chat_logger.gui import theme as T
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


# ── Appearance mode cycling ──────────────────────────────────────────────────

_MODE_ORDER = ("system", "light", "dark")
_MODE_ICON = {"system": "◐", "light": "☀", "dark": "☾"}
_MODE_LABEL = {"system": "Auto", "light": "Light", "dark": "Dark"}


def _apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode("System" if mode == "system" else mode.capitalize())


# ── Main application window ───────────────────────────────────────────────────

class OWChatLoggerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OW Chat Logger")
        self.geometry("960x660")
        self.minsize(780, 460)

        cfg = load_ui_config()
        self._appearance_mode: str = str(cfg.get("ui_appearance_mode", "system"))
        if self._appearance_mode not in _MODE_ORDER:
            self._appearance_mode = "system"
        _apply_appearance(self._appearance_mode)

        self.configure(fg_color=T.BG_ROOT)
        self._bridge = BackendBridge()
        self._polling = False
        self._settings_window: ctk.CTkToplevel | None = None
        self._swatches: dict[str, ctk.CTkButton] = {}
        self._mode_btn: ctk.CTkButton | None = None
        self._build_ui()
        T.apply_chrome(self)
        icon = T.make_app_icon_photo()
        if icon is not None:
            self._app_icon = icon  # retain reference (Tk image registry is weak)
            self.iconphoto(True, icon)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_polling()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Pack order matters: side="bottom" must come before the expanding
        # feed, or Tk gives all remaining cavity to the expander.
        self._build_toolbar()
        self._build_bottom_bar()
        self._build_feed()

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=58, fg_color=T.BG_CHROME, corner_radius=0)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)
        toolbar.grid_columnconfigure(0, weight=0)
        toolbar.grid_columnconfigure(1, weight=1)
        toolbar.grid_columnconfigure(2, weight=0)
        toolbar.grid_rowconfigure(0, weight=1)

        # Left group: title + status chip
        left = ctk.CTkFrame(toolbar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(22, 0), pady=10)

        ctk.CTkLabel(
            left,
            text="OW Chat Logger",
            font=T.font_title(),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 14))

        chip = ctk.CTkFrame(
            left,
            fg_color=T.BG_ELEV,
            corner_radius=T.R_PILL,
        )
        chip.pack(side="left")

        self._status_dot = ctk.CTkLabel(
            chip, text="●", text_color=T.IDLE, font=ctk.CTkFont(size=10)
        )
        self._status_dot.pack(side="left", padx=(12, 6), pady=5)
        self._status_label = ctk.CTkLabel(
            chip,
            text="Idle",
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
        )
        self._status_label.pack(side="left", padx=(0, 14), pady=5)

        # Right group: pill-style action buttons (grid-pinned so they never clip)
        right = ctk.CTkFrame(toolbar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, 18), pady=13)

        self._start_btn = ctk.CTkButton(
            right,
            text="Start",
            width=72,
            height=28,
            corner_radius=14,
            font=T.font_small(),
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            right,
            text="Stop",
            width=72,
            height=28,
            corner_radius=14,
            font=T.font_small(),
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.DANGER,
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left")

    def _build_feed(self) -> None:
        self._feed_panel = FeedPanel(self)
        self._feed_panel.pack(fill="both", expand=True, padx=16, pady=(12, 8))

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=56, fg_color=T.BG_CHROME, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # Hairline top border
        ctk.CTkFrame(bar, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(
            fill="x", side="top"
        )

        # Grid shell: left / flexible spacer / right
        content = ctk.CTkFrame(bar, fg_color="transparent")
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_columnconfigure(2, weight=0)
        content.grid_rowconfigure(0, weight=1)

        # Left group: chat colors + Open Logs
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(22, 0), pady=12)

        ctk.CTkLabel(
            left,
            text="Chat colors",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        ).pack(side="left", padx=(0, 12))

        cfg = load_ui_config()
        for chat_key, label, fallback in (
            ("team", "Team", T.pick(T.CHAT_TEAM)),
            ("all", "All", T.pick(T.CHAT_ALL)),
        ):
            ctk.CTkLabel(
                left,
                text=label,
                text_color=T.TEXT_SECONDARY,
                font=T.font_caption(),
            ).pack(side="left", padx=(0, 6))

            try:
                hex_color = _hsv_bounds_to_hex(
                    cfg[f"{chat_key}_hsv_lower"], cfg[f"{chat_key}_hsv_upper"]
                )
            except Exception:
                hex_color = fallback

            swatch = ctk.CTkButton(
                left,
                text="",
                width=30,
                height=20,
                corner_radius=T.R_SWATCH,
                border_width=0,
                fg_color=hex_color,
                hover_color=hex_color,
                command=lambda k=chat_key: self._pick_color(k),
            )
            swatch.pack(side="left", padx=(0, 14))
            self._swatches[chat_key] = swatch

        ctk.CTkButton(
            left,
            text="Open Logs",
            width=96,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
            command=open_log_folder,
        ).pack(side="left")

        # Right group: appearance toggle + settings icon
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(12, 18), pady=12)

        self._mode_btn = ctk.CTkButton(
            right,
            text=self._mode_button_text(),
            width=84,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
            command=self._cycle_appearance_mode,
        )
        self._mode_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            right,
            text="⚙",
            width=32,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(size=15),
            command=self._open_settings_modal,
        ).pack(side="left")

    # ── Color picker ──────────────────────────────────────────────────────────

    def _pick_color(self, chat_key: str) -> None:
        current_hex = self._swatches[chat_key].cget("fg_color")
        if isinstance(current_hex, (list, tuple)):
            current_hex = current_hex[0]
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

    # ── Appearance mode ───────────────────────────────────────────────────────

    def _mode_button_text(self) -> str:
        icon = _MODE_ICON[self._appearance_mode]
        label = _MODE_LABEL[self._appearance_mode]
        return f"{icon}  {label}"

    def _cycle_appearance_mode(self) -> None:
        idx = _MODE_ORDER.index(self._appearance_mode)
        self._appearance_mode = _MODE_ORDER[(idx + 1) % len(_MODE_ORDER)]
        _apply_appearance(self._appearance_mode)
        save_ui_config({"ui_appearance_mode": self._appearance_mode})
        if self._mode_btn is not None:
            self._mode_btn.configure(text=self._mode_button_text())
        # Re-apply Mica + retint titlebar to new mode
        T.apply_chrome(self)
        if self._settings_window is not None and self._settings_window.winfo_exists():
            T.apply_chrome(self._settings_window)

    # ── Settings modal ────────────────────────────────────────────────────────

    def _open_settings_modal(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus()
            return

        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("500x620")
        win.minsize(440, 440)
        win.configure(fg_color=T.BG_ROOT)
        win.transient(self)
        T.apply_chrome(win)

        header = ctk.CTkFrame(win, height=58, fg_color=T.BG_CHROME, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="Settings",
            font=T.font_title(),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=22, pady=10)
        ctk.CTkFrame(win, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(
            fill="x"
        )

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
            self._set_status("running", "Running")
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
        elif event.kind == "stopped":
            self._set_status("idle", "Idle")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
        elif event.kind == "error":
            self._set_status("error", "Error")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")

    def _set_status(self, kind: str, text: str) -> None:
        color_map = {
            "running": T.SUCCESS,
            "starting": T.WARNING,
            "stopping": T.WARNING,
            "error": T.DANGER,
            "idle": T.IDLE,
        }
        color = color_map.get(kind, T.TEXT_MUTED)
        self._status_dot.configure(text_color=color)
        label_color = T.TEXT_SECONDARY if kind == "idle" else color
        self._status_label.configure(text=text, text_color=label_color)


def run_gui() -> int:
    ctk.set_default_color_theme("blue")
    app = OWChatLoggerApp()
    app.mainloop()
    return 0
