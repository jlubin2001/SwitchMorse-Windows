# SwitchMorse Windows - offline test of the keyboard-keys input (INPUT = keys).
# The decision logic is fed made-up key events; the real Windows hook is only
# started and stopped (a real key press can't be faked: software key presses
# are marked as injected, and the hook rightly lets those through).
#
#   python tools\test_keys.py
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import keyinput  # noqa: E402
import mapload   # noqa: E402
import sendinput  # noqa: E402
from keyinput import WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, LLKHF_INJECTED  # noqa: E402

VK_ENTER, VK_SPACE, VK_A = 0x0D, 0x20, 0x41
R = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print("%s  %s" % ("PASS" if ok else "FAIL", name))
    if not ok:
        print("   ", detail)
    R.append(ok)


k = keyinput.Keys(VK_ENTER, VK_SPACE)
seq = [k.handle(VK_ENTER, WM_KEYDOWN, 0), k.handle(VK_ENTER, WM_KEYDOWN, 0),   # down + a repeat
       k.handle(VK_ENTER, WM_KEYDOWN, 0), k.handle(VK_ENTER, WM_KEYUP, 0),
       k.handle(VK_SPACE, WM_KEYDOWN, 0), k.handle(VK_SPACE, WM_KEYUP, 0)]
check("Enter = dot, Space = dash; key-repeats while held are swallowed, not new presses",
      seq == [(True, ("dot", True)), (True, None), (True, None), (True, ("dot", False)),
              (True, ("dash", True)), (True, ("dash", False))], seq)
check("other keys go through untouched",
      k.handle(VK_A, WM_KEYDOWN, 0) == (False, None) and k.handle(VK_A, WM_KEYUP, 0) == (False, None))
check("Enter / Space typed BY SwitchMorse (injected) go through - Morse Enter still works",
      k.handle(VK_ENTER, WM_KEYDOWN, LLKHF_INJECTED) == (False, None))
check("Alt held with the key (system key message) still counts",
      k.handle(VK_SPACE, WM_SYSKEYDOWN, 0) == (True, ("dash", True)))


def vk_of(name):
    r = mapload._key_part(name)
    return sendinput.HID_TO_VK.get(r[1], (None,))[0] if r and r[1] else None


check("key names from config.txt: Enter, Space, F9, Scroll Lock, Keypad 1",
      [vk_of(n) for n in ("Enter", "Space", "F9", "Scroll Lock", "Keypad 1")]
      == [0x0D, 0x20, 0x78, 0x91, 0x61], [vk_of(n) for n in ("Enter", "Space", "F9")])
check("not a key -> no key (the program then uses Enter / Space and says so)",
      vk_of("Flubber") is None and vk_of("Ctrl") is None)

status = []
r = keyinput.KeyReader(lambda *a: None, status.append, VK_ENTER, VK_SPACE, "Enter = dot, Space = dash")
r.start()
time.sleep(0.5)
check("the Windows keyboard hook starts", r.connected and r.source.startswith("Keys"), status)
r.stop()
check("... and stops", not r.connected, status)

print("\n%d/%d PASS" % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
