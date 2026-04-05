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
        self._thread = None
        self._audio = None
        self._stream = None

    def start(self):
        if not self._stop_event.is_set():
            return  # already running
        self._stop_event.clear()
        self._debouncer._last_per_digit.clear()
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._audio:
            self._audio.terminate()
            self._audio = None

    def _listen_loop(self):
        """Feed every frame to both VAD and Vosk. Single thread — no queue needed."""
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
                if not self._stop_event.is_set():
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            # Feed to Vosk — it decodes incrementally in real-time
            recognizer.AcceptWaveform(data)

            # Feed to VAD state machine — detects speech boundaries
            speech_ended = detector.process_frame(data)

            if speech_ended is not None:
                # Speech segment complete — force Vosk to finalize NOW
                # instead of waiting for its own slow endpointer
                result = json.loads(recognizer.FinalResult())
                text = result.get("text", "").strip()

                if text:
                    for word, digit in extract_digits(text):
                        if self._debouncer.should_fire(digit):
                            self.on_digit(digit, word)
