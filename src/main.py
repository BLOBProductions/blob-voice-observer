"""BLOB Voice Observer — entry point.

Startup sequence:
1. Check admin privileges (VALORANT may silently block keystrokes if elevated)
2. Load config.json (creates default if missing)
3. List and validate microphone
4. Load the Vosk speech model
5. Register hotkey (toggle or hold mode)
6. Enter main loop; Ctrl+C to exit
"""

import ctypes
import os
import sys
import threading
import time

import pyaudio

from config import load_config
from hotkey_manager import HotkeyManager
from key_sender import find_window, send_key, send_key_to_window
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
            mics = [
                f"  [{i}] {pa.get_device_info_by_index(i)['name']}"
                for i in range(pa.get_device_count())
                if pa.get_device_info_by_index(i)["maxInputChannels"] > 0
            ]
        finally:
            pa.terminate()
        if mics:
            print("Detected microphones:")
            print("\n".join(mics))
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


class KeystrokeDispatcher:
    """Owns the on_digit callback, window handle cache, and retry logic."""

    def __init__(self, target_title):
        self._target = target_title
        self._hwnd = None

    def __call__(self, digit, word):
        if self._target:
            if self._hwnd is None:
                self._hwnd = find_window(self._target)
            if not self._hwnd:
                print(f'  WARNING: Heard "{word}" but window "{self._target}" not found')
                return
            success = send_key_to_window(digit, self._hwnd)
            if not success:
                self._hwnd = None  # invalidate; retry on next keystroke
        else:
            success = send_key(digit)

        if success:
            print(f'  Heard: "{word}" -> Sent: {digit}')
        else:
            print(f'  WARNING: Heard "{word}" but keystroke {digit} was BLOCKED (run as admin?)')


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

    active_key = config["toggle_key"] if config["mode"] == "toggle" else config["hold_key"]
    print(f"Mode: {config['mode']} ({active_key})")

    target_title = config.get("target_window", "")
    if target_title:
        hwnd = find_window(target_title)
        status = f"FOUND (hwnd={hwnd})" if hwnd else "NOT FOUND (will retry on each keystroke)"
        print(f'Target window: "{target_title}" (PostMessage mode), {status}')
    else:
        print("Target window: foreground (SendInput mode)")

    print("Status: PAUSED\n")

    print("Loading speech model...")
    listener = VoiceListener(
        model_path=model_path,
        on_digit=KeystrokeDispatcher(target_title),
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
