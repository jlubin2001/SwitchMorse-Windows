# SwitchMorse Windows - press test (Phase 1)
# Shows every switch press and release from the Trinkey, with how long each
# press lasted and the gap before it. Sends nothing to Windows - safe to run
# any time. Close the window or press Ctrl+C to stop.
#
#   python tools\press_test.py              (finds the Trinkey by itself)
#   python tools\press_test.py --port COM19
#
# At the end it prints a summary: presses per switch, shortest / longest, and
# very short gaps (under 40 ms), which mean a switch is chattering.
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from switches import SwitchReader  # noqa: E402

down_at = {}
last_up = {}
lengths = {"dot": [], "dash": []}
short_gaps = {"dot": 0, "dash": 0}
t0 = time.perf_counter()


def on_event(sw, pressed, t):
    stamp = "%8.3f" % (t - t0)
    if pressed:
        gap = ""
        if sw in last_up:
            g = (t - last_up[sw]) * 1000
            gap = "  (%d ms since it was let go)" % g
            if g < 40:
                short_gaps[sw] += 1
                gap += "  <-- very short, chatter?"
        down_at[sw] = t
        print("%s  %-4s down%s" % (stamp, sw.upper(), gap), flush=True)
    else:
        if sw not in down_at:
            return              # the "it's up" state sent on connect, not a release
        ms = (t - down_at.pop(sw)) * 1000
        lengths[sw].append(ms)
        last_up[sw] = t
        print("%s  %-4s up    held %d ms" % (stamp, sw.upper(), ms), flush=True)


def on_status(text):
    print("--- %s" % text, flush=True)


def main():
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else None
    r = SwitchReader(on_event, on_status, port)
    r.start()
    print("Press the switches. Ctrl+C to stop.", flush=True)
    secs = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 1e9
    try:
        end = time.time() + secs
        while time.time() < end:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    r.stop()
    print()
    for sw in ("dot", "dash"):
        L = lengths[sw]
        if L:
            print("%-4s %3d presses, held %d-%d ms, %d very short gaps"
                  % (sw.upper(), len(L), min(L), max(L), short_gaps[sw]))
        else:
            print("%-4s no presses" % sw.upper())


if __name__ == "__main__":
    main()
