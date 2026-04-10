import time

from voice_listener_vosk import extract_digits, DigitDebouncer


def test_extract_digits_from_clean_text():
    assert extract_digits("five") == [("five", 5)]


def test_extract_digits_strips_punctuation():
    assert extract_digits("Five.") == [("five", 5)]


def test_extract_digits_multiple_words():
    result = extract_digits("three seven")
    assert result == [("three", 3), ("seven", 7)]


def test_extract_digits_ignores_unknown():
    assert extract_digits("hello world") == []


def test_extract_digits_mixed_known_unknown():
    result = extract_digits("the number nine please")
    assert result == [("nine", 9)]


def test_extract_digits_strips_whitespace_and_punctuation():
    result = extract_digits(" Five! ")
    assert result == [("five", 5)]


def test_extract_digits_empty():
    assert extract_digits("") == []
    assert extract_digits("   ") == []


class TestDebounce:
    def test_same_digit_debounced(self):
        db = DigitDebouncer(debounce_ms=300)
        assert db.should_fire(5) is True
        assert db.should_fire(5) is False  # within 300ms

    def test_different_digit_not_debounced(self):
        db = DigitDebouncer(debounce_ms=300)
        assert db.should_fire(5) is True
        assert db.should_fire(3) is True  # different digit passes immediately

    def test_same_digit_after_cooldown(self):
        db = DigitDebouncer(debounce_ms=20)
        assert db.should_fire(5) is True
        time.sleep(0.06)  # 60ms >> 20ms debounce, safe margin for Windows ~15ms sleep granularity
        assert db.should_fire(5) is True  # cooldown elapsed
