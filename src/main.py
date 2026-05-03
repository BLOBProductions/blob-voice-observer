"""BLOB Voice Observer — entry point.

Startup sequence:
1. Check admin privileges (VALORANT may silently block keystrokes if elevated)
2. Load config.json (creates default if missing)
3. List and validate microphone
4. Resolve key_map to VK codes
5. Load the Vosk speech model
6. Register hotkey (toggle or hold mode)
7. Enter main loop; Ctrl+C to exit
"""

import ctypes
import os
import sys
import threading
import time

import pyaudio

from config import load_config
from hotkey_manager import HotkeyManager
from key_sender import find_window, resolve_vk, send_key, send_key_to_window
from recognition import WORD_TO_DIGIT
from voice_listener_vosk import VoiceListener


def _config_path():
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.abspath(__file__))
    if not getattr(sys, "frozen", False):
        base = os.path.join(base, "..")
    return os.path.join(base, "config.json")


def _model_path():
    base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."
    )
    return os.path.join(base, "vosk-model-small-en-us-0.15")


def _list_microphones():
    try:
        pa = pyaudio.PyAudio()
        try:
            # PyAudio enumerates the same hardware once per audio API (MME,
            # DirectSound, WASAPI), producing duplicate entries. MME also
            # truncates names to ~31 chars. Strategy: collect all entries,
            # fix mojibake, then for each name keep the longest version seen
            # (which is the un-truncated one from WASAPI/DS), deduplicated by
            # that longest name's first 31 chars as a stable key.
            entries = {}  # key=first-31-chars → (best_name, lowest_index)
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info["maxInputChannels"] <= 0:
                    continue
                name = info["name"].encode("cp1252", errors="replace").decode("utf-8", errors="replace")
                key = name[:31].lower()
                existing = entries.get(key)
                if existing is None or len(name) > len(existing[0]):
                    entries[key] = (name, existing[1] if existing else i)
        finally:
            pa.terminate()
        if entries:
            print("Detected microphones:")
            for name, idx in sorted(entries.values(), key=lambda x: x[1]):
                print(f"  [{idx:>3}] {name}")
    except Exception:
        pass


def _check_microphone(device_index):
    try:
        pa = pyaudio.PyAudio()
        try:
            if device_index is not None:
                info = pa.get_device_info_by_index(device_index)
                return info["maxInputChannels"] > 0
            return any(
                pa.get_device_info_by_index(i)["maxInputChannels"] > 0
                for i in range(pa.get_device_count())
            )
        except Exception:
            return False
        finally:
            pa.terminate()
    except Exception:
        return False


def _resolve_key_map(key_map: dict) -> dict[int, tuple[int, str]]:
    """Resolve word→key_name map to digit→(vk_code, key_name).

    Warns at startup for any key name that cannot be resolved, then omits
    that digit from the active map so misfires are silent rather than noisy.
    """
    resolved = {}
    for word, key_name in key_map.items():
        digit = WORD_TO_DIGIT.get(word)
        if digit is None:
            continue
        vk = resolve_vk(key_name)
        if vk is None:
            print(f"WARNING: key_map['{word}'] = '{key_name}' could not be resolved to a VK code, digit {digit} will be skipped")
            continue
        resolved[digit] = (vk, key_name)
    return resolved


class KeystrokeDispatcher:
    """Owns the on_digit callback, VK map, window handle cache, and retry logic."""

    def __init__(self, target_title: str, vk_map: dict[int, tuple[int, str]]):
        self._target = target_title
        self._vk_map = vk_map  # digit → (vk_code, key_name)
        self._hwnd = None

    def __call__(self, digit: int, word: str):
        entry = self._vk_map.get(digit)
        if entry is None:
            return
        vk, key_name = entry

        if self._target:
            if self._hwnd is None:
                self._hwnd = find_window(self._target)
            if not self._hwnd:
                print(f'  WARNING: Heard "{word}" but window "{self._target}" not found')
                return
            success = send_key_to_window(vk, self._hwnd)
            if not success:
                self._hwnd = None  # invalidate; retry on next keystroke
        else:
            success = send_key(vk)

        if success:
            print(f'  Heard: "{word}" -> Sent: {key_name}')
        else:
            print(f'  WARNING: Heard "{word}" but keystroke "{key_name}" was BLOCKED (run as admin?)')


def main():
    print("=== BLOB Voice Observer ===\n")

    if sys.platform == "win32" and not ctypes.windll.shell32.IsUserAnAdmin():
        print("WARNING: Not running as Administrator. Keystrokes may not reach VALORANT.")
        print("Right-click the exe and select 'Run as administrator'.\n")

    config = load_config(_config_path())

    _list_microphones()
    print()

    mic_index = config.get("microphone_device_index")
    if not _check_microphone(mic_index):
        if mic_index is not None:
            print(f"ERROR: Microphone device index {mic_index} not found or has no input channels.")
        else:
            print("ERROR: No microphone detected. Please connect a microphone and try again.")
        input("Press Enter to exit...")
        sys.exit(1)

    model_path = _model_path()
    if not os.path.exists(model_path):
        print(f"ERROR: Vosk model not found at {model_path}")
        print("Download vosk-model-small-en-us-0.15 from https://alphacephei.com/vosk/models")
        input("Press Enter to exit...")
        sys.exit(1)

    vk_map = _resolve_key_map(config["key_map"])
    if not vk_map:
        print("ERROR: key_map resolved to nothing. Check your config.json key_map entries.")
        input("Press Enter to exit...")
        sys.exit(1)

    active_key = config["toggle_key"] if config["mode"] == "toggle" else config["hold_key"]
    print(f"Mode: {config['mode']} ({active_key})")

    target_title = config.get("target_window", "")
    if target_title:
        hwnd = find_window(target_title)
        status = f"FOUND (hwnd={hwnd})" if hwnd else "NOT FOUND (will retry on each keystroke)"
        print(f'Target window: "{target_title}" (PostMessage mode), {status}')
    else:
        print("Target window: foreground (SendInput mode)")

    print("Key map:")
    for digit in sorted(vk_map):
        _, key_name = vk_map[digit]
        word = next(w for w, d in WORD_TO_DIGIT.items() if d == digit)
        print(f"  {word:>5} -> {key_name}")

    print("Status: PAUSED\n")

    print("Loading speech model...")
    listener = VoiceListener(
        model_path=model_path,
        on_digit=KeystrokeDispatcher(target_title, vk_map),
        debounce_ms=config["debounce_ms"],
        vad_aggressiveness=config["vad_aggressiveness"],
        trailing_silence_ms=config["trailing_silence_ms"],
        device_index=config.get("microphone_device_index"),
    )
    print("Model loaded.\n")

    # Dispatch start/stop off the keyboard hook thread to avoid blocking
    # Windows' hook message pump (which can kill the hook if it stalls).
    def on_state_change(active):
        label = "LISTENING" if active else "PAUSED"
        print(f"[{active_key}] Status: {label}")
        target = listener.start if active else listener.stop
        threading.Thread(target=target, daemon=True).start()

    hotkey_mgr = HotkeyManager(
        mode=config["mode"],
        toggle_key=config["toggle_key"],
        hold_key=config["hold_key"],
        on_state_change=on_state_change,
    )
    hotkey_mgr.start()

    verb = "toggle listening" if config["mode"] == "toggle" else "hold and speak"
    print(f"Press {active_key} to {verb}.")
    print("Press Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        listener.stop()
        hotkey_mgr.stop()


if __name__ == "__main__":
    main()
