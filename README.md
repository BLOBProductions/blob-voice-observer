# BLOB Voice Observer

> A side tool by **[BLOB Productions](https://blob.productions/)**.
> Come join our Discord **[here!](https://discord.gg/T4H64qT764)**.

**Hands-free camera switching for VALORANT observers.** Say a digit (`"one"`
through `"nine"`, or `"zero"`) and the tool presses the matching number key
in VALORANT to switch to that player's camera.

Built for esports broadcasts where observers need to react faster than a
keyboard allows, but works for anyone who wants voice-triggered number-key
hotkeys in any Windows application.

- **Offline.** Uses [Vosk](https://alphacephei.com/vosk/) locally. No
  cloud, no account, no network calls.
- **Fast.** ~120 ms from end-of-speech to keystroke (Change in config.json)
- **Background-friendly by default.** Sends keystrokes to VALORANT even
  when it is **not** the focused window (via the `target_window` config,
  which defaults to `"VALORANT"`).

> ⚠️ **Disclaimer: not affiliated with Riot Games or VALORANT.** This is
> an unofficial community tool. Use at your own risk. VALORANT's Vanguard
> anti-cheat has never, to BLOB's knowledge, flagged keystroke-level
> automation of this kind, but Riot's ToS and anti-cheat behavior can
> change without notice. BLOB takes no responsibility for account
> action. For broadcast/observer use in a controlled production
> environment (its intended use case), this has been stable.

---

## What it can do

- Recognize the spoken digits `zero` through `nine` and send the
  corresponding keystroke (`0` through `9`).
- Toggle mode (tap a hotkey to start/stop listening) **or** hold mode
  (listen only while a key is held).
- Per-digit debounce so a single "five" doesn't fire twice.
- Two keystroke backends:
  - **SendInput**: fires into the foreground window. Works with DirectX
    and fullscreen games.
  - **PostMessage**: fires into a specific window by title, so the game
    does **not** need focus.
- Closed-grammar recognizer (Vosk is restricted to the ten digit words),
  which dramatically improves accuracy in noisy rooms.
- Self-contained config file, sensible defaults, graceful handling of
  invalid values.

## What it will NOT do

- No cloud services, no telemetry, no analytics. Everything stays on
  your machine.
- No arbitrary speech-to-text. The grammar is locked to the ten digits.
  This is by design: accuracy and latency are the priorities.
- No macOS / Linux support. The keystroke injection uses Win32 APIs.

---

## Microphone note

To keep detection both **accurate and fast**, the pipeline is tuned to
react to subtle speech cues, which also makes it somewhat sensitive to
background noise and to software that rewrites your mic signal.

**If the program feels slower or less accurate than you'd like, try
tuning your mic settings first. That usually fixes it before any config
changes are needed.**

A quick checklist, in rough order of impact, in *Windows Settings →
Sound → \<your input device\> → Properties* (and in any vendor app that
owns your mic: NVIDIA Broadcast, Krisp, Logitech G HUB, SteelSeries
Sonar, Razer Synapse, Realtek Audio Console, etc.):

- Turn off **noise suppression / noise cancellation**
- Turn off **echo cancellation (AEC)**
- Turn off **automatic gain control (AGC)**
- Turn off **voice clarity / voice focus / AI voice enhancement**
- In Discord / OBS / game voice chat, disable their noise suppression
  too (it can run on the input device even when you're not talking)
- Prefer a plain wired headset in a reasonably quiet room

The tool captures at **16 kHz mono** from the Windows default input
device, so anything that processes the signal upstream of that is
processing what the recognizer ultimately hears. Bluetooth headsets,
webcam mics, and laptop arrays all *work*, but may need a slightly more
forgiving `vad_aggressiveness` / `trailing_silence_ms`
(see [Configuration](#configuration)).

---

## Quick Start (users, pre-built exe)

1. Download the latest release zip from the
   [Releases](https://github.com/BLOBProductions/blob-voice-observer/releases)
   page and unzip it.
2. **Right-click** `BlobVoiceObserver.exe` → **Run as administrator**
   (required if VALORANT is elevated, which it usually is).
   *Windows SmartScreen may warn about an unsigned exe on first launch.
   Click **More info → Run anyway**.*
3. Press **F6** to start listening (default hotkey).
4. Say a digit: `"one"`, `"two"`, ... `"nine"`, `"zero"`.
5. Press **F6** again to pause.
6. Press **Ctrl+C** in the console window to exit.

Any standard headset or desktop microphone works (see disclaimer above).

> If VALORANT runs as Administrator (common due to Vanguard anti-cheat),
> you **must** run this tool as Administrator too. Otherwise Windows
> silently blocks the keystrokes. User Interface Privilege Isolation
> (UIPI) forbids a non-elevated process from sending input to an
> elevated one.

---

## Configuration

Edit `config.json` next to the executable (or in the project root when
running from source). If the file is missing, one with defaults is
created automatically on first run.

```json
{
  "mode": "toggle",
  "toggle_key": "F6",
  "hold_key": "caps_lock",
  "debounce_ms": 300,
  "vad_aggressiveness": 3,
  "trailing_silence_ms": 120,
  "target_window": "VALORANT"
}
```

| Field                 | Description |
|-----------------------|-------------|
| `mode`                | `"toggle"` (press to flip on/off) or `"hold"` (hold to listen) |
| `toggle_key`          | Key for toggle mode, e.g. `"F6"`, `"F5"`, `"scroll_lock"` |
| `hold_key`            | Key for hold mode, e.g. `"caps_lock"`, `"space"`, `"right_shift"` |
| `debounce_ms`         | Cooldown (per digit) between repeat recognitions; prevents double-fires |
| `vad_aggressiveness`  | `0` to `3`. Higher = stricter silence detection, faster response. Lower for noisy rooms. |
| `trailing_silence_ms` | How long to wait after speech ends before finalizing (30-2000 ms). Lower = faster but may clip short words. |
| `target_window`       | Window title for PostMessage mode. Defaults to `"VALORANT"` so keystrokes land without the game needing focus. Set to `""` to fall back to SendInput (foreground-only) instead. |

### Tuning presets

**Fastest (quiet desk):**

```json
{ "trailing_silence_ms": 90, "vad_aggressiveness": 3 }
```

**Noisy environment (arena, crowd, open mic):**

```json
{ "trailing_silence_ms": 150, "vad_aggressiveness": 2 }
```

**Foreground-only (opt out of PostMessage):**

```json
{ "target_window": "" }
```

> `target_window` does a class-name prefix match, so the default string
> `"VALORANT"` correctly matches VALORANT's actual class
> `VALORANTUnrealWindow` even though its title has trailing whitespace.

---

## Dependencies

Runtime (installed via `requirements.txt`):

| Package             | Why |
|---------------------|-----|
| `vosk`              | Offline speech recognition engine |
| `webrtcvad-wheels`  | Voice Activity Detector (Windows-friendly wheel fork) |
| `pyaudio`           | Microphone audio capture |
| `keyboard`          | Global hotkey binding |

Build-only (not shipped with the exe):

| Package       | Why |
|---------------|-----|
| `pyinstaller` | Packages Python + model into a single folder |
| `pytest`      | Runs the test suite |

External assets:

- **Vosk model**: `vosk-model-small-en-us-0.15` (~50 MB).
  [Download link](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip).
  Licensed Apache 2.0.

---

## Development Setup

Requires **Python 3.10+** on **Windows**.

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install pytest pyinstaller
```

Download the Vosk model (automated):

```bash
venv\Scripts\python -c "import urllib.request,zipfile,os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip','model.zip'); zipfile.ZipFile('model.zip','r').extractall('.'); os.remove('model.zip')"
```

Or manually: grab
[`vosk-model-small-en-us-0.15.zip`](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip),
extract it, and place the `vosk-model-small-en-us-0.15` folder in the
project root.

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

Output lands in `dist\BlobVoiceObserver\`. Zip that folder to
distribute.

> **Developer note:** `build.bat` deletes a broken PyInstaller contrib
> hook for `webrtcvad`. The upstream hook calls
> `copy_metadata('webrtcvad')`, but we install the `webrtcvad-wheels`
> package which registers under a different metadata name. If the build
> breaks after upgrading PyInstaller, check whether the hook has been
> recreated.

---

## How It Works

```
Mic -> 30 ms frames -> webrtcvad -> SpeechDetector state machine
                    \-> Vosk (streaming decode) -> FinalResult() -> keystroke
```

1. **`webrtcvad`** classifies every 30 ms frame as speech or silence.
2. **`SpeechDetector`** is a 3-state machine
   (`idle` → `speaking` → `trailing` → `idle`) that tracks speech
   boundaries and emits the moment a short, complete utterance ends.
3. **Vosk** receives every frame in parallel via `AcceptWaveform()` and
   decodes incrementally in real time, constrained to a closed grammar
   of the ten digit words.
4. The moment `SpeechDetector` signals end-of-speech, we call
   `FinalResult()` to force Vosk to emit its current best hypothesis
   immediately, instead of waiting 500-800 ms for Vosk's own endpointer.
5. The recognized digit is debounced and passed to `key_sender`, which
   uses either `SendInput` (foreground) or `PostMessage` (targeted
   window) to press the corresponding number key.

No GPU required. Runs comfortably on any modern laptop.

---

## Project Structure

```
src/
  main.py                 # Entry point, startup checks, console UI
  voice_listener_vosk.py  # VAD + Vosk hybrid pipeline
  speech_detector.py      # 3-state VAD state machine
  config.py               # Config loading and validation
  key_sender.py           # Win32 SendInput / PostMessage keystroke injection
  hotkey_manager.py       # Toggle / hold hotkey binding

tests/                    # Pytest suite for each src/ module
third_party/              # Third-party license texts (Apache 2.0)
build.bat                 # PyInstaller build script
pyproject.toml            # Project metadata + pytest config
requirements.txt          # Runtime dependencies
LICENSE                   # MIT license
NOTICE                    # Third-party attributions
config.json               # Runtime configuration (gitignored, generated on first run)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No microphone detected" at startup | Plug in your headset **before** launching. Check *Windows Settings → Sound → Input*. |
| Exe blocked by SmartScreen | Click *More info → Run anyway*. The exe is unsigned. |
| Keystrokes not reaching VALORANT | Run the tool as Administrator. VALORANT must either be focused (SendInput mode) **or** `target_window` must be set (PostMessage mode). |
| Wrong digit / misrecognition | Speak clearly, one word at a time. Check your [mic settings](#microphone-note). Try lowering `vad_aggressiveness` to `2`. |
| Recognizer feels slow | Lower `trailing_silence_ms` toward `90`. Confirm mic effects are off. |
| First word after unpausing gets clipped | Raise `trailing_silence_ms` slightly, or raise `pre_pad_ms` (source only). |
| Tool stops responding after unplugging mic | Toggle the hotkey off then back on to reinitialize the audio stream. |
| Antivirus quarantines the exe | Add `BlobVoiceObserver.exe` to exclusions. Win32 `SendInput` is a common false-positive trigger. |
| `target_window` says "NOT FOUND" | The window hasn't been created yet; start VALORANT, then press the hotkey. The tool retries on each keystroke. |

---

## Contributing

Contributions are welcome. Before opening a PR:

1. Run the test suite: `venv\Scripts\pytest tests/ -v`
2. Keep comments focused on **why**, not **what**.
3. Don't add cloud/network dependencies. This is an offline tool by
   design.
4. Windows-only is fine; cross-platform PRs are welcome but not
   required.

For bug reports, please include:

- Windows version
- Microphone model + whether you disabled all effects
- Contents of your `config.json`
- What you said, what happened, and what you expected

---

## About

Built by **[BLOB Productions](https://blob.productions/)**.
For more of what we make, visit
[blob.productions](https://blob.productions/).

## License

MIT. See [LICENSE](LICENSE).

The bundled Vosk model (`vosk-model-small-en-us-0.15`) is licensed under
[Apache 2.0](https://github.com/alphacep/vosk-api/blob/master/COPYING).

VALORANT is a trademark of Riot Games, Inc. This project is not
affiliated with, endorsed by, or sponsored by Riot Games.
