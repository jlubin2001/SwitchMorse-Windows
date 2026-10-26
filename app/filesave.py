# SwitchMorse Windows - filesave.py
# Saving morse_map.txt and config.txt from the program (the Settings window):
#   - a copy of the file as it was goes to a Backups folder next to it first,
#     keeping the newest KEEP copies of each file
#   - the new text is written to a temporary file and then swapped in, so a
#     crash or a full disk never leaves a half-written map
# Only the lines that change are changed: comments, blank lines and the order
# stay as they were, so the file still reads the same in Notepad.
import os
import time

KEEP = 10


def backup(path, keep=KEEP):
    """Copy `path` into Backups\\ next to it as '<name> <date time><ext>'; delete
    the oldest so at most `keep` remain. Returns the copy's path, or None."""
    if not os.path.exists(path):
        return None
    folder = os.path.join(os.path.dirname(path), "Backups")
    os.makedirs(folder, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    stamp = time.strftime("%Y-%m-%d %H%M%S")
    dest = os.path.join(folder, "%s %s%s" % (stem, stamp, ext))
    n = 2
    while os.path.exists(dest):                     # two saves in one second
        dest = os.path.join(folder, "%s %s-%d%s" % (stem, stamp, n, ext))
        n += 1
    with open(path, "rb") as f:
        data = f.read()
    with open(dest, "wb") as f:
        f.write(data)
    mine = sorted(p for p in os.listdir(folder)
                  if p.startswith(stem + " ") and p.endswith(ext))
    for old in mine[:-keep] if keep else []:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return dest


def read_lines(path):
    """The file's lines (no line ends) and the line end it uses."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if b"\r\n" in raw else "\n"
    return text.splitlines(), nl


def write_bytes(path, data, keep=KEEP):
    """Back up `path`, then replace it with `data` exactly (for Undo)."""
    backup(path, keep)
    tmp = path + ".saving"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def write_lines(path, lines, nl="\r\n", keep=KEEP):
    """Back up `path`, then replace it with `lines` (UTF-8, no BOM)."""
    backup(path, keep)
    tmp = path + ".saving"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines) + nl)
    os.replace(tmp, path)
