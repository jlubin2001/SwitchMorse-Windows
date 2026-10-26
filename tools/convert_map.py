# SwitchMorse Windows - convert_map.py
# Turns a map in the AeroMorse format (morse_map.py: g1[4][0b1000]='b') into
# the SwitchMorse Windows plain-text map (morse_map.txt: "-...  b").
#
#   python tools\convert_map.py AEROMORSE_MAP.py OUT.txt
#
# Only groups 0-3 are converted (SwitchMorse has Base, Keyboard, Mouse, Macros).
# Each line's comment is carried over (without the code it repeats), and so are
# the "-- Letters --" style divider comments. Afterwards the new file is read
# back and every code is checked against the original - the conversion is only
# reported OK if every code does exactly the same thing.
import io
import os
import re
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "app"), HERE]
import aeromorse_map      # noqa: E402
import hid_names          # noqa: E402
import mapload            # noqa: E402

GUIDE = """\
# SwitchMorse Windows - morse_map.txt
# The codes, one per line. Edit this file in Notepad; when you save it, the
# program uses the new codes within a second (no restart).
#
# A line is:   CODE   WHAT IT DOES        # a note (optional)
#   CODE is the dots and dashes you send: . is the dot switch, - the dash switch.
#   Lines starting with # are notes. Blank lines are fine.
#   [Keyboard], [Mouse], [Macros] start a group. Codes in [Base] work in every
#   group (and win over the same code in a group).
#
# WHAT IT DOES can be:
#   a character        a   ?   £   A        (any character, on any keyboard layout)
#                      write #  '  "  in quotes:  "#"   '"'   "'"
#                      and  .  -  too, so they don't look like part of a code:
#                      "."   "-"
#   a phrase           "Kind regards"
#   a password etc.    secret email_pw     (the value is set in the SwitchMorse
#                      Passwords window - right-click the SwitchMorse window)
#   a key              Enter  Esc  Tab  Space  Backspace  Delete  Insert
#                      Home  End  Page Up  Page Down  Up  Down  Left  Right
#                      F1 ... F24  Caps Lock  Num Lock  Scroll Lock  Print Screen
#                      Menu  Pause Key  Keypad Enter  Keypad .  Keypad /
#   keys together      Ctrl+C   Ctrl+Alt+Delete   Win+Tab   Ctrl+=   Ctrl++
#   a sticky modifier  Ctrl  Shift  Alt  Win  RCtrl  RShift  RAlt  RWin
#                      (arms it; the next key goes with it. Send again to cancel.)
#   a modifier alone   tap Ctrl
#   media / apps       Mute  Volume Up  Volume Down  Play Pause  Next Track
#                      Previous Track  Stop Media  Calculator  File Explorer
#                      Web Browser  Mail
#   a group            group Keyboard   group Mouse   group Macros
#   commands           repeat   pause   release all   show window
#   mouse              move up / down / left / right / up-left / up-right /
#                      down-left / down-right    scroll up   scroll down
#                      click left / right / middle    double click left / right
#                      drag left   mouse slow   mouse fast   centre pointer
#
# If a line has a mistake, the program leaves out just that line, says which
# line it is, and loads everything else.
"""

SECTION_HEAD = {0: "Base - these codes work in every group",
                1: "Keyboard", 2: "Mouse", 3: "Macros"}
VK_NAMES = {vk: label for vk, label in mapload.MEDIA_KEYS.values()}


def action_text(a):
    """An aeromorse_map Action -> the words for morse_map.txt."""
    if a.kind == "char":
        ch = a.text
        if ch in "#'\" .-" or ch.isspace():
            return '"%s"' % ch if ch != '"' else "'\"'"
        return ch
    if a.kind == "secret":
        return "secret " + a.text
    if a.kind == "text":
        return '"%s"' % a.text if '"' not in a.text else "'%s'" % a.text
    if a.kind == "mod":
        return hid_names.MOD_LABELS[a.mods.bit_length() - 1]
    if a.kind == "key":
        parts = [hid_names.MOD_LABELS[i] for i in range(8) if a.mods & (1 << i)]
        for k in a.keys:
            name = hid_names.KEY_LABELS.get(k, "Key %d" % k)
            parts.append(name)
        if not a.keys:
            return "tap " + "+".join(parts)
        return "+".join(parts)
    if a.kind == "vk":
        return VK_NAMES[a.keys[0]]
    if a.kind == "group":
        return "group " + mapload.SECTION_TITLES[a.group]
    c = a.cmd
    if c[0] in ("repeat", "pause"):
        return c[0]
    if c[0] == "releaseall":
        return "release all"
    if c[0] in ("mslow", "mfast"):
        return "mouse " + c[0][1:]
    if c[0] == "mcenter":
        return "centre pointer"
    if c[0] == "showwindow":
        return "show window"
    if c[0] == "mmove":
        if c[1] == 0 and c[2] == 0:
            return "scroll " + ("up" if c[3] > 0 else "down")
        for name, d in mapload.DIRECTIONS.items():
            if d == (c[1], c[2]):
                return "move " + name
    if c[0] == "mclick":
        return ("double click " if c[2] == 2 else "click ") + c[1]
    if c[0] == "mdrag":
        return "drag " + c[1]
    raise ValueError("can't write %r" % (a,))


ASSIGN = re.compile(r"\s*g(\d)\[(\d)\]\[0b([01]+)\]\s*=")


def source_order(path):
    """[(group, code, comment)] for each assignment, and [(group, divider)] notes,
    in file order, from the Python tokens (so a # inside quotes is no comment)."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lines = src.splitlines()
    comments = {}
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            comments[tok.start[0]] = (tok.start[1], tok.string[1:].strip())
    items = []
    group = None
    for no, line in enumerate(lines, 1):
        m = ASSIGN.match(line)
        g_hdr = re.match(r"\s*groups\[(\d)\]\s*=", line)
        if m:
            g, n, bits = int(m.group(1)), int(m.group(2)), m.group(3)
            code = "".join("-" if b == "1" else "." for b in bits.zfill(n))
            note = comments.get(no, (0, ""))[1]
            # drop the code the comment repeats, and a leading arrow
            note = re.sub(r"^[.\-]+(?=\s|$)", "", note).strip()
            note = re.sub(r"^(->|→)\s*", "", note).strip()
            items.append(("code", g, code, note))
            group = g
        elif no in comments and comments[no][0] == len(line) - len(line.lstrip()):
            text = comments[no][1]
            if re.match(r"(--|──)\s*\S", text):      # a divider like "-- Letters ---"
                title = re.sub(r"[\-─\s]+$", "", re.sub(r"^[\-─\s]+", "", text))
                items.append(("note", group, title))
        elif g_hdr:
            group = int(g_hdr.group(1))
    return items


def main():
    if len(sys.argv) != 3:
        print(__doc__ if __doc__ else "usage: convert_map.py IN.py OUT.txt")
        return 2
    src, out = sys.argv[1], sys.argv[2]
    codes, problems = aeromorse_map.load(src)
    for p in problems:
        print("note (original map):", p)
    items = source_order(src)

    # What to write per group, in the order the original file has it.
    body = {g: [] for g in range(mapload.N_GROUPS)}
    seen = set()
    pending_note = {}
    for it in items:
        if it[0] == "note":
            if it[1] is not None and it[1] < mapload.N_GROUPS:
                pending_note[it[1]] = it[2]
            continue
        _, g, code, note = it
        if g >= mapload.N_GROUPS:
            continue
        n, p = len(code), int(code.replace(".", "0").replace("-", "1"), 2)
        key = (g, n, p)
        if key in seen or key not in codes:
            continue                            # later duplicate, or left out by the reader
        seen.add(key)
        if g in pending_note:
            body[g].append(("note", pending_note.pop(g)))
        body[g].append(("code", code, action_text(codes[key]), note))

    lines = [GUIDE]
    for g in range(mapload.N_GROUPS):
        lines.append("")
        lines.append("[%s]" % mapload.SECTION_TITLES[g])
        lines.append("# %s" % SECTION_HEAD[g])
        for row in body[g]:
            if row[0] == "note":
                lines.append("")
                lines.append("# -- %s" % row[1])
            else:
                _, code, act, note = row
                line = "%-10s%-22s" % (code, act)
                lines.append((line + ("# " + note if note else "")).rstrip())
    with open(out, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")

    # Read it back and compare every code.
    new, new_problems = mapload.load(out)
    bad = []
    for key, a in codes.items():
        b = new.get(key)
        same = b is not None and (a.kind, a.mods, a.keys, a.group, a.cmd, a.text) == \
            (b.kind, b.mods, b.keys, b.group, b.cmd, b.text)
        if not same:
            bad.append("%s %s: was %r, now %r" % (mapload.SECTION_TITLES[key[0]],
                                                  mapload.code_str(key[1], key[2]), a, b))
    extra = [k for k in new if k not in codes]
    for p in new_problems:
        print("note (new map):", p)
    for b in bad:
        print("DIFFERENT:", b)
    for k in extra:
        print("EXTRA:", k)
    print("%d codes written to %s - %s" % (len(new), out,
          "all the same as the original" if not bad and not extra else "CHECK THE LINES ABOVE"))
    return 0 if not bad and not extra else 1


if __name__ == "__main__":
    sys.exit(main())
