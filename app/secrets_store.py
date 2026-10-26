# SwitchMorse Windows - secrets_store.py
# Passwords and other private text for "secret NAME" codes in morse_map.txt.
#
# Kept in %APPDATA%\SwitchMorse\secrets.dat, encrypted with Windows' own
# DPAPI for the user's Windows account: only that account, signed in on this PC,
# can read it. Nothing is ever in morse_map.txt, the window, the press log or
# git. Change them with the SwitchMorse Passwords window (secrets_window.py).
#
# A missing or unreadable file never stops SwitchMorse - the secret codes
# just type nothing and say "(not set)".
import ctypes
import json
import os
from ctypes import wintypes

FOLDER = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SwitchMorse")
PATH = os.path.join(FOLDER, "secrets.dat")
_ENTROPY = b"SwitchMorse Windows secrets v1"     # ties the file to this program


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _protect(data):
    src, keep = _blob(data)
    ent, keep2 = _blob(_ENTROPY)
    out = _Blob()
    if not _crypt32.CryptProtectData(ctypes.byref(src), "SwitchMorse secrets", ctypes.byref(ent),
                                     None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("Windows could not encrypt the secrets (error %d)" % ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel32.LocalFree(out.pbData)


def _unprotect(data):
    src, keep = _blob(data)
    ent, keep2 = _blob(_ENTROPY)
    out = _Blob()
    if not _crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent),
                                       None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("Windows could not open the secrets file (error %d) - was it made "
                      "by another Windows account or PC?" % ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        _kernel32.LocalFree(out.pbData)


def load(path=PATH):
    """{name: value}. Raises OSError / ValueError if the file can't be read;
    a file that isn't there yet is simply empty."""
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        raw = f.read()
    data = json.loads(_unprotect(raw).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the secrets file is not in the right form")
    return {str(k): str(v) for k, v in data.items()}


def save(secrets, path=PATH):
    """Write {name: value}, encrypted. Written to a temporary file first, so a
    failure part-way never leaves a half-written file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = _protect(json.dumps(secrets, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    tmp = path + ".new"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


class Secrets:
    """What the program uses: get(name) -> value or None. Re-reads the file
    when it changes (so the Passwords window takes effect at once)."""

    def __init__(self, path=PATH):
        self.path = path
        self._mtime = None
        self._data = {}
        self.error = None

    def _refresh(self):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            m = None
        if m == self._mtime:
            return
        self._mtime = m
        try:
            self._data = load(self.path)
            self.error = None
        except Exception as ex:             # never stop the program over this file
            self._data = {}
            self.error = str(ex)

    def get(self, name):
        self._refresh()
        return self._data.get(name)
