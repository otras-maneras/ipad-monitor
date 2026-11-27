"""Información de ventanas de Windows para capturar una sola. En otros sistemas no hay ventanas para elegir."""

from __future__ import annotations

import ctypes
import sys

WINDOWS = sys.platform.startswith("win")
if WINDOWS:
    from ctypes import wintypes


def _is_window_visible(hwnd: int) -> bool:
    user32 = ctypes.windll.user32
    return bool(user32.IsWindowVisible(hwnd))


def _get_window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def list_windows(min_width: int = 100, min_height: int = 50) -> list[dict[str, int | str]]:
    """Lista ventanas visibles de Windows con título y posición."""
    if not WINDOWS:
        return []
    user32 = ctypes.windll.user32
    results: list[dict[str, int | str]] = []

    def enum_callback(hwnd: int, _extra: int) -> int:
        if not _is_window_visible(hwnd):
            return 1
        title = _get_window_text(hwnd)
        if not title or title == "Program Manager":
            return 1
        rect = _get_window_rect(hwnd)
        if not rect:
            return 1
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if width < min_width or height < min_height:
            return 1
        results.append(
            {
                "hwnd": hwnd,
                "title": title,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
        )
        return 1

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
    return results


def get_window_rect(hwnd: int) -> dict[str, int] | None:
    """Devuelve el rectángulo actual de una ventana."""
    if not WINDOWS:
        return None
    rect = _get_window_rect(hwnd)
    if not rect:
        return None
    left, top, right, bottom = rect
    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
    }


def is_window_valid(hwnd: int) -> bool:
    if not WINDOWS:
        return False
    user32 = ctypes.windll.user32
    return bool(user32.IsWindow(hwnd))
