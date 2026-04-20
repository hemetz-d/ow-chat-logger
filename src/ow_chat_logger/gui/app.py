from __future__ import annotations

import math
import queue
import time
import tkinter.colorchooser as colorchooser

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.backend_bridge import BackendBridge, StatusEvent
from ow_chat_logger.gui.color_utils import hex_to_hsv_bounds, hsv_bounds_to_hex
from ow_chat_logger.gui.config_io import (
    load_ui_config,
    open_log_folder,
    save_ui_config,
)
from ow_chat_logger.gui.main_tabs import MainTabs
from ow_chat_logger.gui.settings_panel import SettingsPanel

# ── Appearance mode cycling ──────────────────────────────────────────────────

_MODE_ORDER = ("system", "light", "dark")
_MODE_ICON_NAME = {"system": "auto", "light": "sun", "dark": "moon"}
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
        self._status_kind: str = "idle"
        self._pulse_job: str | None = None
        self._stats_job: str | None = None
        self._session_start: float | None = None
        self._message_count: int = 0
        self._build_ui()
        T.apply_chrome(self)
        icon = T.make_app_icon_photo()
        if icon is not None:
            self._app_icon = icon  # retain reference (Tk image registry is weak)
            self.iconphoto(True, icon)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-f>", lambda _e: self._tabs.show_search())
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

        # Session stats chip — hidden until the logger starts
        self._stats_chip = ctk.CTkFrame(
            left,
            fg_color=T.ACCENT_SUBTLE,
            corner_radius=T.R_PILL,
        )
        self._stats_label = ctk.CTkLabel(
            self._stats_chip,
            text="",
            text_color=T.ACCENT,
            font=T.font_caption(),
        )
        self._stats_label.pack(side="left", padx=12, pady=5)

        # Right group: pill-style action buttons (grid-pinned so they never clip)
        right = ctk.CTkFrame(toolbar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, 18), pady=13)

        # Start button with a fake-glow frame behind it when idle
        start_wrap = ctk.CTkFrame(right, fg_color="transparent")
        start_wrap.pack(side="left", padx=(0, 6))
        self._start_glow = ctk.CTkFrame(
            start_wrap,
            width=80,
            height=36,
            corner_radius=18,
            fg_color=T.ACCENT_SUBTLE,
            border_width=0,
        )
        self._start_glow.place(relx=0.5, rely=0.5, anchor="center")
        self._start_btn = ctk.CTkButton(
            start_wrap,
            text="Start",
            image=I.icon("play", 12, color=T.ACCENT_FG),
            compound="left",
            width=72,
            height=28,
            corner_radius=14,
            font=T.font_small(),
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            command=self._on_start,
        )
        self._start_btn.pack(padx=4, pady=4)

        self._stop_btn = ctk.CTkButton(
            right,
            text="Stop",
            image=I.icon("stop", 12, color=T.DANGER),
            compound="left",
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
        from ow_chat_logger.config import get_app_paths

        paths = get_app_paths()
        self._tabs = MainTabs(
            self,
            chat_log_path=paths.chat_log,
            hero_log_path=paths.hero_log,
            on_player_click=lambda name: self._tabs.show_search(player=name),
        )
        self._tabs.pack(fill="both", expand=True, padx=16, pady=(12, 8))
        # Expose the feed for message polling (unchanged call sites below).
        self._feed_panel = self._tabs.feed_panel

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
                hex_color = hsv_bounds_to_hex(
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
            text=_MODE_LABEL[self._appearance_mode],
            image=I.icon(_MODE_ICON_NAME[self._appearance_mode], 14),
            compound="left",
            width=92,
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
            text="",
            image=I.icon("gear", 18),
            width=32,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
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
        lower, upper = hex_to_hsv_bounds(hex_color)
        save_ui_config(
            {
                f"{chat_key}_hsv_lower": lower,
                f"{chat_key}_hsv_upper": upper,
            }
        )
        self._bridge.reload_config()
        self._swatches[chat_key].configure(fg_color=hex_color, hover_color=hex_color)
        self._feed_panel.refresh_chat_colors()

    def _refresh_swatches(self) -> None:
        """Recompute swatch colors from saved config (called after settings modal save)."""
        self._bridge.reload_config()
        cfg = load_ui_config()
        for chat_key in ("team", "all"):
            try:
                hex_color = hsv_bounds_to_hex(
                    cfg[f"{chat_key}_hsv_lower"], cfg[f"{chat_key}_hsv_upper"]
                )
                self._swatches[chat_key].configure(fg_color=hex_color, hover_color=hex_color)
            except Exception:
                pass
        self._feed_panel.refresh_chat_colors()

    # ── Appearance mode ───────────────────────────────────────────────────────

    def _cycle_appearance_mode(self) -> None:
        idx = _MODE_ORDER.index(self._appearance_mode)
        self._appearance_mode = _MODE_ORDER[(idx + 1) % len(_MODE_ORDER)]
        _apply_appearance(self._appearance_mode)
        save_ui_config({"ui_appearance_mode": self._appearance_mode})
        if self._mode_btn is not None:
            self._mode_btn.configure(
                text=_MODE_LABEL[self._appearance_mode],
                image=I.icon(_MODE_ICON_NAME[self._appearance_mode], 14),
            )
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
        ctk.CTkFrame(win, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(fill="x")

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
        self._stop_pulse()
        self._stop_stats_timer()
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
                entry = self._bridge.message_queue.get_nowait()
                self._feed_panel.append_message(entry)
                self._message_count += 1
        except queue.Empty:
            pass

        try:
            while True:
                self._apply_status_event(self._bridge.status_queue.get_nowait())
        except queue.Empty:
            pass

        while True:
            notice = self._bridge.drain_reload_notice()
            if notice is None:
                break
            self._apply_status_event(notice)

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
            self._session_start = time.monotonic()
            self._message_count = 0
            self._show_stats_chip()
            self._start_stats_timer()
        elif event.kind == "stopped":
            self._set_status("idle", "Idle")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._stop_stats_timer()
            self._hide_stats_chip()
        elif event.kind == "error":
            self._set_status("error", "Error")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._stop_stats_timer()
            self._hide_stats_chip()

    def _set_status(self, kind: str, text: str) -> None:
        color_map = {
            "running": T.SUCCESS,
            "starting": T.WARNING,
            "stopping": T.WARNING,
            "error": T.DANGER,
            "idle": T.IDLE,
        }
        color = color_map.get(kind, T.TEXT_MUTED)
        self._status_kind = kind
        self._status_dot.configure(text_color=color)
        label_color = T.TEXT_SECONDARY if kind == "idle" else color
        self._status_label.configure(text=text, text_color=label_color)

        # Start-button glow only when idle (CTA mode)
        if hasattr(self, "_start_glow"):
            if kind == "idle":
                self._start_glow.place(relx=0.5, rely=0.5, anchor="center")
            else:
                self._start_glow.place_forget()

        # Pulse the dot only while running
        if kind == "running":
            self._start_pulse()
        else:
            self._stop_pulse()

    # ── Pulse animation ───────────────────────────────────────────────────────

    def _start_pulse(self) -> None:
        self._stop_pulse()
        self._pulse_step(0)

    def _stop_pulse(self) -> None:
        if self._pulse_job is not None:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        if self._status_kind == "running":
            self._status_dot.configure(text_color=T.SUCCESS)

    def _pulse_step(self, tick: int) -> None:
        # ~1.2s period at 80ms ticks → 15 steps per cycle
        phase = (math.sin(tick * 2 * math.pi / 15) + 1) / 2  # 0..1

        # Interpolate between SUCCESS and a dimmed variant
        def _dim(hex_color: str, amount: float) -> str:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r = int(r * (1 - amount) + 255 * amount * 0.25)
            g = int(g * (1 - amount) + 255 * amount * 0.25)
            b = int(b * (1 - amount) + 255 * amount * 0.25)
            return f"#{r:02x}{g:02x}{b:02x}"

        dim_amount = 0.45 * (1 - phase)
        color = (
            _dim(T.SUCCESS[0], dim_amount),
            _dim(T.SUCCESS[1], dim_amount),
        )
        self._status_dot.configure(text_color=color)
        self._pulse_job = self.after(80, self._pulse_step, tick + 1)

    # ── Session stats chip ────────────────────────────────────────────────────

    def _show_stats_chip(self) -> None:
        self._stats_chip.pack(side="left", padx=(8, 0))

    def _hide_stats_chip(self) -> None:
        self._stats_chip.pack_forget()

    def _start_stats_timer(self) -> None:
        self._stop_stats_timer()
        self._stats_tick()

    def _stop_stats_timer(self) -> None:
        if self._stats_job is not None:
            try:
                self.after_cancel(self._stats_job)
            except Exception:
                pass
            self._stats_job = None

    def _stats_tick(self) -> None:
        if self._session_start is None:
            return
        elapsed = int(time.monotonic() - self._session_start)
        mm, ss = divmod(elapsed, 60)
        hh, mm = divmod(mm, 60)
        clock = f"{hh:d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
        plural = "s" if self._message_count != 1 else ""
        self._stats_label.configure(text=f"{clock} · {self._message_count} msg{plural}")
        self._stats_job = self.after(1000, self._stats_tick)


def run_gui() -> int:
    ctk.set_default_color_theme("blue")
    app = OWChatLoggerApp()
    app.mainloop()
    return 0
