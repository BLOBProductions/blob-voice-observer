from key_sender import VK_CODES, send_key, send_key_to_window, find_window, _make_lparam
from unittest.mock import patch, MagicMock


def test_vk_codes_has_all_ten_digits():
    for digit in range(10):
        assert digit in VK_CODES
    assert len(VK_CODES) == 10


def test_vk_codes_values_are_correct():
    assert VK_CODES[0] == 0x30
    assert VK_CODES[1] == 0x31
    assert VK_CODES[9] == 0x39


def test_send_key_valid_digit_returns_true():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 2
        assert send_key(5) is True


def test_send_key_invalid_digit_returns_false():
    assert send_key(10) is False
    assert send_key(-1) is False


def test_send_key_calls_sendinput_once_with_two_inputs():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 2
        send_key(3)
        mock_user32.SendInput.assert_called_once()


def test_send_key_returns_false_when_sendinput_fails():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 0
        assert send_key(5) is False


# --- _make_lparam tests ---


def test_make_lparam_keydown():
    lp = _make_lparam(scan_code=0x30, is_keyup=False)
    assert lp & 0xFFFF == 1  # repeat count
    assert (lp >> 16) & 0xFF == 0x30  # scan code
    assert (lp >> 30) & 1 == 0  # previous key state
    assert (lp >> 31) & 1 == 0  # transition state


def test_make_lparam_keyup():
    lp = _make_lparam(scan_code=0x30, is_keyup=True)
    assert lp & 0xFFFF == 1
    assert (lp >> 16) & 0xFF == 0x30
    assert (lp >> 30) & 1 == 1  # previous key state = down
    assert (lp >> 31) & 1 == 1  # transition state = releasing


# --- send_key_to_window tests ---


def test_send_key_to_window_invalid_digit():
    assert send_key_to_window(10, 12345) is False
    assert send_key_to_window(-1, 12345) is False


def test_send_key_to_window_posts_keydown_and_keyup():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.MapVirtualKeyW.return_value = 0x30
        mock_user32.PostMessageW.return_value = True
        assert send_key_to_window(5, 12345) is True
        assert mock_user32.PostMessageW.call_count == 2


def test_send_key_to_window_returns_false_on_post_failure():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.MapVirtualKeyW.return_value = 0x30
        mock_user32.PostMessageW.return_value = False
        assert send_key_to_window(5, 12345) is False


# --- find_window tests ---


def test_find_window_returns_none_for_nonexistent():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.FindWindowW.return_value = None
        mock_user32.EnumWindows.return_value = None
        assert find_window("NonexistentWindow12345") is None
