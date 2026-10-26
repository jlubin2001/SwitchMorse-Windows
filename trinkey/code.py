# SwitchMorse Windows - switch reporter for the Adafruit TRRS Trinkey.
# Reads the two switches and tells the PC program about every press and
# release. It does no Morse decoding and sends no keys: the program does that.
#
# Sent on the data serial port, one byte each:
#   D = dot pressed    d = dot released
#   A = dash pressed   a = dash released
#   . = heartbeat, once a second
# and when the program connects:  !SMW 0.1\n  then the switches' current state.
#
# Light: blue = the program is connected, dim red = it isn't, white = a switch
# is held.
import board
import digitalio
import supervisor
import usb_cdc
from neopixel_write import neopixel_write

VERSION = "0.1"
HELLO = b"!SMW 0.1\n"        # keep in step with VERSION (the SAMD21 build has no str.encode)
DOT_PIN = board.TIP          # MorseKey / SwitchMorse wiring
DASH_PIN = board.SLEEVE
GROUND_PIN = board.RING_2
QUIET_MS = 15                # a release counts after this long with no contact
BRIGHT = 0.5

_M = (1 << 29) - 1           # ticks_ms() wraps at 2**29

gnd = digitalio.DigitalInOut(GROUND_PIN)
gnd.switch_to_output(value=False)
pins = []
for p in (DOT_PIN, DASH_PIN):
    d = digitalio.DigitalInOut(p)
    d.switch_to_input(pull=digitalio.Pull.UP)
    pins.append(d)
DOWN = (b"D", b"A")
UP = (b"d", b"a")

px_pin = digitalio.DigitalInOut(board.NEOPIXEL)
px_pin.direction = digitalio.Direction.OUTPUT
px = bytearray(3)
px_last = None


def pixel(r, g, b):
    global px_last
    if px_last == (r, g, b):
        return
    px_last = (r, g, b)
    px[0] = int(g * BRIGHT)          # the NeoPixel wants green, red, blue
    px[1] = int(r * BRIGHT)
    px[2] = int(b * BRIGHT)
    neopixel_write(px_pin, px)


data = usb_cdc.data
if data is not None:
    data.write_timeout = 0           # never wait on the PC
console_note = data is None
if console_note:
    print("SwitchMorse Windows: no data port yet - unplug and replug the Trinkey")


def send(b):
    if data is not None and data.connected:
        try:
            data.write(b)
        except Exception:
            pass


held = [False, False]
last_contact = [0, 0]
was_connected = False
beat = supervisor.ticks_ms()
print("SwitchMorse Windows reporter v" + VERSION)

while True:
    now = supervisor.ticks_ms()
    # MorseKey's hold-filter, per switch: a press counts at once; a release
    # only after QUIET_MS with no contact (bridges a chattery switch).
    for i in (0, 1):
        if not pins[i].value:
            last_contact[i] = now
            if not held[i]:
                held[i] = True
                send(DOWN[i])
        elif held[i] and ((now - last_contact[i]) & _M) >= QUIET_MS:
            held[i] = False
            send(UP[i])

    connected = data is not None and data.connected
    if connected != was_connected:
        print("program", "connected" if connected else "disconnected")
        if connected:
            send(HELLO)
            for i in (0, 1):
                send(DOWN[i] if held[i] else UP[i])
    was_connected = connected

    if ((now - beat) & _M) >= 1000:
        beat = now
        send(b".")

    if held[0] or held[1]:
        pixel(30, 30, 30)
    elif connected:
        pixel(0, 0, 40)
    else:
        pixel(10, 0, 0)
