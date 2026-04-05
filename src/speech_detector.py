SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples
FRAME_BYTES = FRAME_SIZE * 2  # 16-bit = 2 bytes per sample


class SpeechDetector:
    """VAD-based speech boundary detector with 3-state machine.

    Processes audio in 30ms frames. Returns complete speech segments
    (as raw PCM bytes) when trailing silence threshold is reached.
    """

    IDLE = "idle"
    SPEAKING = "speaking"
    TRAILING = "trailing"

    def __init__(self, vad, trailing_silence_ms=120,
                 min_speech_ms=90, max_speech_ms=2000, pre_pad_ms=60):
        self.vad = vad
        self.trailing_frames = max(1, round(trailing_silence_ms / FRAME_MS))
        self.min_speech_frames = max(1, round(min_speech_ms / FRAME_MS))
        self.max_speech_frames = max(1, round(max_speech_ms / FRAME_MS))
        self.pre_pad_count = max(0, round(pre_pad_ms / FRAME_MS))

        self.state = self.IDLE
        self._speech_buffer = bytearray()
        self._speech_frame_count = 0
        self._silence_count = 0
        self._pre_pad_buffer = []

    def process_frame(self, frame_bytes):
        """Process a single 30ms audio frame.

        Returns bytes of the complete speech segment when ready, None otherwise.
        """
        is_speech = self.vad.is_speech(frame_bytes, SAMPLE_RATE)

        if self.state == self.IDLE:
            return self._handle_idle(frame_bytes, is_speech)
        elif self.state == self.SPEAKING:
            return self._handle_speaking(frame_bytes, is_speech)
        elif self.state == self.TRAILING:
            return self._handle_trailing(frame_bytes, is_speech)
        return None

    def _handle_idle(self, frame_bytes, is_speech):
        if is_speech:
            self.state = self.SPEAKING
            self._speech_buffer = bytearray()
            for pad_frame in self._pre_pad_buffer:
                self._speech_buffer.extend(pad_frame)
            self._speech_buffer.extend(frame_bytes)
            self._speech_frame_count = 1
            self._silence_count = 0
        else:
            self._pre_pad_buffer.append(bytes(frame_bytes))
            if len(self._pre_pad_buffer) > self.pre_pad_count:
                self._pre_pad_buffer.pop(0)
        return None

    def _handle_speaking(self, frame_bytes, is_speech):
        self._speech_buffer.extend(frame_bytes)
        if is_speech:
            self._speech_frame_count += 1
            if self._total_frames() >= self.max_speech_frames:
                self._reset()
                return None
        else:
            self.state = self.TRAILING
            self._silence_count = 1
        return None

    def _handle_trailing(self, frame_bytes, is_speech):
        self._speech_buffer.extend(frame_bytes)
        if is_speech:
            self.state = self.SPEAKING
            self._speech_frame_count += 1
            self._silence_count = 0
            if self._total_frames() >= self.max_speech_frames:
                self._reset()
                return None
        else:
            self._silence_count += 1
            if self._silence_count >= self.trailing_frames:
                if self._speech_frame_count >= self.min_speech_frames:
                    result = bytes(self._speech_buffer)
                    self._reset()
                    return result
                else:
                    self._reset()
                    return None
        return None

    def _total_frames(self):
        return len(self._speech_buffer) // FRAME_BYTES

    def _reset(self):
        self.state = self.IDLE
        self._speech_buffer = bytearray()
        self._speech_frame_count = 0
        self._silence_count = 0
        self._pre_pad_buffer = []
