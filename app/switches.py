# SwitchMorse Windows - switches.py
# Finds the switches and reads their presses on a background thread, handing
# each one to a callback with a PC timestamp. Two kinds of device:
#
#   Trinkey    the TRRS Trinkey running the reporter firmware. Read from its
#              SECOND serial port (interface 2), which sends D d A a bytes.
#   AeroMorse  an AeroMorse device with PC_HANDOVER = True in its
#              config.py (v1.32+). Read from its normal serial port. It says
#              "~HO 0" every second; while this program writes the line "~SMW"
#              twice a second, the device stops typing by itself and reports
#              each sip / puff as "~HP D/d/A/a" instead. If this program stops
#              (closed, crashed, PC asleep) the device types again within 2 s.
#              hand_back() also stops the asking while this program can't type
#              (its window not responding, an admin window, a UAC prompt).
#              Nothing is written to an AeroMorse port until it has sent "~HO",
#              and never anything but "~SMW" lines (no Ctrl+C - that would stop
#              the device, as Thonny does).
#
# Reconnects by itself if a device is unplugged and plugged back in.
import subprocess
import threading
import time

import serial
import serial.tools.list_ports as list_ports

ADAFRUIT_VID = 0x239A
ESPRESSIF_VID = 0x303A
TRINKEY_EVENTS = {b"D": ("dot", True), b"d": ("dot", False),
                  b"A": ("dash", True), b"a": ("dash", False)}
# AeroMorse: sip = dot, puff = dash
AEROMORSE_EVENTS = {"D": ("dot", True), "d": ("dot", False),
                    "A": ("dash", True), "a": ("dash", False)}
HEARTBEAT_TIMEOUT = 3.0      # seconds without a sign of life = lost
ASK_EVERY = 0.5              # seconds between "~SMW" lines to an AeroMorse
STOPPED_TEXT = ("Traceback", "Code done running", "Press any key", "soft reboot")


def candidate_ports(want="auto"):
    """[(port, kind)] - Trinkey data ports first, then AeroMorse-like ports.
    want: "auto", "trinkey" or "aeromorse"."""
    trinkeys, others = [], []
    trinkey_serials = set()
    ports = list(list_ports.comports())
    for p in ports:
        hw = (p.hwid or "").upper()
        if p.vid == ADAFRUIT_VID and (hw.endswith(":X.2") or "MI_02" in hw):
            trinkeys.append((p.device, "trinkey"))
            trinkey_serials.add(p.serial_number)
    for p in ports:
        hw = (p.hwid or "").upper()
        first_port = hw.endswith(":X.0") or "MI_00" in hw
        maker_ok = p.vid == ADAFRUIT_VID or (p.vid == ESPRESSIF_VID and (p.pid or 0) >= 0x8000)
        if maker_ok and first_port and p.serial_number not in trinkey_serials:
            others.append((p.device, "aeromorse"))
    if want == "trinkey":
        return trinkeys
    if want == "aeromorse":
        return others
    return trinkeys + others


def device_name(port):
    """The name the board gives itself over USB (e.g. "AeroMorse"), as
    Windows reports it, or None. Asked once per connection; no window appears."""
    try:
        p = next(x for x in list_ports.comports() if x.device == port)
        inst = "USB\\VID_%04X&PID_%04X\\%s" % (p.vid, p.pid, p.serial_number)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-PnpDeviceProperty -InstanceId '%s' -KeyName "
             "DEVPKEY_Device_BusReportedDeviceDesc).Data" % inst],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000)                   # CREATE_NO_WINDOW
        name = out.stdout.strip()
        return name or None
    except Exception:
        return None


class SwitchReader:
    """on_event(switch, pressed, t) - switch is "dot" or "dash", t is
    time.perf_counter() when the event arrived.
    on_status(text) - "connected COM19 (...)", "searching ...", "lost ..." """

    def __init__(self, on_event, on_status=None, port=None, want="auto", hand_back=None):
        self.on_event = on_event
        # hand_back() -> a reason ("admin window", "UAC / secure screen") while
        # Windows would block SwitchMorse's input, else None. An AeroMorse is
        # then left to type by itself (blocked.py says why).
        self.hand_back = hand_back
        self._hb = None             # the reason we are handing back right now
        self._report = on_status or (lambda s: None)
        self.last_status = ""
        self.port = port
        self.want = want
        self.connected = False
        self.version = None
        self.source = ""            # for the window: "Trinkey", "AeroMorse (PC mode)"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def on_status(self, text):
        self.last_status = text
        self._report(text)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(2)

    def _run(self):
        while not self._stop.is_set():
            if self.port:
                kinds = dict(candidate_ports())
                ports = [(self.port, kinds.get(self.port, "aeromorse"))]
            else:
                ports = candidate_ports(self.want)
            if not ports:
                self.on_status("searching - is the Trinkey (or AeroMorse) plugged in?")
                self._stop.wait(1.0)
                continue
            for name, kind in ports:
                if self._stop.is_set():
                    return
                self._serve(name, kind)
                if self.connected is None:          # served a device: start the search over
                    self.connected = False
                    break
            self._stop.wait(1.0)

    def _serve(self, name, kind):
        try:
            s = serial.Serial(name, 115200, timeout=0.05)
        except serial.SerialException as ex:
            if "denied" in str(ex).lower() or "in use" in str(ex).lower():
                self.on_status("%s is in use by another program (AeroMorse Display?)" % name)
            else:
                self.on_status("can't open %s: %s" % (name, ex))
            return
        was = False
        try:
            if kind == "trinkey":
                self._trinkey_loop(s, name)
            else:
                self._aeromorse_loop(s, name)
        except serial.SerialException:
            pass                                    # unplugged
        finally:
            try:
                s.close()
            except Exception:
                pass
            if self.connected:
                was = True
                self.source = ""
                self.on_status("lost %s" % name)
            self.connected = None if was else False

    # ---- Trinkey reporter ------------------------------------------------------------
    def _trinkey_loop(self, s, name):
        last_byte = time.perf_counter()
        hello = None                                # bytes of a "!..." line
        while not self._stop.is_set():
            b = s.read(1)
            now = time.perf_counter()
            if not b:
                if now - last_byte > HEARTBEAT_TIMEOUT:
                    return                          # silent: not our device
                continue
            last_byte = now
            if hello is not None:
                if b == b"\n":
                    text = hello.decode("ascii", "replace")
                    hello = None
                    if text.startswith("SMW"):
                        self.version = text[4:]
                        self.connected = True
                        self.source = "Trinkey"
                        self.on_status("connected %s (Trinkey, SwitchMorse Windows %s)"
                                       % (name, self.version))
                elif len(hello) < 40:
                    hello += b
                continue
            if b == b"!":
                hello = b""
            elif b in TRINKEY_EVENTS and self.connected:
                sw, pressed = TRINKEY_EVENTS[b]
                self.on_event(sw, pressed, now)

    # ---- AeroMorse hand-over -----------------------------------------------------------
    def _set_source(self):
        if self._hb:
            self.source = self._dev + (" (typing itself - %s)" % self._hb if not self._handed
                                       else " (handing back - %s)" % self._hb)
        else:
            self.source = self._dev + (" (PC mode)" if self._handed else "")

    def _check_hand_back(self, now, name):
        """Every 0.25 s: should the AeroMorse type by itself for now? Goes back to
        PC mode only after 0.5 s with nothing blocking (no flicker)."""
        if not self.hand_back or now - self._hb_checked < 0.25:
            return
        self._hb_checked = now
        r = self.hand_back()
        if r:
            self._hb_clear = None
            if r != self._hb:
                self._hb = r
                self._set_source()
                self.on_status("connected %s (AeroMorse typing itself - %s)" % (name, r))
        elif self._hb:
            if self._hb_clear is None:
                self._hb_clear = now
            elif now - self._hb_clear >= 0.5:
                self._hb = None
                self._hb_clear = None
                self._set_source()
                self.on_status("connected %s (AeroMorse - taking over again)" % name)

    def _aeromorse_loop(self, s, name):
        start = time.perf_counter()
        self._dev = "AeroMorse"                     # its own name, once Windows tells us
        self._handed = False
        self._hb = None
        self._hb_clear = None
        self._hb_checked = 0.0
        last_ho = None                              # when "~HO" was last seen
        last_ask = 0.0
        handed = False
        stopped = False                             # the device's program stopped
        buf = b""
        while not self._stop.is_set():
            now = time.perf_counter()
            if last_ho is None and now - start > HEARTBEAT_TIMEOUT:
                return                              # no "~HO": not a hand-over device
            if last_ho is not None and now - last_ho > HEARTBEAT_TIMEOUT:
                return                              # gone quiet
            if last_ho is not None:
                self._check_hand_back(now, name)
            # Ask only while the device is clearly running and saying "~HO", and
            # Windows isn't going to block our input (else the device types itself).
            if (last_ho is not None and not stopped and now - last_ho < 2.5
                    and not self._hb and now - last_ask >= ASK_EVERY):
                s.write(b"~SMW\n")
                last_ask = now
            chunk = s.read(s.in_waiting or 1)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").strip("\r")
                t = time.perf_counter()
                if any(x in line for x in STOPPED_TEXT):
                    stopped = True                  # never write into a stopped device
                    self.on_status("%s: the AeroMorse program stopped - not asking" % name)
                elif line.startswith("~HO\t"):
                    last_ho = t
                    on = line[4:5] == "1"
                    if not self.connected:
                        self.connected = True
                        self.version = "AeroMorse"
                        self._set_source()

                        def look_up(port=name):     # slow (PowerShell): never in this loop
                            found = device_name(port)
                            if found and self.connected:
                                self._dev = found
                                self._set_source()
                                self.on_status(self.last_status)    # window redraws with the name
                        threading.Thread(target=look_up, daemon=True).start()
                        self.on_status("found AeroMorse on %s - waiting for it to hand over" % name)
                    if on != handed:
                        handed = on
                        self._handed = on
                        self._set_source()
                        if on:
                            self.on_status("connected %s (AeroMorse hand-over)" % name)
                        elif self._hb:
                            self.on_status("connected %s (AeroMorse typing itself - %s)"
                                           % (name, self._hb))
                        else:
                            self.on_status("found AeroMorse on %s - waiting for it to hand over"
                                           % name)
                elif line.startswith("~HP\t") and handed and not self._hb:
                    # (while handing back, presses are dropped: if the window
                    # is frozen they would otherwise be typed when it wakes up)
                    ev = AEROMORSE_EVENTS.get(line[4:5])
                    if ev:
                        self.on_event(ev[0], ev[1], t)
            if len(buf) > 4096:
                buf = buf[-512:]
