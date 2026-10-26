# SwitchMorse Windows - sendinput.py
# Presses keys in Windows with SendInput. The map uses USB HID key numbers (the
# same as AeroMorse); they are turned into Windows virtual keys here.
#
# A whole combination (e.g. Ctrl+Shift+Esc) goes in ONE SendInput call: mods
# down, keys down, keys up, mods up - nothing can come in between, and nothing
# is ever left held down.
import ctypes
from ctypes import wintypes

MARK = 0x534D57                 # "SMW" in dwExtraInfo: our own input

# HID usage -> (Windows virtual key, extended key?)
HID_TO_VK = {}
for _i in range(26):
    HID_TO_VK[0x04 + _i] = (0x41 + _i, False)              # A-Z
for _i in range(9):
    HID_TO_VK[0x1E + _i] = (0x31 + _i, False)              # 1-9
HID_TO_VK[0x27] = (0x30, False)                            # 0
for _i in range(12):
    HID_TO_VK[0x3A + _i] = (0x70 + _i, False)              # F1-F12
for _i in range(12):
    HID_TO_VK[0x68 + _i] = (0x7C + _i, False)              # F13-F24
for _i in range(9):
    HID_TO_VK[0x59 + _i] = (0x61 + _i, False)              # keypad 1-9
HID_TO_VK.update({
    0x28: (0x0D, False), 0x29: (0x1B, False), 0x2A: (0x08, False),
    0x2B: (0x09, False), 0x2C: (0x20, False), 0x2D: (0xBD, False),
    0x2E: (0xBB, False), 0x2F: (0xDB, False), 0x30: (0xDD, False),
    0x31: (0xDC, False), 0x32: (0xDC, False), 0x33: (0xBA, False),
    0x34: (0xDE, False), 0x35: (0xC0, False), 0x36: (0xBC, False),
    0x37: (0xBE, False), 0x38: (0xBF, False), 0x39: (0x14, False),
    0x46: (0x2C, True),  0x47: (0x91, False), 0x48: (0x13, False),
    0x49: (0x2D, True),  0x4A: (0x24, True),  0x4B: (0x21, True),
    0x4C: (0x2E, True),  0x4D: (0x23, True),  0x4E: (0x22, True),
    0x4F: (0x27, True),  0x50: (0x25, True),  0x51: (0x28, True),
    0x52: (0x26, True),  0x53: (0x90, True),  0x54: (0x6F, True),
    0x55: (0x6A, False), 0x56: (0x6D, False), 0x57: (0x6B, False),
    0x58: (0x0D, True),  0x62: (0x60, False), 0x63: (0x6E, False),
    0x65: (0x5D, True),
})
# modifier bit -> (virtual key, extended)
MOD_VK = [(0xA2, False), (0xA0, False), (0xA4, False), (0x5B, True),     # L Ctrl Shift Alt Win
          (0xA3, True), (0xA1, False), (0xA5, True), (0x5C, True)]       # R ...


def combo_events(mods, keys):
    """The key presses for mods + keys, as (vk, extended, key_up) tuples."""
    down = [MOD_VK[i] for i in range(8) if mods & (1 << i)]
    down += [HID_TO_VK[k] for k in keys if k in HID_TO_VK]
    return ([(vk, ext, False) for vk, ext in down] +
            [(vk, ext, True) for vk, ext in reversed(down)])


def release_events():
    """Key-up for every modifier - used by 'release all', pause and on exit."""
    return [(vk, ext, True) for vk, ext in MOD_VK]


# ---- Windows SendInput -------------------------------------------------------
ULONG_PTR = ctypes.c_size_t
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT
_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT


def send_events(events):
    """Send (vk, extended, key_up) tuples in one SendInput call.
    Returns how many Windows accepted (fewer = blocked, e.g. an admin window)."""
    if not events:
        return 0
    arr = (INPUT * len(events))()
    for i, (vk, ext, up) in enumerate(events):
        flags = (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(vk, _user32.MapVirtualKeyW(vk, 0), flags, 0, MARK)
    return _user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


# ---- mouse -------------------------------------------------------------------
MOUSEEVENTF_MOVE, MOUSEEVENTF_WHEEL = 0x0001, 0x0800
BUTTON_FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
                "middle": (0x0020, 0x0040)}
WHEEL_DELTA = 120


def _send_mouse(dx=0, dy=0, data=0, flags=0):
    arr = (INPUT * 1)()
    arr[0].type = INPUT_MOUSE
    arr[0].mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, MARK)
    return _user32.SendInput(1, arr, ctypes.sizeof(INPUT))


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


_user32.WindowFromPoint.argtypes = (POINT,)
_user32.WindowFromPoint.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_OWN_PID = ctypes.windll.kernel32.GetCurrentProcessId()


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class Output:
    """Everything SwitchMorse does to Windows. Tests use a recorder with the
    same methods instead."""

    def keys(self, events):
        return send_events(events)

    def char(self, ch, armed=0):
        """Type one character on the current layout; False if Windows refused."""
        ev = char_events(ch, armed)
        return send_char_events(ev) == len(ev)

    def vk(self, vk):
        return send_events([(vk, True, False), (vk, True, True)])

    def move(self, dx, dy):
        # Relative moves: Windows applies its pointer speed / acceleration, the
        # same as for a real mouse (and for AeroMorse's USB mouse).
        return _send_mouse(dx, dy, 0, MOUSEEVENTF_MOVE)

    def wheel(self, notches):
        return _send_mouse(0, 0, notches * WHEEL_DELTA, MOUSEEVENTF_WHEEL)

    def button(self, name, down):
        return _send_mouse(0, 0, 0, BUTTON_FLAGS[name][0 if down else 1])

    def click(self, name):
        """Press and release in ONE SendInput call, so the release is already
        waiting when Windows looks for it (see pointer_on_own_window)."""
        arr = (INPUT * 2)()
        for i, flag in enumerate(BUTTON_FLAGS[name]):
            arr[i].type = INPUT_MOUSE
            arr[i].mi = MOUSEINPUT(0, 0, 0, flag, 0, MARK)
        return _user32.SendInput(2, arr, ctypes.sizeof(INPUT))

    def pointer_on_own_window(self):
        """True if the pointer is over a window of this program (its window,
        title bar, X button or menu). A button held down there makes Windows
        hold this program's main loop until it comes up - and the release is
        sent BY that main loop, so it would never come."""
        pt = POINT()
        if not _user32.GetCursorPos(ctypes.byref(pt)):
            return False
        hwnd = _user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == _OWN_PID

    def pointer_on_own_panel(self):
        """True if the pointer is over the INSIDE of this program's window (the
        black panel), not its title bar, edges, X button or a menu. Holding the
        button down there does not stop the program (the window moves itself
        when the panel is dragged), so a drag may start there."""
        pt = POINT()
        if not _user32.GetCursorPos(ctypes.byref(pt)):
            return False
        hwnd = _user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != _OWN_PID:
            return False
        top = _user32.GetAncestor(hwnd, 2)                  # GA_ROOT
        cls = ctypes.create_unicode_buffer(64)
        _user32.GetClassNameW(top, cls, 64)
        if cls.value == "#32768":                           # a pop-up menu
            return False
        lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        return _user32.SendMessageW(top, 0x0084, 0, lparam) == 1   # WM_NCHITTEST -> HTCLIENT

    def center(self):
        """Put the pointer in the middle of the screen it is on."""
        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        mon = _user32.MonitorFromPoint(pt, 2)          # nearest monitor
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        _user32.GetMonitorInfoW(mon, ctypes.byref(mi))
        r = mi.rcWork
        _user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)


_user32.MonitorFromPoint.argtypes = (POINT, wintypes.DWORD)
_user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_user32.GetAncestor.restype = wintypes.HWND
_user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.SendMessageW.restype = wintypes.LPARAM
_user32.MonitorFromPoint.restype = wintypes.HANDLE
_user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFO))


# ---- characters, on whatever keyboard layout Windows is using -----------------
# A character is typed by asking Windows which key makes it on the layout of
# the window being typed into (VkKeyScanEx), then pressing that key with Shift
# / AltGr as needed - so @ " # \ and friends come out right on a UK, French,
# German... layout, not just US. A character with no plain key on that layout
# (or only a dead key, like ^ on French) is sent as the character itself
# (Unicode input) instead.
_user32.VkKeyScanExW.argtypes = (wintypes.WCHAR, wintypes.HANDLE)
_user32.VkKeyScanExW.restype = ctypes.c_short
_user32.MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.HANDLE)
_user32.MapVirtualKeyExW.restype = wintypes.UINT
_user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
_user32.GetKeyboardLayout.restype = wintypes.HANDLE
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetForegroundWindow.restype = wintypes.HWND

SPECIAL_CHARS = {"\n": 0x0D, "\r": 0x0D, "\t": 0x09}     # always these keys


def current_layout():
    """The keyboard layout of the window being typed into."""
    tid = _user32.GetWindowThreadProcessId(_user32.GetForegroundWindow(), None)
    return _user32.GetKeyboardLayout(tid)


def plan_char(ch, scan, is_dead):
    """How to type `ch`: ("key", mods, vk) or ("unicode",).
    scan(ch) -> VkKeyScanEx result; is_dead(vk) -> True for a dead key.
    mods are modifier bits as in the map: Ctrl 0x01, Shift 0x02, Alt 0x04."""
    if ch in SPECIAL_CHARS:
        return ("key", 0, SPECIAL_CHARS[ch])
    if len(ch) != 1 or ord(ch) > 0xFFFF:
        return ("unicode",)
    r = scan(ch)
    if r == -1:
        return ("unicode",)
    vk, state = r & 0xFF, (r >> 8) & 0xFF
    if state & ~0x07 or is_dead(vk):        # Hankaku etc., or a dead key
        return ("unicode",)
    mods = (0x02 if state & 1 else 0) | (0x01 if state & 2 else 0) | (0x04 if state & 4 else 0)
    return ("key", mods, vk)


def char_events(ch, armed=0, hkl=None):
    """Events to type ch (with any armed modifier bits held as well)."""
    hkl = current_layout() if hkl is None else hkl
    plan = plan_char(ch,
                     lambda c: _user32.VkKeyScanExW(c, hkl),
                     lambda vk: bool(_user32.MapVirtualKeyExW(vk, 2, hkl) & 0x80000000))
    if plan[0] == "key":
        mods = plan[1] | armed
        down = [MOD_VK[i] for i in range(8) if mods & (1 << i)] + [(plan[2], False)]
        return ([(vk, ext, False) for vk, ext in down] +
                [(vk, ext, True) for vk, ext in reversed(down)])
    return [("unicode", ch, False), ("unicode", ch, True)]


def send_char_events(events):
    """Like send_events, but also handles ("unicode", ch, up) entries."""
    arr = (INPUT * len(events))()
    for i, (vk, ext, up) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        if vk == "unicode":
            arr[i].ki = KEYBDINPUT(0, ord(ext), KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0),
                                   0, MARK)
        else:
            flags = (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
            arr[i].ki = KEYBDINPUT(vk, _user32.MapVirtualKeyW(vk, 0), flags, 0, MARK)
    return _user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))

