from __future__ import annotations

import tkinter as tk
import tkinter.colorchooser as colorchooser
import tkinter.messagebox as mb
from typing import Callable

import customtkinter as ctk

from ow_chat_logger.gui import icons as I
from ow_chat_logger.gui import theme as T
from ow_chat_logger.gui.color_utils import (
    hex_to_hsv_bounds,
    hsv_bounds_to_hex,
    hue_tol_from_bounds,
)
from ow_chat_logger.gui.config_io import (
    get_available_ocr_profiles,
    load_ui_config,
    open_config_folder,
    save_ui_config,
)
from ow_chat_logger.gui.region_picker import RegionPickerOverlay

# Capture-speed presets shown as segmented-button options
_SPEED_PRESETS: dict[str, float] = {
    "Fast": 0.5,
    "Normal": 2.0,
    "Slow": 5.0,
}
_SPEED_ORDER = ("Fast", "Normal", "Slow", "Custom")
_SPEED_EPS = 0.01  # tolerance when matching stored interval to a preset


class SettingsPanel(ctk.CTkScrollableFrame):
    """Settings panel: user-friendly up top, Advanced section collapsed."""

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
        # Config-backed StringVars — shared between user-friendly + Advanced UI
        self._vars: dict[str, tk.StringVar] = {}
        self._hsv_vars: dict[str, list[tk.StringVar]] = {}
        # Derived UI state
        self._chat_hex: dict[str, str] = {"team": "#0A84FF", "all": "#FFD60A"}
        self._chat_tol: dict[str, tk.IntVar] = {}
        self._chat_swatches: dict[str, ctk.CTkButton] = {}
        self._region_preview: ctk.CTkCanvas | None = None
        self._region_text: ctk.CTkLabel | None = None
        self._speed_var = tk.StringVar(value="Normal")
        self._custom_speed_entry: ctk.CTkEntry | None = None
        self._advanced_open = tk.BooleanVar(value=False)
        self._advanced_body: ctk.CTkFrame | None = None
        self._advanced_toggle_btn: ctk.CTkButton | None = None

        self._build()
        self.load()

    # ── Layout primitives ─────────────────────────────────────────────────────

    def _section_label(self, text: str) -> None:
        ctk.CTkLabel(
            self,
            text=text,
            font=T.font_section(),
            text_color=T.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=22, pady=(18, 6))

    def _card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        card.pack(fill="x", padx=16, pady=(0, 4))
        return card

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

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_capture_region()
        self._build_capture_speed()
        self._build_chat_colors()
        self._build_advanced()
        self._build_actions()

    # -- Capture region --

    def _build_capture_region(self) -> None:
        self._section_label("CAPTURE REGION")
        card = self._card()

        # Preview strip
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=14)

        self._region_preview = ctk.CTkCanvas(
            body,
            height=70,
            bg=T.pick(T.BG_ELEV),
            highlightthickness=1,
            highlightbackground=T.pick(T.BORDER_HAIRLINE),
        )
        self._region_preview.pack(fill="x")

        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.pack(fill="x", padx=16, pady=(0, 14))
        self._region_text = ctk.CTkLabel(
            meta,
            text="—",
            text_color=T.TEXT_SECONDARY,
            font=T.font_small(),
        )
        self._region_text.pack(side="left")
        ctk.CTkButton(
            meta,
            text="Pick region",
            image=I.icon("chevron_right", 14, color=T.ACCENT_FG),
            compound="right",
            command=self._open_region_picker,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            corner_radius=T.R_BUTTON,
            height=32,
            width=120,
            font=T.font_button(),
        ).pack(side="right")

        # Create the 4 region vars now; Advanced binds them as entries later.
        for i in range(4):
            var = tk.StringVar()
            var.trace_add("write", lambda *_a: self._refresh_region_preview())
            self._vars[f"screen_region_{i}"] = var

    def _refresh_region_preview(self) -> None:
        if self._region_preview is None or self._region_text is None:
            return
        try:
            coords = [int(self._vars[f"screen_region_{i}"].get()) for i in range(4)]
            x, y, w, h = coords
        except (ValueError, KeyError):
            self._region_text.configure(text="—")
            return

        self._region_text.configure(text=f"{w} × {h}   at ({x}, {y})")

        self._region_preview.delete("all")
        cw = max(self._region_preview.winfo_width(), 10)
        ch = 70
        # Use a nominal screen aspect (16:9) — we just want shape context.
        screen_w, screen_h = 1920, 1080
        scale = min((cw - 8) / screen_w, (ch - 8) / screen_h)
        sw, sh = screen_w * scale, screen_h * scale
        ox, oy = (cw - sw) / 2, (ch - sh) / 2

        border = T.pick(T.BORDER_HAIRLINE)
        accent = T.pick(T.ACCENT)
        self._region_preview.create_rectangle(ox, oy, ox + sw, oy + sh, outline=border)
        rx = ox + x * scale
        ry = oy + y * scale
        rw = w * scale
        rh = h * scale
        self._region_preview.create_rectangle(
            rx,
            ry,
            rx + rw,
            ry + rh,
            outline=accent,
            width=2,
        )

    def _open_region_picker(self) -> None:
        def _on_pick(x: int, y: int, w: int, h: int) -> None:
            self._vars["screen_region_0"].set(str(x))
            self._vars["screen_region_1"].set(str(y))
            self._vars["screen_region_2"].set(str(w))
            self._vars["screen_region_3"].set(str(h))

        RegionPickerOverlay(self.winfo_toplevel(), on_pick=_on_pick)

    # -- Capture speed --

    def _build_capture_speed(self) -> None:
        self._section_label("CAPTURE SPEED")
        card = self._card()

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=14)

        seg = ctk.CTkSegmentedButton(
            body,
            values=list(_SPEED_ORDER),
            variable=self._speed_var,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color=T.BG_ELEV,
            selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_ELEV,
            unselected_hover_color=T.BORDER_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
            command=self._on_speed_change,
        )
        seg.pack(side="left")

        custom_wrap = ctk.CTkFrame(body, fg_color="transparent")
        custom_wrap.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            custom_wrap,
            text="seconds",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        ).pack(side="right", padx=(6, 0))
        self._custom_speed_entry = self._entry(
            custom_wrap, self._vars.setdefault("capture_interval", tk.StringVar()), 70
        )
        self._custom_speed_entry.pack(side="right")
        self._custom_speed_entry.pack_forget()  # hidden unless Custom selected

    def _on_speed_change(self, value: str) -> None:
        if value == "Custom":
            if self._custom_speed_entry is not None:
                self._custom_speed_entry.pack(side="right")
        else:
            if self._custom_speed_entry is not None:
                self._custom_speed_entry.pack_forget()
            self._vars["capture_interval"].set(str(_SPEED_PRESETS[value]))

    # -- Chat colors --

    def _build_chat_colors(self) -> None:
        self._section_label("CHAT COLORS")
        card = self._card()

        for idx, (key, label) in enumerate((("team", "Team chat"), ("all", "All chat"))):
            # Top padding only for the second block — gives it separation
            pad_top = 14 if idx == 0 else 6
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(pad_top, 6))

            ctk.CTkLabel(
                row,
                text=label,
                text_color=T.TEXT_PRIMARY,
                font=T.font_body(),
                width=90,
                anchor="w",
            ).pack(side="left")

            swatch = ctk.CTkButton(
                row,
                text="",
                width=34,
                height=24,
                corner_radius=T.R_SWATCH,
                fg_color=self._chat_hex[key],
                hover_color=self._chat_hex[key],
                border_width=0,
                command=lambda k=key: self._pick_chat_color(k),
            )
            swatch.pack(side="left", padx=(10, 14))
            self._chat_swatches[key] = swatch

            ctk.CTkLabel(
                row,
                text="Tolerance",
                text_color=T.TEXT_MUTED,
                font=T.font_caption(),
            ).pack(side="left", padx=(0, 8))

            tol_var = tk.IntVar(value=14)
            self._chat_tol[key] = tol_var

            slider = ctk.CTkSlider(
                row,
                from_=5,
                to=30,
                number_of_steps=25,
                variable=tol_var,
                width=160,
                height=16,
                fg_color=T.BG_ELEV,
                progress_color=T.ACCENT,
                button_color=T.ACCENT,
                button_hover_color=T.ACCENT_HOVER,
                command=lambda _v, k=key: self._on_tolerance_change(k),
            )
            slider.pack(side="left")

            tol_label = ctk.CTkLabel(
                row,
                text="14°",
                text_color=T.TEXT_SECONDARY,
                font=T.font_caption(),
                width=34,
                anchor="e",
            )
            tol_label.pack(side="left", padx=(8, 0))
            # Update label when slider moves
            tol_var.trace_add(
                "write",
                lambda *_a, k=key, L=tol_label: L.configure(
                    text=f"{int(self._chat_tol[k].get())}°"
                ),
            )

        # Helpful caption at the bottom of the card
        ctk.CTkLabel(
            card,
            text="Pick a color in-game, then widen the tolerance if detection is patchy.",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=16, pady=(0, 14))

    def _pick_chat_color(self, key: str) -> None:
        result = colorchooser.askcolor(
            color=self._chat_hex[key],
            title=f"Choose {key.title()} Chat color",
            parent=self.winfo_toplevel(),
        )
        if not (result and result[1]):
            return
        self._chat_hex[key] = result[1]
        self._chat_swatches[key].configure(fg_color=result[1], hover_color=result[1])
        self._apply_color_to_hsv_vars(key)

    def _on_tolerance_change(self, key: str) -> None:
        self._apply_color_to_hsv_vars(key)

    def _apply_color_to_hsv_vars(self, key: str) -> None:
        hue_tol = int(self._chat_tol[key].get())
        lower, upper = hex_to_hsv_bounds(self._chat_hex[key], hue_tol=hue_tol)
        for i, val in enumerate(lower):
            self._hsv_vars[f"{key}_hsv_lower"][i].set(str(val))
        for i, val in enumerate(upper):
            self._hsv_vars[f"{key}_hsv_upper"][i].set(str(val))

    # -- Advanced (collapsed) --

    def _build_advanced(self) -> None:
        # Toggle header row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(20, 6))

        self._advanced_toggle_btn = ctk.CTkButton(
            header_frame,
            text="Advanced",
            image=I.icon("chevron_right", 14),
            compound="left",
            command=self._toggle_advanced,
            fg_color="transparent",
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_SECONDARY,
            anchor="w",
            height=28,
            corner_radius=T.R_BUTTON,
            font=T.font_section(),
        )
        self._advanced_toggle_btn.pack(fill="x")

        # Body card — created once, packed/unpacked on toggle
        self._advanced_body = ctk.CTkFrame(
            self,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        # Populate body now; don't pack it until user expands.
        self._build_advanced_rows(self._advanced_body)

    def _build_advanced_rows(self, parent: ctk.CTkFrame) -> None:
        # Screen region raw entries
        self._adv_row_header(parent, "Screen region", first=True)
        self._adv_hstack(
            parent,
            pairs=[
                ("X", self._vars["screen_region_0"]),
                ("Y", self._vars["screen_region_1"]),
                ("W", self._vars["screen_region_2"]),
                ("H", self._vars["screen_region_3"]),
            ],
        )

        # Capture interval raw
        self._adv_row_header(parent, "Capture interval (s)")
        self._adv_hstack(
            parent,
            pairs=[("", self._vars.setdefault("capture_interval", tk.StringVar()))],
            width=80,
        )

        # Confirmations + dedup
        for key, label, w in (
            ("live_message_confirmations_required", "Confirmations required", 60),
            ("max_remembered", "Max dedup remembered", 80),
        ):
            self._vars.setdefault(key, tk.StringVar())
            self._adv_row_header(parent, label)
            self._adv_hstack(parent, pairs=[("", self._vars[key])], width=w)

        # OCR profile
        self._adv_row_header(parent, "OCR profile")
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        profiles = get_available_ocr_profiles() or ["windows_default"]
        self._vars.setdefault("ocr_default_profile", tk.StringVar())
        ctk.CTkOptionMenu(
            row,
            variable=self._vars["ocr_default_profile"],
            values=profiles,
            width=220,
            height=30,
            corner_radius=T.R_INPUT,
            fg_color=T.BG_ELEV,
            button_color=T.BORDER_HAIRLINE,
            button_hover_color=T.BORDER_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
        ).pack(side="left")

        # Raw HSV bounds (advanced) — team then all
        for chat_key, chat_label in (("team", "Team HSV"), ("all", "All HSV")):
            for bound in ("lower", "upper"):
                key = f"{chat_key}_hsv_{bound}"
                self._adv_row_header(parent, f"{chat_label} — {bound}")
                var_list: list[tk.StringVar] = self._hsv_vars.setdefault(
                    key, [tk.StringVar() for _ in range(3)]
                )
                self._adv_hstack(
                    parent,
                    pairs=[(ch, var) for ch, var in zip(("H", "S", "V"), var_list)],
                    width=58,
                )

    def _adv_row_header(self, parent: ctk.CTkFrame, text: str, first: bool = False) -> None:
        if not first:
            ctk.CTkFrame(parent, height=1, fg_color=T.BORDER_FAINT, corner_radius=0).pack(
                fill="x", padx=16
            )
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 2))

    def _adv_hstack(
        self,
        parent: ctk.CTkFrame,
        pairs: list[tuple[str, tk.StringVar]],
        width: int = 54,
    ) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        for label, var in pairs:
            if label:
                ctk.CTkLabel(
                    row,
                    text=label,
                    width=14,
                    text_color=T.TEXT_MUTED,
                    font=T.font_caption(),
                ).pack(side="left", padx=(0, 2))
            self._entry(row, var, width).pack(side="left", padx=(0, 6))

    def _toggle_advanced(self) -> None:
        if self._advanced_body is None or self._advanced_toggle_btn is None:
            return
        self._advanced_open.set(not self._advanced_open.get())
        if self._advanced_open.get():
            self._advanced_body.pack(fill="x", padx=16, pady=(0, 4))
            self._advanced_toggle_btn.configure(image=I.icon("chevron_down", 14))
        else:
            self._advanced_body.pack_forget()
            self._advanced_toggle_btn.configure(image=I.icon("chevron_right", 14))

    # -- Actions --

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=22, pady=(22, 16))
        ctk.CTkButton(
            frame,
            text="Save",
            image=I.icon("check", 12, color=T.ACCENT_FG),
            compound="left",
            command=self.save,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            corner_radius=T.R_PILL,
            height=34,
            width=104,
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

        interval = float(cfg.get("capture_interval", 2.0))
        self._vars["capture_interval"].set(str(interval))
        # Map interval to segmented-button preset if it matches
        matched = None
        for name, val in _SPEED_PRESETS.items():
            if abs(val - interval) < _SPEED_EPS:
                matched = name
                break
        self._speed_var.set(matched or "Custom")
        if matched is None and self._custom_speed_entry is not None:
            self._custom_speed_entry.pack(side="right")
        elif matched is not None and self._custom_speed_entry is not None:
            self._custom_speed_entry.pack_forget()

        self._vars.setdefault("live_message_confirmations_required", tk.StringVar()).set(
            str(cfg.get("live_message_confirmations_required", 2))
        )
        self._vars.setdefault("max_remembered", tk.StringVar()).set(
            str(cfg.get("max_remembered", 1000))
        )
        self._vars.setdefault("ocr_default_profile", tk.StringVar()).set(
            cfg.get("ocr_default_profile", "windows_default")
        )

        for chat_key in ("team", "all"):
            for bound in ("lower", "upper"):
                key = f"{chat_key}_hsv_{bound}"
                vals = cfg.get(key, [0, 0, 0])
                var_list = self._hsv_vars.setdefault(key, [tk.StringVar() for _ in range(3)])
                for i, var in enumerate(var_list):
                    var.set(str(vals[i]) if i < len(vals) else "0")

        # Derive user-friendly chat color + tolerance from HSV bounds
        for chat_key in ("team", "all"):
            try:
                lower = [int(v.get()) for v in self._hsv_vars[f"{chat_key}_hsv_lower"]]
                upper = [int(v.get()) for v in self._hsv_vars[f"{chat_key}_hsv_upper"]]
                self._chat_hex[chat_key] = hsv_bounds_to_hex(lower, upper)
                self._chat_tol[chat_key].set(hue_tol_from_bounds(lower, upper))
            except (ValueError, KeyError):
                pass
            if chat_key in self._chat_swatches:
                self._chat_swatches[chat_key].configure(
                    fg_color=self._chat_hex[chat_key],
                    hover_color=self._chat_hex[chat_key],
                )

        self.after_idle(self._refresh_region_preview)

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
        # Re-derive friendly color + tolerance from the defaults
        for chat_key in ("team", "all"):
            lower = [int(v.get()) for v in self._hsv_vars[f"{chat_key}_hsv_lower"]]
            upper = [int(v.get()) for v in self._hsv_vars[f"{chat_key}_hsv_upper"]]
            self._chat_hex[chat_key] = hsv_bounds_to_hex(lower, upper)
            self._chat_tol[chat_key].set(hue_tol_from_bounds(lower, upper))
            self._chat_swatches[chat_key].configure(
                fg_color=self._chat_hex[chat_key],
                hover_color=self._chat_hex[chat_key],
            )
        # Reset speed segmented to matching preset
        interval = float(d["capture_interval"])
        matched = next(
            (n for n, v in _SPEED_PRESETS.items() if abs(v - interval) < _SPEED_EPS),
            "Custom",
        )
        self._speed_var.set(matched)
        self._on_speed_change(matched)
        self._refresh_region_preview()

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
            "Settings saved.\nHSV and pipeline changes apply live; engine or "
            "language changes require Stop → Start.",
            parent=self.winfo_toplevel(),
        )
