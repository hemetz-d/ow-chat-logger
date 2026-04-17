from __future__ import annotations

import colorsys
import tkinter as tk
import tkinter.colorchooser as colorchooser
import tkinter.messagebox as mb

import customtkinter as ctk

from ow_chat_logger.gui.config_io import (
    get_available_ocr_profiles,
    load_ui_config,
    open_config_folder,
    open_log_folder,
    save_ui_config,
)

# ── Color conversion helpers ──────────────────────────────────────────────────
# OpenCV HSV: H in [0,180], S in [0,255], V in [0,255]

def _hsv_bounds_to_hex(lower: list[int], upper: list[int]) -> str:
    """Return a representative hex color from the midpoint of two HSV bounds."""
    h = ((lower[0] + upper[0]) / 2) / 180.0
    s = ((lower[1] + upper[1]) / 2) / 255.0
    v = upper[2] / 255.0  # use upper V for a bright swatch
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _hex_to_hsv_bounds(hex_color: str, hue_tol: int = 14) -> tuple[list[int], list[int]]:
    """Convert a picked RGB hex color to a reasonable OpenCV HSV range."""
    hx = hex_color.lstrip("#")
    r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h_ocv = int(h * 180)
    s_ocv = int(s * 255)
    lower = [max(0, h_ocv - hue_tol), max(0, s_ocv - 80), 50]
    upper = [min(180, h_ocv + hue_tol), 255, 255]
    return lower, upper


class SettingsPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            label_text="SETTINGS",
            label_fg_color="#0f3460",
            label_text_color="#5BC8F5",
            fg_color="#111122",
            corner_radius=6,
        )
        # HSV vars: 6 per channel (lower_h, lower_s, lower_v, upper_h, upper_s, upper_v)
        self._hsv_vars: dict[str, list[tk.StringVar]] = {}
        # Swatch button refs for updating color when HSV changes
        self._swatches: dict[str, ctk.CTkButton] = {}
        # Other setting vars
        self._vars: dict[str, tk.StringVar] = {}
        self._adv_expanded = False
        self._adv_frame: ctk.CTkFrame | None = None
        self._build()
        self.load()

    # ── Section helpers ───────────────────────────────────────────────────────

    def _section_header(self, parent: tk.Widget, text: str) -> None:
        f = ctk.CTkFrame(parent, fg_color="#0f3460", corner_radius=4)
        f.pack(fill="x", pady=(10, 4), padx=4)
        ctk.CTkLabel(
            f,
            text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#5BC8F5",
        ).pack(side="left", padx=8, pady=4)

    def _row(self, parent: tk.Widget, label: str, label_width: int = 160) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(
            row, text=label, width=label_width, anchor="w", font=ctk.CTkFont(size=11)
        ).pack(side="left")
        return row

    def _adv_entry_row(self, label: str, key: str, width: int = 100) -> None:
        assert self._adv_frame is not None
        row = self._row(self._adv_frame, label)
        var = tk.StringVar()
        self._vars[key] = var
        ctk.CTkEntry(row, textvariable=var, width=width, height=28).pack(side="left")

    def _adv_hsv_row(self, label: str, key: str) -> None:
        assert self._adv_frame is not None
        row = self._row(self._adv_frame, label)
        var_list: list[tk.StringVar] = []
        for ch in ("H", "S", "V"):
            ctk.CTkLabel(row, text=ch, width=14, font=ctk.CTkFont(size=10)).pack(
                side="left", padx=(4, 0)
            )
            var = tk.StringVar()
            var.trace_add("write", lambda *_, k=key: self._refresh_swatch(k.rsplit("_", 2)[0]))
            ctk.CTkEntry(row, textvariable=var, width=46, height=28).pack(
                side="left", padx=(0, 2)
            )
            var_list.append(var)
        self._hsv_vars[key] = var_list

    # ── Top-level build ───────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_color_section()
        self._build_log_section()
        self._build_advanced_toggle()
        self._build_actions()

    def _build_color_section(self) -> None:
        self._section_header(self, "Chat Colors")

        for chat_key, label, default_hex in (
            ("team", "Team Chat", "#5BC8F5"),
            ("all", "All Chat", "#FFAA00"),
        ):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=5)

            ctk.CTkLabel(
                row, text=label, width=110, anchor="w", font=ctk.CTkFont(size=12)
            ).pack(side="left")

            # Clickable color swatch
            swatch = ctk.CTkButton(
                row,
                text="",
                width=44,
                height=28,
                corner_radius=4,
                fg_color=default_hex,
                hover_color=default_hex,
                command=lambda k=chat_key: self._pick_color(k),
            )
            swatch.pack(side="left", padx=(0, 8))
            self._swatches[chat_key] = swatch

            ctk.CTkButton(
                row,
                text="Change Color",
                width=110,
                height=28,
                fg_color="#2a2a4a",
                hover_color="#3a3a6a",
                command=lambda k=chat_key: self._pick_color(k),
            ).pack(side="left")

    def _build_log_section(self) -> None:
        self._section_header(self, "Log Output")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=4)

        try:
            from ow_chat_logger.config import get_app_paths

            path_text = str(get_app_paths().log_dir)
        except Exception:
            path_text = "(unavailable)"

        ctk.CTkLabel(
            row,
            text=path_text,
            anchor="w",
            text_color="#888888",
            font=ctk.CTkFont(size=10),
            wraplength=215,
            justify="left",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row,
            text="Open Folder ↗",
            width=100,
            height=28,
            fg_color="#1a3a5c",
            hover_color="#1a4a8a",
            command=open_log_folder,
        ).pack(side="right")

    def _build_advanced_toggle(self) -> None:
        # Toggle button
        self._adv_toggle_btn = ctk.CTkButton(
            self,
            text="▶  Advanced Settings",
            anchor="w",
            height=32,
            fg_color="#1e1e30",
            hover_color="#2a2a42",
            font=ctk.CTkFont(size=11),
            command=self._toggle_advanced,
        )
        self._adv_toggle_btn.pack(fill="x", padx=4, pady=(12, 0))

        # Hidden advanced frame (packed on demand)
        self._adv_frame = ctk.CTkFrame(self, fg_color="#0d0d1f", corner_radius=4)

        self._section_header(self._adv_frame, "Capture")
        self._build_region_row()
        self._adv_entry_row("Interval (s)", "capture_interval", width=80)

        self._section_header(self._adv_frame, "OCR")
        self._build_profile_row()
        self._adv_entry_row("Confirmations required", "live_message_confirmations_required", width=60)
        self._adv_entry_row("Max dedup remembered", "max_remembered", width=80)

        self._section_header(self._adv_frame, "Team Chat HSV Range")
        self._adv_hsv_row("Lower", "team_hsv_lower")
        self._adv_hsv_row("Upper", "team_hsv_upper")

        self._section_header(self._adv_frame, "All Chat HSV Range")
        self._adv_hsv_row("Lower", "all_hsv_lower")
        self._adv_hsv_row("Upper", "all_hsv_upper")

        ctk.CTkFrame(self._adv_frame, fg_color="#1e1e30", height=2).pack(
            fill="x", padx=4, pady=(8, 0)
        )
        ctk.CTkButton(
            self._adv_frame,
            text="Config Dir ↗",
            width=90,
            height=26,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            command=open_config_folder,
        ).pack(anchor="w", padx=8, pady=6)

    def _build_region_row(self) -> None:
        assert self._adv_frame is not None
        row = self._row(self._adv_frame, "Screen region")
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
        assert self._adv_frame is not None
        row = self._row(self._adv_frame, "OCR profile")
        profiles = get_available_ocr_profiles() or ["windows_default"]
        var = tk.StringVar()
        self._vars["ocr_default_profile"] = var
        ctk.CTkOptionMenu(row, variable=var, values=profiles, width=190, height=28).pack(
            side="left"
        )

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=(14, 8))
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
        ).pack(side="left")

    # ── Advanced toggle ───────────────────────────────────────────────────────

    def _toggle_advanced(self) -> None:
        self._adv_expanded = not self._adv_expanded
        if self._adv_expanded:
            self._adv_frame.pack(fill="x", padx=4, pady=(0, 4))
            self._adv_toggle_btn.configure(text="▼  Advanced Settings")
        else:
            self._adv_frame.pack_forget()
            self._adv_toggle_btn.configure(text="▶  Advanced Settings")

    # ── Color picker ──────────────────────────────────────────────────────────

    def _pick_color(self, chat_key: str) -> None:
        current_hex = self._swatches[chat_key].cget("fg_color")
        result = colorchooser.askcolor(
            color=current_hex,
            title=f"Choose {chat_key.title()} Chat color",
            parent=self.winfo_toplevel(),
        )
        if result and result[1]:
            hex_color: str = result[1]
            lower, upper = _hex_to_hsv_bounds(hex_color)
            self._set_hsv(f"{chat_key}_hsv_lower", lower)
            self._set_hsv(f"{chat_key}_hsv_upper", upper)
            self._update_swatch(chat_key, hex_color)

    def _set_hsv(self, key: str, vals: list[int]) -> None:
        for i, var in enumerate(self._hsv_vars[key]):
            var.set(str(vals[i]))

    def _update_swatch(self, chat_key: str, hex_color: str) -> None:
        self._swatches[chat_key].configure(fg_color=hex_color, hover_color=hex_color)

    def _refresh_swatch(self, chat_key: str) -> None:
        """Recompute swatch from current HSV vars (called when advanced fields change)."""
        try:
            lower_key = f"{chat_key}_hsv_lower"
            upper_key = f"{chat_key}_hsv_upper"
            lower = [int(v.get()) for v in self._hsv_vars[lower_key]]
            upper = [int(v.get()) for v in self._hsv_vars[upper_key]]
            hex_color = _hsv_bounds_to_hex(lower, upper)
            self._swatches[chat_key].configure(fg_color=hex_color, hover_color=hex_color)
        except (ValueError, KeyError):
            pass

    # ── Data load / reset / collect / save ───────────────────────────────────

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

        # Sync swatches from loaded HSV
        for chat_key in ("team", "all"):
            self._refresh_swatch(chat_key)

    def reset(self) -> None:
        from ow_chat_logger.config import _DEFAULT_CONFIG

        d = _DEFAULT_CONFIG
        region = list(d["screen_region"])
        for i in range(4):
            self._vars[f"screen_region_{i}"].set(str(region[i]))
        self._vars["capture_interval"].set(str(d["capture_interval"]))
        self._vars["live_message_confirmations_required"].set(
            str(d["live_message_confirmations_required"])
        )
        self._vars["max_remembered"].set(str(d["max_remembered"]))
        self._vars["ocr_default_profile"].set(d["ocr"]["default_profile"])
        for key in ("team_hsv_lower", "team_hsv_upper", "all_hsv_lower", "all_hsv_upper"):
            vals = list(d[key])
            for i, var in enumerate(self._hsv_vars[key]):
                var.set(str(vals[i]))
        for chat_key in ("team", "all"):
            self._refresh_swatch(chat_key)

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
        mb.showinfo(
            "Saved",
            "Settings saved.\nRestart the logger (Stop → Start) to apply changes.",
            parent=self.winfo_toplevel(),
        )
