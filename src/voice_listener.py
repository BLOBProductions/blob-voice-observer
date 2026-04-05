import json
import time
import threading
from vosk import Model, KaldiRecognizer
import pyaudio

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
SAMPLE_RATE = 16000
CHUNK_SIZE = 2000  # ~125ms chunks for faster response


class VoiceListener:
    def __init__(self, model_path, on_digit, debounce_ms=300):
        self.model = Model(model_path)
        self.on_digit = on_digit
        self.debounce_ms = debounce_ms
        self._last_per_digit = {}  # per-digit debounce timestamps
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._thread = None
        self._audio = None
        self._stream = None

    def start(self):
        if not self._stop_event.is_set():
            return  # already running
        self._stop_event.clear()
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._audio:
            self._audio.terminate()
            self._audio = None

    def process_recognition(self, text):
        text = text.strip()
        if text not in WORD_TO_DIGIT:
            return None

        digit = WORD_TO_DIGIT[text]
        now = time.time() * 1000

        # Only debounce the SAME digit — different digits pass through immediately
        last_time = self._last_per_digit.get(digit, 0)
        if now - last_time < self.debounce_ms:
            return None

        self._last_per_digit[digit] = now
        return (digit, text)

    def _listen_loop(self):
        recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, GRAMMAR)
        prev_digits = []  # digit words from previous chunk's partial
        fired_count = 0   # how many positions we've already fired

        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                if not self._stop_event.is_set():
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            if recognizer.AcceptWaveform(data):
                prev_digits = []
                fired_count = 0
            else:
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if not partial_text:
                    continue

                # Extract digit words only, preserving order
                digits = [w for w in partial_text.split() if w in WORD_TO_DIGIT]

                # Count how many positions are stable (same word, same position, 2 chunks)
                stable = 0
                for i in range(min(len(prev_digits), len(digits))):
                    if prev_digits[i] == digits[i]:
                        stable = i + 1
                    else:
                        break

                # If Vosk rewrote words we already fired, adjust
                if stable < fired_count:
                    fired_count = stable

                # Fire any newly confirmed words
                for i in range(fired_count, stable):
                    recognition = self.process_recognition(digits[i])
                    if recognition:
                        digit, word = recognition
                        self.on_digit(digit, word)
                    fired_count = i + 1

                prev_digits = digits
