# SwitchMorse Windows - blocked.py
# Is Windows going to block what SwitchMorse types right now?
#
# Windows does not let an ordinary program send keys or mouse moves to:
#   - a window running as administrator (Lorex Cloud, Task Manager, installers)
#   - the "secure screen" (UAC "Do you want to allow..." prompts, Ctrl+Alt+Del,
#     the lock screen)
# and it gives no error - the input just vanishes. A real keyboard or mouse
# (an AeroMorse typing by itself) is never blocked. So while one of these is
# in front, SwitchMorse hands control back to the AeroMorse (switches.py).
import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_user32.OpenInputDesktop.restype = wintypes.HANDLE
_user32.CloseDesktop.argtypes = (wintypes.HANDLE,)
_user32.GetUserObjectInformationW.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                              wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
_advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                          wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION = 20
DESKTOP_SWITCHDESKTOP = 0x0100
UOI_NAME = 2


def _elevated(process_handle):
    """True / False, or None if it can't be read."""
    tok = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(tok)):
        return None
    try:
        val = wintypes.DWORD()
        got = wintypes.DWORD()
        if not _advapi32.GetTokenInformation(tok, TOKEN_ELEVATION, ctypes.byref(val),
                                             ctypes.sizeof(val), ctypes.byref(got)):
            return None
        return bool(val.value)
    finally:
        _kernel32.CloseHandle(tok)


SELF_ELEVATED = bool(_elevated(_kernel32.GetCurrentProcess()))


def secure_screen():
    """True while Windows shows the secure screen (UAC prompt, Ctrl+Alt+Del, lock)."""
    h = _user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not h:
        return True                     # not allowed to see it: the secure desktop
    try:
        buf = ctypes.create_unicode_buffer(64)
        need = wintypes.DWORD()
        if _user32.GetUserObjectInformationW(h, UOI_NAME, buf, ctypes.sizeof(buf),
                                             ctypes.byref(need)):
            return buf.value.lower() != "default"
        return False
    finally:
        _user32.CloseDesktop(h)


def window_blocked(hwnd):
    """True if SwitchMorse's input would be blocked in this window."""
    if not hwnd or SELF_ELEVATED:
        return False
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return True                     # a protected / system window: assume blocked
    try:
        e = _elevated(h)
        return True if e is None else e
    finally:
        _kernel32.CloseHandle(h)


def reason():
    """Why SwitchMorse can't type right now ("admin window", "UAC / secure
    screen"), or None when it can."""
    try:
        if secure_screen():
            return "UAC / secure screen"
        if window_blocked(_user32.GetForegroundWindow()):
            return "admin window"
    except Exception:
        return None
    return None
