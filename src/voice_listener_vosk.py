"""Vosk hybrid voice listener: VAD endpoint detection + forced Vosk finalization.

Every audio frame is fed to both webrtcvad (speech boundary detection) and Vosk
(streaming decode). When the VAD signals end-of-speech, FinalResult() forces an
immediate Vosk hypothesis — ~120ms latency vs the 500-800ms from Vosk's own
endpointer.
"""

import json
import threading

import pyaudio
import webrtcvad
from vosk import Model, KaldiRecognizer

from speech_detector import SpeechDetector, FRAME_SIZE, SAMPLE_RATE
from recognition import GRAMMAR, extract_digits, DigitDebouncer

# Re-export so existing imports from this module keep working.
__all__ = ["VoiceListener", "extract_digits", "DigitDebouncer"]


class VoiceListener:
    def __init__(self, model_path, on_digit, debounce_ms=300,
                 vad_aggressiveness=3, trailing_silence_ms=120,
                 device_index=None):
        self.model = Model(model_path)
        self.on_digit = on_digit
        self.vad_aggressiveness = vad_aggressiveness
        self.trailing_silence_ms = trailing_silence_ms
        self._device_index = device_index
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
                return
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
                    input_device_index=self._device_index,
                )
            except Exception as e:
                print(f"ERROR: Could not open microphone: {e}")
                self._cleanup_audio()
                self._stop_event.set()
                return
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2)
                self._thread = None
            self._cleanup_audio()

    def _cleanup_audio(self):
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
        vad = webrtcvad.Vad(self.vad_aggressiveness)
        detector = SpeechDetector(vad=vad, trailing_silence_ms=self.trailing_silence_ms)
        recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, GRAMMAR)
        recognizer.SetMaxAlternatives(0)
        recognizer.SetWords(False)

        while not self._stop_event.is_set():
            try:
                data = self._stream.read(FRAME_SIZE, exception_on_overflow=False)
            except Exception:
                intentional = self._stop_event.is_set()
                self._stop_event.set()
                self._cleanup_audio()
                if not intentional:
                    print("WARNING: Microphone disconnected. Toggle off and on to resume.")
                break

            recognizer.AcceptWaveform(data)
            if detector.process_frame(data) is not None:
                result = json.loads(recognizer.FinalResult())
                text = result.get("text", "").strip()
                if text:
                    for word, digit in extract_digits(text):
                        if self._debouncer.should_fire(digit):
                            self.on_digit(digit, word)
