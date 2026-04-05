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
