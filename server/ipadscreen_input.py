"""Validated input commands for the paired native viewer.

Everything goes through SendInput. PyAutoGUI was dropped here because its
fail-safe swallowed every command once the pointer reached a screen corner.
"""

import base64
import binascii
import ctypes
import struct
from ctypes import wintypes


OUTPUT_SIZE = (1024, 768)

# name -> (virtual key, extended)
KEYS = {
    "backspace": (0x08, False), "tab": (0x09, False), "enter": (0x0D, False),
    "escape": (0x1B, False), "space": (0x20, False),
    "pageup": (0x21, True), "pagedown": (0x22, True), "end": (0x23, True), "home": (0x24, True),
    "left": (0x25, True), "up": (0x26, True), "right": (0x27, True), "down": (0x28, True),
    "insert": (0x2D, True), "delete": (0x2E, True), "win": (0x5B, True),
    **{f"f{number}": (0x6F + number, False) for number in range(1, 13)},
}
MODIFIERS = {"ctrl": (0x11, False), "alt": (0x12, False), "shift": (0x10, False), "win": (0x5B, True)}
BUTTONS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}

KEY_EXTENDED, KEY_UP, KEY_UNICODE = 1, 2, 4
MOUSE_MOVE, MOUSE_WHEEL, MOUSE_VIRTUAL_DESK, MOUSE_ABSOLUTE = 0x0001, 0x0800, 0x4000, 0x8000


class KeyboardInput(ctypes.Structure):
    _fields_ = [("vk", wintypes.WORD), ("scan", wintypes.WORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("extra", ctypes.c_size_t)]


class MouseInput(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG),
                ("data", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]


class InputData(ctypes.Union):
    _fields_ = [("keyboard", KeyboardInput), ("mouse", MouseInput)]


class Input(ctypes.Structure):
    _fields_ = [("kind", wintypes.DWORD), ("data", InputData)]


def send(events):
    if events:
        batch = (Input * len(events))(*events)
        ctypes.windll.user32.SendInput(len(batch), batch, ctypes.sizeof(Input))


def mouse_event(flags, x=0, y=0, data=0):
    return Input(0, InputData(mouse=MouseInput(x, y, data & 0xFFFFFFFF, flags, 0, 0)))


def key_event(key, up=False):
    virtual_key, extended = key
    flags = (KEY_EXTENDED if extended else 0) | (KEY_UP if up else 0)
    return Input(1, InputData(keyboard=KeyboardInput(virtual_key, 0, flags, 0, 0)))


def move_to(x, y):
    """Absolute move in desktop pixels, exact on every monitor."""
    metrics = ctypes.windll.user32.GetSystemMetrics
    left, top, width, height = (metrics(index) for index in (76, 77, 78, 79))
    x = min(max(x, left), left + width - 1) - left
    y = min(max(y, top), top + height - 1) - top
    # Windows maps 0..65535 back with truncation; rounding up lands on the pixel.
    send([mouse_event(MOUSE_MOVE | MOUSE_ABSOLUTE | MOUSE_VIRTUAL_DESK,
                      -(-x * 65536 // width), -(-y * 65536 // height))])


def move_by(dx, dy):
    point = wintypes.POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        move_to(point.x + dx, point.y + dy)


def picture_point(monitor, x, y):
    """Map a 0..10000 point of the 1024x768 output to desktop pixels."""
    width, height = monitor["width"], monitor["height"]
    scale = min(OUTPUT_SIZE[0] / width, OUTPUT_SIZE[1] / height)
    picture_width = max(2, int(width * scale) // 2 * 2)
    picture_height = max(2, int(height * scale) // 2 * 2)
    inside_x = (x * OUTPUT_SIZE[0] / 10000 - (OUTPUT_SIZE[0] - picture_width) / 2) / picture_width
    inside_y = (y * OUTPUT_SIZE[1] / 10000 - (OUTPUT_SIZE[1] - picture_height) / 2) / picture_height
    return (monitor["left"] + min(max(int(inside_x * width), 0), width - 1),
            monitor["top"] + min(max(int(inside_y * height), 0), height - 1))


def type_unicode(text):
    events = []
    for (code,) in struct.iter_unpack("<H", text.encode("utf-16-le")):
        events.append(Input(1, InputData(keyboard=KeyboardInput(0, code, KEY_UNICODE, 0, 0))))
        events.append(Input(1, InputData(keyboard=KeyboardInput(0, code, KEY_UNICODE | KEY_UP, 0, 0))))
    send(events)


def combo_keys(value):
    """'ctrl+shift+t' -> list of keys, or None when anything is not allowed."""
    *modifiers, last = value.split("+")
    if not 1 <= len(modifiers) <= 3 or len(set(modifiers)) != len(modifiers):
        return None
    if any(name not in MODIFIERS for name in modifiers):
        return None
    if last in KEYS:
        key = KEYS[last]
    elif len(last) == 1 and last.isascii() and last.isalnum():
        key = (ord(last.upper()), False)
    else:
        return None
    return [MODIFIERS[name] for name in modifiers] + [key]


def release_buttons(held):
    """Let go of anything the viewer left pressed when the link drops."""
    send([mouse_event(BUTTONS[name][1]) for name in sorted(held)])
    held.clear()


def apply_input(line, monitor=None, held=None):
    """Apply one command. Returns True when it moved the pointer."""
    command, separator, value = line.partition(b"=")
    if not separator:
        return False
    try:
        value = value.decode("ascii")
        if command == b"move":
            x, y = map(int, value.split(","))
            if abs(x) <= 400 and abs(y) <= 400:
                move_by(x, y)
                return True
        elif command == b"at" and monitor is not None:
            x, y = map(int, value.split(","))
            if 0 <= x <= 10000 and 0 <= y <= 10000:
                move_to(*picture_point(monitor, x, y))
                return True
        elif command == b"click" and value in BUTTONS:
            down, up = BUTTONS[value]
            send([mouse_event(down), mouse_event(up)])
        elif command == b"button" and value in ("down", "up"):
            send([mouse_event(BUTTONS["left"][value == "up"])])
            if held is not None:
                (held.add if value == "down" else held.discard)("left")
        elif command == b"scroll":
            amount = int(value)
            if -12 <= amount <= 12:
                send([mouse_event(MOUSE_WHEEL, data=amount * 120)])
        elif command == b"key" and value in KEYS:
            send([key_event(KEYS[value]), key_event(KEYS[value], up=True)])
        elif command == b"combo":
            keys = combo_keys(value)
            if keys:
                send([key_event(key) for key in keys] +
                     [key_event(key, up=True) for key in reversed(keys)])
        elif command == b"text" and len(value) <= 1024:
            text = base64.b64decode(value, validate=True).decode("utf-8")
            if text and all(ord(char) >= 32 and ord(char) != 127 for char in text):
                type_unicode(text)
    except (ValueError, UnicodeError, binascii.Error):
        pass
    return False
