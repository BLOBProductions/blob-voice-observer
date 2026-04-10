# Latency Problem: Voice Recognition Too Slow

> **Historical note.** This is the research brief that motivated the
> current VAD + Vosk hybrid architecture. It describes the problem as
> it stood **before** the fix — in particular, references to
> `src/voice_listener.py` are to the old final-results-only listener
> that no longer exists. For the current implementation that solved
> this, see [`src/voice_listener_vosk.py`](../src/voice_listener_vosk.py)
> and option **D** ("Hybrid approach") at the bottom of this doc — that
> is the direction we ultimately took.

## The Project

BLOB Voice Observer — a Windows tool that converts spoken digits ("zero" through "nine") into keyboard input for VALORANT observer camera switching. The tool must feel near-realtime for live esports production.

## The Problem

Recognition latency is too high. When the user says a digit, there's a noticeable delay (~500-800ms) before the keystroke fires. For live VALORANT observing, this needs to be under ~200ms to feel responsive.

## Current Architecture

- **Vosk** (v0.3.45, latest Python wheel) for offline speech recognition
- **Restricted grammar**: only 10 words + `[unk]` — `["zero","one","two","three","four","five","six","seven","eight","nine","[unk]"]`
- **PyAudio** captures mic at 16kHz mono, 1000-sample chunks (~62ms per chunk)
- **Final results only** (`AcceptWaveform`) — fires when Vosk detects word boundary (silence after speech)

See `src/voice_listener.py` for the full implementation.

## Why It's Slow

Vosk's `AcceptWaveform()` only returns `True` when it detects an **endpoint** — a silence gap after speech. The default endpoint detection requires ~500-800ms of silence before finalizing. This is the main source of latency.

## What We Tried

### 1. Partial Results (`PartialResult()`) — FAILED

Attempted to fire on Vosk's intermediate results before finalization for near-instant response. Failed after 4+ iterations because `PartialResult()` is fundamentally unreliable as an event source:

- **Multi-word accumulation**: Vosk builds up partials like `"five"` → `"five three"` → `"five three two"`. Tracking which words are "new" is fragile.
- **Vosk rewrites history**: A partial `"three four five zero"` can change to `"three four five six"` next chunk — if we already fired "zero", we can't undo it.
- **False positives from noise**: Ambient noise gets matched to "one" (closest grammar match). Vosk returns `"[unk] one"` from static.
- **State accumulation bugs**: Any tracking state (fired sets, word counts, confirmation counters) eventually gets stuck or out of sync with Vosk's internal state, causing the listener to go dead or repeat entire sequences.
- **Heisenbug behavior**: Adding debug `print()` statements changed timing enough to mask bugs — classic sign of a race between our state tracking and Vosk's internal state.

Each fix for one partial-results issue introduced a new one. After 4 fix cycles, we concluded the approach is architecturally unsound.

### 2. Endpointer Configuration — NOT AVAILABLE

Vosk's C API has `vosk_recognizer_set_endpointer_mode()` and `vosk_recognizer_set_endpointer_delays()` which would allow reducing the silence threshold from ~800ms to ~150ms. However:

- **Python vosk 0.3.45** (latest on PyPI) does NOT expose these methods
- The `KaldiRecognizer` Python class has no `SetEndpointerMode` or `SetEndpointerDelays`
- The native `libvosk.dll` shipped with 0.3.45 doesn't even contain the C symbols — they were added after this release
- No newer Python wheel has been published

### 3. Smaller Chunk Size — MARGINAL IMPROVEMENT

Reduced chunk size from 4000 (250ms) → 2000 (125ms) → 1000 (62ms). This helps Vosk check for endpoints more frequently but doesn't change the fundamental silence duration required before finalization. Improvement: ~50-100ms, not enough.

## What We Need

A solution that gives us **<200ms latency from end-of-speech to keystroke** while maintaining:

1. **Reliability** — no double-fires, no stuck states, no false positives from noise
2. **Offline operation** — no API keys, no internet
3. **Windows compatibility** — runs on Windows 10/11
4. **Simple vocabulary** — literally just 10 words (digit names)
5. **Bundleable** — can be packaged into a standalone .exe via PyInstaller

## Possible Research Directions

### A. Build Vosk from source with endpointer support
The endpointer API exists in Vosk's C source on GitHub but was never shipped in a Python wheel. Could we:
- Build `libvosk.dll` from source with the endpointer symbols?
- Monkey-patch the Python bindings to call the C functions via ctypes?
- This would let us set `trailing_silence=0.15` which solves the problem.

### B. Alternative speech recognition engines
- **faster-whisper** / **whisper.cpp** — more accurate but potentially slower for single words?
- **Coqui STT** (successor to Mozilla DeepSpeech) — has streaming support
- **Windows Speech Recognition API** (`System.Speech`) — built into Windows, might have lower latency
- **PocketSphinx** — lightweight, might have configurable endpoint timing
- **SpeechRecognition** library with various backends

### C. Audio-level voice activity detection (VAD)
Use a separate VAD (like **webrtcvad** or **silero-vad**) to detect speech boundaries, then only feed the speech segments to Vosk. This could give us tighter control over when to finalize.

### D. Hybrid approach
Use VAD to detect when speech ends, then immediately call `recognizer.FinalResult()` to force Vosk to finalize with whatever it has, instead of waiting for Vosk's own endpoint detection.

## Key Constraint

Whatever solution we pick must work with the existing project structure. The voice listener is a single class (`VoiceListener` in `src/voice_listener.py`) with `start()`, `stop()`, and a callback `on_digit(digit, word)`. The rest of the app (hotkey manager, key sender, config, main) is stable and doesn't need to change.

## File References (historical)

- `src/voice_listener.py` — the original final-results-only listener
  (reliable but slow). Replaced by `src/voice_listener_vosk.py`, which
  implements option D below.
- `requirements.txt` — current dependencies.
