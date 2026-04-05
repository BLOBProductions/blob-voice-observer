import json
import os
from config import load_config, DEFAULTS


def test_missing_config_creates_default(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(str(config_path))
    assert config == DEFAULTS
    assert config_path.exists()
    with open(config_path) as f:
        written = json.load(f)
    assert written == DEFAULTS


def test_valid_config_loaded(tmp_path):
    config_path = tmp_path / "config.json"
    custom = {
        "mode": "hold",
        "toggle_key": "F5",
        "hold_key": "space",
        "debounce_ms": 500
    }
    config_path.write_text(json.dumps(custom))
    config = load_config(str(config_path))
    assert config == custom


def test_invalid_mode_falls_back_to_default(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"mode": "invalid"}))
    config = load_config(str(config_path))
    assert config["mode"] == DEFAULTS["mode"]


def test_invalid_debounce_falls_back_to_default(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"debounce_ms": -100}))
    config = load_config(str(config_path))
    assert config["debounce_ms"] == DEFAULTS["debounce_ms"]


def test_empty_toggle_key_falls_back_to_default(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"toggle_key": ""}))
    config = load_config(str(config_path))
    assert config["toggle_key"] == DEFAULTS["toggle_key"]


def test_missing_fields_use_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"mode": "hold"}))
    config = load_config(str(config_path))
    assert config["mode"] == "hold"
    assert config["toggle_key"] == DEFAULTS["toggle_key"]
    assert config["hold_key"] == DEFAULTS["hold_key"]
    assert config["debounce_ms"] == DEFAULTS["debounce_ms"]
