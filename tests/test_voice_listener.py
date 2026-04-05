import time
from unittest.mock import patch, MagicMock
from voice_listener import WORD_TO_DIGIT, VoiceListener


def _make_listener(debounce_ms=300):
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = MagicMock()
    listener.debounce_ms = debounce_ms
    listener._last_per_digit = {}
    listener._last_partial = None
    return listener


def test_word_to_digit_has_all_ten_words():
    expected_words = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
    assert set(WORD_TO_DIGIT.keys()) == expected_words


def test_word_to_digit_maps_correctly():
    assert WORD_TO_DIGIT["zero"] == 0
    assert WORD_TO_DIGIT["five"] == 5
    assert WORD_TO_DIGIT["nine"] == 9


def test_process_recognition_valid_word():
    listener = _make_listener()
    result = listener.process_recognition("five")
    assert result == (5, "five")


def test_process_recognition_unknown_word():
    listener = _make_listener()
    result = listener.process_recognition("hello")
    assert result is None


def test_process_recognition_empty_string():
    listener = _make_listener()
    result = listener.process_recognition("")
    assert result is None


def test_debounce_blocks_same_digit():
    listener = _make_listener()
    result1 = listener.process_recognition("five")
    assert result1 == (5, "five")

    result2 = listener.process_recognition("five")
    assert result2 is None  # same digit blocked


def test_debounce_allows_different_digit_immediately():
    listener = _make_listener()
    result1 = listener.process_recognition("three")
    assert result1 == (3, "three")

    result2 = listener.process_recognition("four")
    assert result2 == (4, "four")  # different digit passes through

    result3 = listener.process_recognition("five")
    assert result3 == (5, "five")  # another different digit passes through


def test_debounce_allows_same_digit_after_cooldown():
    listener = _make_listener(debounce_ms=50)
    result1 = listener.process_recognition("five")
    assert result1 == (5, "five")

    time.sleep(0.06)

    result2 = listener.process_recognition("five")
    assert result2 == (5, "five")
