from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as mb
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.config_io import (
    get_available_ocr_profiles,
    load_ui_config,
    open_config_folder,
    save_ui_config,
)


class SettingsPanel(ctk.CTkScrollableFrame):
    """Technical settings panel — intended to be embedded in a modal window."""

    def __init__(
        self,
        parent: tk.Widget,
        on_save: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_ROOT,
            corner_radius=0,
            scrollbar_button_color=T.BORDER_HOVER,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self._on_save_cb = on_save
        self._hsv_vars: dict[str, list[tk.StringVar]] = {}
        self._vars: dict[str, tk.StringVar] = {}
        self._current_section: ctk.CTkFrame | None = None
        self._build()
        self.load()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _section(self, text: str) -> None:
        ctk.CTkLabel(
            self,
            text=text,
            font=T.font_section(),
            text_color=T.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=22, pady=(18, 6))
        card = ctk.CTkFrame(
            self,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        card.pack(fill="x", padx=16, pady=(0, 4))
        self._current_section = card

    def _parent(self) -> ctk.CTkFrame:
        return self._current_section if self._current_section is not None else self

    def _row(self, label: str, label_width: int = 190, first: bool = False) -> ctk.CTkFrame:
        parent = self._parent()
        # Thin divider between rows inside the same card
        if not first and isinstance(parent, ctk.CTkFrame):
            ctk.CTkFrame(
                parent, height=1, fg_color=T.BORDER_FAINT, corner_radius=0
            ).pack(fill="x", padx=16)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(
            row,
            text=label,
            width=label_width,
            anchor="w",
            text_color=T.TEXT_PRIMARY,
            font=T.font_body(),
        ).pack(side="left")
        return row

    def _entry(self, parent, var, width: int) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            textvariable=var,
            width=width,
            height=30,
            corner_radius=T.R_INPUT,
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            fg_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
        )

    def _entry_row(self, label: str, key: str, width: int = 100, first: bool = False) -> None:
        row = self._row(label, first=first)
        var = tk.StringVar()
        self._vars[key] = var
        self._entry(row, var, width).pack(side="left")

    def _hsv_row(self, label: str, key: str, first: bool = False) -> None:
        row = self._row(label, first=first)
        var_list: list[tk.StringVar] = []
        for ch in ("H", "S", "V"):
            ctk.CTkLabel(
                row,
                text=ch,
                width=14,
                text_color=T.TEXT_MUTED,
                font=T.font_caption(),
            ).pack(side="left", padx=(4, 2))
            var = tk.StringVar()
            self._entry(row, var, 52).pack(side="left", padx=(0, 4))
            var_list.append(var)
        self._hsv_vars[key] = var_list

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._section("CAPTURE")
        self._build_region_row(first=True)
        self._entry_row("Interval (s)", "capture_interval", width=80)

        self._section("OCR")
        self._build_profile_row(first=True)
        self._entry_row(
            "Confirmations required", "live_message_confirmations_required", width=60
        )
        self._entry_row("Max dedup remembered", "max_remembered", width=80)

        self._section("TEAM CHAT COLOR (HSV)")
        self._hsv_row("Lower", "team_hsv_lower", first=True)
        self._hsv_row("Upper", "team_hsv_upper")

        self._section("ALL CHAT COLOR (HSV)")
        self._hsv_row("Lower", "all_hsv_lower", first=True)
        self._hsv_row("Upper", "all_hsv_upper")

        self._build_actions()

    def _build_region_row(self, first: bool = False) -> None:
        row = self._row("Screen region", first=first)
        for lbl in ("X", "Y", "W", "H"):
            ctk.CTkLabel(
                row,
                text=lbl,
                width=14,
                text_color=T.TEXT_MUTED,
                font=T.font_caption(),
            ).pack(side="left", padx=(4, 2))
            i = ("X", "Y", "W", "H").index(lbl)
            var = tk.StringVar()
            self._vars[f"screen_region_{i}"] = var
            self._entry(row, var, 54).pack(side="left", padx=(0, 4))

    def _build_profile_row(self, first: bool = False) -> None:
        row = self._row("OCR profile", first=first)
        profiles = get_available_ocr_profiles() or ["windows_default"]
        var = tk.StringVar()
        self._vars["ocr_default_profile"] = var
        ctk.CTkOptionMenu(
            row,
            variable=var,
            values=profiles,
            width=200,
            height=30,
            corner_radius=T.R_INPUT,
            fg_color=T.BG_ELEV,
            button_color=T.BORDER_HAIRLINE,
            button_hover_color=T.BORDER_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
        ).pack(side="left")

    def _build_actions(self) -> None:
        self._current_section = None
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=22, pady=(22, 16))
        ctk.CTkButton(
            frame,
            text="Save",
            command=self.save,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            corner_radius=T.R_PILL,
            height=34,
            width=96,
            font=T.font_button(),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="Reset",
            command=self.reset,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            corner_radius=T.R_PILL,
            height=34,
            width=90,
            font=T.font_body(),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="Config folder",
            command=open_config_folder,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            corner_radius=T.R_PILL,
            height=34,
            width=120,
            font=T.font_body(),
        ).pack(side="right")

    # ── Data operations ───────────────────────────────────────────────────────

    def load(self) -> None:
        cfg = load_ui_config()

        region = cfg.get("screen_region", [80, 400, 400, 600])
        for i in range(4):
            self._vars[f"screen_region_{i}"].set(str(region[i] if i < len(region) else 0))

        self._vars["capture_interval"].set(str(cfg.get("capture_interval", 2.0)))
        self._vars["live_message_confirmations_required"].set(
            str(cfg.get("live_message_confirmations_required", 2))
        )
        self._vars["max_remembered"].set(str(cfg.get("max_remembered", 1000)))
        self._vars["ocr_default_profile"].set(cfg.get("ocr_default_profile", "windows_default"))

        for key in ("team_hsv_lower", "team_hsv_upper", "all_hsv_lower", "all_hsv_upper"):
            vals = cfg.get(key, [0, 0, 0])
            for i, var in enumerate(self._hsv_vars[key]):
                var.set(str(vals[i]) if i < len(vals) else "0")

    def reset(self) -> None:
        from ow_chat_logger.config import _DEFAULT_CONFIG

        d = _DEFAULT_CONFIG
        for i, val in enumerate(d["screen_region"]):
            self._vars[f"screen_region_{i}"].set(str(val))
        self._vars["capture_interval"].set(str(d["capture_interval"]))
        self._vars["live_message_confirmations_required"].set(
            str(d["live_message_confirmations_required"])
        )
        self._vars["max_remembered"].set(str(d["max_remembered"]))
        self._vars["ocr_default_profile"].set(d["ocr"]["default_profile"])
        for key in ("team_hsv_lower", "team_hsv_upper", "all_hsv_lower", "all_hsv_upper"):
            for i, var in enumerate(self._hsv_vars[key]):
                var.set(str(d[key][i]))

    def collect(self) -> dict | None:
        errors: list[str] = []
        data: dict = {}

        region: list[int] = []
        for i in range(4):
            raw = self._vars[f"screen_region_{i}"].get().strip()
            try:
                region.append(int(raw))
            except ValueError:
                errors.append(f"Screen region field {i + 1} must be an integer (got '{raw}')")
        if len(region) == 4:
            data["screen_region"] = region

        for key, label, cast in (
            ("capture_interval", "Capture interval", float),
            ("live_message_confirmations_required", "Confirmations required", int),
            ("max_remembered", "Max dedup", int),
        ):
            raw = self._vars[key].get().strip()
            try:
                data[key] = cast(raw)
            except ValueError:
                errors.append(f"{label} must be a number (got '{raw}')")

        data["ocr_default_profile"] = self._vars["ocr_default_profile"].get()

        for key in ("team_hsv_lower", "team_hsv_upper", "all_hsv_lower", "all_hsv_upper"):
            vals: list[int] = []
            ok = True
            for var in self._hsv_vars[key]:
                raw = var.get().strip()
                try:
                    vals.append(int(raw))
                except ValueError:
                    errors.append(f"{key} values must be integers (got '{raw}')")
                    ok = False
                    break
            if ok and len(vals) == 3:
                data[key] = vals

        if errors:
            mb.showerror("Settings Error", "\n".join(errors), parent=self.winfo_toplevel())
            return None
        return data

    def save(self) -> None:
        data = self.collect()
        if data is None:
            return
        save_ui_config(data)
        from ow_chat_logger.config import reset_config

        reset_config()
        if self._on_save_cb:
            self._on_save_cb()
        mb.showinfo(
            "Saved",
            "Settings saved.\nRestart the logger (Stop → Start) to apply changes.",
            parent=self.winfo_toplevel(),
        )
