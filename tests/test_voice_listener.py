import time
from unittest.mock import patch, MagicMock
from voice_listener import WORD_TO_DIGIT, VoiceListener


def test_word_to_digit_has_all_ten_words():
    expected_words = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
    assert set(WORD_TO_DIGIT.keys()) == expected_words


def test_word_to_digit_maps_correctly():
    assert WORD_TO_DIGIT["zero"] == 0
    assert WORD_TO_DIGIT["five"] == 5
    assert WORD_TO_DIGIT["nine"] == 9


def test_process_recognition_valid_word():
    callback = MagicMock()
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = callback
    listener.debounce_ms = 300
    listener._last_recognition_time = 0

    result = listener.process_recognition("five")
    assert result == (5, "five")


def test_process_recognition_unknown_word():
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = MagicMock()
    listener.debounce_ms = 300
    listener._last_recognition_time = 0

    result = listener.process_recognition("hello")
    assert result is None


def test_process_recognition_empty_string():
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = MagicMock()
    listener.debounce_ms = 300
    listener._last_recognition_time = 0

    result = listener.process_recognition("")
    assert result is None


def test_debounce_blocks_rapid_recognition():
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = MagicMock()
    listener.debounce_ms = 300
    listener._last_recognition_time = 0

    result1 = listener.process_recognition("five")
    assert result1 == (5, "five")

    result2 = listener.process_recognition("three")
    assert result2 is None  # blocked by debounce


def test_debounce_allows_after_cooldown():
    listener = VoiceListener.__new__(VoiceListener)
    listener.on_digit = MagicMock()
    listener.debounce_ms = 50
    listener._last_recognition_time = 0

    result1 = listener.process_recognition("five")
    assert result1 == (5, "five")

    time.sleep(0.06)

    result2 = listener.process_recognition("three")
    assert result2 == (3, "three")
