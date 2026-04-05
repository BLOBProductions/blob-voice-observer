import re
import threading
import time

import numpy as np
import pyaudio
import webrtcvad
from faster_whisper import WhisperModel

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

INITIAL_PROMPT = "zero one two three four five six seven eight nine"

NO_SPEECH_PROB_THRESHOLD = 0.6
AVG_LOGPROB_THRESHOLD = -1.0


def extract_digits(text):
    """Extract recognized digit words from Whisper output text.

    Returns list of (word, digit) tuples.
    """
    words = re.findall(r'[a-z]+', text.lower())
    results = []
    for word in words:
        if word in WORD_TO_DIGIT:
            results.append((word, WORD_TO_DIGIT[word]))
    return results


def passes_hallucination_filter(no_speech_prob, avg_logprob):
    """Check if a Whisper segment passes confidence thresholds."""
    if no_speech_prob > NO_SPEECH_PROB_THRESHOLD:
        return False
    if avg_logprob < AVG_LOGPROB_THRESHOLD:
        return False
    return True


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
        self.model = self._load_model(model_path)

        self.on_digit = on_digit
        self.vad_aggressiveness = vad_aggressiveness
        self.trailing_silence_ms = trailing_silence_ms
        self._debouncer = DigitDebouncer(debounce_ms)
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._thread = None
        self._audio = None
        self._stream = None

    @staticmethod
    def _load_model(model_path):
        """Load model with CUDA→CPU fallback. Warmup forces full initialization."""
        dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
        try:
            model = WhisperModel(model_path, device="cuda", compute_type="float16")
            # Force CUDA to fully initialize — cublas etc. are lazy-loaded
            list(model.transcribe(dummy, language="en", beam_size=1))
            return model
        except Exception:
            model = WhisperModel(model_path, device="cpu", compute_type="int8")
            list(model.transcribe(dummy, language="en", beam_size=1))
            return model

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
            frames_per_buffer=FRAME_SIZE,
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
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _listen_loop(self):
        vad = webrtcvad.Vad(self.vad_aggressiveness)
        detector = SpeechDetector(
            vad=vad,
            trailing_silence_ms=self.trailing_silence_ms,
        )

        while not self._stop_event.is_set():
            try:
                data = self._stream.read(FRAME_SIZE, exception_on_overflow=False)
            except Exception:
                if not self._stop_event.is_set():
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            speech_audio = detector.process_frame(data)
            if speech_audio is not None:
                self._transcribe(speech_audio)

    def _transcribe(self, audio_bytes):
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, _info = self.model.transcribe(
                audio,
                language="en",
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
                initial_prompt=INITIAL_PROMPT,
            )

            for segment in segments:
                if not passes_hallucination_filter(segment.no_speech_prob, segment.avg_logprob):
                    continue

                for word, digit in extract_digits(segment.text):
                    if self._debouncer.should_fire(digit):
                        self.on_digit(digit, word)
        except Exception as e:
            print(f"WARNING: Transcription error: {e}")
