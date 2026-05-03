"""Config loader for BLOB Voice Observer.

Reads `config.json` next to the executable (or project root when running from
source). Missing keys fall back to DEFAULTS; invalid values log a warning and
fall back too — the program never hard-fails on a bad config.

If `config.json` does not exist, a default file is created on first run.
"""

import json
import os

DEFAULTS = {
    "mode": "toggle",
    "toggle_key": "F6",
    "hold_key": "caps_lock",
    "debounce_ms": 300,
    "vad_aggressiveness": 3,
    "trailing_silence_ms": 120,
    "target_window": "VALORANT",
    "microphone_device_index": 0,
}

_VALID_MODES = {"toggle", "hold"}


def _is_number(val):
    # bool is a subclass of int; reject it so True/False don't satisfy ranges.
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _is_int(val):
    return isinstance(val, int) and not isinstance(val, bool)


def _validate(key, val):
    """Return (value, error_message) for a single config key."""
    default = DEFAULTS[key]

    if key == "mode":
        if val in _VALID_MODES:
            return val, None
        return default, f"Invalid mode '{val}'"

    if key in ("toggle_key", "hold_key"):
        if isinstance(val, str) and val:
            return val, None
        return default, f"Invalid {key}"

    if key == "debounce_ms":
        if _is_number(val) and val >= 0:
            return int(val), None
        return default, f"Invalid debounce_ms"

    if key == "vad_aggressiveness":
        if _is_int(val) and 0 <= val <= 3:
            return val, None
        return default, f"Invalid vad_aggressiveness '{val}'"

    if key == "trailing_silence_ms":
        if not _is_number(val):
            return default, f"Invalid trailing_silence_ms '{val}'"
        if val < 0:
            return default, f"Invalid trailing_silence_ms '{val}'"
        if val < 30:
            return 30, f"trailing_silence_ms {val} below minimum, clamped to 30"
        if val > 2000:
            return 2000, f"trailing_silence_ms {val} above maximum, clamped to 2000"
        return int(val), None

    if key == "target_window":
        if isinstance(val, str):
            return val, None
        return default, f"Invalid target_window '{val}', must be a string"

    if key == "microphone_device_index":
        if val is None:
            return None, None
        if _is_int(val) and val >= 0:
            return val, None
        return default, f"Invalid microphone_device_index '{val}', must be a non-negative integer or null"

    return val, None  # unknown key: pass through


def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        _save_config(DEFAULTS, config_path)
        print(f"Created default config at {config_path}")
        return dict(DEFAULTS)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except json.JSONDecodeError:
        print(f"WARNING: Config file at {config_path} is not valid JSON, using defaults")
        return dict(DEFAULTS)

    config = dict(DEFAULTS)
    for key in DEFAULTS:
        if key not in user_config:
            continue
        value, warning = _validate(key, user_config[key])
        if warning:
            print(f"WARNING: {warning}, using default {DEFAULTS[key]!r}")
        config[key] = value

    return config


def _save_config(config, config_path):
    # dirname("config.json") returns ""; fall back to "." to avoid makedirs("").
    os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
