"""Puntero y teclado para el modo web: PyAutoGUI en Windows, XTest en Linux/X11.

Las páginas envían nombres de tecla de PyAutoGUI ("enter", "esc", "win",
"ctrl"...). En Linux se traducen a keysyms de X11.
"""

from __future__ import annotations

import sys

WINDOWS = sys.platform.startswith("win")

if WINDOWS:
    import ctypes

    import pyautogui

    pyautogui.FAILSAFE = False
else:
    from server import ipadscreen_input_linux as x11

    # Nombre de PyAutoGUI -> keysym de X11 (lo que no está se busca tal cual).
    _KEYSYMS = {
        "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape",
        "backspace": "BackSpace", "tab": "Tab", "space": "space", "delete": "Delete",
        "del": "Delete", "insert": "Insert", "home": "Home", "end": "End",
        "pageup": "Prior", "pagedown": "Next", "left": "Left", "right": "Right",
        "up": "Up", "down": "Down", "win": "Super_L", "winleft": "Super_L",
        "ctrl": "Control_L", "ctrlleft": "Control_L", "alt": "Alt_L", "altleft": "Alt_L",
        "shift": "Shift_L", "shiftleft": "Shift_L", "capslock": "Caps_Lock",
        "printscreen": "Print",
        "playpause": "XF86AudioPlay", "nexttrack": "XF86AudioNext", "prevtrack": "XF86AudioPrev",
        "volumemute": "XF86AudioMute", "volumeup": "XF86AudioRaiseVolume",
        "volumedown": "XF86AudioLowerVolume",
        **{f"f{n}": f"F{n}" for n in range(1, 13)},
    }

    def _keycode(name: str) -> int:
        display = x11.x11()
        keysym = _KEYSYMS.get(name.lower(), name if len(name) > 1 else name.lower())
        return display.keycode(display.keysym(keysym))


def move_rel(dx: float, dy: float) -> None:
    if WINDOWS:
        pyautogui.moveRel(dx, dy, _pause=False)
    else:
        x11.move_by(int(round(dx)), int(round(dy)))
        x11.x11().flush()


def move_to(x: int, y: int) -> None:
    if WINDOWS:
        ctypes.windll.user32.SetCursorPos(x, y)
    else:
        x11.move_to(x, y)
        x11.x11().flush()


def click(button: str) -> None:
    if WINDOWS:
        pyautogui.click(button=button, _pause=False)
    else:
        x11.apply_input(b"click=" + button.encode())


# Las páginas mandan unidades de rueda de Windows (120 = un paso) en pedazos
# chicos para un scroll suave. X11 solo tiene pasos enteros: se acumulan y un
# paso sale cada 40 unidades (valor inicial, sin comparar todavía con Windows).
_WHEEL_UNITS = 40
_wheel = 0


def scroll(amount: int) -> None:
    global _wheel
    if WINDOWS:
        pyautogui.scroll(amount, _pause=False)
        return
    _wheel += amount
    steps = int(_wheel / _WHEEL_UNITS)
    if steps:
        _wheel -= steps * _WHEEL_UNITS
        x11.apply_input(f"scroll={max(-12, min(12, steps))}".encode())


def zoom(amount: int) -> None:
    if WINDOWS:
        pyautogui.keyDown("ctrl", _pause=False)
        pyautogui.scroll(amount, _pause=False)
        pyautogui.keyUp("ctrl", _pause=False)
    else:
        display = x11.x11()
        ctrl = _keycode("ctrl")
        display.key(ctrl, True)
        scroll(amount)
        display.key(ctrl, False)
        display.flush()


def press(key: str) -> None:
    if WINDOWS:
        pyautogui.press(key, _pause=False)
    else:
        code = _keycode(key)
        if code:
            x11.x11().tap([code])
            x11.x11().flush()


def hotkey(keys: list[str]) -> None:
    if WINDOWS:
        pyautogui.hotkey(*keys, _pause=False)
    else:
        codes = [_keycode(key) for key in keys]
        if all(codes):
            x11.x11().tap(codes)
            x11.x11().flush()


def write(text: str) -> None:
    if WINDOWS:
        pyautogui.write(text, interval=0.015, _pause=False)
    else:
        x11.type_text(text)
