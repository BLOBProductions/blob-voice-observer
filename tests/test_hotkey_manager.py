from unittest.mock import patch, MagicMock, call
from hotkey_manager import HotkeyManager


def test_starts_inactive():
    mgr = HotkeyManager(
        mode="toggle",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=MagicMock(),
    )
    assert mgr.is_active is False


def test_toggle_flips_state():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="toggle",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    mgr._on_toggle(None)
    assert mgr.is_active is True
    callback.assert_called_with(True)

    mgr._on_toggle(None)
    assert mgr.is_active is False
    callback.assert_called_with(False)


def test_hold_press_activates():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="hold",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    mgr._on_hold_press(None)
    assert mgr.is_active is True
    callback.assert_called_once_with(True)


def test_hold_release_deactivates():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="hold",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    mgr._on_hold_press(None)
    mgr._on_hold_release(None)
    assert mgr.is_active is False
    assert callback.call_args_list == [call(True), call(False)]


def test_hold_press_does_not_double_activate():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="hold",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    mgr._on_hold_press(None)
    mgr._on_hold_press(None)
    callback.assert_called_once_with(True)


def test_hold_release_without_press_does_nothing():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="hold",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    mgr._on_hold_release(None)
    assert mgr.is_active is False
    callback.assert_not_called()


def test_start_registers_toggle_hotkey():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="toggle",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    with patch("hotkey_manager.keyboard") as mock_kb:
        mgr.start()
        mock_kb.on_press_key.assert_called_once_with("F6", mgr._on_toggle, suppress=False)


def test_start_registers_hold_hotkeys():
    callback = MagicMock()
    mgr = HotkeyManager(
        mode="hold",
        toggle_key="F6",
        hold_key="caps_lock",
        on_state_change=callback,
    )

    with patch("hotkey_manager.keyboard") as mock_kb:
        mgr.start()
        mock_kb.on_press_key.assert_called_once_with("caps_lock", mgr._on_hold_press, suppress=False)
        mock_kb.on_release_key.assert_called_once_with("caps_lock", mgr._on_hold_release, suppress=False)
