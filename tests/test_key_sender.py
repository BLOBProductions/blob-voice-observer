from key_sender import VK_CODES, send_key
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
    with patch("key_sender.ctypes") as mock_ctypes:
        mock_ctypes.windll.user32.SendInput = MagicMock(return_value=1)
        mock_ctypes.sizeof = MagicMock(return_value=40)
        mock_ctypes.byref = MagicMock()
        assert send_key(5) is True


def test_send_key_invalid_digit_returns_false():
    assert send_key(10) is False
    assert send_key(-1) is False


def test_send_key_calls_sendinput_twice():
    with patch("key_sender.ctypes") as mock_ctypes:
        mock_ctypes.windll.user32.SendInput = MagicMock(return_value=1)
        mock_ctypes.sizeof = MagicMock(return_value=40)
        mock_ctypes.byref = MagicMock()
        send_key(3)
        assert mock_ctypes.windll.user32.SendInput.call_count == 2
