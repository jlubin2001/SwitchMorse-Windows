# SwitchMorse Windows - appicon.py
# SwitchMorse's own icon (a cyan dot and dash on black) and its own taskbar
# identity. Without them Windows shows Python's icon, the same as every other
# Python program (e.g. other Tkinter tools), and may group them all under one
# taskbar button.
import ctypes

APP_ID = "SwitchMorse.Windows"
BG, FG = "#000000", "#00FFFF"


def set_app_id():
    """Call before the first window is made: SwitchMorse gets its own taskbar
    button and icon instead of sharing Python's."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _picture(tk, size):
    """A dot and a dash, drawn pixel by pixel (no icon file needed)."""
    img = tk.PhotoImage(width=size, height=size)
    img.put(BG, to=(0, 0, size, size))
    s = size / 64.0
    cx, cy, r = 17 * s, 32 * s, 8 * s                      # the dot
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            dot = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r
            dash = 31 * s <= x < 57 * s and 26 * s <= y < 38 * s
            row.append(FG if dot or dash else BG)
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    return img


def set_icon(root):
    """Give this Tk window (and the taskbar) the SwitchMorse icon."""
    try:
        import tkinter as tk
        root._sm_icons = [_picture(tk, n) for n in (64, 32, 16)]   # keep them alive
        root.iconphoto(True, *root._sm_icons)
    except Exception:
        pass
