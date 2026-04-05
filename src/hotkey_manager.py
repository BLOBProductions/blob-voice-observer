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

    @property
    def is_active(self):
        return self._active

    def start(self):
        if self.mode == "toggle":
            keyboard.on_press_key(self.toggle_key, self._on_toggle, suppress=False)
        elif self.mode == "hold":
            keyboard.on_press_key(self.hold_key, self._on_hold_press, suppress=False)
            keyboard.on_release_key(self.hold_key, self._on_hold_release, suppress=False)

    def stop(self):
        keyboard.unhook_all()

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
