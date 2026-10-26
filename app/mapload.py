# SwitchMorse Windows - mapload.py
# Reads morse_map.txt, the plain-text list of codes:
#
#   [Keyboard]
#   .-        a
#   -.-.      Ctrl              # sticky: applies to the next key
#   ---.-.    Shift+Tab
#
# and turns every line into an Action the program can carry out. The full
# description of what a line can say is at the top of morse_map.txt.
# Problems never stop the map loading: a bad line is left out and reported
# with its line number; every other line still works.
# set_code() / delete_code() change one code from the program, line by line.
import os
import re
from collections import namedtuple

import hid_names

N_GROUPS = 4                    # SwitchMorse uses groups 0-3 only
GROUP_NAMES = ["BASE", "KEYBOARD", "MOUSE", "MACRO"]
SECTIONS = {"base": 0, "keyboard": 1, "mouse": 2, "macros": 3, "macro": 3,
            "group 0": 0, "group 1": 1, "group 2": 2, "group 3": 3}
SECTION_TITLES = ["Base", "Keyboard", "Mouse", "Macros"]

# kind: "char"  one character (text), typed on the current keyboard layout
#       "text"  a phrase (text), typed character by character
#       "secret" a password / private text, by name (text) - see secrets_store.py
#       "key"   mods bitmask + HID keys (a key or keys pressed together)
#       "mod"   sticky modifier (bit in mods)
#       "vk"    a Windows-only key (media / app launch), its virtual key in keys[0]
#       "group" group number
#       "cmd"   command: cmd is a tuple, e.g. ("repeat",), ("mmove", 1, 0, 0),
#               ("mclick", "left", 2), ("mdrag", "left")
Action = namedtuple("Action", "kind mods keys group cmd label text", defaults=(None,))

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "right": (1, 0), "left": (-1, 0),
              "up-left": (-1, -1), "up-right": (1, -1),
              "down-left": (-1, 1), "down-right": (1, 1)}
# Windows-only keys: name -> (virtual key, label)
MEDIA_KEYS = {"playpause": (0xB3, "Play/Pause"), "mute": (0xAD, "Mute"),
              "volumedown": (0xAE, "Volume Down"), "volumeup": (0xAF, "Volume Up"),
              "nexttrack": (0xB0, "Next Track"), "previoustrack": (0xB1, "Previous Track"),
              "stopmedia": (0xB2, "Stop Media"), "calculator": (0xB7, "Calculator"),
              "fileexplorer": (0xB6, "File Explorer"), "webbrowser": (0xAC, "Web Browser"),
              "mail": (0xB4, "Mail")}


def _norm(name):
    return re.sub(r"[\s_\-]", "", name.lower())


# Key names -> HID key number. Every Keycode name works (PAGE_DOWN, Page Down,
# pagedown ...), plus the everyday names below.
KEY_NAMES = {}
for _n, _v in vars(hid_names.Keycode).items():
    if not _n.startswith("_"):
        KEY_NAMES.setdefault(_norm(_n), _v)
KEY_NAMES.update({
    "ctrl": 0xE0, "control": 0xE0, "lctrl": 0xE0, "shift": 0xE1, "lshift": 0xE1,
    "alt": 0xE2, "lalt": 0xE2, "win": 0xE3, "windows": 0xE3, "lwin": 0xE3,
    "rctrl": 0xE4, "rightctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6, "altgr": 0xE6,
    "rightalt": 0xE6, "rwin": 0xE7, "rightwin": 0xE7,
    "esc": 0x29, "del": 0x4C, "ins": 0x49, "pgup": 0x4B, "pgdn": 0x4E,
    "up": 0x52, "down": 0x51, "left": 0x50, "right": 0x4F,
    "numlock": 0x53, "prtsc": 0x46, "menu": 0x65, "contextmenu": 0x65,
    "keypad.": 0x63, "keypad/": 0x54, "keypad*": 0x55, "keypad+": 0x57,
    "keypad=": 0x67,
    "pausekey": 0x48, "break": 0x48,    # "pause" on its own is the pause COMMAND
})
for _i in range(1, 10):                 # Keypad 1 ... Keypad 9, Keypad 0
    KEY_NAMES["keypad%d" % _i] = 0x58 + _i
KEY_NAMES["keypad0"] = 0x62
MOD_BITS = {0xE0 + i: 1 << i for i in range(8)}


def code_str(n, p):
    return "".join("-" if (p >> (n - 1 - i)) & 1 else "." for i in range(n))


def _key_label(mods, keys):
    parts = [hid_names.MOD_LABELS[i] for i in range(8) if mods & (1 << i)]
    parts += [hid_names.KEY_LABELS.get(k, "Key %d" % k) for k in keys]
    return "+".join(parts)


def _key_part(part):
    """One piece of a key combination -> (mod bits, HID key or None), or None."""
    if len(part) == 1:
        if part.isalnum():                          # Ctrl+C, Alt+4: the key itself
            return 0, hid_names.US_CHARS[part.lower()][1] if part.lower() in hid_names.US_CHARS else None
        if part in hid_names.US_CHARS:              # Ctrl+=  Ctrl+-  Ctrl+?
            shift, k = hid_names.US_CHARS[part]
            return (2 if shift else 0), k
        return None
    k = KEY_NAMES.get(_norm(part))
    if k is None:
        return None
    if k in MOD_BITS:
        return MOD_BITS[k], None
    return 0, k


def _command(words):
    """A command -> (cmd tuple, label), or None."""
    w = [x.lower() for x in words]
    s = " ".join(w)
    if s in ("repeat", "pause"):
        return (s,), s.title()
    if s == "release all":
        return ("releaseall",), "Release all"
    if s in ("mouse slow", "mouse fast"):
        return ("m" + w[1],), s.capitalize()
    if s in ("show window", "show switchmorse"):
        return ("showwindow",), "Window to the front"
    if s == "settings":
        return ("settings",), "Settings"
    if s in ("centre pointer", "center pointer"):
        return ("mcenter",), "Centre pointer"
    if len(w) == 2 and w[0] == "move" and w[1] in DIRECTIONS:
        dx, dy = DIRECTIONS[w[1]]
        return ("mmove", dx, dy, 0), "Mouse " + w[1]
    if len(w) == 2 and w[0] == "scroll" and w[1] in ("up", "down"):
        return ("mmove", 0, 0, 1 if w[1] == "up" else -1), "Scroll " + w[1]
    if len(w) == 2 and w[0] == "click" and w[1] in ("left", "right", "middle"):
        return ("mclick", w[1], 1), w[1].title() + " click"
    if len(w) == 3 and w[:2] == ["double", "click"] and w[2] in ("left", "right", "middle"):
        return ("mclick", w[2], 2), "Double " + w[2] + " click"
    if len(w) == 2 and w[0] == "drag" and w[1] in ("left", "right"):
        return ("mdrag", w[1]), "Drag " + w[1]
    return None


def parse_action(text):
    """The action part of a line -> Action, or an error message (str)."""
    t = text.strip()
    if not t:
        return "nothing after the code"
    if t[0] in "\"'":
        body = t[1:-1]
        if len(t) < 2 or t[-1] != t[0]:
            return "the text has no closing quote"
        if len(body) == 1:
            return Action("char", 0, (), None, None, body, body)
        if not body:
            return "the quotes are empty"
        short = body if len(body) <= 18 else body[:17] + "…"
        return Action("text", 0, (), None, None, '"%s"' % short, body)
    if len(t) == 1:
        return Action("char", 0, (), None, None, t, t)

    words = t.split()
    if words[0].lower() == "group" and len(words) >= 2:
        name = " ".join(words[1:]).lower()
        g = int(name) if name.isdigit() else SECTIONS.get(name)
        if g is None or not 0 < g < N_GROUPS:
            return "no group called %r (Keyboard, Mouse or Macros)" % " ".join(words[1:])
        return Action("group", 0, (), g, None, "Group %d %s" % (g, SECTION_TITLES[g]))
    if words[0].lower() == "secret":
        if len(words) != 2 or not re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", words[1]):
            return "a secret needs one name made of letters, numbers, _ - or ., e.g. secret email_pw"
        return Action("secret", 0, (), None, None, "secret " + words[1], words[1])
    c = _command(words)
    if c:
        return Action("cmd", 0, (), None, c[0], c[1])
    tap = words[0].lower() == "tap"
    if tap:
        t = " ".join(words[1:])
    if _norm(t) in MEDIA_KEYS and not tap:
        vk, label = MEDIA_KEYS[_norm(t)]
        return Action("vk", 0, (vk,), None, None, label)

    parts = t.split("+")
    if t.endswith("++"):                            # Ctrl++  = Ctrl and the + key
        parts = parts[:-2] + ["+"]
    mods = 0
    keys = []
    for part in parts:
        r = _key_part(part.strip())
        if r is None or (r[1] is None and r[0] == 0):
            return "%r is not a key name or a command" % part.strip()
        mods |= r[0]
        if r[1] is not None:
            keys.append(r[1])
    if len(parts) == 1 and not keys and not tap:
        return Action("mod", mods, (), None, None, hid_names.MOD_LABELS[mods.bit_length() - 1])
    if len(keys) > 6:
        return "more than 6 keys at once"
    return Action("key", mods, tuple(keys), None, None,
                  ("Tap " if tap else "") + _key_label(mods, keys))


def _split_line(line):
    """'.-   a   # note' -> ('.-', 'a'). The comment starts at a # that follows
    a space and is not inside quotes."""
    m = re.match(r"\s*(\S+)\s*(.*)$", line)
    code, rest = m.group(1), m.group(2)
    if rest[:1] in ("'", '"'):
        end = rest.find(rest[0], 1)
        if end > 0:
            return code, rest[:end + 1]
        return code, rest                       # no closing quote: parse_action says so
    cut = re.search(r"\s#", rest)
    if rest.startswith("#") and len(rest.split()[0]) > 1:
        return code, ""                         # '.-  #comment' (no action)
    return code, (rest[:cut.start()] if cut else rest).strip()


def default_path():
    """The user's map: in their work folder (paths.py), else next to this file."""
    import paths
    return os.path.join(paths.work_folder(), "morse_map.txt")


def ensure_map(path=None):
    """First start: there is no morse_map.txt yet, so make it from
    morse_map.example.txt (which ships with SwitchMorse). Your own copy is then
    yours to change; later updates never overwrite it."""
    path = path or default_path()
    example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morse_map.example.txt")
    if not os.path.exists(path) and os.path.exists(example):
        import shutil
        shutil.copyfile(example, path)


def load(path=None):
    """Returns (codes, problems). codes[(group, length, pattern)] = Action;
    each problem is a sentence starting with its line number."""
    if not path:
        path = default_path()
        ensure_map(path)
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    codes = {}
    where = {}                                  # (g, n, p) -> line number
    problems = []
    group = None
    bad_heading = False             # under a [heading] that was already reported
    for no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            name = line.strip("[] ").lower()
            group = SECTIONS.get(name)
            bad_heading = group is None
            if bad_heading:
                problems.append("line %d: no group called [%s] - its codes are left out"
                                % (no, line.strip("[] ")))
            continue
        code, act = _split_line(raw)
        if group is None:
            if not bad_heading:
                problems.append("line %d: a code before any [Group] heading - left out" % no)
            continue
        if not re.fullmatch(r"[.\-]{1,8}", code):
            problems.append("line %d: %r is not a code (1 to 8 dots and dashes)" % (no, code))
            continue
        a = parse_action(act)
        if isinstance(a, str):
            problems.append("line %d: %s %s - %s" % (no, code, act or "", a))
            continue
        n = len(code)
        p = int(code.replace(".", "0").replace("-", "1"), 2)
        key = (group, n, p)
        if key in codes:
            problems.append("line %d: %s is already used on line %d in [%s] - this line is left out"
                            % (no, code, where[key], SECTION_TITLES[group]))
            continue
        codes[key] = a
        where[key] = no

    # Leave out group commands that lead to an empty group.
    filled = {g for (g, n, p) in codes if g}
    for key, a in list(codes.items()):
        if a.kind == "group" and a.group not in filled:
            problems.append("line %d: %s goes to [%s], which has no codes yet - left out"
                            % (where[key], code_str(key[1], key[2]), SECTION_TITLES[a.group]))
            del codes[key]

    # Base codes work in every group, so they hide the same code elsewhere.
    for (g, n, p), a in sorted(codes.items()):
        if g and (0, n, p) in codes:
            problems.append("line %d: %s (%s) is hidden by the same code in [Base]"
                            % (where[(g, n, p)], code_str(n, p), a.label))
    problems.sort(key=lambda s: int(re.match(r"line (\d+)", s).group(1)))
    return codes, problems


def groups_in(codes):
    return sorted({g for (g, n, p) in codes if g})


# ---- changing the map from the program (the Settings window) -----------------
# Only the line for that code changes; every comment, blank line and the order
# stay, so the file still reads the same in Notepad. A backup is kept first.
CODE_COLUMN = 10        # actions start in this column (as in morse_map.example.txt)
NOTE_COLUMN = 32        # and notes after # in this one


def phrase(text):
    """Text to type -> the action as written in the map: "Thank you"."""
    return ("'%s'" if '"' in text and "'" not in text else '"%s"') % text


def _sections(lines):
    """{group: (heading line index, index after its last line)} - the first
    [heading] for each group."""
    heads = [(i, SECTIONS.get(l.strip().strip("[] ").lower()))
             for i, l in enumerate(lines) if l.strip().startswith("[")]
    out = {}
    for k, (i, g) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        if g is not None and g not in out:
            out[g] = (i, end)
    return out


def _code_lines(lines, start, end):
    """(index, code) of every code line between start and end."""
    for i in range(start + 1, end):
        s = lines[i].strip()
        if s and not s.startswith("#") and not s.startswith("["):
            yield i, _split_line(lines[i])[0]


LINE_WIDTH = 88         # a long note wraps onto indented # lines under its code


def _line(code, action, note=None, like=None):
    """A map line, with the action (and note) in the same columns as `like`.
    A long note goes on as indented '# ...' lines: the result can be several
    lines, joined with newlines."""
    import textwrap
    col = CODE_COLUMN
    if like:
        m = re.match(r"\s*\S+\s+", like)
        if m:
            col = len(m.group(0))
    s = code + " " * max(2, col - len(code)) + action
    if note:
        at = max(len(s) + 3, NOTE_COLUMN)
        parts = textwrap.wrap(note.lstrip("# "), max(20, LINE_WIDTH - at - 2)) or [""]
        s += " " * (at - len(s)) + "# " + parts[0]
        for p in parts[1:]:
            s += "\n" + " " * at + "# " + p
    return s


def _note(line):
    """The '# note' at the end of a code line, or None."""
    code, act = _split_line(line)
    rest = line[re.match(r"\s*\S+\s*", line).end():]
    if act and rest.startswith(act):
        rest = rest[len(act):]
    m = re.search(r"#\s?(.*)$", rest)
    return m.group(1) if m else None


def _note_lines(lines, i):
    """How many indented '# ...' lines follow line i (the rest of its note)."""
    n = 0
    while i + 1 + n < len(lines) and lines[i + 1 + n].startswith((" ", "\t")) \
            and lines[i + 1 + n].strip().startswith("#"):
        n += 1
    return n


def _full_note(lines, i):
    """The note of code line i, with the indented note lines under it joined on."""
    parts = [_note(lines[i])] + [lines[j].strip().lstrip("#").strip()
                                 for j in range(i + 1, i + 1 + _note_lines(lines, i))]
    return " ".join(p for p in parts if p) or None


def entries(path=None):
    """Every code line, for the Settings window: a list of dicts with group,
    code, text (the action as written), note, line (number) and action (an
    Action, or an error message when the line is left out)."""
    lines, _ = _read(path)
    out = []
    for group, (start, end) in sorted(_sections(lines).items()):
        seen = set()
        for i, code in _code_lines(lines, start, end):
            text = _split_line(lines[i])[1]
            a = parse_action(text) if re.fullmatch(r"[.\-]{1,8}", code) else "not a code"
            if code in seen and not isinstance(a, str):
                a = "already used above - left out"     # (settings_window.DUPLICATE)
            seen.add(code)
            out.append(dict(group=group, code=code, text=text, note=_full_note(lines, i),
                            line=i + 1, action=a))
    return out


def find_code(group, code, path=None):
    """(line number, action text, note) of `code` in [group], or None."""
    lines, _ = _read(path)
    sec = _sections(lines).get(group)
    if sec:
        for i, c in _code_lines(lines, *sec):
            if c == code:
                return i + 1, _split_line(lines[i])[1], _note(lines[i])
    return None


def _read(path):
    import filesave
    return filesave.read_lines(path or default_path())


def _check_code(code):
    if not re.fullmatch(r"[.\-]{1,8}", code or ""):
        raise ValueError("%r is not a code (1 to 8 dots and dashes)" % code)


def set_code(group, code, action, note=None, path=None, old_code=None, replace=False):
    """Put `code` -> `action` (written as in the map: a, Ctrl+C, "phrase",
    move left ...) in [group]. `old_code` = the code this one was (changing a
    code's dots and dashes); otherwise a code already there is changed in place
    only with replace=True. A note of None keeps the line's note. Raises
    ValueError, writing nothing, if the code or action is wrong or the code is
    already used. Returns the line number."""
    import filesave
    _check_code(code)
    a = parse_action(action)
    if isinstance(a, str):
        raise ValueError("%s - %s" % (action, a))
    if not 0 <= group < N_GROUPS:
        raise ValueError("no group %r" % group)
    path = path or default_path()
    lines, nl = _read(path)
    secs = _sections(lines)
    if group not in secs:                           # no [heading] yet: add one
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[%s]" % SECTION_TITLES[group])
        secs = _sections(lines)
    start, end = secs[group]
    found = {c: i for i, c in reversed(list(_code_lines(lines, start, end)))}   # first one wins
    at = found.get(old_code if old_code else code)
    if old_code and old_code not in found:
        raise ValueError("%s is not in [%s]" % (old_code, SECTION_TITLES[group]))
    if code in found and found[code] != at:
        raise ValueError("%s is already used in [%s]: %s" % (
            code, SECTION_TITLES[group], _split_line(lines[found[code]])[1]))
    if at is not None and not old_code and not replace:
        raise ValueError("%s is already used in [%s]: %s" % (
            code, SECTION_TITLES[group], _split_line(lines[at])[1]))
    if at is not None:
        if note is None:                            # keep the note as it is (unwrapped)
            old = _note(lines[at])
            s = _line(code, action, None, lines[at])
            lines[at] = s + (" " * max(3, NOTE_COLUMN - len(s)) + "# " + old if old else "")
        else:                                       # the note (all of it) is replaced
            del lines[at + 1:at + 1 + _note_lines(lines, at)]
            lines[at:at + 1] = _line(code, action, note, lines[at]).split("\n")
    else:                                           # new: after the last code line
        last = max([i for i, _ in _code_lines(lines, start, end)] or [start])
        while last + 1 < end and lines[last + 1].startswith((" ", "\t")) \
                and lines[last + 1].strip().startswith("#"):
            last += 1                               # past that line's note lines
        at = last + 1
        lines[at:at] = _line(code, action, note, lines[last] if last > start else None).split("\n")
    filesave.write_lines(path, lines, nl)
    return at + 1


def delete_code(group, code, path=None):
    """Take `code` out of [group], with the indented note lines under it.
    Raises ValueError if it isn't there."""
    import filesave
    path = path or default_path()
    lines, nl = _read(path)
    sec = _sections(lines).get(group)
    at = next((i for i, c in _code_lines(lines, *sec) if c == code), None) if sec else None
    if at is None:
        raise ValueError("%s is not in [%s]" % (code, SECTION_TITLES[group]))
    stop = at + 1
    while stop < len(lines) and lines[stop].startswith((" ", "\t")) \
            and lines[stop].strip().startswith("#"):
        stop += 1
    del lines[at:stop]
    filesave.write_lines(path, lines, nl)
