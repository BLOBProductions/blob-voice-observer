"""Blob Voice Observer — entry point.

Startup sequence:
1. Check admin privileges (warn if not elevated — VALORANT may ignore keystrokes)
2. Load config.json (creates default if missing)
3. Check for a connected microphone
4. Load the Vosk speech model (takes 1-2 seconds)
5. Register hotkey (toggle or hold mode)
6. Enter main loop — Ctrl+C to exit
"""

import ctypes
import sys
import os
import threading
import time

import pyaudio

from config import load_config
from key_sender import send_key, send_key_to_window, find_window
from voice_listener_vosk import VoiceListener
from hotkey_manager import HotkeyManager


def get_model_path():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    return os.path.join(base, "vosk-model-small-en-us-0.15")


def check_microphone():
    try:
        audio = pyaudio.PyAudio()
    except Exception:
        return False
    try:
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                return True
        return False
    finally:
        audio.terminate()


def main():
    print("=== Blob Voice Observer ===")
    print()

    # Admin check — SendInput is silently blocked by Windows UIPI if VALORANT
    # runs elevated but this tool does not.
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("WARNING: Not running as Administrator. Keystrokes may not reach VALORANT.")
        print("Right-click the exe and select 'Run as administrator'.")
        print()

    # Resolve config path
    if getattr(sys, "frozen", False):
        config_path = os.path.join(os.path.dirname(sys.executable), "config.json")
    else:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )

    config = load_config(config_path)

    # Check microphone
    if not check_microphone():
        print("ERROR: No microphone detected. Please connect a microphone and try again.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Check model
    model_path = get_model_path()
    if not os.path.exists(model_path):
        print(f"ERROR: Vosk model not found at {model_path}")
        print("Download vosk-model-small-en-us-0.15 from https://alphacephei.com/vosk/models")
        input("Press Enter to exit...")
        sys.exit(1)

    # Display config
    active_key = config["toggle_key"] if config["mode"] == "toggle" else config["hold_key"]
    print(f"Mode: {config['mode']} ({active_key})")

    target_title = config.get("target_window", "")
    if target_title:
        hwnd = find_window(target_title)
        if hwnd:
            print(f"Target window: \"{target_title}\" (PostMessage mode) — FOUND (hwnd={hwnd})")
        else:
            print(f"Target window: \"{target_title}\" (PostMessage mode) — NOT FOUND (will retry on each keystroke)")
    else:
        print("Target window: foreground (SendInput mode)")

    print("Status: PAUSED")
    print()

    # Voice listener callback — cache the target HWND to avoid
    # per-keystroke EnumWindows lookups.
    cached_hwnd = [None]  # mutable container for nonlocal access

    def on_digit(digit, word):
        if target_title:
            if cached_hwnd[0] is None:
                cached_hwnd[0] = find_window(target_title)
            if not cached_hwnd[0]:
                print(f'  WARNING: Heard "{word}" but window "{target_title}" not found')
                return
            success = send_key_to_window(digit, cached_hwnd[0])
            if not success:
                cached_hwnd[0] = None  # invalidate, retry next keystroke
        else:
            success = send_key(digit)

        if success:
            print(f'  Heard: "{word}" -> Sent: {digit}')
        else:
            print(f'  WARNING: Heard "{word}" but keystroke {digit} was BLOCKED (run as admin?)')

    # Initialize voice listener (model loaded here, takes a moment)
    print("Loading speech model...")
    listener = VoiceListener(
        model_path=model_path,
        on_digit=on_digit,
        debounce_ms=config["debounce_ms"],
        vad_aggressiveness=config["vad_aggressiveness"],
        trailing_silence_ms=config["trailing_silence_ms"],
    )
    print("Model loaded.")
    print()

    # Hotkey state change callback — dispatch start/stop off the keyboard hook
    # thread to avoid blocking Windows' hook message pump (which can cause
    # Windows to kill the hook if it doesn't return promptly).
    def on_state_change(active):
        if active:
            print(f"[{active_key}] Status: LISTENING")
            threading.Thread(target=listener.start, daemon=True).start()
        else:
            print(f"[{active_key}] Status: PAUSED")
            threading.Thread(target=listener.stop, daemon=True).start()

    # Start hotkey manager
    hotkey_mgr = HotkeyManager(
        mode=config["mode"],
        toggle_key=config["toggle_key"],
        hold_key=config["hold_key"],
        on_state_change=on_state_change,
    )
    hotkey_mgr.start()

    print(f"Press {active_key} to {'toggle listening' if config['mode'] == 'toggle' else 'hold and speak'}.")
    print("Press Ctrl+C to exit.")
    print()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        listener.stop()
        hotkey_mgr.stop()


if __name__ == "__main__":
    main()
