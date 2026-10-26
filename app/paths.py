# SwitchMorse Windows - paths.py
# Where the user's own files live: their map (morse_map.txt), their settings
# (config.txt) and the cheat sheet. Normally that is a separate WORK FOLDER
# (made by tools\make_work_folder.py, e.g. Documents\SwitchMorse), named in
# app\workfolder.txt; without one, it is this app folder itself.
# Installed (SwitchMorse.exe) the program folder can't be written to, so the
# work folder is always separate: the one named in
# %APPDATA%\SwitchMorse\workfolder.txt, else Documents\SwitchMorse (made at
# the first start).
import ctypes
import os
import sys

APP = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)          # running as SwitchMorse.exe
POINTER = (os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SwitchMorse",
                        "workfolder.txt") if FROZEN else os.path.join(APP, "workfolder.txt"))


def documents():
    """The user's Documents folder (wherever Windows has moved it)."""
    buf = ctypes.create_unicode_buffer(260)
    try:
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def work_folder():
    """The user's work folder, or the app folder if there is none."""
    try:
        with open(POINTER, encoding="utf-8-sig") as f:
            path = f.readline().strip()
        if path and os.path.isdir(path):
            return path
    except OSError:
        pass
    if FROZEN:
        path = os.path.join(documents(), "SwitchMorse")
        os.makedirs(path, exist_ok=True)
        return path
    return APP
