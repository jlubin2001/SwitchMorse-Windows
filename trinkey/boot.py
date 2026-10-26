# SwitchMorse Windows boot.py - Adafruit TRRS Trinkey (#5954)
# Runs once at power-up. Changes here need an unplug and replug.
#   - a second USB serial port ("data") just for switch events; the first
#     (console) port stays free for messages
#   - USB keyboard/mouse stay on for the later hybrid mode (PLAN.md section 7);
#     the reporter firmware never sends anything through them
import usb_cdc
import usb_hid

usb_cdc.enable(console=True, data=True)

# No boot_device=1 here: it needs the keyboard to be USB interface #0, which
# it isn't while the serial ports and drive are on - the Trinkey then starts
# in safe mode and runs nothing.
usb_hid.enable((usb_hid.Device.KEYBOARD,
                usb_hid.Device.MOUSE,
                usb_hid.Device.CONSUMER_CONTROL))

try:
    import supervisor
    supervisor.set_usb_identification("Adafruit", "SwitchMorse Windows")
except Exception:
    pass
