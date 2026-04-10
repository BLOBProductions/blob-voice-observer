"""Toggle/hold hotkey binding for activating/deactivating voice listening.

Supports two modes:
- toggle: press key once to start, press again to stop
- hold: hold key to listen, release to stop
"""

import keyboard
import threading


class HotkeyManager:
    def __init__(self, mode, toggle_key, hold_key, on_state_change):
        self.mode = mode
        self.toggle_key = toggle_key
        self.hold_key = hold_key
        self.on_state_change = on_state_change
        self._active = False
        self._lock = threading.Lock()
        # Track the handles we registered so stop() can unhook only
        # *our* hooks instead of `keyboard.unhook_all()`, which would
        # stomp on any other hook the host process has registered.
        self._hook_handles = []

    @property
    def is_active(self):
        return self._active

    def start(self):
        if self._hook_handles:
            # Already started, refuse to re-register and duplicate hooks.
            return
        if self.mode == "toggle":
            self._hook_handles.append(
                keyboard.on_press_key(self.toggle_key, self._on_toggle, suppress=False)
            )
        elif self.mode == "hold":
            self._hook_handles.append(
                keyboard.on_press_key(self.hold_key, self._on_hold_press, suppress=False)
            )
            self._hook_handles.append(
                keyboard.on_release_key(self.hold_key, self._on_hold_release, suppress=False)
            )

    def stop(self):
        for handle in self._hook_handles:
            try:
                keyboard.unhook(handle)
            except (KeyError, ValueError):
                # Already unhooked, safe to ignore.
                pass
        self._hook_handles.clear()

    def _on_toggle(self, event):
        with self._lock:
            self._active = not self._active
            self.on_state_change(self._active)

    def _on_hold_press(self, event):
        with self._lock:
            if not self._active:
                self._active = True
                self.on_state_change(True)

    def _on_hold_release(self, event):
        with self._lock:
            if self._active:
                self._active = False
                self.on_state_change(False)
