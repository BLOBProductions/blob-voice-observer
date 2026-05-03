"""Win32 keystroke injection.

Two delivery modes:
- send_key(vk): injects into the foreground window via SendInput.
- send_key_to_window(vk, hwnd): sends WM_KEYDOWN/WM_KEYUP to a specific
  window via PostMessage (game does not need focus).

Key resolution:
- resolve_vk(name) converts a friendly key name to a Windows virtual-key
  code.  It uses VkKeyScanW so layout-specific characters work out of the
  box: on AZERTY, "&" resolves to VK_1 (0x31), "é" to VK_2 (0x32), etc.
  Named keys (F1-F12, space, enter, …) are handled via a fallback table.

Note: ctypes.windll only exists on Windows.  On other platforms the module
imports cleanly (user32 = None) so pytest can mock it; calling send_key /
send_key_to_window on a non-Windows host raises AttributeError on None,
which is intentional — this tool is Windows-only at runtime.
"""

import ctypes
import sys
from ctypes import wintypes

# Default digit→VK mapping (layout-independent row of number keys).
VK_CODES = {i: 0x30 + i for i in range(10)}

# --- SendInput structures ---
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

# Named key → VK code table (supplements VkKeyScanW for non-character keys).
_NAMED_VK: dict[str, int] = {
    # Function keys
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    # Navigation / editing
    "enter": 0x0D, "return": 0x0D,
    "space": 0x20, "tab": 0x09,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D, "ins": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    # Modifiers (rarely used as targets but listed for completeness)
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "capslock": 0x14, "caps_lock": 0x14,
    "escape": 0x1B, "esc": 0x1B,
    "numlock": 0x90,
    # Numpad
    "num0": 0x60, "num1": 0x61, "num2": 0x62, "num3": 0x63,
    "num4": 0x64, "num5": 0x65, "num6": 0x66, "num7": 0x67,
    "num8": 0x68, "num9": 0x69,
    "multiply": 0x6A, "add": 0x6B, "subtract": 0x6D,
    "decimal": 0x6E, "divide": 0x6F,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",       wintypes.WORD),
        ("wScan",     wintypes.WORD),
        ("dwFlags",   wintypes.DWORD),
        ("time",      wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


WM_KEYDOWN = 0x0100
WM_KEYUP   = 0x0101

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes    = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype     = wintypes.HWND
    user32.PostMessageW.argtypes   = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype    = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype  = wintypes.UINT
    user32.VkKeyScanW.argtypes     = [wintypes.WCHAR]
    user32.VkKeyScanW.restype      = wintypes.SHORT
else:
    user32 = None


def resolve_vk(name: str) -> int | None:
    """Resolve a key name to a Windows virtual-key code.

    Accepts:
    - Named keys:  "f6", "space", "enter", "num1", …
    - Single characters resolved via VkKeyScanW (layout-aware):
        QWERTY "1" -> 0x31,  AZERTY "&" -> 0x31,  "é" -> 0x32, etc.
    - Raw hex strings: "0x35" -> 0x35

    Returns None if the name cannot be resolved.
    """
    key = name.strip().lower()

    if not key:
        return None

    # Raw hex literal
    if key.startswith("0x"):
        try:
            return int(key, 16)
        except ValueError:
            return None

    # Named key table
    if key in _NAMED_VK:
        return _NAMED_VK[key]

    # Single character — VkKeyScanW is layout-aware (handles &, é, ", etc.)
    original = name.strip()  # preserve original case/accent for VkKeyScanW
    if len(original) == 1 and user32 is not None:
        result = user32.VkKeyScanW(original)
        # High byte = required modifier flags; low byte = VK code.
        # 0xFF in either byte means "not found".
        vk  = result & 0xFF
        mod = (result >> 8) & 0xFF
        if vk != 0xFF and mod != 0xFF:
            return vk

    # ASCII single character fallback (for non-Windows test environments)
    if len(original) == 1:
        c = ord(original.upper())
        if 0x20 <= c <= 0x7E:
            return c

    return None


def _make_lparam(scan_code, is_keyup):
    """Build the lParam bitfield for WM_KEYDOWN / WM_KEYUP."""
    lparam = 1  # repeat count = 1
    lparam |= (scan_code & 0xFF) << 16
    if is_keyup:
        lparam |= (1 << 30)  # previous key state = down
        lparam |= (1 << 31)  # transition state = releasing
    return lparam


def find_window(title):
    """Return the HWND matching title (exact, then class-name prefix)."""
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        return hwnd

    results = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_cb(h, _lp):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls_buf, 256)
        if cls_buf.value.upper().startswith(title.upper()):
            results.append(h)
            return False
        return True

    user32.EnumWindows(_enum_cb, 0)
    return results[0] if results else None


def send_key(vk: int) -> bool:
    """Send a keystroke for virtual-key code vk to the foreground window."""
    key_down = INPUT()
    key_down.type = INPUT_KEYBOARD
    key_down._input.ki.wVk = vk
    key_down._input.ki.dwFlags = 0

    key_up = INPUT()
    key_up.type = INPUT_KEYBOARD
    key_up._input.ki.wVk = vk
    key_up._input.ki.dwFlags = KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(key_down, key_up)
    return user32.SendInput(2, inputs, ctypes.sizeof(INPUT)) > 0


def send_key_to_window(vk: int, hwnd: int) -> bool:
    """Send a keystroke for virtual-key code vk to a specific window."""
    scan = user32.MapVirtualKeyW(vk, 0)
    down_ok = user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _make_lparam(scan, False))
    up_ok   = user32.PostMessageW(hwnd, WM_KEYUP,   vk, _make_lparam(scan, True))
    return bool(down_ok and up_ok)
