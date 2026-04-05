import queue
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
AVG_LOGPROB_THRESHOLD = -1.5


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
        self._listen_thread = None
        self._transcribe_thread = None
        self._audio = None
        self._stream = None
        self._segment_queue = queue.Queue(maxsize=5)

    @staticmethod
    def _load_model(model_path):
        """Load model with CUDA->CPU fallback. Warmup forces full initialization."""
        # Non-silent audio + vad_filter=False forces the encoder to actually run,
        # which triggers cublas loading. Without this, CUDA appears to work but
        # fails on real audio (cublas is lazy-loaded by CTranslate2).
        dummy = np.ones(SAMPLE_RATE, dtype=np.float32) * 0.01
        warmup_kwargs = dict(language="en", beam_size=1, vad_filter=False)
        try:
            model = WhisperModel(model_path, device="cuda", compute_type="float16")
            # transcribe() returns (generator, info) — must iterate the generator
            # to run the encoder. list() on the tuple does NOT iterate it.
            segments, _info = model.transcribe(dummy, **warmup_kwargs)
            for _ in segments:
                pass
            print("Device: GPU (CUDA)")
            return model
        except Exception:
            model = WhisperModel(model_path, device="cpu", compute_type="int8")
            segments, _info = model.transcribe(dummy, **warmup_kwargs)
            for _ in segments:
                pass
            print("Device: CPU (slower, digits may queue during rapid speech)")
            print("  Tip: For GPU acceleration, run: pip install nvidia-cublas-cu12")
            return model

    def start(self):
        if not self._stop_event.is_set():
            return  # already running
        self._stop_event.clear()
        # Clear stale segments and debounce state from previous session
        while not self._segment_queue.empty():
            try:
                self._segment_queue.get_nowait()
            except queue.Empty:
                break
        self._debouncer._last_per_digit.clear()
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._transcribe_thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._listen_thread.start()
        self._transcribe_thread.start()

    def stop(self):
        self._stop_event.set()
        # Join threads BEFORE closing stream. The listen thread checks
        # _stop_event after each 30ms read and exits cleanly. If we close
        # the stream first, the thread's next read() hits a closed/None
        # stream, printing a false "Microphone disconnected" warning.
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
            self._listen_thread = None
        if self._transcribe_thread:
            self._transcribe_thread.join(timeout=2)
            self._transcribe_thread = None
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._audio:
            self._audio.terminate()
            self._audio = None

    def _listen_loop(self):
        """Read mic frames and feed to VAD. Never blocks on transcription."""
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
                try:
                    self._segment_queue.put_nowait(speech_audio)
                except queue.Full:
                    pass  # drop segment — transcriber is behind

    def _transcribe_loop(self):
        """Consume speech segments from queue and transcribe."""
        while not self._stop_event.is_set():
            try:
                audio_bytes = self._segment_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._transcribe(audio_bytes)
            except Exception as e:
                print(f"WARNING: Transcription loop error: {e}")

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
