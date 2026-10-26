# SwitchMorse Windows - keyinput.py
# Two keyboard keys used as the switches (INPUT = keys in config.txt):
# DOT_KEY (default Enter) and DASH_KEY (default Space). Holding the key is
# holding the switch. Many switch interfaces plug in as a USB keyboard and send
# exactly these keys, so they work with SwitchMorse without a Trinkey.
#
# A Windows low-level keyboard hook sees every key press first. The two keys
# are SWALLOWED (they don't type their own Enter / Space while SwitchMorse runs
# in this mode); every other key goes through untouched. Keys that SwitchMorse
# itself types (injected input) always go through, so Morse codes for Enter
# and Space still work. A held key repeats - the repeats are ignored, so a
# long hold is one press. Same interface as switches.SwitchReader.
import ctypes
import threading
import time
from ctypes import wintypes

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10


class Keys:
    """The decision, apart from Windows (so it can be tested): for one key
    event, what happens - (swallow?, event or None)."""

    def __init__(self, dot_vk, dash_vk):
        self.vk = {dot_vk: "dot", dash_vk: "dash"}
        self.down = {"dot": False, "dash": False}

    def handle(self, vk, msg, flags):
        sw = self.vk.get(vk)
        if sw is None or flags & LLKHF_INJECTED:
            return False, None                       # not ours, or typed by SwitchMorse
        pressed = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)
        if pressed == self.down[sw]:
            return True, None                        # a key-repeat: swallow, no event
        self.down[sw] = pressed
        return True, (sw, pressed)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


_HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KeyReader:
    """on_event(switch, pressed, t), on_status(text) - like SwitchReader."""

    def __init__(self, on_event, on_status, dot_vk, dash_vk, label):
        self.on_event = on_event
        self.on_status = on_status
        self.keys = Keys(dot_vk, dash_vk)
        self.label = label                           # e.g. "Enter = dot, Space = dash"
        self.connected = False
        self.source = ""
        self.version = None
        self._tid = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread.join(2)

    def _run(self):
        u = ctypes.windll.user32
        u.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u.CallNextHookEx.restype = wintypes.LPARAM
        u.SetWindowsHookExW.argtypes = (ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
        u.SetWindowsHookExW.restype = wintypes.HHOOK
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()

        def proc(code, wparam, lparam):
            if code == 0:                            # HC_ACTION
                k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                swallow, ev = self.keys.handle(k.vkCode, wparam, k.flags)
                if ev:
                    self.on_event(ev[0], ev[1], time.perf_counter())
                if swallow:
                    return 1
            return u.CallNextHookEx(None, code, wparam, lparam)

        self._proc = _HOOKPROC(proc)                 # keep it alive while hooked
        hook = u.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not hook:
            self.on_status("could not watch the keyboard (error %d)" % ctypes.get_last_error())
            return
        self.connected = True
        self.source = "Keys (%s)" % self.label
        self.on_status("connected keyboard keys (%s)" % self.label)
        msg = wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:   # the hook needs this loop
            pass
        u.UnhookWindowsHookEx(hook)
        self.connected = False
