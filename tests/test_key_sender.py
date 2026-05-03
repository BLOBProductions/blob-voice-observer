from unittest.mock import patch

from key_sender import VK_CODES, _make_lparam, find_window, resolve_vk, send_key, send_key_to_window


def test_vk_codes_has_all_ten_digits():
    for digit in range(10):
        assert digit in VK_CODES
    assert len(VK_CODES) == 10


def test_vk_codes_values_are_correct():
    assert VK_CODES[0] == 0x30
    assert VK_CODES[1] == 0x31
    assert VK_CODES[9] == 0x39


# --- resolve_vk tests ---


def test_resolve_vk_named_key():
    assert resolve_vk("f6") == 0x75
    assert resolve_vk("F6") == 0x75
    assert resolve_vk("space") == 0x20
    assert resolve_vk("enter") == 0x0D
    assert resolve_vk("escape") == 0x1B


def test_resolve_vk_raw_hex():
    assert resolve_vk("0x35") == 0x35
    assert resolve_vk("0x41") == 0x41


def test_resolve_vk_ascii_letter():
    # ASCII fallback (no user32 in test environment)
    with patch("key_sender.user32", None):
        assert resolve_vk("A") == 0x41
        assert resolve_vk("a") == 0x41
        assert resolve_vk("z") == 0x5A


def test_resolve_vk_ascii_digit():
    with patch("key_sender.user32", None):
        assert resolve_vk("0") == 0x30
        assert resolve_vk("9") == 0x39


def test_resolve_vk_unknown_returns_none():
    with patch("key_sender.user32", None):
        assert resolve_vk("not_a_key") is None
        assert resolve_vk("") is None


def test_resolve_vk_layout_aware_uses_vkkeyscanw():
    mock_user32 = patch("key_sender.user32").start()
    # Simulate AZERTY: "&" → VK 0x31 (no modifier needed, mod=0)
    mock_user32.VkKeyScanW.return_value = (0 << 8) | 0x31
    result = resolve_vk("&")
    assert result == 0x31
    mock_user32.VkKeyScanW.assert_called_once_with("&")
    patch.stopall()


def test_resolve_vk_vkkeyscanw_not_found_falls_back():
    mock_user32 = patch("key_sender.user32").start()
    # 0xFFFF means "not found"
    mock_user32.VkKeyScanW.return_value = 0xFFFF
    # single non-ASCII char with no named-key match → None
    result = resolve_vk("é")
    assert result is None
    patch.stopall()


# --- send_key tests ---


def test_send_key_returns_true_on_success():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 2
        assert send_key(0x35) is True


def test_send_key_calls_sendinput_once_with_two_inputs():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 2
        send_key(0x33)
        mock_user32.SendInput.assert_called_once()


def test_send_key_returns_false_when_sendinput_fails():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.SendInput.return_value = 0
        assert send_key(0x35) is False


# --- _make_lparam tests ---


def test_make_lparam_keydown():
    lp = _make_lparam(scan_code=0x30, is_keyup=False)
    assert lp & 0xFFFF == 1
    assert (lp >> 16) & 0xFF == 0x30
    assert (lp >> 30) & 1 == 0
    assert (lp >> 31) & 1 == 0


def test_make_lparam_keyup():
    lp = _make_lparam(scan_code=0x30, is_keyup=True)
    assert lp & 0xFFFF == 1
    assert (lp >> 16) & 0xFF == 0x30
    assert (lp >> 30) & 1 == 1
    assert (lp >> 31) & 1 == 1


# --- send_key_to_window tests ---


def test_send_key_to_window_posts_keydown_and_keyup():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.MapVirtualKeyW.return_value = 0x30
        mock_user32.PostMessageW.return_value = True
        assert send_key_to_window(0x35, 12345) is True
        assert mock_user32.PostMessageW.call_count == 2


def test_send_key_to_window_returns_false_on_post_failure():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.MapVirtualKeyW.return_value = 0x30
        mock_user32.PostMessageW.return_value = False
        assert send_key_to_window(0x35, 12345) is False


# --- find_window tests ---


def test_find_window_returns_none_for_nonexistent():
    with patch("key_sender.user32") as mock_user32:
        mock_user32.FindWindowW.return_value = None
        mock_user32.EnumWindows.return_value = None
        assert find_window("NonexistentWindow12345") is None
