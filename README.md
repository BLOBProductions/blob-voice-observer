# Blob Voice Observer

Hands-free camera switching for VALORANT observers. Say a digit (0-9) and the tool sends the corresponding keypress to switch player cameras.

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
  "debounce_ms": 300
}
```

| Field | Description |
|-------|-------------|
| `mode` | `"toggle"` (press to flip on/off) or `"hold"` (hold key to listen) |
| `toggle_key` | Key for toggle mode (e.g. `"F6"`, `"F5"`, `"scroll_lock"`) |
| `hold_key` | Key for hold mode (e.g. `"caps_lock"`, `"space"`, `"right_shift"`) |
| `debounce_ms` | Cooldown between recognitions in milliseconds |

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
