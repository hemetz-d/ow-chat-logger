"""HSV/hex color helpers shared between the main window and settings panel.

OpenCV HSV convention: H ∈ [0, 180], S ∈ [0, 255], V ∈ [0, 255].
"""

from __future__ import annotations

import colorsys


def hsv_bounds_to_hex(lower: list[int], upper: list[int]) -> str:
    h = ((lower[0] + upper[0]) / 2) / 180.0
    s = ((lower[1] + upper[1]) / 2) / 255.0
    v = upper[2] / 255.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def hex_to_hsv_bounds(hex_color: str, hue_tol: int = 14) -> tuple[list[int], list[int]]:
    hx = hex_color.lstrip("#")
    r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, s, _v = colorsys.rgb_to_hsv(r, g, b)
    h_ocv = int(h * 180)
    s_ocv = int(s * 255)
    lower = [max(0, h_ocv - hue_tol), max(0, s_ocv - 80), 50]
    upper = [min(180, h_ocv + hue_tol), 255, 255]
    return lower, upper


def hue_tol_from_bounds(lower: list[int], upper: list[int]) -> int:
    """Recover the hue tolerance that produced a given (lower, upper) pair.

    Returns half the hue span, clamped to the slider range.
    """
    span = max(0, upper[0] - lower[0])
    return max(5, min(30, span // 2))
