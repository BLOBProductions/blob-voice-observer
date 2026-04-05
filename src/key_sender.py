"""Win32 SendInput keystroke injection for digit keys 0-9.

Uses SendInput (not keybd_event or the keyboard library) because:
1. SendInput reliably injects into DirectX/fullscreen games
2. keybd_event is deprecated and ignored by modern game input handlers
3. The keyboard library uses hooks that some anti-cheat blocks

Requires admin privileges if the target window (VALORANT) is elevated.
"""

import ctypes
from ctypes import wintypes

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VK_CODES = {
    0: 0x30,
    1: 0x31,
    2: 0x32,
    3: 0x33,
    4: 0x34,
    5: 0x35,
    6: 0x36,
    7: 0x37,
    8: 0x38,
    9: 0x39,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("_pad", ctypes.c_byte * 32),
        ]

    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT),
    ]


def send_key(digit):
    if digit not in VK_CODES:
        return False

    vk = VK_CODES[digit]

    key_down = INPUT()
    key_down.type = INPUT_KEYBOARD
    key_down._input.ki.wVk = vk
    key_down._input.ki.dwFlags = 0

    key_up = INPUT()
    key_up.type = INPUT_KEYBOARD
    key_up._input.ki.wVk = vk
    key_up._input.ki.dwFlags = KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(key_down, key_up)
    result = ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    return result > 0
