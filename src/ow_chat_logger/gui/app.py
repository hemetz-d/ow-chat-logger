from __future__ import annotations

import math
import queue
import time

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.backend_bridge import BackendBridge, StatusEvent
from ow_chat_logger.gui.config_io import (
    load_ui_config,
    save_ui_config,
)
from ow_chat_logger.gui.main_tabs import MainTabs

# ── Appearance mode cycling ──────────────────────────────────────────────────

_MODE_ORDER = ("system", "light", "dark")
_MODE_ICON_NAME = {"system": "auto", "light": "sun", "dark": "moon"}
_MODE_LABEL = {"system": "Auto", "light": "Light", "dark": "Dark"}


def _apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode("System" if mode == "system" else mode.capitalize())


def _statusbar_sep(parent) -> None:
    """Subtle '·' separator used between groups in the status bar."""
    ctk.CTkLabel(
        parent,
        text="·",
        text_color=T.TEXT_DIM,
        font=T.font_caption(),
    ).pack(side="left", padx=(0, 18))


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

        # Apply the saved accent BEFORE building any widgets — most widgets
        # capture references to T.ACCENT* lists at construction, and we want
        # them to start with the correct values.
        accent_name = str(cfg.get("ui_accent", "blue"))
        T.set_accent(accent_name)

        # Push the accent-tinted .ico to the OS as early as possible so the
        # title bar starts in the right color. Done here — before
        # ``_build_ui`` does its heavy widget construction — so the window's
        # first paint already carries the correct icon. We deliberately do
        # NOT use a withdraw/deiconify pair: on some Tk + Python 3.14 builds
        # that combination has been observed to leave the window hidden,
        # which is a much worse failure mode than a brief icon flicker.
        self._refresh_app_icon()

        self.configure(fg_color=T.BG_ROOT)
        self._bridge = BackendBridge()
        self._polling = False
        self._mode_btn: ctk.CTkButton | None = None
        self._status_kind: str = "idle"
        self._pulse_job: str | None = None
        self._stats_job: str | None = None
        self._session_start: float | None = None
        self._message_count: int = 0
        self._build_ui()
        T.apply_chrome(self)
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
        toolbar = ctk.CTkFrame(self, height=64, fg_color=T.BG_CHROME, corner_radius=0)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)
        # Hairline divider below the toolbar — packed in the main window so it
        # doesn't mix pack and grid inside the toolbar frame.
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(
            fill="x", side="top"
        )
        toolbar.grid_columnconfigure(0, weight=0)
        toolbar.grid_columnconfigure(1, weight=1)
        toolbar.grid_columnconfigure(2, weight=0)
        toolbar.grid_rowconfigure(0, weight=1)

        # Left group: logo + title + recording chip
        left = ctk.CTkFrame(toolbar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(22, 0), pady=10)

        logo = T.make_toolbar_logo_photo()
        self._logo_label: ctk.CTkLabel | None = None
        if logo is not None:
            self._toolbar_logo = logo  # retain reference (Tk image registry is weak)
            self._logo_label = ctk.CTkLabel(left, text="", image=logo)
            self._logo_label.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            left,
            text="OW Chat Logger",
            font=ctk.CTkFont(family=T.ui_family(), size=14, weight="bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 14))

        # Recording chip: accent-tinted pill with dot + label + mono timer.
        chip = ctk.CTkFrame(
            left,
            fg_color=T.ACCENT_SUBTLE,
            border_color=T.ACCENT_SUBTLE,
            border_width=1,
            corner_radius=T.R_PILL,
        )
        chip.pack(side="left")

        self._status_dot = ctk.CTkLabel(
            chip, text="●", text_color=T.IDLE, font=ctk.CTkFont(size=10)
        )
        self._status_dot.pack(side="left", padx=(12, 6), pady=4)
        self._status_label = ctk.CTkLabel(
            chip,
            text="Idle",
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
        )
        self._status_label.pack(side="left", padx=(0, 10), pady=4)

        # Mono timer — only visible during a session. Tucked inside the same chip.
        self._status_timer = ctk.CTkLabel(
            chip,
            text="",
            text_color=T.TEXT_SECONDARY,
            font=ctk.CTkFont(family=T.mono_family(), size=11),
        )
        # Not packed yet — appears when the timer starts.

        # Session message-count chip — hidden until the logger starts.
        self._stats_chip = ctk.CTkFrame(
            left,
            fg_color="transparent",
            corner_radius=T.R_PILL,
        )
        self._stats_label = ctk.CTkLabel(
            self._stats_chip,
            text="",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        )
        self._stats_label.pack(side="left", padx=10, pady=4)

        # Middle group: view-switcher segmented control (Live / Search).
        # Placeholder for now — populated after MainTabs exists, since the
        # click handlers call into it.
        self._toolbar_views = ctk.CTkFrame(toolbar, fg_color="transparent")
        self._toolbar_views.grid(row=0, column=1, sticky="", pady=10)

        # Right group: Stop + Start — boxy 32h / 7-radius per the design.
        right = ctk.CTkFrame(toolbar, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, 18), pady=10)

        self._stop_btn = ctk.CTkButton(
            right,
            text="Stop",
            image=I.icon("stop", 10, color=T.DANGER),
            compound="left",
            width=78,
            height=32,
            corner_radius=7,
            font=T.font_small(),
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_SECONDARY,
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(0, 8))

        self._start_btn = ctk.CTkButton(
            right,
            text="Start",
            image=I.icon("play", 10, color=T.ACCENT_FG),
            compound="left",
            width=86,
            height=32,
            corner_radius=7,
            font=ctk.CTkFont(family=T.ui_family(), size=12, weight="bold"),
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            command=self._on_start,
        )
        self._start_btn.pack(side="left")

    def _build_feed(self) -> None:
        from ow_chat_logger.config import get_app_paths

        paths = get_app_paths()
        self._tabs = MainTabs(
            self,
            chat_log_path=paths.chat_log,
            hero_log_path=paths.hero_log,
            # Side panel's "Search" button — jumps to the Search tab focused
            # on that player. Row/player click now opens the side panel in
            # place instead of navigating away.
            on_open_in_search=lambda name: self._tabs.show_search(player=name),
            on_settings_saved=self._on_settings_saved,
            on_accent_change=self.apply_accent,
            current_accent=T.current_accent_name(),
            # Onboarding empty-state Start button shares the toolbar's flow.
            on_start=self._on_start,
            inline_tab_bar=False,  # tabs live in the toolbar instead
        )
        # Flush to the window edges — matches the Console direction's
        # edge-to-edge feed with hairline separators.
        self._tabs.pack(fill="both", expand=True)
        # Expose the feed for message polling (unchanged call sites below).
        self._feed_panel = self._tabs.feed_panel

        # Now that MainTabs exists, populate the toolbar's segmented control.
        self._build_toolbar_view_switcher()
        self._tabs.add_tab_change_listener(self._on_tabs_changed_externally)

    def _build_bottom_bar(self) -> None:
        # Console status bar — compact 32px, session stats on the left,
        # secondary text-buttons on the right.
        bar = ctk.CTkFrame(self, height=36, fg_color=T.BG_CHROME, corner_radius=0)
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

        # Left group: live indicator + session stats (Region · Interval · OCR)
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(24, 0), pady=4)

        # Live/idle indicator — mirrors the Console status bar's leading dot.
        self._statusbar_dot = ctk.CTkLabel(
            left,
            text="●",
            text_color=T.IDLE,
            font=ctk.CTkFont(size=10),
        )
        self._statusbar_dot.pack(side="left", padx=(0, 7))
        self._statusbar_label = ctk.CTkLabel(
            left,
            text="Idle",
            text_color=T.TEXT_PRIMARY,
            font=T.font_caption(),
        )
        # Keep the "Idle/Live" word visually grouped with its dot; the
        # session-stats group starts after a separator below.
        self._statusbar_label.pack(side="left", padx=(0, 18))

        # Session stats — derived from saved config. Updated on settings save.
        stats = self._format_statusbar_stats()
        self._statusbar_stats_labels: list[ctk.CTkLabel] = []
        for i, text in enumerate(stats):
            if i > 0:
                _statusbar_sep(left)
            lbl = ctk.CTkLabel(
                left,
                text=text,
                text_color=T.TEXT_MUTED,
                font=T.font_caption(),
            )
            lbl.pack(side="left")
            self._statusbar_stats_labels.append(lbl)

        # Right group: appearance toggle + settings icon (subtle text-style)
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(12, 22), pady=4)

        self._mode_btn = ctk.CTkButton(
            right,
            text=_MODE_LABEL[self._appearance_mode],
            image=I.icon(_MODE_ICON_NAME[self._appearance_mode], 12, color=T.TEXT_SECONDARY),
            compound="left",
            width=0,
            height=24,
            corner_radius=6,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
            command=self._cycle_appearance_mode,
        )
        self._mode_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            right,
            text="Settings",
            image=I.icon("gear", 12, color=T.TEXT_SECONDARY),
            compound="left",
            width=0,
            height=24,
            corner_radius=6,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
            command=lambda: self._tabs.show_settings(),
        ).pack(side="left")

    # ── Status-bar session stats ─────────────────────────────────────────────

    def _format_statusbar_stats(self) -> list[str]:
        """Read the saved config and format Region / Interval / OCR strings."""
        cfg = load_ui_config()
        out: list[str] = []
        region = cfg.get("screen_region")
        if isinstance(region, (list, tuple)) and len(region) == 4:
            # screen_region is [left, top, width, height] — show W×H.
            try:
                out.append(f"Region {int(region[2])}×{int(region[3])}")
            except (TypeError, ValueError):
                pass
        interval = cfg.get("capture_interval")
        if isinstance(interval, (int, float)):
            out.append(f"Interval {float(interval):.1f}s")
        ocr_profile = cfg.get("ocr_default_profile") or cfg.get("ocr_profile")
        if isinstance(ocr_profile, str) and ocr_profile:
            # Shorten "windows_default" → "Windows" for a compact pill.
            pretty = ocr_profile.split("_", 1)[0].capitalize()
            out.append(f"OCR {pretty}")
        if not out:
            out.append("Ready")
        return out

    def _refresh_statusbar_stats(self) -> None:
        """Rebuild the left-side stats labels after config changes."""
        if not hasattr(self, "_statusbar_stats_labels"):
            return
        new_stats = self._format_statusbar_stats()
        # Only touch text — layout is already in place.
        for lbl, text in zip(self._statusbar_stats_labels, new_stats):
            lbl.configure(text=text)

    # ── Toolbar view-switcher (segmented control) ────────────────────────────

    def _build_toolbar_view_switcher(self) -> None:
        labels = (MainTabs.TAB_FEED, MainTabs.TAB_SEARCH, MainTabs.TAB_SETTINGS)
        icons = {
            MainTabs.TAB_FEED: "message_square",
            MainTabs.TAB_SEARCH: "search",
            MainTabs.TAB_SETTINGS: "gear",
        }

        tray = ctk.CTkFrame(
            self._toolbar_views,
            fg_color=T.BG_ELEV,
            border_color=T.BORDER_HAIRLINE,
            border_width=1,
            corner_radius=T.R_BUTTON,
        )
        tray.pack()

        self._toolbar_tab_buttons: dict[str, ctk.CTkButton] = {}
        for col, label in enumerate(labels):
            btn = ctk.CTkButton(
                tray,
                text=label,
                image=I.icon(icons[label], 14, color=T.TEXT_MUTED),
                compound="left",
                width=98,
                height=28,
                corner_radius=T.R_BADGE,
                font=T.font_small(),
                fg_color="transparent",
                hover_color=T.BG_CARD,
                text_color=T.TEXT_MUTED,
                command=lambda lbl=label: self._on_toolbar_tab_click(lbl),
            )
            btn.grid(row=0, column=col, padx=3, pady=3)
            self._toolbar_tab_buttons[label] = btn
        self._apply_toolbar_tab_styles()

    def _apply_toolbar_tab_styles(self) -> None:
        active = self._tabs.active_tab
        icons = {
            MainTabs.TAB_FEED: "message_square",
            MainTabs.TAB_SEARCH: "search",
            MainTabs.TAB_SETTINGS: "gear",
        }
        for label, btn in self._toolbar_tab_buttons.items():
            if label == active:
                btn.configure(
                    fg_color=T.BG_CARD,
                    hover_color=T.BG_CARD,
                    text_color=T.TEXT_PRIMARY,
                    image=I.icon(icons[label], 14, color=T.pick(T.TEXT_PRIMARY)),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color=T.BG_CARD,
                    text_color=T.TEXT_MUTED,
                    image=I.icon(icons[label], 14, color=T.pick(T.TEXT_MUTED)),
                )

    def _on_toolbar_tab_click(self, label: str) -> None:
        if label == MainTabs.TAB_FEED:
            self._tabs.show_feed()
        elif label == MainTabs.TAB_SEARCH:
            self._tabs.show_search()
        else:
            self._tabs.show_settings()
        self._apply_toolbar_tab_styles()

    def _on_tabs_changed_externally(self, _label: str) -> None:
        # Keeps the toolbar segmented control in sync when something else
        # (e.g. a player-click → Search transition) switches tabs.
        self._apply_toolbar_tab_styles()

    # ── Settings-save hook ────────────────────────────────────────────────────

    def _on_settings_saved(self) -> None:
        """Propagate a settings save into live UI surfaces.

        Triggered by the Settings modal's ``on_save``. Chat colors and capture
        params are configured there (the bottom bar no longer hosts swatches);
        this refreshes every UI element that depends on them — including the
        onboarding side panel which mirrors Region/Interval/colors.
        """
        self._bridge.reload_config()
        self._feed_panel.refresh_chat_colors()
        self._refresh_statusbar_stats()
        if hasattr(self._feed_panel, "_onboarding_panel"):
            try:
                self._feed_panel._onboarding_panel.refresh()
            except Exception:
                pass

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
        # Just retint the DWM titlebar — don't re-apply Mica. Re-applying the
        # backdrop visibly flashes the taskbar entry on Windows; tinting alone
        # is a cheap pywinstyles call that swaps colors in place.
        T.refresh_chrome(self)

    # ── Accent (cosmetic) ─────────────────────────────────────────────────────

    def apply_accent(self, name: str) -> None:
        """Swap the global accent palette and refresh every widget live.

        Persists the choice so the next launch starts in the same accent.
        """
        T.set_accent(name)
        save_ui_config({"ui_accent": T.current_accent_name()})

        # Regenerate the toolbar logo bitmap — it's a pre-rendered gradient
        # baked from the accent color, so it can't auto-refresh like a CTk
        # color tuple. Replace the image on the existing label so the layout
        # doesn't shift.
        if self._logo_label is not None:
            new_logo = T.make_toolbar_logo_photo()
            if new_logo is not None:
                self._toolbar_logo = new_logo
                self._logo_label.configure(image=new_logo)

        # The OS-level title-bar / taskbar icon is also a baked PNG in the
        # accent gradient — regenerate it and push it through Win32 (via
        # iconbitmap with a .ico) so the window decoration tracks the
        # chosen accent.
        self._refresh_app_icon()

        # Walk the widget tree and force every CTk widget to re-resolve its
        # color args. CTk holds references to the (light, dark) lists, which
        # we mutated in place — but it only re-reads them on a redraw cycle.
        self._refresh_widget_colors()
        # The search results widget is a raw tk.Text with Python-managed tag
        # colors — it sits outside CTk's redraw chain, so explicitly nudge it
        # to re-pick its tag colors from the (now mutated) accent palette.
        try:
            self._tabs.search_view._apply_mode_colors()
        except Exception:
            pass
        # Also push a fresh status update so the chip dot/label pick up the
        # new accent without waiting for a backend status event.
        self._set_status(self._status_kind, self._status_label.cget("text"))

    def _refresh_app_icon(self) -> None:
        """Push the current accent-tinted icon to the OS window decoration.

        On Windows, ``iconphoto`` updates Tk's stored image but the title-bar
        / taskbar HICON often stays at whatever was set first — Windows
        serves the cached one. ``iconbitmap`` with a real .ico file goes
        through ``LoadImage`` + ``WM_SETICON``, which the OS honors on every
        call. We save the PIL render to a stable temp .ico and point Tk at
        it; a try/except fallback covers non-Windows / .ico failures.
        """
        ico_path = T.save_app_icon_ico()
        if ico_path is not None:
            try:
                self.iconbitmap(str(ico_path))
                return
            except Exception:
                pass  # fall through to PhotoImage fallback below
        icon = T.make_app_icon_photo()
        if icon is not None:
            self._app_icon = icon  # retain reference (Tk's image registry is weak)
            try:
                self.iconphoto(True, icon)
            except Exception:
                pass

    def _refresh_widget_colors(self) -> None:
        """Force every CTk widget to re-read its accent color references.

        Calling ``_set_appearance_mode`` would also work but mutates global
        CTk state (``AppearanceModeBaseClass._appearance_mode``) which can
        visibly flash toplevel windows and cause focus loss on Windows. The
        cheap path is ``_draw()`` — it re-reads stored color tuples/lists
        and repaints in place, no global side-effects.
        """

        def walk(w) -> None:
            try:
                draw = getattr(w, "_draw", None)
                if callable(draw):
                    draw()
            except Exception:
                pass
            try:
                children = w.winfo_children()
            except Exception:
                return
            for c in children:
                walk(c)

        walk(self)

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
        # Toolbar "Recording" chip uses the accent color when running so the
        # whole top-bar reads as one accent-themed surface. The bottom-left
        # status bar dot stays semantic (green = live, etc.) — that's the
        # one place the user wants a green indicator.
        toolbar_color_map = {
            "running": T.ACCENT,
            "starting": T.WARNING,
            "stopping": T.WARNING,
            "error": T.DANGER,
            "idle": T.IDLE,
        }
        statusbar_color_map = {
            "running": T.SUCCESS,
            "starting": T.WARNING,
            "stopping": T.WARNING,
            "error": T.DANGER,
            "idle": T.IDLE,
        }
        toolbar_color = toolbar_color_map.get(kind, T.TEXT_MUTED)
        statusbar_color = statusbar_color_map.get(kind, T.TEXT_MUTED)

        self._status_kind = kind
        self._status_dot.configure(text_color=toolbar_color)
        label_color = T.TEXT_SECONDARY if kind == "idle" else toolbar_color
        self._status_label.configure(text=text, text_color=label_color)

        # Mirror into the bottom status bar — semantic green dot, word-form label.
        bar_label_map = {
            "running": "Live",
            "starting": "Starting",
            "stopping": "Stopping",
            "error": "Error",
            "idle": "Idle",
        }
        if hasattr(self, "_statusbar_dot"):
            self._statusbar_dot.configure(text_color=statusbar_color)
            self._statusbar_label.configure(text=bar_label_map.get(kind, text))

        # Onboarding empty-state Start button hides whenever we're not idle.
        if hasattr(self, "_feed_panel") and self._feed_panel is not None:
            try:
                self._feed_panel.set_status(kind)
            except Exception:
                pass

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
            self._status_dot.configure(text_color=T.ACCENT)

    def _pulse_step(self, tick: int) -> None:
        # ~1.2s period at 80ms ticks → 15 steps per cycle
        phase = (math.sin(tick * 2 * math.pi / 15) + 1) / 2  # 0..1

        # Interpolate between ACCENT and a dimmed variant.
        def _dim(hex_color: str, amount: float) -> str:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r = int(r * (1 - amount) + 255 * amount * 0.25)
            g = int(g * (1 - amount) + 255 * amount * 0.25)
            b = int(b * (1 - amount) + 255 * amount * 0.25)
            return f"#{r:02x}{g:02x}{b:02x}"

        dim_amount = 0.45 * (1 - phase)
        color = (
            _dim(T.ACCENT[0], dim_amount),
            _dim(T.ACCENT[1], dim_amount),
        )
        self._status_dot.configure(text_color=color)
        self._pulse_job = self.after(80, self._pulse_step, tick + 1)

    # ── Session stats chip ────────────────────────────────────────────────────

    def _show_stats_chip(self) -> None:
        self._status_timer.pack(side="left", padx=(0, 12), pady=4)
        self._stats_chip.pack(side="left", padx=(8, 0))

    def _hide_stats_chip(self) -> None:
        self._status_timer.pack_forget()
        self._status_timer.configure(text="")
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
        self._status_timer.configure(text=clock)
        plural = "s" if self._message_count != 1 else ""
        self._stats_label.configure(text=f"{self._message_count} message{plural}")
        self._stats_job = self.after(1000, self._stats_tick)


def run_gui() -> int:
    ctk.set_default_color_theme("blue")
    app = OWChatLoggerApp()
    app.mainloop()
    return 0
