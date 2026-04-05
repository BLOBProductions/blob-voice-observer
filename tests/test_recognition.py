import time
import pytest


WORD_TO_DIGIT = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


def test_extract_digits_from_clean_text():
    from voice_listener import extract_digits
    assert extract_digits("five") == [("five", 5)]


def test_extract_digits_strips_punctuation():
    from voice_listener import extract_digits
    assert extract_digits("Five.") == [("five", 5)]


def test_extract_digits_multiple_words():
    from voice_listener import extract_digits
    result = extract_digits("three seven")
    assert result == [("three", 3), ("seven", 7)]


def test_extract_digits_ignores_unknown():
    from voice_listener import extract_digits
    assert extract_digits("hello world") == []


def test_extract_digits_mixed_known_unknown():
    from voice_listener import extract_digits
    result = extract_digits("the number nine please")
    assert result == [("nine", 9)]


def test_extract_digits_whisper_artifacts():
    from voice_listener import extract_digits
    result = extract_digits(" Five! ")
    assert result == [("five", 5)]


def test_extract_digits_empty():
    from voice_listener import extract_digits
    assert extract_digits("") == []
    assert extract_digits("   ") == []


class TestHallucinationFilter:
    def test_accepts_good_segment(self):
        from voice_listener import passes_hallucination_filter
        assert passes_hallucination_filter(no_speech_prob=0.1, avg_logprob=-0.5) is True

    def test_rejects_high_no_speech_prob(self):
        from voice_listener import passes_hallucination_filter
        assert passes_hallucination_filter(no_speech_prob=0.7, avg_logprob=-0.5) is False

    def test_rejects_low_avg_logprob(self):
        from voice_listener import passes_hallucination_filter
        assert passes_hallucination_filter(no_speech_prob=0.1, avg_logprob=-2.0) is False

    def test_boundary_no_speech_prob(self):
        from voice_listener import passes_hallucination_filter
        # 0.6 is at the boundary — should pass (threshold is >0.6)
        assert passes_hallucination_filter(no_speech_prob=0.6, avg_logprob=-0.5) is True

    def test_boundary_avg_logprob(self):
        from voice_listener import passes_hallucination_filter
        # -1.5 is at the boundary — should pass (threshold is < -1.5)
        assert passes_hallucination_filter(no_speech_prob=0.1, avg_logprob=-1.5) is True


class TestDebounce:
    def test_same_digit_debounced(self):
        from voice_listener import DigitDebouncer
        db = DigitDebouncer(debounce_ms=300)
        assert db.should_fire(5) is True
        assert db.should_fire(5) is False  # within 300ms

    def test_different_digit_not_debounced(self):
        from voice_listener import DigitDebouncer
        db = DigitDebouncer(debounce_ms=300)
        assert db.should_fire(5) is True
        assert db.should_fire(3) is True  # different digit passes immediately

    def test_same_digit_after_cooldown(self):
        from voice_listener import DigitDebouncer
        db = DigitDebouncer(debounce_ms=20)
        assert db.should_fire(5) is True
        time.sleep(0.06)  # 60ms >> 20ms debounce — safe margin for Windows ~15ms sleep granularity
        assert db.should_fire(5) is True  # cooldown elapsed
