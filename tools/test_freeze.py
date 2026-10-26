# SwitchMorse Windows - offline test: the program's main loop freezes while it
# has an AeroMorse in hand-over mode (what happened 2026-10-23 when a Morse
# click landed on the window's own X button). Runs the REAL program (window
# hidden) with a pretend AeroMorse on a pretend serial port; nothing is typed or
# clicked on the PC - the program's output goes to a recorder.
#
#   python tools\test_freeze.py
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import blocked      # noqa: E402
import config       # noqa: E402
import switches     # noqa: E402
import switchmorse  # noqa: E402
from actions import Actions     # noqa: E402

T0 = time.perf_counter()


def now():
    return time.perf_counter() - T0


class FakeAeroMorse:
    """Behaves like an AeroMorse with PC_HANDOVER = True: "~HO 0/1" every second;
    handed over while "~SMW" came in the last 2 s; while handed over it reports
    presses as "~HP", otherwise it would type them itself (noted in .typed_itself)."""

    def __init__(self, *a, **k):
        self.out = b""
        self.last_smw = None
        self.next_ho = 0.0
        self.smw = []               # times of "~SMW" lines
        self.handed_log = []        # (time, handed) changes
        self.typed_itself = []
        self.presses = [1.5, 3.0, 6.0, 10.5]     # a sip (dot), press + release
        self.was = False
        FakeAeroMorse.it = self

    def handed(self):
        return self.last_smw is not None and now() - self.last_smw < 2.0

    def _feed(self):
        t = now()
        h = self.handed()
        if h != self.was:
            self.was = h
            self.handed_log.append((round(t, 2), h))
        if t >= self.next_ho:
            self.next_ho = t + 1.0
            self.out += b"~HO\t%d\r\n" % h
        while self.presses and self.presses[0] <= t:
            p = self.presses.pop(0)
            if h:
                self.out += b"~HP\tD\r\n~HP\td\r\n"
            else:
                self.typed_itself.append(p)

    @property
    def in_waiting(self):
        self._feed()
        return len(self.out)

    def read(self, n=1):
        self._feed()
        if not self.out:
            time.sleep(0.01)
            return b""
        data, self.out = self.out[:n], self.out[n:]
        return data

    def write(self, b):
        assert b == b"~SMW\n", b
        self.last_smw = now()
        self.smw.append(round(now(), 2))

    def close(self):
        pass


class Recorder:
    def __init__(self):
        self.log = []

    def __getattr__(self, name):
        return lambda *a, **k: self.log.append((round(now(), 2), name, a)) or True


def check(name, ok, detail=""):
    print("%s  %s" % ("PASS" if ok else "FAIL", name))
    if not ok:
        print("   ", detail)
    return bool(ok)


# The pretend world: one AeroMorse port, nothing blocking, no press log written.
switches.serial.Serial = FakeAeroMorse
switches.candidate_ports = lambda want="auto": [("COM99", "aeromorse")]
switches.device_name = lambda port: "AeroMorse Test"
blocked.reason = lambda: None
config.PRESS_LOG = False
config.PORT = None
config.START_GROUP = 1      # the sips below are letters, whatever your own config.txt says

app = switchmorse.App()
app.win.root.withdraw()
rec = Recorder()
app.actions.out = rec
status = []
_put = app.events.put
app.events.put = lambda ev: (ev[0] == "link" and status.append((round(now(), 2), ev[1]))) or _put(ev)

# The freeze: from 2.5 s to 8.5 s the main loop does nothing (as when Windows
# holds it for a mouse button down on the X).
app.win.root.after(int((2.5 - now()) * 1000), lambda: time.sleep(6.0))
app.win.root.after(int((12.0 - now()) * 1000), app.win.quit)
app.run()

g = FakeAeroMorse.it
typed = [x for x in rec.log if x[1] in ("char", "keys", "vk")
         and not (x[1] == "keys" and len(x[2][0]) >= 8)]      # (8 key-ups = release all)
R = []
R.append(check("the AeroMorse handed over at the start", g.handed_log and g.handed_log[0][1],
               g.handed_log))
R.append(check("the sip at 1.5 s was typed by SwitchMorse",
               any(1.5 <= t < 2.5 for t, _, _ in typed), typed))
R.append(check("main loop frozen at 2.5 s: no ~SMW after 3.3 s until it wakes",
               not [t for t in g.smw if 3.3 < t < 8.5], g.smw))
R.append(check("the AeroMorse types by itself again within 3 s of the freeze",
               any(not h and 2.5 < t <= 5.5 for t, h in g.handed_log), g.handed_log))
R.append(check("the sip at 6.0 s (during the freeze) was typed by the AeroMorse itself",
               6.0 in g.typed_itself, g.typed_itself))
R.append(check("nothing from the freeze is typed late by SwitchMorse",
               not any(2.5 <= t < 10.5 for t, _, _ in typed), typed))
R.append(check("window told 'typing itself - SwitchMorse not responding'",
               any("SwitchMorse not responding" in s for _, s in status), status))
R.append(check("after waking, it takes over again",
               any(t > 8.5 for t in g.smw) and any(h and t > 8.5 for t, h in g.handed_log),
               g.handed_log))
R.append(check("the sip at 10.5 s was typed by SwitchMorse",
               any(t >= 10.5 for t, _, _ in typed), typed))

# Clicks over SwitchMorse's own window: press + release in one go, no drag.
class OwnWindow(Recorder):
    def pointer_on_own_window(self):
        return True


import mapload    # noqa: E402
codes, _ = mapload.load()
a = Actions(codes, 2, out=OwnWindow(), cfg=config)
a._click("left", 2)
for _ in range(50):
    a.tick(time.perf_counter() + 1)
calls = [x[1] for x in a.out.log]
R.append(check("double click on own window: two whole clicks, no held button",
               calls.count("click") == 2 and "button" not in calls, a.out.log))
a.out.log.clear()
a._command(type("A", (), {"cmd": ("mdrag", "left"), "label": "Drag",
                          "_replace": lambda self, **k: self})())
R.append(check("drag on own window: not started", a.drag is None and not a.out.log, a.out.log))

print("\n%d/%d PASS" % (sum(R), len(R)))
sys.stdout.flush()
os._exit(0 if all(R) else 1)
