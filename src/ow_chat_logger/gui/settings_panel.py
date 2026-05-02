from __future__ import annotations

import tkinter as tk
import tkinter.colorchooser as colorchooser
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from datetime import datetime
from pathlib import Path
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

# Capture-speed presets shown as segmented-button options
_SPEED_PRESETS: dict[str, float] = {
    "Fast": 0.5,
    "Normal": 2.0,
    "Slow": 5.0,
}
_SPEED_ORDER = ("Fast", "Normal", "Slow", "Custom")
_SPEED_EPS = 0.01  # tolerance when matching stored interval to a preset


class SettingsPanel(ctk.CTkFrame):
    """Settings panel — scrollable content with a sticky action footer.

    The outer frame splits into two layers:
      * ``self._footer`` — pinned to the bottom, hosts Save / Reset / Config
        folder so the primary actions stay reachable no matter how far the
        user has scrolled or how much Advanced content is unfolded.
      * ``self._scroll`` — the actual scrollable area where every section
        (Accent, Capture speed, Chat colors, Advanced) lives.

    Previously the panel was itself a ``CTkScrollableFrame`` and the actions
    were packed inline at the end. That meant unfolding Advanced caused its
    body to appear *below* the action row (bug), and Save/Reset stayed off
    screen for users who scrolled to fiddle with HSV bounds.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_save: Callable[[], None] | None = None,
        on_accent_change: Callable[[str], None] | None = None,
        current_accent: str = "blue",
    ) -> None:
        super().__init__(
            parent,
            fg_color=T.BG_ROOT,
            corner_radius=0,
        )
        self._on_save_cb = on_save
        self._on_accent_change_cb = on_accent_change
        self._current_accent = current_accent
        self._accent_swatches: dict[str, ctk.CTkFrame] = {}
        # Config-backed StringVars — shared between user-friendly + Advanced UI
        self._vars: dict[str, tk.StringVar] = {}
        self._hsv_vars: dict[str, list[tk.StringVar]] = {}
        # Derived UI state
        self._chat_hex: dict[str, str] = {"team": "#0A84FF", "all": "#FFD60A"}
        self._chat_tol: dict[str, tk.IntVar] = {}
        self._chat_swatches: dict[str, ctk.CTkButton] = {}
        self._speed_var = tk.StringVar(value="Normal")
        self._custom_speed_entry: ctk.CTkEntry | None = None
        self._advanced_open = tk.BooleanVar(value=False)
        self._advanced_body: ctk.CTkFrame | None = None
        self._advanced_toggle_btn: ctk.CTkButton | None = None
        # Save-confirmation toast — accent-tinted pill that pops above the
        # footer for ~2.5s. Replaces the native ``mb.showinfo`` modal that
        # didn't match the app's visual language.
        self._toast: ctk.CTkFrame | None = None
        self._toast_after_id: str | None = None

        self._build()
        self.load()

    # ── Layout primitives ─────────────────────────────────────────────────────

    def _section_label(self, text: str) -> None:
        ctk.CTkLabel(
            self._scroll,
            text=text,
            font=T.font_section(),
            text_color=T.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=22, pady=(18, 6))

    def _card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self._scroll,
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
        # Screen-region StringVars must exist before the Advanced section is
        # built (it binds them to read-only entries). The user-friendly path
        # no longer surfaces a region picker — the chat region is fixed by
        # the in-game UI, so it's a static value the user shouldn't have to
        # think about. Edge-case overrides happen via the Advanced section.
        for i in range(4):
            self._vars[f"screen_region_{i}"] = tk.StringVar()

        # Footer first (side="bottom" before any expanding sibling), then the
        # scrollable content fills the rest. Order matters in Tk pack — if
        # the scroll were packed first with expand=True, the footer might be
        # squeezed off-screen on tight window heights.
        self._build_footer()
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=T.BG_ROOT,
            corner_radius=0,
            scrollbar_button_color=T.BORDER_HOVER,
            scrollbar_button_hover_color=T.TEXT_MUTED,
        )
        self._scroll.pack(side="top", fill="both", expand=True)

        self._build_accent()
        self._build_capture_speed()
        self._build_chat_colors()
        self._build_advanced()

    # -- Accent (cosmetic) --

    def _build_accent(self) -> None:
        self._section_label("ACCENT")
        card = self._card()

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)

        for name in T.ACCENT_PRESET_NAMES:
            color = T.accent_preset_swatch(name)
            container = ctk.CTkFrame(
                row,
                width=44,
                height=44,
                fg_color="transparent",
                border_width=2,
                border_color=T.ACCENT if name == self._current_accent else T.BORDER_HAIRLINE,
                corner_radius=10,
            )
            container.pack(side="left", padx=(0, 8))
            container.pack_propagate(False)

            inner = ctk.CTkButton(
                container,
                text="",
                width=30,
                height=30,
                corner_radius=7,
                fg_color=color,
                hover_color=color,
                border_width=0,
                command=lambda n=name: self._on_accent_click(n),
            )
            inner.pack(expand=True, padx=4, pady=4)
            self._accent_swatches[name] = container

    def _on_accent_click(self, name: str) -> None:
        if name == self._current_accent:
            return
        self._current_accent = name
        # Update the selection ring on swatches.
        for n, w in self._accent_swatches.items():
            w.configure(border_color=T.ACCENT if n == name else T.BORDER_HAIRLINE)
        # Notify the host to apply + persist + refresh widget colors.
        if self._on_accent_change_cb is not None:
            self._on_accent_change_cb(name)

    # -- Capture speed --

    def _build_capture_speed(self) -> None:
        self._section_label("CAPTURE SPEED")
        card = self._card()

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(14, 6))

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

        # Seconds entry — always visible, but only editable when "Custom" is
        # the selected preset. Otherwise it's a read-only mirror of whatever
        # value the active preset writes into the StringVar.
        custom_wrap = ctk.CTkFrame(body, fg_color="transparent")
        custom_wrap.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            custom_wrap,
            text="seconds",
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
        ).pack(side="right", padx=(6, 0))
        self._vars.setdefault("capture_interval", tk.StringVar())
        self._custom_speed_entry = self._entry(custom_wrap, self._vars["capture_interval"], 70)
        self._custom_speed_entry.pack(side="right")
        # Default segmented value is "Normal" (a preset) so the entry starts
        # locked. ``load()`` flips it editable if the saved interval doesn't
        # match any preset.
        self._set_speed_entry_editable(False)

        # Hint — same pattern as the Chat colors caption.
        ctk.CTkLabel(
            card,
            text=(
                "How often the chat area is scanned for new messages. "
                "Lower values catch messages faster but use more CPU."
            ),
            text_color=T.TEXT_MUTED,
            font=T.font_caption(),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=16, pady=(0, 14))

    def _on_speed_change(self, value: str) -> None:
        """Handle a click on the segmented Fast/Normal/Slow/Custom control."""
        if value == "Custom":
            # Keep the previously-displayed value as a starting point and
            # let the user edit it.
            self._set_speed_entry_editable(True)
            return
        # Preset click → write the canonical interval and lock the entry.
        self._vars["capture_interval"].set(str(_SPEED_PRESETS[value]))
        self._set_speed_entry_editable(False)

    def _set_speed_entry_editable(self, editable: bool) -> None:
        """Toggle the seconds entry between editable and read-only mirroring."""
        if self._custom_speed_entry is None:
            return
        if editable:
            self._custom_speed_entry.configure(
                state="normal",
                text_color=T.TEXT_PRIMARY,
                border_color=T.BORDER_HAIRLINE,
            )
        else:
            self._custom_speed_entry.configure(
                state="readonly",
                text_color=T.TEXT_MUTED,
            )

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
        header_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
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

        # Body card — created once, packed/unpacked on toggle. Lives inside
        # the scrollable area, packed last in that area so it sits directly
        # below the toggle when expanded (instead of floating below the
        # action footer like in the previous layout).
        self._advanced_body = ctk.CTkFrame(
            self._scroll,
            fg_color=T.BG_CARD,
            corner_radius=T.R_CARD,
            border_width=0,
        )
        # Populate body now; don't pack it until user expands.
        self._build_advanced_rows(self._advanced_body)

    def _build_advanced_rows(self, parent: ctk.CTkFrame) -> None:
        # Screen region — read-only. The chat panel position is fixed by the
        # in-game UI, so the region is the same for every user at a given
        # resolution. Editable only by hand-editing config.json (the
        # "Config folder" button in the actions row jumps there).
        self._adv_row_header(parent, "Screen region (read-only)", first=True)
        self._adv_hstack(
            parent,
            pairs=[
                ("X", self._vars["screen_region_0"]),
                ("Y", self._vars["screen_region_1"]),
                ("W", self._vars["screen_region_2"]),
                ("H", self._vars["screen_region_3"]),
            ],
            readonly=True,
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
        readonly: bool = False,
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
            entry = self._entry(row, var, width)
            if readonly:
                entry.configure(state="readonly", text_color=T.TEXT_MUTED)
            entry.pack(side="left", padx=(0, 6))

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

    # -- Footer (sticky action bar) --

    def _build_footer(self) -> None:
        """Pin Save / Reset / Config folder to the bottom of the panel.

        Always visible regardless of scroll position or Advanced expansion.
        Mirrors the toolbar's Stop/Start anchor pattern.
        """
        # Hairline separator above the footer so it reads as its own surface.
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_HAIRLINE, corner_radius=0).pack(
            side="bottom", fill="x"
        )

        self._footer = ctk.CTkFrame(self, fg_color=T.BG_CHROME, corner_radius=0)
        self._footer.pack(side="bottom", fill="x")

        inner = ctk.CTkFrame(self._footer, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=14)

        ctk.CTkButton(
            inner,
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
            inner,
            text="Reset to defaults",
            command=self.reset,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            corner_radius=T.R_PILL,
            height=34,
            width=140,
            font=T.font_body(),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            inner,
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
        ctk.CTkButton(
            inner,
            text="Export history…",
            command=self._open_export_modal,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            corner_radius=T.R_PILL,
            height=34,
            width=140,
            font=T.font_body(),
        ).pack(side="right", padx=(0, 8))

    # ── Data operations ───────────────────────────────────────────────────────

    def load(self) -> None:
        cfg = load_ui_config()

        region = cfg.get("screen_region", [80, 400, 400, 600])
        for i in range(4):
            self._vars[f"screen_region_{i}"].set(str(region[i] if i < len(region) else 0))

        interval = float(cfg.get("capture_interval", 2.0))
        self._vars["capture_interval"].set(str(interval))
        # Map the saved interval to a preset (or "Custom" when it doesn't
        # line up). Programmatically setting ``_speed_var`` does NOT fire
        # the segmented button's ``command`` — it just updates the visual
        # selection — so we toggle the entry state explicitly.
        matched = next(
            (n for n, v in _SPEED_PRESETS.items() if abs(v - interval) < _SPEED_EPS),
            None,
        )
        self._speed_var.set(matched or "Custom")
        self._set_speed_entry_editable(matched is None)

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
        self._show_saved_toast()

    # ── Save-feedback toast ──────────────────────────────────────────────────

    def _show_saved_toast(self, message: str = "Settings saved") -> None:
        """Brief in-panel confirmation pill — defaults to a save acknowledgement.

        Replaces the native ``mb.showinfo`` dialog with an accent-tinted pill
        that pops in just above the action footer and auto-dismisses after
        ~2.5 seconds. Repeated triggers cancel any pending hide and refresh
        the timer so the toast feels stable rather than racing itself. The
        ``message`` argument lets non-save flows (e.g. export) reuse the
        same widget without copy-pasting the layout code.
        """
        if self._toast_after_id is not None:
            try:
                self.after_cancel(self._toast_after_id)
            except Exception:
                pass
            self._toast_after_id = None
        if self._toast is not None:
            try:
                self._toast.destroy()
            except Exception:
                pass
            self._toast = None

        toast = ctk.CTkFrame(
            self,
            fg_color=T.ACCENT_SUBTLE,
            border_color=T.ACCENT,
            border_width=1,
            corner_radius=8,
        )
        ctk.CTkLabel(
            toast,
            text="✓",
            text_color=T.ACCENT,
            font=ctk.CTkFont(family=T.ui_family(), size=13, weight="bold"),
        ).pack(side="left", padx=(14, 8), pady=8)
        ctk.CTkLabel(
            toast,
            text=message,
            text_color=T.ACCENT,
            font=ctk.CTkFont(family=T.ui_family(), size=12, weight="bold"),
        ).pack(side="left", padx=(0, 16), pady=8)

        # Place centered horizontally, just above the footer's top edge.
        # ``place`` uses anchor="s" so the toast's bottom edge sits at y.
        self.update_idletasks()
        try:
            panel_w = self.winfo_width()
            footer_y = self._footer.winfo_y()
        except tk.TclError:
            panel_w, footer_y = 600, 500
        toast.place(x=panel_w // 2, y=footer_y - 12, anchor="s")
        toast.lift()

        self._toast = toast
        self._toast_after_id = self.after(2500, self._hide_saved_toast)

    def _hide_saved_toast(self) -> None:
        self._toast_after_id = None
        if self._toast is not None:
            try:
                self._toast.destroy()
            except Exception:
                pass
            self._toast = None

    # ── Export history modal ─────────────────────────────────────────────────

    def _open_export_modal(self) -> None:
        """Open the small "Export history" modal anchored to this panel.

        The modal collects format + channel + optional date range, then
        defers to a native save dialog for the destination path. The actual
        export work happens in :mod:`ow_chat_logger.log_export` so the GUI
        layer stays focused on UI plumbing.
        """
        ExportModal(self)

    def _run_export(
        self,
        *,
        fmt: str,
        channel_filter: str | None,
        since: str | None,
        until: str | None,
        out_path: Path,
    ) -> None:
        """Dispatch to the export core and surface the result via toast."""
        from ow_chat_logger.log_export import export_to_csv, export_to_txt

        try:
            if fmt == "csv":
                count = export_to_csv(
                    out_path,
                    channel_filter=channel_filter,  # type: ignore[arg-type]
                    since=since,
                    until=until,
                )
            else:
                count = export_to_txt(
                    out_path,
                    channel_filter=channel_filter,  # type: ignore[arg-type]
                    since=since,
                    until=until,
                )
        except FileNotFoundError as exc:
            mb.showerror("Export failed", str(exc), parent=self.winfo_toplevel())
            return
        except Exception as exc:  # noqa: BLE001 — surface anything to the user
            mb.showerror(
                "Export failed",
                f"Could not export history: {exc}",
                parent=self.winfo_toplevel(),
            )
            return

        self._show_saved_toast(f"Exported {count} messages to {out_path.name}")


# ── Export modal ────────────────────────────────────────────────────────────


_EXPORT_CHANNELS = (
    ("All channels", None),
    ("Team", "team"),
    ("All chat", "all"),
    ("Hero", "hero"),
)


class ExportModal(ctk.CTkToplevel):
    """Tiny export-options dialog parented to the settings panel.

    Kept as its own class so the settings panel doesn't grow another long
    ``_build_*`` method, and so future call sites (e.g. a dedicated History
    section) can reuse it without copy-pasting layout code.
    """

    def __init__(self, parent: SettingsPanel) -> None:
        super().__init__(parent)
        self._panel = parent
        self.title("Export history")
        self.resizable(False, False)
        # ``transient`` + ``grab_set`` make this a true modal: no clicks land
        # on the main window until it is dismissed. ``after_idle`` defers
        # the grab past the window-mapping race that bites ``CTkToplevel``
        # — calling ``grab_set`` synchronously sometimes raises ``TclError``
        # because the window is not yet viewable.
        self.transient(parent.winfo_toplevel())
        self.after_idle(self._safe_grab)

        T.apply_chrome(self)
        self.configure(fg_color=T.BG_ROOT)

        self._fmt_var = tk.StringVar(value="txt")
        self._channel_var = tk.StringVar(value=_EXPORT_CHANNELS[0][0])
        self._since_var = tk.StringVar()
        self._until_var = tk.StringVar()

        self._build()
        self.update_idletasks()
        self._center_over_parent(parent)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build(self) -> None:
        body = ctk.CTkFrame(self, fg_color=T.BG_ROOT, corner_radius=0)
        body.pack(fill="both", expand=True, padx=18, pady=(16, 12))

        # Format
        ctk.CTkLabel(
            body, text="Format", text_color=T.TEXT_SECONDARY, font=T.font_caption(), anchor="w"
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkSegmentedButton(
            body,
            values=[".txt", ".csv"],
            command=lambda v: self._fmt_var.set(v.lstrip(".")),
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color=T.BG_ELEV,
            selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_ELEV,
            unselected_hover_color=T.BORDER_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
        ).pack(fill="x", pady=(0, 12))

        # Channel
        ctk.CTkLabel(
            body, text="Channel", text_color=T.TEXT_SECONDARY, font=T.font_caption(), anchor="w"
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkSegmentedButton(
            body,
            values=[label for label, _ in _EXPORT_CHANNELS],
            variable=self._channel_var,
            height=30,
            corner_radius=T.R_BUTTON,
            fg_color=T.BG_ELEV,
            selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_ELEV,
            unselected_hover_color=T.BORDER_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
        ).pack(fill="x", pady=(0, 12))

        # Date range
        ctk.CTkLabel(
            body,
            text="Date range (YYYY-MM-DD, optional)",
            text_color=T.TEXT_SECONDARY,
            font=T.font_caption(),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        date_row = ctk.CTkFrame(body, fg_color="transparent")
        date_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            date_row, text="From", text_color=T.TEXT_MUTED, font=T.font_caption(), width=40
        ).pack(side="left")
        self._mk_entry(date_row, self._since_var).pack(side="left", padx=(4, 12))
        ctk.CTkLabel(
            date_row, text="To", text_color=T.TEXT_MUTED, font=T.font_caption(), width=24
        ).pack(side="left")
        self._mk_entry(date_row, self._until_var).pack(side="left", padx=(4, 0))

        # Buttons
        buttons = ctk.CTkFrame(self, fg_color=T.BG_CHROME, corner_radius=0)
        buttons.pack(side="bottom", fill="x")
        inner = ctk.CTkFrame(buttons, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)
        ctk.CTkButton(
            inner,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            hover_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            corner_radius=T.R_PILL,
            height=32,
            width=92,
            font=T.font_body(),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            inner,
            text="Export",
            command=self._on_export,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_FG,
            corner_radius=T.R_PILL,
            height=32,
            width=92,
            font=T.font_button(),
        ).pack(side="right")

    def _mk_entry(self, parent: tk.Widget, var: tk.StringVar) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            textvariable=var,
            width=110,
            height=28,
            corner_radius=T.R_INPUT,
            border_width=1,
            border_color=T.BORDER_HAIRLINE,
            fg_color=T.BG_ELEV,
            text_color=T.TEXT_PRIMARY,
            font=T.font_small(),
            placeholder_text="YYYY-MM-DD",
        )

    def _center_over_parent(self, parent: tk.Widget) -> None:
        try:
            top = parent.winfo_toplevel()
            top.update_idletasks()
            px, py = top.winfo_rootx(), top.winfo_rooty()
            pw, ph = top.winfo_width(), top.winfo_height()
            mw, mh = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - mw) // 2}+{py + (ph - mh) // 3}")
        except tk.TclError:
            pass

    def _on_export(self) -> None:
        # Resolve channel label → log_export filter value.
        label = self._channel_var.get()
        channel_filter = next(
            (val for lbl, val in _EXPORT_CHANNELS if lbl == label),
            None,
        )

        # Date inputs are optional. Empty → no bound. A non-empty value must
        # parse as a calendar date; we expand to start/end-of-day ISO strings
        # so the lexical comparison in log_export covers the full day.
        try:
            since = self._date_to_since(self._since_var.get())
            until = self._date_to_until(self._until_var.get())
        except ValueError as exc:
            mb.showerror("Invalid date", str(exc), parent=self)
            return

        fmt = self._fmt_var.get() or "txt"
        default_name = f"chat_history_{datetime.now():%Y%m%d}.{fmt}"
        filetypes = (
            [("Text", "*.txt"), ("All files", "*.*")]
            if fmt == "txt"
            else [("CSV", "*.csv"), ("All files", "*.*")]
        )
        chosen = fd.asksaveasfilename(
            parent=self,
            title="Export history",
            defaultextension=f".{fmt}",
            initialfile=default_name,
            filetypes=filetypes,
        )
        if not chosen:
            return

        # Hand control back to the panel so the success toast lands on the
        # surface the user is already looking at — and so the modal can
        # close cleanly before any blocking dialogs (errors) might appear.
        self.destroy()
        self._panel._run_export(
            fmt=fmt,
            channel_filter=channel_filter,
            since=since,
            until=until,
            out_path=Path(chosen),
        )

    @staticmethod
    def _date_to_since(raw: str) -> str | None:
        raw = raw.strip()
        if not raw:
            return None
        # Validate; raises ValueError with a usable message on bad input.
        datetime.strptime(raw, "%Y-%m-%d")
        return f"{raw} 00:00:00"

    @staticmethod
    def _date_to_until(raw: str) -> str | None:
        raw = raw.strip()
        if not raw:
            return None
        datetime.strptime(raw, "%Y-%m-%d")
        return f"{raw} 23:59:59"
