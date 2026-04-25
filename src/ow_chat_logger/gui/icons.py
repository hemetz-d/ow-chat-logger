"""Lucide-style stroke icons rendered at runtime via PIL.

Each icon is drawn at 4x the target size then downscaled for a crisp AA edge.
Both light and dark variants are rendered once and wrapped in a CTkImage so
CustomTkinter picks the right one per appearance mode automatically.

Keep the icon set small and consistent — 1.5px stroke at logical size, round
caps, no fills. Designed to pair with the Apple/Lucide aesthetic already used
in theme.py.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

_CACHE: dict[tuple[str, int], "ctk.CTkImage | None"] = {}


def _with_pil(fn: Callable):
    """Decorator that returns None if PIL is unavailable — keeps icon calls
    safe at import time on minimal environments."""

    def wrapper(*args, **kwargs):
        try:
            from PIL import Image  # noqa: F401
        except Exception:
            return None
        return fn(*args, **kwargs)

    return wrapper


def _stroke_px(size: int) -> int:
    """Upscaled stroke width — 1.5px at logical size, scaled to 4x canvas."""
    return max(4, int(size * 4 * 1.5 / 16))


def _blank(size: int):
    from PIL import Image

    return Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))


def _downscale(img, size: int):
    from PIL import Image

    return img.resize((size, size), Image.LANCZOS)


# ── Individual icon renderers (draw at 4x scale, downscale at the end) ──────


def _draw_gear(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    w = _stroke_px(size)
    cx = cy = size * 2
    # Outer toothed circle — 8 short rectangles around the rim + inner ring
    outer_r = int(size * 4 * 0.40)
    inner_r = int(size * 4 * 0.16)
    import math

    for i in range(8):
        a = math.radians(i * 45)
        x1 = cx + math.cos(a) * outer_r
        y1 = cy + math.sin(a) * outer_r
        x2 = cx + math.cos(a) * (outer_r + size * 4 * 0.08)
        y2 = cy + math.sin(a) * (outer_r + size * 4 * 0.08)
        d.line([(x1, y1), (x2, y2)], fill=color, width=w)
    d.ellipse(
        (cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r),
        outline=color,
        width=w,
    )
    d.ellipse(
        (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
        outline=color,
        width=w,
    )
    return img


def _draw_play(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    # Filled triangle pointing right
    d.polygon(
        [(s * 0.30, s * 0.22), (s * 0.30, s * 0.78), (s * 0.80, s * 0.50)],
        fill=color,
    )
    return img


def _draw_stop(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    d.rounded_rectangle(
        (s * 0.28, s * 0.28, s * 0.72, s * 0.72),
        radius=int(s * 0.06),
        fill=color,
    )
    return img


def _draw_sun(size: int, color: str):
    from PIL import ImageDraw
    import math

    img = _blank(size)
    d = ImageDraw.Draw(img)
    w = _stroke_px(size)
    cx = cy = size * 2
    r = int(size * 4 * 0.20)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    ray = size * 4 * 0.15
    gap = size * 4 * 0.06
    for i in range(8):
        a = math.radians(i * 45)
        x1 = cx + math.cos(a) * (r + gap)
        y1 = cy + math.sin(a) * (r + gap)
        x2 = cx + math.cos(a) * (r + gap + ray)
        y2 = cy + math.sin(a) * (r + gap + ray)
        d.line([(x1, y1), (x2, y2)], fill=color, width=w)
    return img


def _draw_moon(size: int, color: str):
    from PIL import ImageDraw, Image

    img = _blank(size)
    s = size * 4
    w = _stroke_px(size)
    # Crescent: outer circle minus offset circle
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((s * 0.20, s * 0.20, s * 0.80, s * 0.80), fill=255)
    md.ellipse((s * 0.35, s * 0.15, s * 0.95, s * 0.75), fill=0)
    # Shrink mask inward by w to get outline
    outline = Image.new("L", (s, s), 0)
    od = ImageDraw.Draw(outline)
    od.ellipse((s * 0.20, s * 0.20, s * 0.80, s * 0.80), outline=255, width=w)
    od.ellipse((s * 0.35, s * 0.15, s * 0.95, s * 0.75), fill=0)
    color_layer = Image.new("RGBA", (s, s), color)
    img.paste(color_layer, (0, 0), outline)
    return img


def _draw_auto(size: int, color: str):
    """Half-moon dial — system appearance glyph."""
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    r = int(s * 0.30)
    cx = cy = s // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    d.pieslice((cx - r, cy - r, cx + r, cy + r), start=90, end=270, fill=color)
    return img


def _draw_search(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    r = int(s * 0.22)
    cx, cy = int(s * 0.42), int(s * 0.42)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    d.line(
        [(cx + r * 0.7, cy + r * 0.7), (s * 0.78, s * 0.78)],
        fill=color,
        width=w,
    )
    return img


def _draw_jump_down(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    # Down chevron
    d.line(
        [(s * 0.25, s * 0.40), (s * 0.50, s * 0.65), (s * 0.75, s * 0.40)],
        fill=color,
        width=w,
        joint="curve",
    )
    return img


def _draw_message_square(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    d.rounded_rectangle(
        (s * 0.18, s * 0.20, s * 0.82, s * 0.68),
        radius=int(s * 0.10),
        outline=color,
        width=w,
    )
    d.line(
        [(s * 0.35, s * 0.68), (s * 0.30, s * 0.82), (s * 0.48, s * 0.68)],
        fill=color,
        width=w,
        joint="curve",
    )
    return img


def _draw_chevron_right(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    d.line(
        [(s * 0.40, s * 0.25), (s * 0.62, s * 0.50), (s * 0.40, s * 0.75)],
        fill=color,
        width=w,
        joint="curve",
    )
    return img


def _draw_chevron_down(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    d.line(
        [(s * 0.25, s * 0.40), (s * 0.50, s * 0.62), (s * 0.75, s * 0.40)],
        fill=color,
        width=w,
        joint="curve",
    )
    return img


def _draw_check(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    d.line(
        [(s * 0.22, s * 0.52), (s * 0.42, s * 0.72), (s * 0.78, s * 0.30)],
        fill=color,
        width=w,
        joint="curve",
    )
    return img


def _draw_eye(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    # Almond outline — two arcs meeting at the corners
    d.chord((s * 0.10, s * 0.28, s * 0.90, s * 0.90), 180, 360, outline=color, width=w)
    d.chord((s * 0.10, s * 0.10, s * 0.90, s * 0.72), 0, 180, outline=color, width=w)
    # Pupil
    r = int(s * 0.12)
    cx = cy = s // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    return img


def _draw_alert(size: int, color: str):
    from PIL import ImageDraw

    img = _blank(size)
    d = ImageDraw.Draw(img)
    s = size * 4
    w = _stroke_px(size)
    # Triangle outline
    d.polygon(
        [(s * 0.50, s * 0.18), (s * 0.86, s * 0.80), (s * 0.14, s * 0.80)],
        outline=color,
        width=w,
    )
    # Exclamation bar + dot
    d.line([(s * 0.50, s * 0.38), (s * 0.50, s * 0.58)], fill=color, width=w)
    d.ellipse(
        (s * 0.47, s * 0.65, s * 0.53, s * 0.71),
        fill=color,
    )
    return img


_RENDERERS: dict[str, Callable] = {
    "gear": _draw_gear,
    "play": _draw_play,
    "stop": _draw_stop,
    "sun": _draw_sun,
    "moon": _draw_moon,
    "auto": _draw_auto,
    "search": _draw_search,
    "jump_down": _draw_jump_down,
    "message_square": _draw_message_square,
    "chevron_right": _draw_chevron_right,
    "chevron_down": _draw_chevron_down,
    "check": _draw_check,
    "alert": _draw_alert,
    "eye": _draw_eye,
}


@_with_pil
def icon(name: str, size: int = 16, color: str | tuple[str, str] | None = None):
    """Return a CTkImage of the named icon at the given logical pixel size.

    `color` may be a single hex, a (light, dark) tuple, or None to use the
    primary text color for each mode. Cached by (name, size) assuming the
    default text color — callers passing a custom color get a fresh image.
    """
    from PIL import Image  # noqa: F401

    from ow_chat_logger.gui import theme as T

    renderer = _RENDERERS.get(name)
    if renderer is None:
        return None

    use_cache = color is None
    key = (name, size)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    if color is None:
        light_color = T.TEXT_PRIMARY[0]
        dark_color = T.TEXT_PRIMARY[1]
    elif isinstance(color, (tuple, list)):
        light_color, dark_color = color[0], color[1]
    else:
        light_color = dark_color = color

    light_img = _downscale(renderer(size, light_color), size)
    dark_img = _downscale(renderer(size, dark_color), size)
    img = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))

    if use_cache:
        _CACHE[key] = img
    return img
