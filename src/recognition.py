"""Pure digit-recognition helpers: grammar, text parsing, and per-digit debounce."""

import json
import re
import time

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

# Closed grammar restricts Vosk to only these words, improving accuracy and speed.
# "[unk]" is required so Vosk doesn't force every utterance into a digit word.
GRAMMAR = json.dumps(list(WORD_TO_DIGIT.keys()) + ["[unk]"])


def extract_digits(text):
    """Return list of (word, digit) tuples for every digit word found in text."""
    return [
        (word, WORD_TO_DIGIT[word])
        for word in re.findall(r"[a-z]+", text.lower())
        if word in WORD_TO_DIGIT
    ]


class DigitDebouncer:
    """Per-digit cooldown using monotonic time, immune to NTP/clock changes."""

    def __init__(self, debounce_ms=300):
        self.debounce_ms = debounce_ms
        self._last: dict[int, float] = {}

    def should_fire(self, digit):
        now = time.monotonic() * 1000
        if now - self._last.get(digit, 0) < self.debounce_ms:
            return False
        self._last[digit] = now
        return True

    def reset(self):
        self._last.clear()
