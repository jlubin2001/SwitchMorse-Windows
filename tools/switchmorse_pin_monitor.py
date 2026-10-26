# SwitchMorse pin monitor v0.1
# For the Adafruit TRRS Trinkey (#5954, SAMD21) running CircuitPython.
# Save this file as code.py on the CIRCUITPY drive, then open the serial console.
#
# It does NOT send any keyboard or mouse input. It only reports which jack
# contact each switch press lands on, so we can confirm the splitter wiring.
#
# NeoPixel: needs neopixel.mpy in CIRCUITPY/lib (optional; the script runs without it).
#   dim red   = nothing plugged into the Trinkey jack
#   dim blue  = plug inserted, no switch pressed
#   green     = at least one switch pressed

import time
import board
import digitalio

# Which jack contact is driven low as ground.
#   CTIA splitter (your cable): "RING_2"
#   OMTP cable:                 "SLEEVE"
GROUND = "RING_2"

CONTACTS = ("TIP", "RING_1", "RING_2", "SLEEVE")
STUCK_SECONDS = 2.0   # pin held low this long is reported as stuck/shorted

try:
    import neopixel
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1)
except Exception:
    pixel = None


def color(rgb):
    if pixel is not None:
        pixel[0] = rgb


pins = {}
for name in CONTACTS:
    pins[name] = digitalio.DigitalInOut(getattr(board, name))

tip_switch = digitalio.DigitalInOut(board.TIP_SWITCH)
tip_switch.switch_to_input(pull=digitalio.Pull.UP)

inputs = [n for n in CONTACTS if n != GROUND]


def plug_inserted():
    # Adafruit's method: TIP_SWITCH is connected to TIP when no plug is in the
    # jack and floats when a plug is in. Drive TIP low, then read TIP_SWITCH
    # with a pull-up: high means a plug is inserted.
    pins["TIP"].switch_to_output(value=False)
    time.sleep(0.001)
    return tip_switch.value


def configure_for_reading():
    for n in CONTACTS:
        if n == GROUND:
            pins[n].switch_to_output(value=False)
        else:
            pins[n].switch_to_input(pull=digitalio.Pull.UP)


print("SwitchMorse pin monitor v0.1")
print("Ground pin:", GROUND, "| Reading:", ", ".join(inputs))
print("Plug a splitter into the Trinkey, then press each switch.")

last_plugged = False
last_state = {n: False for n in inputs}   # True = pressed (reads low)
low_since = {}
reported_stuck = set()

while True:
    plugged = plug_inserted()
    if plugged != last_plugged:
        print("PLUG", "inserted" if plugged else "removed")
        last_plugged = plugged
        low_since.clear()
        reported_stuck.clear()
        if plugged:
            time.sleep(0.25)   # let the plug seat fully

    if plugged:
        configure_for_reading()
        time.sleep(0.001)
        now = time.monotonic()
        any_pressed = False
        for n in inputs:
            pressed = not pins[n].value
            any_pressed = any_pressed or pressed
            if pressed != last_state[n]:
                print(n, "PRESSED" if pressed else "released")
                last_state[n] = pressed
            if pressed:
                low_since.setdefault(n, now)
                if now - low_since[n] > STUCK_SECONDS and n not in reported_stuck:
                    print("NOTE:", n, "has been low for", STUCK_SECONDS,
                          "s - stuck or shorted (a mono plug in a stereo jack does this)")
                    reported_stuck.add(n)
            else:
                low_since.pop(n, None)
                reported_stuck.discard(n)
        color((0, 60, 0) if any_pressed else (0, 0, 60))
    else:
        for n in inputs:
            last_state[n] = False
        color((60, 0, 0))

    time.sleep(0.01)
