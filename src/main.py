import sys
import os
import time

import pyaudio

from config import load_config
from key_sender import send_key
from voice_listener import VoiceListener
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
        print("Run the model download step from README.md.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Display config
    active_key = config["toggle_key"] if config["mode"] == "toggle" else config["hold_key"]
    mode_label = "toggle" if config["mode"] == "toggle" else "hold"
    print(f"Mode: {mode_label} ({active_key})")
    print("Status: PAUSED")
    print()

    # Voice listener callback
    def on_digit(digit, word):
        print(f'  Heard: "{word}" -> Sent: {digit}')
        send_key(digit)

    # Initialize voice listener (model loaded here, takes a moment)
    print("Loading speech model...")
    listener = VoiceListener(
        model_path=model_path,
        on_digit=on_digit,
        debounce_ms=config["debounce_ms"],
    )
    print("Model loaded.")
    print()

    # Hotkey state change callback
    def on_state_change(active):
        if active:
            print(f"[{active_key}] Status: LISTENING")
            listener.start()
        else:
            print(f"[{active_key}] Status: PAUSED")
            listener.stop()

    # Start hotkey manager
    hotkey_mgr = HotkeyManager(
        mode=config["mode"],
        toggle_key=config["toggle_key"],
        hold_key=config["hold_key"],
        on_state_change=on_state_change,
    )
    hotkey_mgr.start()

    print(f"Press {active_key} to {'toggle listening' if mode_label == 'toggle' else 'hold and speak'}.")
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
