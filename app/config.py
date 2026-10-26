# SwitchMorse Windows - config.py
# Reads the settings - nothing to edit here. They are in plain text:
#   app\config.txt              every setting with its default and a note
#   <work folder>\config.txt    your own values (only what you change matters)
# `import config` then gives each setting by name (config.ACCEPT_DELAY ...).
#
# Each setting's kind (yes/no, a number, a list, a word) comes from its default.
# A line with a mistake - an unknown name, "0.2s" for a number - is left out,
# that setting keeps its default, and the problem goes in PROBLEMS (the window
# says so). Nothing in these files is ever run as a program.
# reload() reads them again after a change (the program does this by itself
# when a file changes); save() writes changed values back, line by line.
import os
import re

_APP = os.path.dirname(os.path.abspath(__file__))
DEFAULTS_FILE = os.path.join(_APP, "config.txt")
TRUE = {"yes", "true", "on", "1"}
FALSE = {"no", "false", "off", "0"}
PROBLEMS = []           # "config.txt line 12: ..." for each line left out
_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*(?:\s#.*)?$")


def _lines(path):
    """(line number, NAME, raw value) for each setting line in a file."""
    with open(path, encoding="utf-8-sig") as f:
        for no, line in enumerate(f.read().splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            m = _LINE.match(s)
            yield no, (m.group(1).upper() if m else None), (m.group(2) if m else s)


def _guess(raw):
    """A default's value and kind, from how it is written."""
    v = raw.strip().strip('"\'')
    low = v.lower()
    if low in TRUE - {"1"} or low in FALSE - {"0"}:
        return low in TRUE
    if low == "none":
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    if "," in v:
        return tuple(p.strip() for p in v.split(",") if p.strip())
    return v


def _as(raw, default):
    """`raw` read as the same kind as `default`; raises ValueError if it isn't."""
    v = raw.strip().strip('"\'')
    low = v.lower()
    if isinstance(default, bool):
        if low in TRUE:
            return True
        if low in FALSE:
            return False
        raise ValueError("should be yes or no")
    if isinstance(default, int):
        if not re.fullmatch(r"-?\d+", v):
            raise ValueError("should be a whole number")
        return int(v)
    if isinstance(default, float):
        if not re.fullmatch(r"-?\d*\.?\d+", v):
            raise ValueError("should be a number, like 0.2")
        return float(v)
    if isinstance(default, tuple):
        return tuple(p.strip() for p in v.split(",") if p.strip())
    if default is None:
        return None if low in ("none", "") else v
    return v


def _work_file():
    try:
        import paths
        work = paths.work_folder()
    except Exception:
        return None
    if work == _APP:
        return None
    p = os.path.join(work, "config.txt")
    return p if os.path.exists(p) else None


def read(defaults_file, mine=None):
    """(settings, problems) from the defaults file and, on top, `mine`."""
    values, problems = {}, []
    for no, name, raw in _lines(defaults_file):
        if name:
            values[name] = _guess(raw)
    if mine:
        for no, name, raw in _lines(mine):
            where = "config.txt line %d" % no
            if not name:
                problems.append("%s: %r is not NAME = value - left out" % (where, raw[:40]))
            elif name not in values:
                problems.append("%s: there is no setting called %s - left out" % (where, name))
            else:
                try:
                    values[name] = _as(raw, values[name])
                except ValueError as ex:
                    problems.append("%s: %s = %s %s - the default is used"
                                    % (where, name, raw, ex))
    return values, problems


def reload():
    """Read both files again (they were changed - by hand or from Settings).
    Returns the names of the settings whose value changed."""
    global WORK_FILE
    WORK_FILE = _work_file()
    values, problems = read(DEFAULTS_FILE, WORK_FILE)
    g = globals()
    changed = {name for name, v in values.items() if g.get(name, object()) != v}
    g.update(values)
    PROBLEMS[:] = problems
    return changed


def as_text(value):
    """A value as it is written in config.txt: yes / no, 0.2, a, b, none."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "none"
    if isinstance(value, (tuple, list)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, float):
        return ("%.3f" % value).rstrip("0").rstrip(".") if value % 1 else "%.1f" % value
    return str(value)


def my_file():
    """The config.txt that the Settings window writes: the work folder's (made
    if it isn't there yet), or app\\config.txt when there is no work folder."""
    try:
        import paths
        work = paths.work_folder()
    except Exception:
        work = _APP
    return DEFAULTS_FILE if work == _APP else os.path.join(work, "config.txt")


_EDIT = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\s+#.*)?\s*$")


def save(changes, path=None):
    """Write {NAME: value} into config.txt, changing only those lines: the note
    after # stays (in the same column where it fits), as do every other line,
    comment and blank line. A setting not in the file yet is added at the end.
    Raises ValueError (and writes nothing) for an unknown name or a value of
    the wrong kind. A backup of the file is kept first (filesave.py)."""
    import filesave
    path = path or my_file()
    defaults, _ = read(DEFAULTS_FILE)
    text = {}
    for name, value in changes.items():
        name = name.upper()
        if name not in defaults:
            raise ValueError("there is no setting called %s" % name)
        t = as_text(value)
        try:
            _as(t, defaults[name])
        except ValueError as ex:
            raise ValueError("%s = %s %s" % (name, t, ex))
        text[name] = t
    if os.path.exists(path):
        lines, nl = filesave.read_lines(path)
    else:
        lines, nl = ["# SwitchMorse - your settings (see the program's app\\config.txt",
                     "# for every setting, its default and what it does)", ""], "\r\n"
    done = set()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        m = _EDIT.match(line)
        if not m or m.group(2).upper() not in text:
            continue
        name = m.group(2).upper()
        new = m.group(1) + m.group(2) + m.group(3) + text[name]
        if m.group(5):
            note = m.group(5).lstrip()
            column = len(line) - len(note)
            new += " " * max(1, column - len(new)) + note
        lines[i] = new
        done.add(name)
    missing = [n for n in text if n not in done]
    if missing and lines and lines[-1].strip():
        lines.append("")
    lines += ["%s = %s" % (n, text[n]) for n in missing]
    filesave.write_lines(path, lines, nl)
    return path


WORK_FILE = _work_file()
_values, PROBLEMS = read(DEFAULTS_FILE, WORK_FILE)
globals().update(_values)
