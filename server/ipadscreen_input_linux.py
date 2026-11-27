"""Comandos de entrada del visor nativo en Linux/X11, mediante XTest.

Ofrece la misma interfaz que server.ipadscreen_input (Windows). XTest no
necesita permisos de administrador: alcanza con estar en la sesión X11.
"""

import base64
import binascii
import ctypes
import ctypes.util

from server.ipadscreen_input import KEYS as WINDOWS_KEYS, MODIFIERS as WINDOWS_MODIFIERS
from server.ipadscreen_input import picture_point


# Mismos nombres que en Windows, con su keysym de X11.
KEYS = {
    "backspace": "BackSpace", "tab": "Tab", "enter": "Return", "escape": "Escape",
    "space": "space", "pageup": "Prior", "pagedown": "Next", "end": "End", "home": "Home",
    "left": "Left", "up": "Up", "right": "Right", "down": "Down",
    "insert": "Insert", "delete": "Delete", "win": "Super_L",
    **{f"f{number}": f"F{number}" for number in range(1, 13)},
}
MODIFIERS = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L", "win": "Super_L"}
BUTTONS = {"left": 1, "middle": 2, "right": 3}
WHEEL_UP, WHEEL_DOWN = 4, 5
assert KEYS.keys() == WINDOWS_KEYS.keys() and MODIFIERS.keys() == WINDOWS_MODIFIERS.keys()


class X11:
    """Una conexión propia a la pantalla X11 y las funciones que usamos."""

    def __init__(self):
        xlib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xtst = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")
        ulong, pointer = ctypes.c_ulong, ctypes.c_void_p
        xlib.XOpenDisplay.restype = pointer
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XDefaultRootWindow.restype = ulong
        xlib.XDefaultRootWindow.argtypes = [pointer]
        xlib.XStringToKeysym.restype = ulong
        xlib.XStringToKeysym.argtypes = [ctypes.c_char_p]
        xlib.XKeysymToKeycode.restype = ctypes.c_ubyte
        xlib.XKeysymToKeycode.argtypes = [pointer, ulong]
        xlib.XDisplayKeycodes.argtypes = [pointer, ctypes.POINTER(ctypes.c_int),
                                          ctypes.POINTER(ctypes.c_int)]
        xlib.XGetKeyboardMapping.restype = ctypes.POINTER(ulong)
        xlib.XGetKeyboardMapping.argtypes = [pointer, ctypes.c_ubyte, ctypes.c_int,
                                             ctypes.POINTER(ctypes.c_int)]
        xlib.XChangeKeyboardMapping.argtypes = [pointer, ctypes.c_int, ctypes.c_int,
                                                ctypes.POINTER(ulong), ctypes.c_int]
        xlib.XFree.argtypes = [pointer]
        xlib.XFlush.argtypes = [pointer]
        xlib.XSync.argtypes = [pointer, ctypes.c_int]
        xlib.XQueryPointer.restype = ctypes.c_int
        xlib.XQueryPointer.argtypes = [pointer, ulong, ctypes.POINTER(ulong), ctypes.POINTER(ulong),
                                       *[ctypes.POINTER(ctypes.c_int)] * 4,
                                       ctypes.POINTER(ctypes.c_uint)]
        xtst.XTestFakeMotionEvent.argtypes = [pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int, ulong]
        xtst.XTestFakeButtonEvent.argtypes = [pointer, ctypes.c_uint, ctypes.c_int, ulong]
        xtst.XTestFakeKeyEvent.argtypes = [pointer, ctypes.c_uint, ctypes.c_int, ulong]
        self.xlib, self.xtst = xlib, xtst
        self.display = xlib.XOpenDisplay(None)
        if not self.display:
            raise OSError("No se pudo abrir la pantalla X11")
        self.root = xlib.XDefaultRootWindow(self.display)
        self.scratch = self._free_keycodes()
        self.scratch_next = 0
        self.scratch_keysyms = {}

    def _keyboard_mapping(self, first, count):
        per_code = ctypes.c_int()
        table = self.xlib.XGetKeyboardMapping(self.display, first, count, ctypes.byref(per_code))
        try:
            return [[table[code * per_code.value + level] for level in range(per_code.value)]
                    for code in range(count)]
        finally:
            self.xlib.XFree(table)

    def _free_keycodes(self):
        """Códigos de tecla sin símbolo, para escribir caracteres que no están en el teclado."""
        low, high = ctypes.c_int(), ctypes.c_int()
        self.xlib.XDisplayKeycodes(self.display, ctypes.byref(low), ctypes.byref(high))
        mapping = self._keyboard_mapping(low.value, high.value - low.value + 1)
        return [low.value + index for index, symbols in enumerate(mapping)
                if not any(symbols)][-8:]

    def flush(self):
        self.xlib.XFlush(self.display)

    def pointer(self):
        root, child = ctypes.c_ulong(), ctypes.c_ulong()
        x, y, wx, wy = (ctypes.c_int() for _ in range(4))
        mask = ctypes.c_uint()
        same = self.xlib.XQueryPointer(self.display, self.root, ctypes.byref(root),
                                       ctypes.byref(child), ctypes.byref(x), ctypes.byref(y),
                                       ctypes.byref(wx), ctypes.byref(wy), ctypes.byref(mask))
        return bool(same), x.value, y.value

    def move(self, x, y):
        self.xtst.XTestFakeMotionEvent(self.display, -1, x, y, 0)

    def button(self, number, down):
        self.xtst.XTestFakeButtonEvent(self.display, number, int(down), 0)

    def keysym(self, name):
        return self.xlib.XStringToKeysym(name.encode("ascii"))

    def keycode(self, keysym):
        return self.xlib.XKeysymToKeycode(self.display, keysym)

    def key(self, code, down):
        self.xtst.XTestFakeKeyEvent(self.display, code, int(down), 0)

    def tap(self, codes):
        for code in codes:
            self.key(code, True)
        for code in reversed(codes):
            self.key(code, False)

    def character_keys(self, char):
        """Teclas que escriben el carácter: el código directo, con Shift o uno libre reasignado."""
        point = ord(char)
        keysym = point if 0x20 <= point <= 0x7E or 0xA0 <= point <= 0xFF else 0x01000000 + point
        code = self.keycode(keysym)
        if code:
            levels = self._keyboard_mapping(code, 1)[0]
            if levels and levels[0] == keysym:
                return [code]
            if len(levels) > 1 and levels[1] == keysym:
                return [self.keycode(self.keysym("Shift_L")), code]
        # Nivel AltGr o carácter ausente: se le asigna un código libre. Los
        # códigos rotan para que un evento todavía en cola no cambie de letra.
        if not self.scratch:
            return []
        if keysym in self.scratch_keysyms:
            return [self.scratch_keysyms[keysym]]
        code = self.scratch[self.scratch_next % len(self.scratch)]
        self.scratch_next += 1
        self.scratch_keysyms = {sym: used for sym, used in self.scratch_keysyms.items() if used != code}
        symbols = (ctypes.c_ulong * 2)(keysym, keysym)
        self.xlib.XChangeKeyboardMapping(self.display, code, 2, symbols, 1)
        self.xlib.XSync(self.display, 0)
        self.scratch_keysyms[keysym] = code
        return [code]


_x11 = None


def x11():
    global _x11
    if _x11 is None:
        _x11 = X11()
    return _x11


def cursor_position():
    """(visible, x, y) en píxeles del escritorio, como GetCursorPos en Windows."""
    return x11().pointer()


def move_to(x, y):
    x11().move(x, y)


def move_by(dx, dy):
    visible, x, y = x11().pointer()
    if visible:
        x11().move(x + dx, y + dy)


def type_text(text):
    display = x11()
    for char in text:
        if char == "\n":
            display.tap([display.keycode(display.keysym("Return"))])
        elif codes := display.character_keys(char):
            display.tap(codes)
    display.flush()


def combo_keys(value):
    """'ctrl+shift+t' -> códigos de tecla, o None si algo no está permitido."""
    *modifiers, last = value.split("+")
    if not 1 <= len(modifiers) <= 3 or len(set(modifiers)) != len(modifiers):
        return None
    if any(name not in MODIFIERS for name in modifiers):
        return None
    if last in KEYS:
        name = KEYS[last]
    elif len(last) == 1 and last.isascii() and last.isalnum():
        name = last.lower()
    else:
        return None
    display = x11()
    codes = [display.keycode(display.keysym(MODIFIERS[item])) for item in modifiers]
    codes.append(display.keycode(display.keysym(name)))
    return codes if all(codes) else None


def release_buttons(held):
    """Suelta lo que el visor dejó apretado al cortarse el enlace."""
    if held:
        display = x11()
        for name in sorted(held):
            display.button(BUTTONS[name], False)
        display.flush()
    held.clear()


def apply_input(line, monitor=None, held=None):
    """Aplica un comando. Devuelve True cuando movió el puntero."""
    command, separator, value = line.partition(b"=")
    if not separator:
        return False
    display = x11()
    moved = False
    try:
        value = value.decode("ascii")
        if command == b"move":
            x, y = map(int, value.split(","))
            if abs(x) <= 400 and abs(y) <= 400:
                move_by(x, y)
                moved = True
        elif command == b"at" and monitor is not None:
            x, y = map(int, value.split(","))
            if 0 <= x <= 10000 and 0 <= y <= 10000:
                move_to(*picture_point(monitor, x, y))
                moved = True
        elif command == b"click" and value in BUTTONS:
            display.button(BUTTONS[value], True)
            display.button(BUTTONS[value], False)
        elif command == b"button" and value in ("down", "up"):
            display.button(BUTTONS["left"], value == "down")
            if held is not None:
                (held.add if value == "down" else held.discard)("left")
        elif command == b"scroll":
            amount = int(value)
            if -12 <= amount <= 12:
                # Positivo sube, como la rueda de Windows.
                wheel = WHEEL_UP if amount > 0 else WHEEL_DOWN
                for _ in range(abs(amount)):
                    display.button(wheel, True)
                    display.button(wheel, False)
        elif command == b"key" and value in KEYS:
            code = display.keycode(display.keysym(KEYS[value]))
            if code:
                display.tap([code])
        elif command == b"combo":
            codes = combo_keys(value)
            if codes:
                display.tap(codes)
        elif command == b"text" and len(value) <= 1024:
            text = base64.b64decode(value, validate=True).decode("utf-8")
            if text and all(ord(char) >= 32 and ord(char) != 127 for char in text):
                type_text(text)
    except (ValueError, UnicodeError, binascii.Error):
        pass
    display.flush()
    return moved
