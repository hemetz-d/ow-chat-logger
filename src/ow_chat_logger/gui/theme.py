from __future__ import annotations

import tkinter.font as tkfont

import customtkinter as ctk

# ── Dual-mode palette (light, dark) ──────────────────────────────────────────
# Apple-inspired neutrals. First element = light, second = dark.

# Surfaces
BG_ROOT = ("#f2f2f5", "#1c1c1e")
BG_CHROME = ("#fbfbfd", "#2a2a2c")  # toolbar / bottom bar, subtle lift
BG_CARD = ("#ffffff", "#2c2c2e")  # feed card, settings section cards
BG_ELEV = ("#eeeef0", "#3a3a3c")  # inputs, hover fill
BG_SELECT = ("#d0d0d5", "#48484a")  # selection background in text widgets

# Borders — very subtle; often we prefer color contrast over a visible border.
BORDER_HAIRLINE = ("#e3e3e7", "#3a3a3c")
BORDER_FAINT = ("#ececf0", "#2f2f31")
BORDER_HOVER = ("#c7c7cc", "#5a5a5c")

# Text
TEXT_PRIMARY = ("#1d1d1f", "#f5f5f7")
TEXT_SECONDARY = ("#515155", "#aeaeb2")
TEXT_MUTED = ("#86868b", "#8e8e93")
TEXT_DIM = ("#aeaeb2", "#636366")

# Accents — Apple System Blue
ACCENT = ("#007AFF", "#0A84FF")
ACCENT_HOVER = ("#0062cc", "#3395ff")
ACCENT_FG = ("#ffffff", "#ffffff")

# Semantic (System colors)
SUCCESS = ("#34C759", "#30D158")
DANGER = ("#FF3B30", "#FF453A")
DANGER_HOVER = ("#d92f26", "#ff5b54")
WARNING = ("#FF9500", "#FF9F0A")
IDLE = ("#c7c7cc", "#48484a")

# Chat colors (tuned per mode for contrast on card background)
CHAT_TEAM = ("#0A84FF", "#64D2FF")
CHAT_ALL = ("#B25000", "#FFD60A")
CHAT_HERO = ("#248A3D", "#30D158")
CHAT_TS = ("#86868b", "#8e8e93")

# Radii — generous, Apple-ish
R_CARD = 14
R_BUTTON = 10
R_INPUT = 8
R_SWATCH = 7
R_PILL = 18

# ── Font families ────────────────────────────────────────────────────────────
_UI_FAMILY: str | None = None
_MONO_FAMILY: str | None = None


def _pick_family(candidates: list[str]) -> str:
    try:
        fams = set(tkfont.families())
    except Exception:
        return candidates[-1]
    for f in candidates:
        if f in fams:
            return f
    return candidates[-1]


def ui_family() -> str:
    global _UI_FAMILY
    if _UI_FAMILY is None:
        _UI_FAMILY = _pick_family(
            [
                "Segoe UI Variable",
                "Segoe UI Variable Display",
                "Segoe UI",
                "SF Pro Text",
                "Helvetica Neue",
                "Arial",
            ]
        )
    return _UI_FAMILY


def mono_family() -> str:
    global _MONO_FAMILY
    if _MONO_FAMILY is None:
        _MONO_FAMILY = _pick_family(
            [
                "Cascadia Mono",
                "Cascadia Code",
                "SF Mono",
                "JetBrains Mono",
                "Consolas",
                "Courier New",
            ]
        )
    return _MONO_FAMILY


def font_title() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=17, weight="bold")


def font_section() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=11, weight="bold")


def font_body() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=13)


def font_button() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=13, weight="bold")


def font_small() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=12)


def font_caption() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=11)


def font_mono() -> tuple[str, int]:
    return (mono_family(), 11)


# ── Mode helpers ─────────────────────────────────────────────────────────────
def is_dark() -> bool:
    return ctk.get_appearance_mode() == "Dark"


def pick(color) -> str:
    """Resolve a (light, dark) tuple or plain string to a hex for current mode."""
    if isinstance(color, tuple):
        return color[1] if is_dark() else color[0]
    return color


# ── Win11 backdrop + titlebar ────────────────────────────────────────────────
def apply_chrome(window) -> None:
    """Apply Mica + sync titlebar colors to current appearance mode.

    No-op on non-Windows, pre-Win11, or if pywinstyles import fails.
    Two independent try blocks so a Mica failure doesn't skip header tinting.
    """
    try:
        import pywinstyles  # type: ignore

        pywinstyles.apply_style(window, "mica")
    except Exception:
        pass
    try:
        import pywinstyles  # type: ignore

        pywinstyles.change_header_color(window, pick(BG_CHROME))
        pywinstyles.change_title_color(window, pick(TEXT_PRIMARY))
    except Exception:
        pass


# ── App icon (generated at runtime with PIL) ─────────────────────────────────
def make_app_icon_photo():
    """Generate the app icon as a tk PhotoImage. Returns None on PIL failure."""
    try:
        from PIL import Image, ImageDraw, ImageTk
    except Exception:
        return None

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Rounded square, Apple system blue
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=14, fill="#007AFF")
    # White speech bubble body
    draw.rounded_rectangle((14, 18, 50, 42), radius=8, fill="white")
    # Bubble tail
    draw.polygon([(22, 42), (30, 42), (22, 50)], fill="white")
    return ImageTk.PhotoImage(img)
