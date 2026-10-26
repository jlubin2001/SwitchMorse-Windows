# SwitchMorse Windows - aeromorse_map.py (used by convert_map.py only)
# Reads a map written in the AeroMorse morse_map.py format (Python:
# g1[4][0b1000]='b') and turns every value into an Action. The program itself
# reads morse_map.txt instead (app/mapload.py).
import os
import sys
import types
from collections import namedtuple

import hid_names

N_GROUPS = 4                    # SwitchMorse uses groups 0-3 only
GROUP_NAMES = ["BASE", "KEYBOARD", "MOUSE", "MACRO"]
COMMANDS = {"repeat": "Repeat", "pause": "Pause", "releaseall": "Release all",
            "mslow": "Slow mouse", "mfast": "Fast mouse", "mcenter": "Centre pointer"}
DIRECTIONS = {(0, -1, 0): "up", (0, 1, 0): "down", (1, 0, 0): "right",
              (-1, 0, 0): "left", (-1, -1, 0): "up-left", (1, -1, 0): "up-right",
              (-1, 1, 0): "down-left", (1, 1, 0): "down-right"}
# Media / app keys (AeroMorse CC(...) values) -> Windows virtual keys
CC_TO_VK = {0xCD: (0xB3, "Play/Pause"), 0xE2: (0xAD, "Mute"),
            0xEA: (0xAE, "Volume down"), 0xE9: (0xAF, "Volume up"),
            0xB5: (0xB0, "Next track"), 0xB6: (0xB1, "Previous track"),
            0xB7: (0xB2, "Stop"), 0x192: (0xB7, "Calculator"),
            0x194: (0xB6, "File Explorer"), 0x196: (0xAC, "Web browser"),
            0x18A: (0xB4, "Mail")}

# kind: "char"  one character (text), typed on the current keyboard layout
#       "key"   mods bitmask + HID keys
#       "mod"   sticky modifier (bit in mods)
#       "vk"    a Windows-only key (media / app launch), its virtual key in keys[0]
#       "group" group number
#       "cmd"   command: cmd is a tuple, e.g. ("repeat",), ("mmove", 1, 0, 0),
#               ("mclick", "left", 2), ("mdrag", "left")
Action = namedtuple("Action", "kind mods keys group cmd label text", defaults=(None,))


def _command(value):
    """A command string -> (cmd tuple, label), or None if it isn't one."""
    w = value.split()
    try:
        if value in COMMANDS:
            return (value,), COMMANDS[value]
        if w[0] == "mmove" and len(w) == 4:
            v = (int(w[1]), int(w[2]), int(w[3]))
            if v[2] and not (v[0] or v[1]):
                return ("mmove",) + v, "Scroll " + ("up" if v[2] > 0 else "down")
            return ("mmove",) + v, "Mouse " + DIRECTIONS.get(v, str(v))
        if w[0] == "mclick" and len(w) == 3 and w[1] in ("left", "right", "middle"):
            n = int(w[2])
            return ("mclick", w[1], n), ("Double " if n == 2 else "") + w[1].title() + " click"
        if w[0] == "mdrag" and len(w) == 2 and w[1] in ("left", "right"):
            return ("mdrag", w[1]), "Drag " + w[1]
    except (ValueError, IndexError):
        pass
    return None


def code_str(n, p):
    return "".join("-" if (p >> (n - 1 - i)) & 1 else "." for i in range(n))


def _mod_bit(kc):
    return 1 << (kc - 0xE0) if 0xE0 <= kc <= 0xE7 else 0


def _key_label(mods, keys):
    parts = [hid_names.MOD_LABELS[i] for i in range(8) if mods & (1 << i)]
    parts += [hid_names.KEY_LABELS.get(k, "Key %d" % k) for k in keys]
    return "+".join(parts)


class CC:
    """Media / app-key marker, as in AeroMorse: CC(ConsumerControlCode.MUTE)."""
    __slots__ = ("code",)

    def __init__(self, code):
        self.code = code


def _convert(value, where, problems):
    if type(value).__name__ == "Secret":        # _secret('name', placeholder) in the map
        return Action("secret", 0, (), None, None, "secret " + value.key, value.key)
    if isinstance(value, str):
        if len(value) == 1:
            # Typed by what it IS, on whatever keyboard layout Windows uses.
            label = {" ": "Space", "\n": "Enter", "\t": "Tab"}.get(value, value)
            return Action("char", 0, (), None, None, label, value)
        words = value.split()
        if len(words) == 2 and words[0] == "group" and words[1].isdigit():
            g = int(words[1])
            if g >= N_GROUPS:
                problems.append("%s: SwitchMorse has no group %d - left out" % (where, g))
                return None
            return Action("group", 0, (), g, None,
                          "Group %d %s" % (g, GROUP_NAMES[g].title()))
        c = _command(value)
        if c:
            return Action("cmd", 0, (), None, c[0], c[1])
        if value.strip() and value not in ("lock", "unlock"):     # a phrase to type
            short = value if len(value) <= 18 else value[:17] + "\u2026"
            return Action("text", 0, (), None, None, '"%s"' % short, value)
        problems.append("%s: %r is not supported yet - left out" % (where, value))
        return None
    if isinstance(value, int):
        value = (value,)
    if isinstance(value, tuple) and value and all(isinstance(v, int) for v in value):
        if len(value) == 1 and _mod_bit(value[0]):
            b = _mod_bit(value[0])
            return Action("mod", b, (), None, None,
                          hid_names.MOD_LABELS[b.bit_length() - 1])
        mods = 0
        keys = []
        for v in value:
            if _mod_bit(v):
                mods |= _mod_bit(v)
            else:
                keys.append(v)
        return Action("key", mods, tuple(keys), None, None, _key_label(mods, keys))
    if isinstance(value, CC):
        if value.code in CC_TO_VK:
            vk, label = CC_TO_VK[value.code]
            return Action("vk", 0, (vk,), None, None, label)
        problems.append("%s: media code %#x has no Windows key - left out" % (where, value.code))
        return None
    problems.append("%s: %r is not supported yet - left out" % (where, value))
    return None


def load(path=None):
    """Returns (codes, problems). codes[(group, length, pattern)] = Action."""
    if path is None:
        raise ValueError("give the path of an AeroMorse-format morse_map.py")
    # morse_map.py imports adafruit_hid like an AeroMorse map; give it the
    # PC stand-ins instead of the real library.
    kc = types.ModuleType("adafruit_hid.keycode")
    kc.Keycode = hid_names.Keycode
    ccc = types.ModuleType("adafruit_hid.consumer_control_code")
    ccc.ConsumerControlCode = hid_names.ConsumerControlCode
    sys.modules.update({"adafruit_hid": types.ModuleType("adafruit_hid"),
                        "adafruit_hid.keycode": kc,
                        "adafruit_hid.consumer_control_code": ccc})
    ns = {"__name__": "morse_map", "CC": CC,
          "_cc": lambda name, uid: CC(uid)}
    with open(path, encoding="utf-8") as f:
        exec(compile(f.read(), path, "exec"), ns)
    groups = ns["groups"]

    problems = []
    codes = {}
    for g in sorted(groups):
        if g >= N_GROUPS:
            if any(groups[g].values()):
                problems.append("group %d: SwitchMorse has groups 0-%d only - left out"
                                % (g, N_GROUPS - 1))
            continue
        for n in range(1, 9):
            for p, v in groups[g].get(n, {}).items():
                where = "g%d %s" % (g, code_str(n, p))
                if not 0 <= p < (1 << n):
                    problems.append("%s: pattern is longer than %d symbols" % (where, n))
                    continue
                a = _convert(v, where, problems)
                if a:
                    codes[(g, n, p)] = a

    # Leave out group commands that lead to an empty group.
    filled = {g for (g, n, p) in codes if g}
    for key, a in list(codes.items()):
        if a.kind == "group" and a.group not in filled:
            problems.append("g%d %s: group %d has no codes yet - left out"
                            % (key[0], code_str(key[1], key[2]), a.group))
            del codes[key]

    # Group 0 wins over every group: say so when it hides a code.
    for (g, n, p), a in sorted(codes.items()):
        if g and (0, n, p) in codes:
            problems.append("g%d %s (%s) is hidden by Group 0" % (g, code_str(n, p), a.label))
    return codes, problems


def groups_in(codes):
    return sorted({g for (g, n, p) in codes if g})
