from speech_detector import SAMPLE_RATE, FRAME_MS, FRAME_SIZE, FRAME_BYTES


def _silent_frame():
    """A frame of silence (all zeros)."""
    return b'\x00' * FRAME_BYTES


def _speech_frame():
    """A frame that a mock VAD will classify as speech."""
    return b'\x01' * FRAME_BYTES


class MockVad:
    """Mock VAD that classifies frames based on their first byte."""
    def __init__(self, mode=3):
        self.mode = mode

    def is_speech(self, frame, sample_rate):
        return frame[0] != 0


def _make_detector(**kwargs):
    from speech_detector import SpeechDetector
    vad = MockVad()
    return SpeechDetector(vad=vad, **kwargs)


class TestIdleState:
    def test_silence_stays_idle(self):
        det = _make_detector()
        result = det.process_frame(_silent_frame())
        assert result is None
        assert det.state == "idle"

    def test_speech_transitions_to_speaking(self):
        det = _make_detector()
        det.process_frame(_speech_frame())
        assert det.state == "speaking"


class TestSpeakingState:
    def test_continued_speech_stays_speaking(self):
        det = _make_detector()
        det.process_frame(_speech_frame())
        det.process_frame(_speech_frame())
        assert det.state == "speaking"

    def test_silence_transitions_to_trailing(self):
        det = _make_detector()
        det.process_frame(_speech_frame())
        det.process_frame(_silent_frame())
        assert det.state == "trailing"


class TestTrailingState:
    def test_speech_returns_to_speaking(self):
        det = _make_detector()
        det.process_frame(_speech_frame())
        det.process_frame(_silent_frame())
        assert det.state == "trailing"
        det.process_frame(_speech_frame())
        assert det.state == "speaking"

    def test_enough_silence_triggers_recognition(self):
        """4 frames of trailing silence (120ms default) should emit speech."""
        det = _make_detector(trailing_silence_ms=120)
        # 3 speech frames (meets min_speech_ms=90ms)
        for _ in range(3):
            det.process_frame(_speech_frame())
        # 4 silence frames to hit threshold
        for i in range(4):
            result = det.process_frame(_silent_frame())
            if i < 3:
                assert result is None
        assert result is not None
        assert len(result) > 0
        assert det.state == "idle"

    def test_not_enough_silence_stays_trailing(self):
        det = _make_detector(trailing_silence_ms=120)
        det.process_frame(_speech_frame())
        det.process_frame(_speech_frame())
        det.process_frame(_speech_frame())
        det.process_frame(_silent_frame())
        det.process_frame(_silent_frame())
        assert det.state == "trailing"


class TestMinSpeechDuration:
    def test_short_burst_discarded(self):
        """Speech shorter than min_speech_ms (90ms = 3 frames) is noise."""
        det = _make_detector(min_speech_ms=90, trailing_silence_ms=120)
        # 1 speech frame (only 30ms, below 90ms minimum)
        det.process_frame(_speech_frame())
        # 4 silence frames
        result = None
        for _ in range(4):
            result = det.process_frame(_silent_frame())
        # Should discard, not return speech
        assert result is None
        assert det.state == "idle"


class TestMaxSpeechDuration:
    def test_exceeds_max_discards_buffer(self):
        """Speech exceeding max_speech_ms is discarded (noise protection)."""
        det = _make_detector(max_speech_ms=150)
        max_frames = max(1, round(150 / FRAME_MS))  # 5 frames
        result = None
        for i in range(max_frames):
            result = det.process_frame(_speech_frame())
        # At frame 5 (index 4), _total_frames reaches max -> reset to IDLE
        assert det.state == "idle"
        assert result is None


class TestPreSpeechPadding:
    def test_pre_pad_included_in_output(self):
        """2 silence frames before speech should be prepended to output."""
        det = _make_detector(pre_pad_ms=60, min_speech_ms=90, trailing_silence_ms=120)
        # Feed 3 silence frames (only 2 should be kept as pre-pad)
        s1 = _silent_frame()
        s2 = _silent_frame()
        s3 = _silent_frame()
        det.process_frame(s1)
        det.process_frame(s2)
        det.process_frame(s3)
        # 3 speech frames
        for _ in range(3):
            det.process_frame(_speech_frame())
        # 4 silence to finalize
        result = None
        for _ in range(4):
            result = det.process_frame(_silent_frame())
        assert result is not None
        # Output should contain: 2 pre-pad + 3 speech + 4 trailing = 9 frames
        expected_frames = 2 + 3 + 4
        assert len(result) == expected_frames * FRAME_BYTES


class TestReset:
    def test_after_recognition_returns_to_idle(self):
        det = _make_detector(min_speech_ms=90, trailing_silence_ms=120)
        for _ in range(3):
            det.process_frame(_speech_frame())
        for _ in range(4):
            det.process_frame(_silent_frame())
        assert det.state == "idle"
        # Can detect next utterance
        det.process_frame(_speech_frame())
        assert det.state == "speaking"
