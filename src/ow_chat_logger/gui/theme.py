from __future__ import annotations

import hashlib
import tkinter.font as tkfont
from pathlib import Path

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

# Accents — runtime-mutable so a Settings preset can swap them live.
# CTk widgets that capture references to these lists (e.g. via ``text_color=T.ACCENT``)
# pick up the new values on the next redraw, so :func:`set_accent` followed by a
# widget-tree refresh is enough to retheme the whole app.
ACCENT_PRESET_NAMES: tuple[str, ...] = (
    "blue",
    "indigo",
    "violet",
    "emerald",
    "amber",
    "rose",
    "pink",
    "cyan",
)

_ACCENT_PRESETS: dict[str, dict[str, tuple[str, str]]] = {
    "blue": {
        "main": ("#007AFF", "#0A84FF"),  # Apple system blue (default)
        "hover": ("#0062cc", "#3395ff"),
        "subtle": ("#e8f0fe", "#1e2a3f"),
        "fg": ("#ffffff", "#ffffff"),
    },
    "indigo": {
        "main": ("#4f46e5", "#6366f1"),
        "hover": ("#4338ca", "#818cf8"),
        "subtle": ("#eef2ff", "#1f1f3a"),
        "fg": ("#ffffff", "#ffffff"),
    },
    "violet": {
        "main": ("#7c3aed", "#8b5cf6"),
        "hover": ("#6d28d9", "#a78bfa"),
        "subtle": ("#f3e8ff", "#2e1f48"),
        "fg": ("#ffffff", "#ffffff"),
    },
    "emerald": {
        "main": ("#16a34a", "#22c55e"),
        "hover": ("#15803d", "#4ade80"),
        "subtle": ("#dcfce7", "#0a2e1a"),
        "fg": ("#ffffff", "#0a0a0b"),
    },
    "amber": {
        "main": ("#d97706", "#f59e0b"),
        "hover": ("#b45309", "#fbbf24"),
        "subtle": ("#fef3c7", "#3b2a06"),
        "fg": ("#ffffff", "#0a0a0b"),
    },
    "rose": {
        "main": ("#e11d48", "#f43f5e"),
        "hover": ("#be123c", "#fb7185"),
        "subtle": ("#ffe4e6", "#3a141d"),
        "fg": ("#ffffff", "#ffffff"),
    },
    "pink": {
        # Distinct from rose (which leans red) — true magenta-pink, pulled
        # from Tailwind's pink-600/500 pair so it reads cleanly against both
        # light and dark surfaces.
        "main": ("#db2777", "#ec4899"),
        "hover": ("#be185d", "#f472b6"),
        "subtle": ("#fce7f3", "#3a0f24"),
        "fg": ("#ffffff", "#ffffff"),
    },
    "cyan": {
        "main": ("#0891b2", "#06b6d4"),
        "hover": ("#0e7490", "#22d3ee"),
        "subtle": ("#cffafe", "#0a2a32"),
        "fg": ("#ffffff", "#0a0a0b"),
    },
}

# Mutable lists — CTk re-resolves the (light, dark) pair on every redraw, so
# in-place mutation propagates to widgets that already captured the reference.
ACCENT = list(_ACCENT_PRESETS["blue"]["main"])
ACCENT_HOVER = list(_ACCENT_PRESETS["blue"]["hover"])
ACCENT_FG = list(_ACCENT_PRESETS["blue"]["fg"])
ACCENT_SUBTLE = list(_ACCENT_PRESETS["blue"]["subtle"])

_current_accent_name: str = "blue"


def set_accent(name: str) -> None:
    """Swap the global accent palette to one of :data:`ACCENT_PRESET_NAMES`.

    Falls back to ``"blue"`` for unknown names. Mutates the four ``ACCENT*``
    lists in place — does NOT trigger widget redraws on its own. Callers
    typically follow this with a tree-walk that calls ``_set_appearance_mode``
    on each CTk widget so they re-resolve the new color values.
    """
    global _current_accent_name
    preset = _ACCENT_PRESETS.get(name) or _ACCENT_PRESETS["blue"]
    _current_accent_name = name if name in _ACCENT_PRESETS else "blue"
    ACCENT[0], ACCENT[1] = preset["main"]
    ACCENT_HOVER[0], ACCENT_HOVER[1] = preset["hover"]
    ACCENT_SUBTLE[0], ACCENT_SUBTLE[1] = preset["subtle"]
    ACCENT_FG[0], ACCENT_FG[1] = preset["fg"]


def current_accent_name() -> str:
    return _current_accent_name


def accent_preset_swatch(name: str) -> str:
    """Return the dark-mode hex of a preset's main color — used for swatches."""
    preset = _ACCENT_PRESETS.get(name) or _ACCENT_PRESETS["blue"]
    return preset["main"][1]


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

# Channel-chip tinted backgrounds (18% alpha baked onto the card surface)
CHAT_TEAM_CHIP = ("#dbeafe", "#0a2540")
CHAT_ALL_CHIP = ("#fef3c7", "#3b2a06")
CHAT_HERO_CHIP = ("#dcfce7", "#0a2e1a")

# Avatar color pool — deterministic hash → hue. Muted so white initials read.
AVATAR_BG_POOL = (
    ("#4f46e5", "#6366f1"),  # indigo
    ("#0891b2", "#06b6d4"),  # cyan
    ("#059669", "#10b981"),  # emerald
    ("#ca8a04", "#eab308"),  # amber
    ("#dc2626", "#ef4444"),  # red
    ("#c026d3", "#d946ef"),  # fuchsia
    ("#7c3aed", "#8b5cf6"),  # violet
    ("#ea580c", "#f97316"),  # orange
)

# Radii — generous, Apple-ish
R_CARD = 16
R_BUTTON = 10
R_INPUT = 8
R_SWATCH = 7
R_PILL = 18
R_CHIP = 12
R_BADGE = 6

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


def font_display() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=22, weight="bold")


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


def font_badge() -> ctk.CTkFont:
    return ctk.CTkFont(family=ui_family(), size=10, weight="bold")


def font_mono() -> tuple[str, int]:
    return (mono_family(), 11)


# ── Mode helpers ─────────────────────────────────────────────────────────────
def is_dark() -> bool:
    return ctk.get_appearance_mode() == "Dark"


def pick(color) -> str:
    """Resolve a (light, dark) tuple/list or plain string to a hex for current mode."""
    if isinstance(color, (tuple, list)):
        return color[1] if is_dark() else color[0]
    return color


def avatar_color_for(name: str) -> tuple[str, str]:
    """Deterministic (light, dark) avatar background for a player name."""
    if not name:
        return AVATAR_BG_POOL[0]
    digest = hashlib.md5(name.lower().encode("utf-8")).digest()
    return AVATAR_BG_POOL[digest[0] % len(AVATAR_BG_POOL)]


# ── Win11 titlebar tint ──────────────────────────────────────────────────────
def apply_chrome(window) -> None:
    """Sync the DWM titlebar to the current appearance mode.

    We deliberately do NOT enable a Mica/Acrylic system backdrop. Mica looks
    nice but DWM re-samples the desktop wallpaper under the window on every
    resize tick, which throttles the apparent redraw rate on software-rendered
    Tk windows — the user sees "stutter" while dragging the window edge.
    A flat opaque background gives a much smoother resize. The titlebar is
    still tinted to match light/dark via :func:`refresh_chrome`.

    No-op on non-Windows, pre-Win11, or if the DWM call fails.
    """
    refresh_chrome(window)


def refresh_chrome(window) -> None:
    """Flip the DWM titlebar between light and dark in place — no flash.

    pywinstyles' ``change_header_color`` calls ``SetWindowCompositionAttribute``
    with WCA_ACCENT_POLICY=0 first, which forces DWM to re-composite the window
    chrome and produces the visible "almost close & reopen" flash on every
    appearance-mode toggle. We avoid that by calling ``DwmSetWindowAttribute``
    directly with ``DWMWA_USE_IMMERSIVE_DARK_MODE``: a single, idempotent DWM
    call that asks the OS to retint the titlebar to match its built-in light
    or dark theme. Mica stays on, no composition reset, no flash.
    """
    try:
        from ctypes import byref, c_int, sizeof, windll  # type: ignore[import-not-found]

        # Resolve the top-level HWND the same way pywinstyles does, but
        # without its ``update()`` side-effect which itself triggers a redraw.
        hwnd = windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            return
        dark = c_int(1 if is_dark() else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 on Win10 1903+/Win11.
        # 19 was the pre-1903 attribute id; try both for safety on older builds.
        for attr in (20, 19):
            try:
                windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, byref(dark), sizeof(dark))
                break
            except Exception:
                continue
    except Exception:
        pass


# ── Toolbar logo (small accent-gradient square, matches design) ──────────────
def make_toolbar_logo_photo(size: int = 22):
    """Accent-gradient rounded square shown before the app title in the toolbar.

    Returns a ``ctk.CTkImage`` so it picks up the current appearance mode
    automatically. Matches the 24×24 accent logo in the Console design.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

    px = size * 4  # oversample for crisp corners, then downscale

    def _render(hex_color: str):
        img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        mask = Image.new("L", (px, px), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, px - 1, px - 1), radius=int(px * 0.26), fill=255
        )
        # Vertical gradient from accent → ~80% accent for a subtle sheen.
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        grad = Image.new("RGB", (1, px), hex_color)
        gpx = grad.load()
        for y in range(px):
            t = y / (px - 1)
            gpx[0, y] = (
                int(r * (1 - 0.20 * t)),
                int(g * (1 - 0.20 * t)),
                int(b * (1 - 0.20 * t)),
            )
        grad = grad.resize((px, px))
        img.paste(grad, (0, 0), mask)
        return img.resize((size, size), Image.LANCZOS)

    light = _render(ACCENT[0])
    dark = _render(ACCENT[1])
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))


# ── App icon (generated at runtime with PIL) ─────────────────────────────────
def make_app_icon_photo():
    """Generate the app icon as a tk PhotoImage. Returns None on PIL failure.

    Used as a fallback path on non-Windows or when the .ico-based
    :func:`save_app_icon_ico` flow fails. On Windows prefer
    :func:`save_app_icon_ico` + ``Tk.iconbitmap`` for runtime refreshes —
    Tk's ``iconphoto`` doesn't reliably update the title-bar HICON after the
    window has been displayed once.
    """
    img = _render_app_icon_pil()
    if img is None:
        return None
    try:
        from PIL import ImageTk
    except Exception:
        return None
    return ImageTk.PhotoImage(img)


_app_icon_ico_path: Path | None = None


def save_app_icon_ico() -> Path | None:
    """Save the current accent-tinted app icon as a .ico in the system temp dir.

    Returns the on-disk path on success, ``None`` if PIL is missing or the
    write fails. Uses a stable temp filename so each accent change overwrites
    the same file — no temp-dir littering.

    Pair with ``Tk.iconbitmap(str(path))`` on Windows to actually refresh the
    title-bar / taskbar icon at runtime. ``iconbitmap`` calls into Win32's
    ``LoadImage`` + ``SendMessage(WM_SETICON)``, which the OS honors on every
    call — unlike ``iconphoto``, which Windows often serves from cache.
    """
    img = _render_app_icon_pil()
    if img is None:
        return None
    global _app_icon_ico_path
    if _app_icon_ico_path is None:
        import tempfile

        _app_icon_ico_path = Path(tempfile.gettempdir()) / "ow_chat_logger_icon.ico"
    try:
        img.save(
            _app_icon_ico_path,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
        )
        return _app_icon_ico_path
    except Exception:
        return None


def _render_app_icon_pil():
    """Render the accent-gradient + speech-bubble icon as an RGBA PIL image.

    Shared by both the PhotoImage and .ico paths. Returns ``None`` if PIL
    isn't available.

    Design: vertical gradient rounded square in the current accent color
    (derived from :data:`ACCENT`), with a white speech bubble overlay and
    accent-tinted lines inside.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

    size = 64

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _shift(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
        # factor < 1 darkens, factor > 1 brightens, both clamped to 0..255.
        return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]

    # Use the dark-mode accent hex as the icon's "base" — it tends to be the
    # more saturated of the (light, dark) pair and reads well on both light
    # and dark Windows taskbars. Top stop is a darkened variant, bottom stop
    # a brightened one, giving a soft top-to-bottom sheen.
    base_rgb = _hex_to_rgb(ACCENT[1])
    top = _shift(base_rgb, 0.78)
    bot = _shift(base_rgb, 1.10)

    grad = Image.new("RGB", (1, size), ACCENT[1])
    gpx = grad.load()
    for y in range(size):
        t = y / (size - 1)
        gpx[0, y] = (
            int(top[0] + (bot[0] - top[0]) * t),
            int(top[1] + (bot[1] - top[1]) * t),
            int(top[2] + (bot[2] - top[2]) * t),
        )
    grad = grad.resize((size, size))

    # Round-rect mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=15, fill=255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    # Speech bubble — rounded rect + tail (stroke-matched to icons.py)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((14, 17, 50, 42), radius=9, fill=(255, 255, 255, 240))
    draw.polygon([(22, 42), (32, 42), (23, 52)], fill=(255, 255, 255, 240))
    # Three chat lines inside the bubble — accent-tinted at ~70% opacity.
    line_color = (*base_rgb, 180)
    for dy in (23, 29, 35):
        draw.rounded_rectangle((20, dy, 44, dy + 2), radius=1, fill=line_color)

    return img
