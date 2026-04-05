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
        self._last_partial = None  # track last partial to avoid re-firing
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
        self._last_partial = None
        self._partial_fired = False  # track if we already fired for this utterance
        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                if not self._stop_event.is_set():
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            # Feed audio to recognizer first
            is_final = recognizer.AcceptWaveform(data)

            if is_final:
                # Utterance complete — reset for next word
                self._last_partial = None
                self._partial_fired = False
            else:
                # Check partial results for near-realtime response
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if (partial_text
                        and partial_text != self._last_partial
                        and partial_text in WORD_TO_DIGIT
                        and not self._partial_fired):
                    self._last_partial = partial_text
                    self._partial_fired = True
                    recognition = self.process_recognition(partial_text)
                    if recognition:
                        digit, word = recognition
                        self.on_digit(digit, word)
