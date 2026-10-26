# SwitchMorse Windows - offline test: saving and live-reloading settings (Phase 8).
#   - config.save() and mapload.set_code() / delete_code() change only their
#     own lines (comments, blank lines and order stay), refuse mistakes without
#     writing, and keep backups (the newest 10)
#   - the running program notices a changed config.txt / morse_map.txt and
#     uses it at once: no restart
# Works in a temporary work folder; your own map and config are never touched.
# Nothing is typed on the PC.
#
#   python tools\test_settings.py
import os
import shutil
import sys
import tempfile
import time

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APP)
import paths        # noqa: E402

WORK = tempfile.mkdtemp(prefix="smw_settings_")
paths.work_folder = lambda: WORK                 # before anything reads the work folder
shutil.copyfile(os.path.join(APP, "morse_map.example.txt"), os.path.join(WORK, "morse_map.txt"))
with open(os.path.join(WORK, "config.txt"), "w", encoding="utf-8", newline="") as f:
    f.write("# my settings\r\n\r\nACCEPT_DELAY = 0.5          # learning speed\r\n"
            "MOUSE_SPEED_FACTOR = 7\r\n")

import blocked      # noqa: E402
import config       # noqa: E402
import filesave     # noqa: E402
import mapload      # noqa: E402
import switches     # noqa: E402

config.reload()
MAP = os.path.join(WORK, "morse_map.txt")
CFG = os.path.join(WORK, "config.txt")
R = []


def check(name, ok, detail=""):
    print("%s  %s" % ("PASS" if ok else "FAIL", name))
    if not ok:
        print("   ", detail)
    R.append(bool(ok))


def raw(path):
    with open(path, "rb") as f:
        return f.read()


def backups(stem):
    folder = os.path.join(WORK, "Backups")
    return sorted(p for p in os.listdir(folder) if p.startswith(stem + " ")) \
        if os.path.isdir(folder) else []


# --- config.save -------------------------------------------------------------------
check("config.my_file() is the work folder's config.txt", config.my_file() == CFG, config.my_file())
config.save({"ACCEPT_DELAY": 0.3, "LONG_PRESS": 1.0, "SHIFT_SELECT": False})
text = raw(CFG).decode()
check("config: changed value keeps its note in the same column",
      "ACCEPT_DELAY = 0.3          # learning speed\r\n" in text, repr(text))
check("config: comments, blank line and other lines unchanged",
      text.startswith("# my settings\r\n\r\n") and "MOUSE_SPEED_FACTOR = 7\r\n" in text, repr(text))
check("config: settings not in the file are added at the end (yes/no written as no)",
      text.endswith("\r\nLONG_PRESS = 1.0\r\nSHIFT_SELECT = no\r\n"), repr(text))
check("config: no BOM, Windows line ends kept", not raw(CFG).startswith(b"\xef\xbb\xbf")
      and b"\n" not in raw(CFG).replace(b"\r\n", b""))
before = raw(CFG)
for bad in ({"ACCEPT_DELAY": "fast"}, {"NO_SUCH_SETTING": 1}):
    try:
        config.save(bad)
        ok = False
    except ValueError:
        ok = True
    check("config: %s refused, nothing written" % bad, ok and raw(CFG) == before)
check("config: a backup was kept", len(backups("config")) == 1, backups("config"))
changed = config.reload()
check("config.reload(): reports exactly what changed",
      changed == {"ACCEPT_DELAY", "LONG_PRESS", "SHIFT_SELECT"}, changed)
check("config.reload(): new values in use", config.ACCEPT_DELAY == 0.3 and config.LONG_PRESS == 1.0
      and config.SHIFT_SELECT is False and not config.PROBLEMS, config.PROBLEMS)
check("config.as_text: 0.04 / 1.0 / yes / list / none",
      [config.as_text(v) for v in (0.04, 1.0, True, ("Page Up", "Esc"), None)]
      == ["0.04", "1.0", "yes", "Page Up, Esc", "none"])

# --- mapload.set_code / delete_code ---------------------------------------------------
orig = raw(MAP).decode().splitlines()
codes0, probs0 = mapload.load()
at = mapload.set_code(3, "..-.-.", mapload.phrase("See you soon"), note="added in Settings")
now_lines = raw(MAP).decode().splitlines()
codes1, probs1 = mapload.load()
n, p = 6, int("001010", 2)
check("map: new phrase code works", codes1.get((3, n, p)) and codes1[(3, n, p)].text == "See you soon",
      codes1.get((3, n, p)))
check("map: new line goes at the end of [Macros], code/action/note in their columns",
      now_lines[at - 1] == '..-.-.    "See you soon"        # added in Settings', now_lines[at - 1])
check("map: every other line unchanged", now_lines[:at - 1] + now_lines[at:] == orig)
check("map: no new problems", probs1 == probs0, probs1)
try:
    mapload.set_code(1, ".-", "b")
    ok = False
except ValueError as ex:
    ok = "already used" in str(ex)
check("map: a code already used is refused (unless replace=True)", ok)
line_a = mapload.find_code(1, ".-")
mapload.set_code(1, ".-", "Ctrl+A", replace=True)
check("map: replace=True changes it in place, same line",
      mapload.find_code(1, ".-")[:2] == (line_a[0], "Ctrl+A"), mapload.find_code(1, ".-"))
mapload.set_code(1, ".-..-..", "a", old_code=".-")
codes2, _ = mapload.load()
check("map: changing a code's dots and dashes (old_code) moves it",
      (1, 2, 1) not in codes2 and codes2.get((1, 7, int("0100100", 2))).text == "a")
for args, why in (((1, ".-.-.-.-.", "a"), "9 symbols"), ((1, "..x", "a"), "not a code"),
                  ((1, "......--", "Ctrl+Nonsense"), "bad action"),
                  ((1, "--", "q", None, None, ".-"), "old code no longer there")):
    before = raw(MAP)
    try:
        mapload.set_code(*args)
        ok = False
    except ValueError:
        ok = True
    check("map: %s refused, nothing written" % why, ok and raw(MAP) == before)
before = raw(MAP).decode().splitlines()
mapload.delete_code(0, ".-.-.-")                  # has an indented note line under it
after = raw(MAP).decode().splitlines()
check("map: delete takes the line and its indented note line, nothing else",
      len(before) - len(after) == 2 and ".-.-.-" not in [mapload._split_line(l)[0] for l in after
                                                          if l.strip() and not l.lstrip().startswith(("#", "["))])
long_note = ("find pointer: with Show location of pointer when I press the CTRL key on, "
             "Windows draws circles round the pointer")
mapload.set_code(2, "-.-.-...", "tap Ctrl", note=long_note)
e = [x for x in mapload.entries() if x["group"] == 2 and x["code"] == "-.-.-..."][0]
lines = raw(MAP).decode().splitlines()
check("map: a long note wraps onto indented lines, and reads back whole",
      e["note"] == long_note and lines[e["line"]].startswith(" " * mapload.NOTE_COLUMN + "# ")
      and max(len(l) for l in lines[e["line"] - 1:e["line"] + 2]) <= mapload.LINE_WIDTH, e["note"])
mapload.set_code(2, "-.-.-...", "tap Ctrl", note="short now", replace=True)
lines2 = raw(MAP).decode().splitlines()
check("map: changing the note replaces all its lines", len(lines2) == len(lines) - 2
      and mapload.find_code(2, "-.-.-...")[2] == "short now")
mapload.set_code(2, "-.-.--.", "click middle")
check("map: a code in a group in the middle ([Mouse]) lands inside [Mouse]",
      (2, 7, int("1010110", 2)) in mapload.load()[0])
for i in range(12):
    filesave.backup(MAP)
check("backups: only the newest 10 are kept", len(backups("morse_map")) == 10, len(backups("morse_map")))

# --- the running program picks the changes up -------------------------------------------
class FakePort:
    in_waiting = 0

    def __init__(self, *a, **k):
        pass

    def read(self, n=1):
        time.sleep(0.01)
        return b""

    def write(self, b):
        pass

    def close(self):
        pass


switches.serial.Serial = FakePort
switches.candidate_ports = lambda want="auto": [("COM99", "trinkey")]
switches.device_name = lambda port: "Test"
blocked.reason = lambda: None
config.PRESS_LOG = False
import switchmorse  # noqa: E402
app = switchmorse.App()
app.win.root.withdraw()
app.reader.start()


def look():
    app.watch_due = 0
    app.watch()


time.sleep(0.05)
config.save({"MOUSE_SPEED_FACTOR": 3, "LONG_PRESS": 2.0, "ACCEPT_DELAY": 0.25})
look()
check("live: mouse speed and long press used at once",
      app.actions.factor == 3 and app.decoder.long_press == 2.0, (app.actions.factor, app.decoder.long_press))
app.poll()
check("live: accept delay used at once", abs(app.decoder.accept_delay - 0.25) < 1e-9, app.decoder.accept_delay)
check("live: the window says what changed", app.actions.action.startswith("Settings:"), app.actions.action)
time.sleep(0.05)
mapload.set_code(1, "......-.", '"live"')
look()
check("live: a new code works without Reload map", app.actions.codes.get((1, 8, 2)) is not None)
old_reader = app.reader
time.sleep(0.05)
config.save({"INPUT": "trinkey"})
look()
check("live: changing INPUT starts a new reader", app.reader is not old_reader
      and not old_reader._thread.is_alive())
app.decoder.count = 2                              # in the middle of a code
time.sleep(0.05)
config.save({"MOUSE_SPEED_FACTOR": 5})
app.poll()
check("live: nothing reloads in the middle of a code", app.actions.factor == 3)
app.decoder.clear()
app.watch_due = 0
app.poll()
check("live: ... and it does as soon as the code is done", app.actions.factor == 5)

# --- Settings window: open from a code, record the next code from the switches ----------
import settings_window   # noqa: E402
settings_window.take_focus = lambda win: None      # don't pull the focus while testing
app.actions.open_settings()
check("settings: opens inside the program", app.settings is not None)
s = app.settings
s.root.withdraw()
s.start_add()
s.record()
check("settings: Record asks the program for the next code", app.capture is not None)
t = time.perf_counter()
for sw_, down, at in (("dash", True, 0), ("dash", False, .05), ("dot", True, .1), ("dot", False, .15)):
    app.events.put(("switch", sw_, down, t + at))
app.poll()
app.decoder.last_release = time.perf_counter() - 5      # long past the accept delay
typed = []
app.actions.code = lambda *a: typed.append(a)
app.poll()
check("settings: the recorded code goes into the Code box", s.v_code.get() == "-.", s.v_code.get())
check("settings: ... and is not carried out", not typed and app.capture is None, typed)
s.v_kind.set(settings_window.KINDS[3])
s.v_value.set("from settings")
s.save()
check("settings: -. is n already - Save asks first", s.b_save.cget("text") == "Yes, save it")
s.save()
time.sleep(0.05)
look()
check("settings: a saved code is in use at once",
      getattr(app.actions.codes.get((1, 2, 2)), "text", None) == "from settings")
s.show_tab("Keyboard")
check("settings: Keyboard starts with the AeroMorse letters", s.layout_now() == "aeromorse")
s.toggle_layout()
check("settings: standard Morse asks first", s.layout_now() == "aeromorse")
s.toggle_layout()
time.sleep(0.05)
look()
check("settings: standard Morse - M is -- and Backspace ----, in use at once",
      s.layout_now() == "standard" and app.actions.codes[(1, 2, 3)].text == "m"
      and app.actions.codes[(1, 4, 15)].label == "Backspace")
s.do_undo()
check("settings: Undo puts the AeroMorse letters back", s.layout_now() == "aeromorse")
check("settings: mouse moves show an arrow",
      s.does(dict(action=mapload.parse_action("move up-left"), text="")) == "↖  Mouse up-left")
import settings_tabs   # noqa: E402
s.show_tab("Speed")
check("settings: the code editor hides on other tabs", s.group is None and not s.editor.winfo_ismapped())
s.extra["Speed"].preset(settings_tabs.PRESETS[2][1])        # Fast
time.sleep(0.05)
look()
check("settings: Speed preset saved and in use at once",
      config.ACCEPT_DELAY == 0.2 and config.LONG_PRESS == 1.0 and app.decoder.long_press == 1.0,
      (config.ACCEPT_DELAY, config.LONG_PRESS))
check("settings: preset shown as the current one", "Fast" in s.extra["Speed"].l_preset.cget("text"))
s.switch_event("dash", True)
check("settings: Switches test lights DASH", s.extra["Switches"].lights["dash"].cget("bg") == settings_tabs.OK)
s.close()
check("settings: closing forgets the window", app.settings is None)
app.stop()
app.win.root.destroy()
shutil.rmtree(WORK, ignore_errors=True)

print("\n%d/%d %s" % (sum(R), len(R), "PASS" if all(R) else "FAIL"))
sys.exit(0 if all(R) else 1)
