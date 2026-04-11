"""Config loader for BLOB Voice Observer.

Reads `config.json` next to the executable (or project root when running
from source). Missing keys fall back to DEFAULTS, invalid values log a
warning and fall back too, the program never hard-fails on a bad config.

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
}

VALID_MODES = {"toggle", "hold"}


def _is_real_number(val):
    # bool is a subclass of int in Python, so isinstance(True, int) is True.
    # Reject it explicitly, True/False should never satisfy numeric ranges.
    return isinstance(val, (int, float)) and not isinstance(val, bool)


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

    if "mode" in user_config:
        if user_config["mode"] in VALID_MODES:
            config["mode"] = user_config["mode"]
        else:
            print(f"WARNING: Invalid mode '{user_config['mode']}', using default '{DEFAULTS['mode']}'")

    for key in ("toggle_key", "hold_key"):
        if key in user_config:
            if isinstance(user_config[key], str) and user_config[key]:
                config[key] = user_config[key]
            else:
                print(f"WARNING: Invalid {key}, using default '{DEFAULTS[key]}'")

    if "debounce_ms" in user_config:
        val = user_config["debounce_ms"]
        if _is_real_number(val) and val >= 0:
            config["debounce_ms"] = int(val)
        else:
            print(f"WARNING: Invalid debounce_ms, using default {DEFAULTS['debounce_ms']}")

    if "vad_aggressiveness" in user_config:
        val = user_config["vad_aggressiveness"]
        if isinstance(val, int) and not isinstance(val, bool) and 0 <= val <= 3:
            config["vad_aggressiveness"] = val
        else:
            print(f"WARNING: Invalid vad_aggressiveness '{val}', using default {DEFAULTS['vad_aggressiveness']}")

    if "trailing_silence_ms" in user_config:
        val = user_config["trailing_silence_ms"]
        if _is_real_number(val) and 30 <= val <= 2000:
            config["trailing_silence_ms"] = int(val)
        elif _is_real_number(val) and 0 < val < 30:
            config["trailing_silence_ms"] = 30
            print(f"WARNING: trailing_silence_ms {val} below minimum, clamped to 30")
        elif _is_real_number(val) and val > 2000:
            config["trailing_silence_ms"] = 2000
            print(f"WARNING: trailing_silence_ms {val} above maximum, clamped to 2000")
        else:
            print(f"WARNING: Invalid trailing_silence_ms '{val}', using default {DEFAULTS['trailing_silence_ms']}")

    if "target_window" in user_config:
        val = user_config["target_window"]
        if isinstance(val, str):
            config["target_window"] = val
        else:
            print(f"WARNING: Invalid target_window '{val}', must be a string")

    return config


def _save_config(config, config_path):
    # dirname("config.json") returns "", fall back to "." to avoid
    # makedirs("") which raises FileNotFoundError on Windows.
    os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
