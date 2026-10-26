# SwitchMorse Windows - offline test of the map, decoder and actions.
# Plays scripted switch presses with made-up times through the same steps the
# program uses, and records what WOULD be sent to Windows (nothing is really
# typed or moved).
#
#   python tools\test_decode.py
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config                     # noqa: E402
import mapload                    # noqa: E402
import sendinput                  # noqa: E402
from actions import Actions       # noqa: E402
from decoder import Decoder       # noqa: E402

# The right-click nudge tests need it on, whatever your own config.txt says.
config.RIGHT_CLICK_MOVE_RIGHT = config.read(config.DEFAULTS_FILE)[0]["RIGHT_CLICK_MOVE_RIGHT"]

VK_NAMES = {0xA2: "Ctrl", 0xA0: "Shift", 0xA3: "RCtrl", 0xA4: "Alt", 0x5B: "Win",
            0x0D: "Enter", 0x08: "Bksp", 0x20: " ", 0x70: "F1", 0x26: "Up",
            0x27: "Right", 0x28: "Down", 0x22: "PgDn", 0x09: "Tab", 0x1B: "Esc"}


def vk_text(vk):
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    return VK_NAMES.get(vk, "vk%02X" % vk)


class Recorder:
    """Stands in for sendinput.Output: writes down what would happen."""

    def __init__(self):
        self.log = []

    def keys(self, events):
        downs = [vk_text(vk) for vk, ext, up in events if not up]
        ups = [vk_text(vk) for vk, ext, up in events if up]
        if downs and ups:
            self.log.append("+".join(downs))
        elif downs:
            self.log.append("down " + "+".join(downs))
        elif len(ups) < 8:              # (all 8 = release all, not interesting)
            self.log.append("up " + "+".join(ups))
        return len(events)

    def char(self, ch, armed=0):
        """(a phrase arrives here one character at a time)"""
        names = [("Ctrl", "Shift", "Alt", "Win", "RCtrl", "RShift", "RAlt", "RWin")[i]
                 for i in range(8) if armed & (1 << i)]
        self.log.append("+".join(names + [ch]))
        return True

    def vk(self, vk):
        self.log.append("vk%02X" % vk)

    def move(self, dx, dy):
        self.log.append(("move", dx, dy))

    def wheel(self, n):
        self.log.append(("wheel", n))

    def button(self, name, down):
        self.log.append("%s %s" % (name, "down" if down else "up"))

    def center(self):
        self.log.append("center")


class Clock:
    t = 0.0

    def __call__(self):
        return Clock.t


def run(script, press=0.15, step=0.4, secrets=None):
    """script items:
      '.-..'             a code (press-s presses every step s, then 800 ms idle;
                         the default is 150 ms presses with 250 ms gaps)
      ('hold', sw, s)    one press held s seconds
      ('tap', sw)        one 150 ms press (e.g. to stop a repeat), 800 ms idle
      ('wait', s)        nothing for s seconds
    Returns (recorder log, window action texts)."""
    codes, _ = mapload.load()
    rec = Recorder()
    act = Actions(codes, 1, out=rec, cfg=config, clock=Clock(), secrets=secrets)
    dec = Decoder(config.ACCEPT_DELAY, config.LONG_PRESS, True)
    events = []
    t = 1.0
    for item in script:
        if isinstance(item, tuple):
            if item[0] == "hold":
                events += [(t, item[1], True), (t + item[2], item[1], False)]
                t += item[2] + 0.8
            elif item[0] == "tap":
                events += [(t, item[1], True), (t + 0.15, item[1], False)]
                t += 0.95
            else:
                t += item[1]
            continue
        for ch in item:
            sw = "dot" if ch == "." else "dash"
            events += [(t, sw, True), (t + press, sw, False)]
            t += step
        t += 0.8
    events.sort()
    shown = []
    i = 0
    Clock.t = 0.0

    def note():
        if act.action and (not shown or shown[-1] != act.action):
            shown.append(act.action)

    while Clock.t < t + 2:
        now = Clock.t
        while i < len(events) and events[i][0] <= now:
            et, sw, pr = events[i]
            for out in dec.feed(sw, pr, et):
                if out[0] == "cycle":
                    act.next_group()
                    note()
            if pr and act.repeating:            # same as switchmorse.py poll()
                act.stop_repeat()
                act.action = "Repeat off"
                note()
                dec.consume(sw)
            i += 1
        dec.accept_delay = config.MOUSE_ACCEPT_DELAY if act.group == 2 else config.ACCEPT_DELAY
        act.tick(now)
        for out in dec.tick(now):
            if out[0] == "code":
                act.code(out[1], out[2])
                note()
        Clock.t = round(now + 0.01, 3)
    return rec.log, shown


def check(name, ok, detail=""):
    print("%s  %s" % ("PASS" if ok else "FAIL", name))
    if not ok and detail:
        print("   ", detail)
    return ok


REAL = {n: getattr(config, n) for n in
        ("ACCEPT_DELAY", "MOUSE_ACCEPT_DELAY", "MOUSE_SPEED_FACTOR")}
# The scripted tests below were written for these values: their codes have
# 250 ms gaps (so they need a pause longer than that) and they expect 4 px moves.
# They test the logic, not the speed - the last test uses the real settings.
TEST = {"ACCEPT_DELAY": 0.5, "MOUSE_ACCEPT_DELAY": 0.5, "MOUSE_SPEED_FACTOR": 2,
        "LONG_PRESS": 1.0}          # the long-hold tests hold for 1.3 s


def main():
    R = []
    for n, v in TEST.items():
        setattr(config, n, v)
    codes, problems = mapload.load()
    for p in problems:
        print("map note:", p)

    # --- keyboard -----------------------------------------------------------------
    log, shown = run(["....", "..", "..--", "-.-.", "---.", "--...-", ".-", ".-.-"])
    R.append(check("letters, Space, Ctrl+C, Shift+A, Enter",
                   log == ["h", "i", " ", "Ctrl+c", "Shift+a", "Enter"], log))

    log, shown = run(["-.----", "..-..", ("wait", 1.0), ("tap", "dot"), ("wait", 0.5), "."])
    qs = [x for x in log if x == "?"]
    R.append(check("repeat keeps typing ? until a press; that press adds nothing",
                   len(qs) > 20 and log[-1] == "e" and "? ." not in shown,
                   (len(qs), log[-3:], shown)))

    log, shown = run(["...-..", "..-.."])
    R.append(check("Page Down is never repeated (NO_REPEAT_KEYS)",
                   log == ["PgDn"] and shown[-1] == "Nothing to repeat", (log, shown)))

    log, shown = run(["--...-", ".-.-.", ".-.-.", "."])
    R.append(check("Shift + Right, Right keeps Shift; a letter drops it",
                   log == ["Shift+Right", "Shift+Right", "e"], log))

    log, shown = run(["-.-.-.-.", ".", "-.-.-.-.", "."])
    R.append(check("pause blocks keys, start again", log == ["e"], log))

    log, shown = run([("hold", "dot", 1.3), ("hold", "dash", 1.3), ("hold", "dot", 1.3), ".", ".-.-.-.", "--.----"])
    R.append(check("long holds: Mouse, Macros, back to Keyboard, no symbols; unknown code; F1",
                   log == ["e", "F1"] and shown == ["Group 2 Mouse", "Group 3 Macro", "Group 1 Keyboard", "e",
                                                    "? .-.-.-.", "F1"], (log, shown)))

    # --- mouse --------------------------------------------------------------------
    log, shown = run(["--------", "...", ".", ("wait", 1.0), ("tap", "dot"), ("wait", 0.3), "..."])
    moves = [x for x in log if isinstance(x, tuple) and x[0] == "move"]
    glide = sum(m[1] for m in moves[1:-1])
    R.append(check("move right 4 px, repeat glides ~100 px/s, a press stops it",
                   moves[0] == ("move", 4, 0) and moves[-1] == ("move", 4, 0)
                   and 90 <= glide <= 160 and all(m[2] == 0 for m in moves),
                   (moves[:2], glide, moves[-1])))

    log, shown = run(["--------", ".-", "..-", ".--"])
    R.append(check("left click, double click, right click",
                   log == ["left down", "left up", "left down", "left up",
                           "left down", "left up", "right down", "right up",
                           ("move", config.RIGHT_CLICK_MOVE_RIGHT * config.MOUSE_SPEED_NORMAL
                            * config.MOUSE_SPEED_FACTOR, 0)], log))

    log, shown = run(["--------", "-.", "---", ".-", "-.", ".-.-.-.-"])
    R.append(check("drag on, move, click = just let go; drag again, release all lets go",
                   log == ["left down", ("move", 0, 4), "left up", "left down", "left up"],
                   log))

    log, shown = run(["--------", "-.-.", ".-", ".-"])
    R.append(check("RCtrl + click twice (Ctrl stays armed)",
                   log == ["down RCtrl", "left down", "left up", "up RCtrl",
                           "down RCtrl", "left down", "left up", "up RCtrl"], log))

    log, shown = run(["--------", ".....-", "--..", "...", "--..", "...", "-..--", "-.-.-."])
    R.append(check("scroll 4 notches, slow move 2 px, normal again, centre, calculator",
                   log == [("wheel", 4), ("move", 2, 0), ("move", 4, 0), "center", "vkB7"],
                   log))

    log, shown = run(["..--.-", "..----", "---..-"])
    R.append(check("pound, dollar, at go out as characters", log == ["£", "$", "@"], log))

    # --- keyboard layouts ------------------------------------------------------------
    # A UK layout as VkKeyScanEx describes it (low byte = key, high byte: 1 Shift,
    # 2 Ctrl, 4 Alt; Ctrl+Alt = AltGr). These are the keys that differ from US.
    uk = {"@": 0x1C0, '"': 0x132, "#": 0x0DE, "~": 0x1DE, "£": 0x133, "\\": 0x0DC,
          "|": 0x1DC, "`": 0x0DF, "€": 0x634, "a": 0x041, "A": 0x141}
    dead = set()
    plan = lambda c: sendinput.plan_char(c, lambda x: uk.get(x, -1), lambda vk: vk in dead)  # noqa: E731
    R.append(check("UK: @ is Shift + the ' key, \" is Shift+2, # is the # key",
                   (plan("@"), plan('"'), plan("#")) ==
                   (("key", 0x02, 0xC0), ("key", 0x02, 0x32), ("key", 0, 0xDE)),
                   (plan("@"), plan('"'), plan("#"))))
    R.append(check("UK: \u00a3 is Shift+3, \u20ac is AltGr+4 (Ctrl+Alt)",
                   (plan("£"), plan("€")) == (("key", 0x02, 0x33), ("key", 0x05, 0x34)),
                   (plan("£"), plan("€"))))
    R.append(check("no key on the layout -> typed as the character itself",
                   plan("ñ") == ("unicode",), plan("ñ")))
    dead.add(0xDF)
    R.append(check("a dead key (e.g. ` on some layouts) -> typed as the character",
                   plan("`") == ("unicode",), plan("`")))
    R.append(check("Enter and Tab are always those keys",
                   (plan("\n"), plan("\t")) == (("key", 0, 0x0D), ("key", 0, 0x09)), ""))

    # This PC's real layout (read-only: nothing is typed or loaded)
    hkl = sendinput.current_layout()
    ascii_plans = {c: sendinput.char_events(c, 0, hkl) for c in map(chr, range(32, 127))}
    uni = [c for c, ev in ascii_plans.items() if ev[0][0] == "unicode"]
    print("    this PC's layout: %08X" % ((hkl or 0) & 0xFFFFFFFF))
    R.append(check("this PC's layout has a real key for every printable ASCII character",
                   not uni, uni))
    ev = sendinput.char_events("@", 0x01, hkl)
    R.append(check("Ctrl armed + '@' presses Ctrl with the @ key",
                   ev[0][0] == 0xA2 and not ev[0][2], ev))

    # --- the text map format ----------------------------------------------------------
    import tempfile
    sample = "\n".join([
        "# a note",
        "[Keyboard]",
        ".-        a                 # the letter a",
        "-...      '#'",
        "-.-.      Ctrl",
        "---.      Ctrl+Alt+Delete",
        "--.-      Ctrl++",
        "....      tap Ctrl",
        "..        \"Kind regards, Sam  # not a comment\"",
        "-.--      Ctlr+C",
        ".-        b                 # same code again",
        "..-.-.-.- x",
        "...       group Nowhere",
        "-         Volume Up",
        "[Macros]",
        ".-        \"Sam\"",
        "[Fred]",
        "--        z",
    ])
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(sample)
        tc, tp = mapload.load(p)
    K = lambda code, g=1: tc.get((g, len(code), int(code.replace(".", "0").replace("-", "1"), 2)))  # noqa: E731
    R.append(check("text map: char, quoted #, sticky Ctrl, Ctrl+Alt+Delete, Ctrl++, tap Ctrl",
                   (K(".-").text, K("-...").text, K("-.-.").kind, K("---.").mods, K("---.").keys,
                    K("--.-").keys, K("....").kind, K("....").mods) ==
                   ("a", "#", "mod", 0x05, (0x4C,), (0x2E,), "key", 0x01),
                   [K(c) for c in (".-", "-...", "-.-.", "---.", "--.-", "....")]))
    R.append(check("text map: a phrase keeps a # inside its quotes; media key; [Macros]",
                   K("..").text == "Kind regards, Sam  # not a comment" and K("..").kind == "text"
                   and K("-").kind == "vk" and K(".-", 3).text == "Sam", (K(".."), K("-"))))
    want = ["line 10", "line 11", "line 12", "line 13", "line 17"]
    R.append(check("text map: mistakes reported by line, the rest still loads",
                   [p.split(":")[0] for p in tp] == want and len(tc) == 9, tp))

    log, shown = run(["--------", "---.-"])
    R.append(check("find pointer taps Ctrl (not a sticky Ctrl)", log == ["Ctrl"], log))

    # --- dragging SwitchMorse's own window -----------------------------------------------
    class OwnWindowRecorder(Recorder):
        def pointer_on_own_window(self):
            return True
    follow = []
    rec2 = OwnWindowRecorder()
    act2 = Actions(codes, 2, out=rec2, cfg=config, clock=Clock())
    act2.window_follow = (lambda: follow.append("start"), lambda: follow.append("stop"))
    act2.code(2, 0b10)          # -.  drag on (pointer on our own window)
    act2.code(2, 0b11)          # --  move up
    act2.code(2, 0b10)          # -.  drag again = stop
    buttons = [x for x in rec2.log if isinstance(x, str) and "left" in x]
    R.append(check("drag on our own window: no button held, the window follows, drag again stops",
                   follow == ["start", "stop"] and not buttons
                   and any(isinstance(x, tuple) and x[0] == "move" for x in rec2.log),
                   (follow, rec2.log)))
    follow.clear()
    act2.code(2, 0b10)          # drag on again ...
    act2.release_all()          # ... release all stops it too
    R.append(check("release all stops the window following", follow == ["start", "stop"]
                   and act2.drag is None, follow))

    # --- .-.-.- brings the window to the front, in every group ------------------------
    shown_calls = []
    for g in (1, 2, 3):
        act3 = Actions(codes, g, out=Recorder(), cfg=config, clock=Clock())
        act3.window_show = lambda: shown_calls.append("front")
        act3.code(6, 0b010101)
    R.append(check(".-.-.- brings the SwitchMorse window to the front in Keyboard, Mouse, Macros",
                   shown_calls == ["front"] * 3, shown_calls))

    # --- config.txt: mistakes are left out, defaults kept -----------------------------
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        mine = os.path.join(d, "config.txt")
        with open(mine, "w", encoding="utf-8") as f:
            f.write("ACCEPT_DELAY = 0.35   # mine\nPRESS_LOG = yes\nMOUSE_SPEED_FACTOR = 7x\n"
                    "NO_SUCH = 1\njust words\nNO_REPEAT_KEYS = Tab\nPORT = COM5\n")
        vals, probs = config.read(config.DEFAULTS_FILE, mine)
    R.append(check("config.txt: good lines read as numbers / yes-no / list / text",
                   (vals["ACCEPT_DELAY"], vals["PRESS_LOG"], vals["NO_REPEAT_KEYS"], vals["PORT"])
                   == (0.35, True, ("Tab",), "COM5"), vals))
    R.append(check("config.txt: bad number, unknown name, non-setting line -> reported, default kept",
                   vals["MOUSE_SPEED_FACTOR"] == 7 and [p.split(":")[0] for p in probs]
                   == ["config.txt line 3", "config.txt line 4", "config.txt line 5"], probs))

    # --- hints line ---------------------------------------------------------------------
    import hints
    h = hints.hint(codes, 1, "-..")
    R.append(check("hint after -.. : = d, then .:b and -:x",
                   h.startswith("= d") and ".:b" in h and "-:x" in h, h))
    h = hints.hint(codes, 2, "..")
    R.append(check("hint in Mouse: = left (no 'Mouse' prefix), .:right",
                   h.startswith("= left") and ".:right" in h, h))
    h = hints.hint(codes, 3, ".-")
    R.append(check("hint for a password shows its NAME, never a value",
                   h.startswith("= name"), h))
    R.append(check("no hint when nothing is entered", hints.hint(codes, 1, "") == "", ""))

    # --- right-click steps into the menu ---------------------------------------------
    log, shown = run(["--------", ".--", ".-"])
    step = config.MOUSE_SPEED_NORMAL * config.MOUSE_SPEED_FACTOR
    moves = [x for x in log if isinstance(x, tuple) and x[0] == "move"]
    want_dx = config.RIGHT_CLICK_MOVE_RIGHT * step
    R.append(check("after a right-click the pointer moves right %d steps; a left click doesn't move"
                   % config.RIGHT_CLICK_MOVE_RIGHT,
                   log[:3] == ["right down", "right up", ("move", want_dx, 0)]
                   and moves == [("move", want_dx, 0)], log))

    # --- Macros: phrases and passwords ---------------------------------------------
    sec = {"name": "Sam Smith"}
    log, shown = run(["....----", ".-", "."], secrets=sec)
    R.append(check("secret name types its value, then back to Keyboard (. = e)",
                   log == list("Sam Smith") + ["e"], log))
    R.append(check("the value never appears in the window text",
                   not any("Sam Smith" in x for x in shown) and "secret name" in shown, shown))
    log, shown = run(["....----", "-...", "..-.."], secrets=sec)
    R.append(check("a secret with no value types nothing and says (not set)",
                   log == [] and "secret address (not set)" in shown, (log, shown)))
    log, shown = run(["....----", ".-", "..-.."], secrets=sec)
    R.append(check("a password is never repeated",
                   log == list("Sam Smith") and shown[-1] == "Nothing to repeat", (log, shown)))
    log, shown = run(["....----", "..---", "....----", "...-."], secrets=sec)
    R.append(check("Macros digits type; ...-. goes to Keyboard",
                   log == ["2"] and shown[-1] == "Group 1 Keyboard", (log, shown)))
    macro_secrets = sorted(a.text for (g, n, p), a in codes.items() if g == 3 and a.kind == "secret")
    R.append(check("the map's Macros group has secret codes", len(macro_secrets) > 0,
                   macro_secrets))

    missing = sorted({k for a in codes.values() if a.kind == "key" for k in a.keys
                      if k not in sendinput.HID_TO_VK})
    R.append(check("every map key has a Windows key", not missing, missing))
    R.append(check("Group 2 is loaded", any(g == 2 for g, n, p in codes), ""))

    # --- a switch that lets go for a moment mid-press (seen on a sip-and-puff switch) ---
    def codes_of(evs, accept=0.4):
        d = Decoder(accept, 1.0, True, config.SWITCH_BOUNCE_MS / 1000)
        got = []
        for et, sw, pr in evs:
            d.feed(sw, pr, et)
            for o in d.tick(et):
                if o[0] == "code":
                    got.append(d_str(o[1], o[2]))
        for o in d.tick(evs[-1][0] + 2):
            if o[0] == "code":
                got.append(d_str(o[1], o[2]))
        return got
    d_str = lambda n, p: "".join("-" if (p >> (n - 1 - i)) & 1 else "." for i in range(n))  # noqa: E731
    # .-.- where the first dash's switch opens for 9 ms in the middle (from the log)
    evs = [(1.000, "dot", True), (1.140, "dot", False), (1.200, "dash", True),
           (1.219, "dash", False), (1.228, "dash", True), (1.260, "dash", False),
           (1.340, "dot", True), (1.440, "dot", False), (1.520, "dash", True), (1.600, "dash", False)]
    R.append(check("a 9 ms let-go inside one puff is one dash: .-.- stays .-.-",
                   codes_of(evs) == [".-.-"], codes_of(evs)))
    # q = --.- with only 18 ms between the two puffs (from the log): two dashes
    evs = [(1.000, "dash", True), (1.218, "dash", False), (1.236, "dash", True),
           (1.362, "dash", False), (1.453, "dot", True), (1.702, "dot", False),
           (1.738, "dash", True), (1.897, "dash", False)]
    R.append(check("two real puffs 18 ms apart are still two dashes: q stays --.-",
                   codes_of(evs) == ["--.-"], codes_of(evs)))
    evs = [(1.000, "dot", True), (1.600, "dot", False), (1.605, "dot", True), (2.200, "dot", False)]
    d = Decoder(0.4, 1.0, True, config.SWITCH_BOUNCE_MS / 1000)
    cyc = [o for et, sw, pr in evs for o in d.feed(sw, pr, et) if o[0] == "cycle"]
    R.append(check("a let-go inside a long hold: still one group change, no dot",
                   cyc == [("cycle",)] and d.count == 0, (cyc, d.count)))

    # --- the real settings (config.py), at sip-and-puff speed ------------------------
    for n, v in REAL.items():
        setattr(config, n, v)
    gap = REAL["ACCEPT_DELAY"] * 0.5            # gaps inside a code: half the pause
    log, shown = run(["....", "..", "--------", "...", ".", ("wait", 1.0), ("tap", "dot")],
                     press=0.12, step=0.12 + gap)
    moves = [x for x in log if isinstance(x, tuple) and x[0] == "move"]
    px = config.MOUSE_SPEED_NORMAL * REAL["MOUSE_SPEED_FACTOR"]
    speed = px / config.MOUSE_REPEAT_DELAY
    glide = sum(m[1] for m in moves[1:])
    secs = 0.8 + 1.0 - REAL["MOUSE_ACCEPT_DELAY"]   # repeat starts after "." is accepted
    R.append(check("real settings (pause %.2f s, %d px moves): 'hi' at %d ms gaps, "
                   "glide ~%d px/s" % (REAL["ACCEPT_DELAY"], px, gap * 1000, speed),
                   log[:2] == ["h", "i"] and moves and moves[0] == ("move", px, 0)
                   and 0.8 <= glide / (speed * secs) <= 1.2,
                   (log[:3], moves[:1], glide, round(glide / secs))))

    print("\n%d/%d PASS" % (sum(R), len(R)))
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
