"""Vosk hybrid voice listener — VAD + forced finalization for ~120ms latency.

Feeds every audio frame to both webrtcvad (for speech boundary detection) and
Vosk (for streaming decode). When the VAD detects speech has ended, FinalResult()
forces Vosk to emit its best hypothesis immediately — near-instant since Vosk has
been decoding in real-time. This bypasses Vosk's built-in endpointer which adds
500-800ms of silence-detection latency.
"""

import json
import re
import threading
import time

import pyaudio
import webrtcvad
from vosk import Model, KaldiRecognizer

from speech_detector import SpeechDetector, FRAME_SIZE, SAMPLE_RATE

WORD_TO_DIGIT = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}

# Constrain Vosk to only recognize these words (closed grammar).
# This dramatically improves accuracy and speed for digit-only recognition.
# "[unk]" is Vosk's catch-all for anything outside the grammar — without it,
# Vosk forces every utterance into one of the digit words.
GRAMMAR = json.dumps(list(WORD_TO_DIGIT.keys()) + ["[unk]"])


def extract_digits(text):
    """Extract recognized digit words from text.

    Returns list of (word, digit) tuples.
    """
    words = re.findall(r'[a-z]+', text.lower())
    results = []
    for word in words:
        if word in WORD_TO_DIGIT:
            results.append((word, WORD_TO_DIGIT[word]))
    return results


class DigitDebouncer:
    """Per-digit debounce to prevent double-fires."""

    def __init__(self, debounce_ms=300):
        self.debounce_ms = debounce_ms
        self._last_per_digit = {}

    def should_fire(self, digit):
        now = time.time() * 1000
        last_time = self._last_per_digit.get(digit, 0)
        if now - last_time < self.debounce_ms:
            return False
        self._last_per_digit[digit] = now
        return True

    def reset(self):
        self._last_per_digit.clear()


class VoiceListener:
    def __init__(self, model_path, on_digit, debounce_ms=300,
                 vad_aggressiveness=3, trailing_silence_ms=120):
        self.model = Model(model_path)
        self.on_digit = on_digit
        self.vad_aggressiveness = vad_aggressiveness
        self.trailing_silence_ms = trailing_silence_ms
        self._debouncer = DigitDebouncer(debounce_ms)
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._lock = threading.Lock()
        self._thread = None
        self._audio = None
        self._stream = None

    def start(self):
        with self._lock:
            if not self._stop_event.is_set():
                return  # already running
            self._stop_event.clear()
            self._debouncer.reset()
            try:
                self._audio = pyaudio.PyAudio()
                self._stream = self._audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=FRAME_SIZE,
                )
            except Exception as e:
                print(f"ERROR: Could not open microphone: {e}")
                self._stop_event.set()
                if self._stream:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                    self._stream = None
                if self._audio:
                    try:
                        self._audio.terminate()
                    except Exception:
                        pass
                    self._audio = None
                return
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2)
                self._thread = None
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._audio:
                try:
                    self._audio.terminate()
                except Exception:
                    pass
                self._audio = None

    def _listen_loop(self):
        """Main audio loop — feeds every frame to both VAD and Vosk.

        Vosk receives EVERY frame via AcceptWaveform() so it decodes
        incrementally in real-time. But we do NOT rely on Vosk's built-in
        endpointer (which adds 500-800ms of latency). Instead, webrtcvad
        detects speech boundaries via SpeechDetector, and when it signals
        speech-end we call FinalResult() to force Vosk to emit immediately.
        FinalResult() also resets the recognizer, which is correct — each
        utterance is independent.
        """
        vad = webrtcvad.Vad(self.vad_aggressiveness)
        detector = SpeechDetector(
            vad=vad,
            trailing_silence_ms=self.trailing_silence_ms,
        )
        recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, GRAMMAR)
        recognizer.SetMaxAlternatives(0)
        recognizer.SetWords(False)

        while not self._stop_event.is_set():
            try:
                data = self._stream.read(FRAME_SIZE, exception_on_overflow=False)
            except Exception:
                # A read error during a clean stop is expected — stop() closes
                # the stream under us. Only surface it to the user if it
                # happened while we were still meant to be listening.
                if not self._stop_event.is_set():
                    self._stop_event.set()  # allow restart via start()
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            recognizer.AcceptWaveform(data)
            speech_ended = detector.process_frame(data)

            if speech_ended is not None:
                result = json.loads(recognizer.FinalResult())
                text = result.get("text", "").strip()

                if text:
                    for word, digit in extract_digits(text):
                        if self._debouncer.should_fire(digit):
                            self.on_digit(digit, word)
