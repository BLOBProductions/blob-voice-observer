# Blob Voice Observer

Hands-free camera switching for VALORANT observers. Say a digit (0-9) and the tool sends the corresponding keypress to switch player cameras.

Uses a two-stage pipeline for low-latency recognition (~120ms):
1. **webrtcvad** detects when you start and stop speaking
2. **Vosk** decodes your speech in real-time, finalized instantly on speech end

## Quick Start (Users)

1. Unzip the release
2. **Right-click** `BlobVoiceObserver.exe` and select **Run as administrator**
3. Press **F6** to start listening (default hotkey)
4. Say a digit: "one", "two", ... "nine", "zero"
5. Press **F6** again to pause
6. Press **Ctrl+C** to exit

VALORANT must be the focused window for keystrokes to register. Any standard headset or desktop microphone works (the tool records in mono at 16 kHz).

> **Important:** If VALORANT is running as Administrator (common due to Vanguard anti-cheat), you must also run this tool as Administrator. Otherwise keystrokes are silently blocked by Windows.

## Configuration

Edit `config.json` next to the exe:

```json
{
  "mode": "toggle",
  "toggle_key": "F6",
  "hold_key": "caps_lock",
  "debounce_ms": 300,
  "vad_aggressiveness": 3,
  "trailing_silence_ms": 120
}
```

| Field | Description |
|-------|-------------|
| `mode` | `"toggle"` (press to flip on/off) or `"hold"` (hold key to listen) |
| `toggle_key` | Key for toggle mode (e.g. `"F6"`, `"F5"`, `"scroll_lock"`) |
| `hold_key` | Key for hold mode (e.g. `"caps_lock"`, `"space"`, `"right_shift"`) |
| `debounce_ms` | Cooldown between recognitions of the same digit (ms) |
| `vad_aggressiveness` | 0-3, higher = stricter silence detection, faster response. Lower for noisy rooms. |
| `trailing_silence_ms` | How long to wait after speech ends before recognizing (30-2000ms). Lower = faster but may clip words. |

### Tuning for Speed

For the fastest response at a quiet desk, try:
```json
{
  "trailing_silence_ms": 90,
  "vad_aggressiveness": 3
}
```

For noisy environments (arena, crowd), try:
```json
{
  "trailing_silence_ms": 150,
  "vad_aggressiveness": 2
}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No microphone detected" at startup | Make sure your headset is plugged in **before** launching. Check Windows Settings > Sound > Input. |
| Exe is blocked by Windows SmartScreen | Click "More info" then "Run anyway". The exe is unsigned. |
| Keystrokes not reaching VALORANT | Run the tool as Administrator (right-click > Run as administrator). VALORANT must be the focused window. |
| Wrong digit / misrecognition | Speak clearly in short single words. Reduce background noise or lower `vad_aggressiveness` to 2. |
| Tool stops responding after unplugging mic | Press the hotkey off then on again to reinitialize the mic stream. |
| Antivirus quarantines the exe | Add `BlobVoiceObserver.exe` to your antivirus exclusion list. The exe uses Win32 `SendInput` which some antivirus flag. |

## How It Works

```
Mic -> 30ms frames -> webrtcvad (speech/silence) -> SpeechDetector state machine
                  \-> Vosk (streaming decode) -> FinalResult() on speech end -> keystroke
```

- **webrtcvad** classifies each 30ms frame as speech or silence
- **SpeechDetector** tracks speech boundaries with a 3-state machine (idle/speaking/trailing)
- **Vosk** receives every frame and decodes incrementally in real-time
- When trailing silence threshold is reached, `FinalResult()` forces Vosk to output immediately
- No waiting for Vosk's built-in endpointer (which adds 500-800ms)
- Works on any hardware, no GPU required

## Development Setup

Requires Python 3.10+ on Windows.

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install pytest pyinstaller
```

Download the Vosk model (~50MB English, small):

```bash
# Automated (downloads, extracts, cleans up):
venv\Scripts\python -c "import urllib.request,zipfile,os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip','model.zip'); zipfile.ZipFile('model.zip','r').extractall('.'); os.remove('model.zip')"
```

Or manually: download [vosk-model-small-en-us-0.15.zip](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip), extract it, and place the `vosk-model-small-en-us-0.15` folder in the project root.

Run from source:

```bash
venv\Scripts\python src\main.py
```

Run tests:

```bash
venv\Scripts\pytest tests/ -v
```

Build standalone exe:

```bash
build.bat
```

Output is in `dist\BlobVoiceObserver\`.

> **Note for developers:** The build script removes a broken PyInstaller hook for `webrtcvad` that ships with `pyinstaller-hooks-contrib`. This hook calls `copy_metadata('webrtcvad')` but we use the `webrtcvad-wheels` package which registers under a different metadata name. If the build fails after upgrading PyInstaller, check whether the hook has been recreated.

## Project Structure

```
src/
  main.py                 # Entry point, startup checks, console UI
  voice_listener_vosk.py  # VAD + Vosk hybrid pipeline
  speech_detector.py      # 3-state VAD state machine
  config.py               # Config loading and validation
  key_sender.py           # Win32 SendInput keystroke injection
  hotkey_manager.py       # Toggle/hold hotkey binding
```

## License

Internal tool for Blob esports production.

The bundled Vosk model (`vosk-model-small-en-us-0.15`) is licensed under [Apache 2.0](https://github.com/alphacep/vosk-api/blob/master/COPYING).
