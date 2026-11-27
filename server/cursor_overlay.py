"""Dibuja el cursor del mouse sobre capturas de pantalla (Windows)."""

import sys

from PIL import Image, ImageDraw


def draw_cursor(image: Image.Image, region: dict[str, int]) -> Image.Image:
    if sys.platform != "win32":
        return image

    try:
        import ctypes
        from ctypes import wintypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return image

        rx = pt.x - region["left"]
        ry = pt.y - region["top"]
        if not (0 <= rx < image.width and 0 <= ry < image.height):
            return image

        draw = ImageDraw.Draw(image)
        x, y = rx, ry
        # Flecha estilo cursor de Windows
        draw.polygon(
            [
                (x, y),
                (x, y + 20),
                (x + 5, y + 15),
                (x + 12, y + 24),
                (x + 15, y + 21),
                (x + 8, y + 12),
                (x + 15, y + 9),
            ],
            fill="white",
            outline="black",
        )
    except Exception:
        pass

    return image
