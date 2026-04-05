# Blob Voice Observer

Hands-free camera switching for VALORANT observers. Say a digit (0-9) and the tool sends the corresponding keypress to switch player cameras.

Uses a two-stage pipeline for low-latency recognition (~120ms):
1. **webrtcvad** detects when you start and stop speaking
2. **Vosk** decodes your speech in real-time, finalized instantly on speech end

## Quick Start (Users)

1. Unzip the release
2. Double-click `BlobVoiceObserver.exe`
3. Press **F6** to start listening (default hotkey)
4. Say a digit: "one", "two", ... "nine", "zero"
5. Press **F6** again to pause
6. Press **Ctrl+C** to exit

VALORANT must be the focused window for keystrokes to register.

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

Download the Vosk model (~50MB):

```bash
venv\Scripts\python -c "import urllib.request,zipfile,os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip','model.zip'); zipfile.ZipFile('model.zip','r').extractall('.'); os.remove('model.zip')"
```

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
