# SwitchMorse Windows - offline test of reading an AeroMorse in hand-over mode.
# A pretend serial port plays what an AeroMorse sends; the test records what the
# program writes back and which presses it reports.
#
#   python tools\test_switches.py
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import switches   # noqa: E402


class FakeSerial:
    """Plays (seconds-from-open, line) pairs; records writes with their times."""

    def __init__(self, script):
        self.t0 = time.perf_counter()
        self.script = list(script)
        self.out = b""
        self.writes = []

    @property
    def in_waiting(self):
        self._feed()
        return len(self.out)

    def _feed(self):
        now = time.perf_counter() - self.t0
        while self.script and self.script[0][0] <= now:
            self.out += (self.script.pop(0)[1] + "\r\n").encode()

    def read(self, n=1):
        self._feed()
        if not self.out:
            time.sleep(0.01)
            return b""
        data, self.out = self.out[:n], self.out[n:]
        return data

    def write(self, b):
        self.writes.append((round(time.perf_counter() - self.t0, 2), b))


def run(script, seconds, hand_back=None):
    events, status = [], []
    s = FakeSerial(script)
    hb = (lambda: hand_back(time.perf_counter() - s.t0)) if hand_back else None
    r = switches.SwitchReader(lambda sw, p, t: events.append((sw, p)),
                              status.append, hand_back=hb)
    th = threading.Thread(target=r._aeromorse_loop, args=(s, "COM8"), daemon=True)
    th.start()
    time.sleep(seconds)
    r._stop.set()
    th.join(1)
    run.source = r.source
    return s.writes, events, status


def check(name, ok, detail=""):
    ok = bool(ok)
    print("%s  %s" % ("PASS" if ok else "FAIL", name))
    if not ok:
        print("   ", detail)
    return ok


R = []
# The AeroMorse: "~HO 0" each second; hands over after the first ~SMW; reports a sip
# and a puff; and ~AM / ~AS display lines that must be ignored.
script = [(0.2, "~AM\t[ MOUSE ]\t \t \t "), (0.5, "~HO\t0"), (1.0, "~HO\t1"),
          (1.2, "~HP\tD"), (1.35, "~HP\td"), (1.5, "~AS\t1\t800"), (1.6, "~HP\tA"),
          (1.8, "~HP\ta"), (2.0, "~HO\t1"), (3.0, "~HO\t1")]
writes, events, status = run(script, 3.3)
R.append(check("nothing written before the device says ~HO",
               writes and writes[0][0] >= 0.5, writes[:2]))
R.append(check("only ~SMW lines are ever written", all(w == b"~SMW\n" for _, w in writes), writes))
R.append(check("asks about twice a second", 4 <= len(writes) <= 7, len(writes)))
R.append(check("sip -> dot, puff -> dash (press and release)",
               events == [("dot", True), ("dot", False), ("dash", True), ("dash", False)], events))
R.append(check("window told 'connected' once handed over",
               any(x.startswith("connected COM8") for x in status), status))
R.append(check("input named, with PC mode (its real USB name if one is plugged in)",
               run.source.endswith(" (PC mode)") and run.source.startswith("AeroMorse"),
               run.source))
print("    input shown as:", run.source)

# A device without hand-over (no ~HO): nothing is written, and it gives up.
writes, events, status = run([(0.2, "~AM\t[ KEYBOARD ]\t \t \t ")], 3.5)
R.append(check("a device with no hand-over is never written to", writes == [], writes))

# The device's program stops (traceback): writing stops at once.
script = [(0.2, "~HO\t0"), (0.4, "~HO\t1"), (1.0, "Traceback (most recent call last):"),
          (1.0, "Code done running.")]
writes, events, status = run(script, 2.5)
R.append(check("after 'Traceback' nothing more is written",
               all(t < 1.05 for t, _ in writes) and writes, writes))

# An admin window is in front from 1.5 s to 2.5 s: stop asking (the device
# types by itself), then ask again 0.5 s after it has gone.
script = [(0.2 + 0.5 * i, "~HO\t1" if i else "~HO\t0") for i in range(10)]
writes, events, status = run(script, 4.8,
                             hand_back=lambda t: "admin window" if 1.5 <= t < 2.5 else None)
during = [w for w in writes if 1.8 <= w[0] < 2.9]
after = [w for w in writes if w[0] >= 3.0]
R.append(check("admin window in front: stops asking, so the device types itself",
               not during and any(t < 1.6 for t, _ in writes), writes))
R.append(check("admin window gone: asks again after 0.5 s", after, writes))
R.append(check("window told 'typing itself - admin window', then 'taking over again'",
               any("typing itself - admin window" in x for x in status) and
               any("taking over again" in x for x in status), status))

print("\n%d/%d PASS" % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
