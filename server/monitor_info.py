"""Resolución lógica de monitores en Windows (corrige escala DPI 125%, etc.)."""

from __future__ import annotations

import sys
from typing import Any


def _logical_from_physical(width: int, height: int, dpi_x: int, dpi_y: int) -> tuple[int, int, int]:
    dpi_x = max(int(dpi_x or 96), 96)
    dpi_y = max(int(dpi_y or 96), 96)
    logical_w = max(int(round(width * 96 / dpi_x)), 1)
    logical_h = max(int(round(height * 96 / dpi_y)), 1)
    scale = max(int(round(dpi_x / 96 * 100)), 100)
    return logical_w, logical_h, scale


def _windows_monitor_meta() -> list[dict[str, Any]]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    shcore = getattr(ctypes.windll, "shcore", None)

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MDT_EFFECTIVE_DPI = 0
    results: list[dict[str, Any]] = []

    def _callback(hmonitor, _hdc, _rect, _data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return 1

        physical_w = info.rcMonitor.right - info.rcMonitor.left
        physical_h = info.rcMonitor.bottom - info.rcMonitor.top
        dpi_x, dpi_y = 96, 96

        if shcore is not None:
            try:
                dx = wintypes.UINT()
                dy = wintypes.UINT()
                if shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                    dpi_x, dpi_y = int(dx.value), int(dy.value)
            except Exception:
                pass

        logical_w, logical_h, scale = _logical_from_physical(physical_w, physical_h, dpi_x, dpi_y)
        results.append(
            {
                "left": int(info.rcMonitor.left),
                "top": int(info.rcMonitor.top),
                "width": physical_w,
                "height": physical_h,
                "logical_width": logical_w,
                "logical_height": logical_h,
                "scale_percent": scale,
                "is_primary": bool(info.dwFlags & 1),
            }
        )
        return 1

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(RECT),
        ctypes.c_double,
    )
    user32.EnumDisplayMonitors(0, 0, callback_type(_callback), 0)
    return results


def enrich_monitor(physical: dict[str, int]) -> dict[str, int | str | bool]:
    """Añade resolución lógica emparejando por posición con monitores de Windows."""
    out = dict(physical)
    out["logical_width"] = int(physical["width"])
    out["logical_height"] = int(physical["height"])
    out["scale_percent"] = 100

    if sys.platform != "win32":
        return out

    try:
        win_monitors = _windows_monitor_meta()
    except Exception:
        return out

    left = int(physical.get("left", 0))
    top = int(physical.get("top", 0))
    width = int(physical.get("width", 0))
    height = int(physical.get("height", 0))

    best = None
    best_score = -1
    for meta in win_monitors:
        score = 0
        if meta["left"] == left:
            score += 2
        if meta["top"] == top:
            score += 2
        if meta["width"] == width:
            score += 1
        if meta["height"] == height:
            score += 1
        if score > best_score:
            best_score = score
            best = meta

    if best and best_score >= 3:
        out["logical_width"] = int(best["logical_width"])
        out["logical_height"] = int(best["logical_height"])
        out["scale_percent"] = int(best["scale_percent"])
        out["is_primary"] = bool(best.get("is_primary"))

    return out
