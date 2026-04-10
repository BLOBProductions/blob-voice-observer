"""Win32 keystroke injection for digit keys 0-9.

Two modes:
- SendInput (default): injects into the foreground window. Reliable for
  DirectX/fullscreen games but requires VALORANT to be in focus.
- PostMessage (target_window mode): sends WM_KEYDOWN/WM_KEYUP to a specific
  window by title, so VALORANT does NOT need to be the active window.

Requires admin privileges if the target window (VALORANT) is elevated.

Note: this module uses `ctypes.windll` which only exists on Windows. On
other platforms we still let the module import cleanly (so pytest can
collect tests that mock `user32`) but leave `user32 = None`. Actually
calling `send_key` / `send_key_to_window` on a non-Windows host will
raise `AttributeError` on `None`, which is intentional; the tool is
Windows-only at runtime.
"""

import ctypes
import sys
from ctypes import wintypes

# --- Shared constants ---
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

# --- SendInput constants & structures ---
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002


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


# --- PostMessage constants ---
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
else:
    user32 = None


def _make_lparam(scan_code, is_keyup):
    """Build the lParam bitfield for WM_KEYDOWN / WM_KEYUP."""
    lparam = 1  # repeat count = 1
    lparam |= (scan_code & 0xFF) << 16
    if is_keyup:
        lparam |= (1 << 30)  # previous key state = down
        lparam |= (1 << 31)  # transition state = releasing
    return lparam


def find_window(title):
    """Return the HWND for a window matching the given title.

    First tries an exact match, then falls back to searching by window
    class name (e.g. "VALORANT" matches class "VALORANTUnrealWindow").
    This handles games like VALORANT whose title has trailing whitespace.
    """
    # Exact title match
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        return hwnd

    # Class-name prefix match (e.g. "VALORANT" -> "VALORANTUnrealWindow")
    results = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_cb(h, _lp):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls_buf, 256)
        if cls_buf.value.upper().startswith(title.upper()):
            results.append(h)
            return False  # stop enumerating
        return True

    user32.EnumWindows(_enum_cb, 0)
    return results[0] if results else None


def send_key(digit):
    """Send a digit keystroke to the foreground window via SendInput."""
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
    result = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    return result > 0


def send_key_to_window(digit, hwnd):
    """Send a digit keystroke to a specific window via PostMessage."""
    if digit not in VK_CODES:
        return False

    vk = VK_CODES[digit]
    scan = user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC

    down_ok = user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _make_lparam(scan, False))
    up_ok = user32.PostMessageW(hwnd, WM_KEYUP, vk, _make_lparam(scan, True))
    return bool(down_ok and up_ok)
