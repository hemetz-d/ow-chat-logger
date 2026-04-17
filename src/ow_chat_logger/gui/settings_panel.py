from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as mb
from typing import Callable

import customtkinter as ctk

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
            fg_color="#111122",
            corner_radius=0,
        )
        self._on_save_cb = on_save
        self._hsv_vars: dict[str, list[tk.StringVar]] = {}
        self._vars: dict[str, tk.StringVar] = {}
        self._build()
        self.load()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _section(self, text: str) -> None:
        f = ctk.CTkFrame(self, fg_color="#0f3460", corner_radius=4)
        f.pack(fill="x", pady=(10, 4), padx=4)
        ctk.CTkLabel(
            f,
            text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#5BC8F5",
        ).pack(side="left", padx=8, pady=4)

    def _row(self, label: str, label_width: int = 185) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(
            row, text=label, width=label_width, anchor="w", font=ctk.CTkFont(size=11)
        ).pack(side="left")
        return row

    def _entry_row(self, label: str, key: str, width: int = 100) -> None:
        row = self._row(label)
        var = tk.StringVar()
        self._vars[key] = var
        ctk.CTkEntry(row, textvariable=var, width=width, height=28).pack(side="left")

    def _hsv_row(self, label: str, key: str) -> None:
        row = self._row(label)
        var_list: list[tk.StringVar] = []
        for ch in ("H", "S", "V"):
            ctk.CTkLabel(row, text=ch, width=14, font=ctk.CTkFont(size=10)).pack(
                side="left", padx=(4, 0)
            )
            var = tk.StringVar()
            ctk.CTkEntry(row, textvariable=var, width=50, height=28).pack(
                side="left", padx=(0, 2)
            )
            var_list.append(var)
        self._hsv_vars[key] = var_list

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._section("Capture")
        self._build_region_row()
        self._entry_row("Interval (s)", "capture_interval", width=80)

        self._section("OCR")
        self._build_profile_row()
        self._entry_row("Confirmations required", "live_message_confirmations_required", width=60)
        self._entry_row("Max dedup remembered", "max_remembered", width=80)

        self._section("Team Chat Color (HSV)")
        self._hsv_row("Lower", "team_hsv_lower")
        self._hsv_row("Upper", "team_hsv_upper")

        self._section("All Chat Color (HSV)")
        self._hsv_row("Lower", "all_hsv_lower")
        self._hsv_row("Upper", "all_hsv_upper")

        self._build_actions()

    def _build_region_row(self) -> None:
        row = self._row("Screen region")
        for i, lbl in enumerate(("X", "Y", "W", "H")):
            ctk.CTkLabel(row, text=lbl, width=14, font=ctk.CTkFont(size=10)).pack(
                side="left", padx=(4, 0)
            )
            var = tk.StringVar()
            self._vars[f"screen_region_{i}"] = var
            ctk.CTkEntry(row, textvariable=var, width=52, height=28).pack(
                side="left", padx=(0, 2)
            )

    def _build_profile_row(self) -> None:
        row = self._row("OCR profile")
        profiles = get_available_ocr_profiles() or ["windows_default"]
        var = tk.StringVar()
        self._vars["ocr_default_profile"] = var
        ctk.CTkOptionMenu(row, variable=var, values=profiles, width=190, height=28).pack(
            side="left"
        )

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=(16, 8))
        ctk.CTkButton(
            frame,
            text="Save Settings",
            command=self.save,
            fg_color="#1a4a8a",
            hover_color="#1e5cb3",
            height=32,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="Reset Defaults",
            command=self.reset,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            height=32,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            frame,
            text="Config Dir ↗",
            command=open_config_folder,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            height=32,
            width=90,
        ).pack(side="left")

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
