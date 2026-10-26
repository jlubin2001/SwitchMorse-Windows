# SwitchMorse Windows - the program.
# Reads the switches from the Trinkey, decodes the Morse, types into Windows,
# and shows what is happening in a small window.
#
#   python app\switchmorse.py
#
# Right-click the window for its menu (always on top, reload map, quit).
import atexit
import os
import queue
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blocked     # noqa: E402
import hints      # noqa: E402
import sound      # noqa: E402
import secrets_store  # noqa: E402
import config      # noqa: E402     (reads app\config.txt + the work folder's config.txt)
import mapload     # noqa: E402
import paths       # noqa: E402
from actions import Actions      # noqa: E402
from decoder import Decoder      # noqa: E402
from switches import SwitchReader  # noqa: E402
from window import Window        # noqa: E402

VERSION = "1.1.0"
UI_STALE = 0.5      # seconds without a turn of the main loop = not responding

try:    # real screen coordinates on scaled (125 %, 150 %) screens, for Centre pointer
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


class App:
    def __init__(self):
        self.events = queue.Queue()             # from the serial thread
        self.input_problems = []                # notes about DOT_KEY / DASH_KEY
        self.first_run = not os.path.exists(mapload.default_path())    # load() makes it
        codes, problems = mapload.load()
        self.map_problems = problems
        self.note_problems(problems)
        self.actions = Actions(codes, config.START_GROUP, cfg=config,
                               secrets=secrets_store.Secrets())
        self.decoder = self.new_decoder()
        self.link = "Looking for the switches..."
        self.link_ok = False
        self.hint = ""
        self.win = Window(config.ALWAYS_ON_TOP,
                          on_reload=self.reload, on_quit=self.stop,
                          on_passwords=lambda: self.open_settings("Passwords"),
                          on_sound=self.set_sound,
                          on_settings=self.open_settings)
        self.settings = None                    # the Settings window, while open
        self.capture = None                     # Settings is recording: the next code goes here
        self.sound = sound.Sound(self.win.sound_level)
        self.actions.window_follow = (self.win.start_follow, self.win.stop_follow)
        self.actions.window_show = self.win.bring_to_front
        self.actions.open_settings = self.open_settings
        self.sound.prime()
        self.ui_beat = time.perf_counter()      # last turn of the main loop (poll)
        self.reader = self.make_reader()
        self.note_problems(self.map_problems)   # again: setting up the input may add notes
        self.watched = self.file_times()
        self.watch_due = 0.0
        atexit.register(self.actions.release_all)

    def make_reader(self):
        """The reader for the switches chosen by INPUT (not started yet)."""
        on_event = lambda sw, pressed, t: self.events.put(("switch", sw, pressed, t))  # noqa: E731
        on_link = lambda text: self.events.put(("link", text))                         # noqa: E731
        self.input_problems = []
        if str(getattr(config, "INPUT", "auto")).lower() == "keys":
            return self.key_reader(on_event, on_link)     # two keyboard keys
        return SwitchReader(
            on_event, on_link, config.PORT, getattr(config, "INPUT", "auto"),
            hand_back=self.hand_back)   # frozen / admin window / UAC: the AeroMorse types by itself

    def new_decoder(self):
        return Decoder(config.ACCEPT_DELAY, config.LONG_PRESS, config.LONG_PRESS_CYCLES_GROUP,
                       getattr(config, "SWITCH_BOUNCE_MS", 15) / 1000)

    # ---- changes to morse_map.txt / config.txt take effect by themselves --------
    WATCH_EVERY = 1.0       # seconds between looks at the files' times
    INPUT_SETTINGS = {"INPUT", "PORT", "DOT_KEY", "DASH_KEY"}

    def file_times(self):
        """{path: last-changed time} of the map and both config files."""
        out = {}
        for p in (mapload.default_path(), config.DEFAULTS_FILE, config.my_file()):
            try:
                out[p] = os.path.getmtime(p)
            except OSError:
                out[p] = None
        return out

    def watch(self):
        """Called from poll: reload whatever was changed (by hand, or from the
        Settings window)."""
        now = time.perf_counter()
        if now < self.watch_due:
            return
        self.watch_due = now + self.WATCH_EVERY
        times = self.file_times()
        if times == self.watched:
            return
        changed = {p for p in times if times[p] != self.watched.get(p)}
        self.watched = times
        if mapload.default_path() in changed:
            self.reload()
        if changed - {mapload.default_path()}:
            self.apply_config()

    def apply_config(self):
        """config.txt changed: read it again and use the new values at once."""
        try:
            names = config.reload()
        except Exception as ex:                 # e.g. caught half-written: next look
            self.actions.action = "Settings NOT reloaded: %s" % ex
            self.watched = {}
            self.refresh()
            return
        self.actions.configure(config)
        d = self.decoder
        d.long_press = config.LONG_PRESS
        d.long_press_cycles = config.LONG_PRESS_CYCLES_GROUP
        d.bounce = getattr(config, "SWITCH_BOUNCE_MS", 15) / 1000
        if names & self.INPUT_SETTINGS:         # other switches: start that reader
            self.actions.release_all()
            self.reader.stop()
            self.link, self.link_ok = "Looking for the switches...", False
            self.reader = self.make_reader()
            self.reader.start()
            self.decoder = self.new_decoder()
            self.ui_beat = time.perf_counter()  # stopping the old one took a moment
        self.note_problems(self.map_problems)
        if names:
            shown = sorted(names)
            self.actions.action = "Settings: " + ", ".join(
                "%s %s" % (n.replace("_", " ").lower(), config.as_text(getattr(config, n)))
                for n in shown[:2]) + (" ..." if len(shown) > 2 else "")
        self.refresh()

    def key_reader(self, on_event, on_link):
        """INPUT = keys: DOT_KEY and DASH_KEY (key names as in the map) are the
        switches. A name that isn't a key falls back to Enter / Space, noted."""
        import sendinput
        from keyinput import KeyReader
        names, vks = [], []
        for setting, fallback in (("DOT_KEY", "Enter"), ("DASH_KEY", "Space")):
            name = str(getattr(config, setting, fallback))
            r = mapload._key_part(name.strip())
            vk = sendinput.HID_TO_VK.get(r[1], (None,))[0] if r and r[1] else None
            if vk is None:
                self.input_problems.append("config.txt: %s = %s is not a key - %s is used"
                                           % (setting, name, fallback))
                name = fallback
                vk = sendinput.HID_TO_VK[mapload._key_part(fallback)[1]][0]
            names.append(name)
            vks.append(vk)
        if vks[0] == vks[1]:
            self.input_problems.append("config.txt: DOT_KEY and DASH_KEY are the same key - "
                                       "Enter and Space are used")
            names, vks = ["Enter", "Space"], [0x0D, 0x20]
        return KeyReader(on_event, on_link, vks[0], vks[1],
                         "%s = dot, %s = dash" % (names[0], names[1]))

    def hand_back(self):
        """Called from the serial thread: why the AeroMorse should type by itself
        now, or None. If the main loop has stopped turning (e.g. Windows holds it
        while a mouse button is down on this window's own title bar), nothing
        decodes the presses - so stop asking and the AeroMorse takes over within 2 s,
        even though this program is still running."""
        if time.perf_counter() - self.ui_beat > UI_STALE:
            return "SwitchMorse not responding"
        return blocked.reason()

    def run(self):
        self.reader.start()
        self.refresh()
        self.win.root.after(10, self.poll)
        if self.first_run:                      # new here: the guide (Settings > Start here)
            self.win.root.after(1500, lambda: self.open_settings("Start here"))
        self.win.root.mainloop()

    def open_settings(self, tab=None):
        """The Settings window, in this program so it can record a code from
        the switches and show them working. Already open: bring it to the front
        (on `tab`, if given)."""
        import tkinter as tk
        import settings_window
        if self.settings is not None:
            try:
                if tab:
                    self.settings.show_tab(tab)
                settings_window.take_focus(self.settings.root)
                return
            except tk.TclError:
                self.settings = None
        r = self.win.root
        avoid = (r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height())
        try:
            self.settings = settings_window.SettingsWindow(
                tk.Toplevel(r), on_record=self.record_next, avoid=avoid,
                on_close=self.settings_closed, app=self, tab=tab)
        except Exception as ex:
            self.actions.action = "Settings did not open: %s" % ex
            self.refresh()
            return
        settings_window.take_focus(self.settings.root)

    def settings_closed(self):
        self.settings = None
        self.capture = None

    def record_next(self, callback):
        """From Settings: the next code sent goes to callback(code), not typed.
        None = stop recording."""
        self.capture = callback
        self.actions.action = "Recording a code for Settings" if callback else ""
        self.refresh()

    def set_sound(self, level):
        """Sound chosen in the menu: switch to it and let it be heard."""
        self.sound.set_level(level)
        if level != "off":
            self.win.root.after(120 if self.sound.ok else 700,
                                lambda: self.sound.blip(sound.ACTION_FREQ, 120))

    def stop(self):
        self.sound.stop()
        self.actions.release_all()
        self.reader.stop()

    def reload(self):
        try:
            codes, problems = mapload.load()
        except Exception as ex:                 # e.g. the file is missing: keep the old map
            self.actions.action = "Map NOT reloaded: %s" % ex
        else:
            self.actions.set_codes(codes)
            self.map_problems = problems
            self.note_problems(problems)
            self.actions.action = "Map reloaded (%d codes)" % len(codes)
        self.refresh()

    def note_problems(self, problems):
        """Lines of morse_map.txt (and config.txt) that were left out go to
        morse_map_problems.txt (next to the map), so they can be read in
        Notepad; the window says so."""
        problems = (list(getattr(config, "PROBLEMS", [])) + list(self.input_problems)
                    + list(problems))
        self.problems = problems
        path = os.path.join(os.path.dirname(mapload.default_path()), "morse_map_problems.txt")
        try:
            if problems:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("morse_map.txt - lines left out or worth a look (%s)\n\n"
                            % time.strftime("%Y-%m-%d %H:%M"))
                    f.write("\n".join(problems) + "\n")
            elif os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        for p in problems:
            print("map:", p)

    def log_line(self, text, t):
        """config PRESS_LOG: every press, release and finished code, with the time
        since the previous line, to press_log.txt in the work folder (for tuning
        ACCEPT_DELAY from real use). Started fresh each time the program starts."""
        if not getattr(config, "PRESS_LOG", False):
            return
        try:
            if self._log is None:
                self._log = open(os.path.join(paths.work_folder(), "press_log.txt"), "w",
                                 encoding="utf-8")
                self._log.write("SwitchMorse Windows %s press log, %s - ACCEPT_DELAY %.2f, "
                                "MOUSE_ACCEPT_DELAY %.2f\n  gap(ms)  event\n"
                                % (VERSION, time.strftime("%Y-%m-%d %H:%M"),
                                   config.ACCEPT_DELAY, config.MOUSE_ACCEPT_DELAY))
            gap = (t - self._log_t) * 1000 if self._log_t else 0
            self._log_t = t
            self._log.write("%9.0f  %s\n" % (gap, text))
            self._log.flush()
        except OSError:
            pass

    _log = None
    _log_t = 0.0

    def poll(self):
        self.ui_beat = time.perf_counter()
        changed = False
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if ev[0] == "link":
                self.link = ev[1]
                self.link_ok = ev[1].startswith("connected")
                # Unplugged, or handing back to the AeroMorse (admin window / UAC):
                # let go of everything and drop any half-entered code.
                if not self.link_ok or "typing itself" in ev[1]:
                    self.actions.release_all()
                    self.decoder = self.new_decoder()
            else:
                _, sw, pressed, t = ev
                self.log_line("%-4s %s" % (sw, "down" if pressed else "up"), t)
                if self.settings is not None:
                    try:
                        self.settings.switch_event(sw, pressed)
                    except Exception:
                        pass
                if pressed:
                    self.sound.tone(sound.DOT_FREQ if sw == "dot" else sound.DASH_FREQ)
                elif not self.decoder.holding or self.decoder.down_at.get(sw) is not None:
                    self.sound.stop()
                for out in self.decoder.feed(sw, pressed, t):
                    if out[0] == "cycle":
                        self.actions.next_group()
                        self.sound.blip(sound.GROUP_FREQ, 140)
                        self.hint = ""
                if pressed:
                    self.hint = ""
                    if self.actions.repeating:
                        # A press while repeating only stops the repeat.
                        self.actions.stop_repeat()
                        self.actions.action = "Repeat off"
                        self.decoder.consume(sw)
        self.decoder.accept_delay = (config.MOUSE_ACCEPT_DELAY if self.actions.group == 2
                                     else config.ACCEPT_DELAY)
        rep = self.actions.repeating
        self.actions.tick()
        if rep != self.actions.repeating:
            changed = True
        for out in self.decoder.tick(time.perf_counter()):
            changed = True
            if out[0] == "code":
                code = "".join("-" if (out[2] >> (out[1] - 1 - i)) & 1 else "."
                               for i in range(out[1]))
                if self.capture:                # recorded for Settings, not carried out
                    give, self.capture = self.capture, None
                    self.actions.action = "Recorded " + code
                    self.sound.blip(sound.ACTION_FREQ, 60)
                    try:
                        give(code)
                    except Exception:
                        pass
                    continue
                before = self.actions.group
                done = self.actions.code(out[1], out[2])
                if done is not None:
                    if self.actions.group != before and done.kind == "group":
                        self.sound.blip(sound.GROUP_FREQ, 140)
                    else:
                        self.sound.blip(sound.ACTION_FREQ, 60)
                self.log_line("CODE %-8s -> %s" % (code, self.actions.action), time.perf_counter())
            elif out[0] == "long":
                self.hint = "let go = next group"
        if changed:
            self.refresh()
        if not self.decoder.count and not self.decoder.holding:
            self.watch()            # not in the middle of a code: look for changed files
        self.win.root.after(10, self.poll)

    def refresh(self):
        a = self.actions
        status = a.status_bits()                # armed keys, PAUSED, DRAG, REPEAT ...
        if self.hint:
            status.append(self.hint)
        state = []                              # the small line at the bottom
        if not self.link_ok:
            state.append(self.link)
        else:
            state.append("Input: " + (self.reader.source or "?"))
            if not self.reader.source.startswith("AeroMorse"):
                why = blocked.reason()          # no AeroMorse to hand back to: warn
                if why:
                    state.append("Windows blocks SwitchMorse here (%s)" % why)
        if a.blocked:
            state.append("Windows blocked the keys (admin window?)")
        if self.problems:
            state.append("%d note%s - see morse_map_problems.txt"
                         % (len(self.problems), "" if len(self.problems) == 1 else "s"))
        title = "SwitchMorse - " + (self.reader.source if self.link_ok and self.reader.source
                                    else "no input")
        if title != self.win.root.title():
            self.win.root.title(title)
        warn = a.paused or a.blocked or not self.link_ok
        buf = self.decoder.buffer
        self.win.show(a.group, a.group_name, buf, hints.hint(a.codes, a.group, buf),
                      a.action, a.repeating, " ".join(status), "   ".join(state), warn)

def already_running():
    """True if another SwitchMorse is already running (it holds the switches'
    port, so a second copy could do nothing useful)."""
    try:
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.restype = ctypes.c_void_p
        already_running.handle = k.CreateMutexW(None, False, "SwitchMorseWindows.Running")
        return ctypes.get_last_error() == 183          # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def selftest(out):
    """--selftest FILE: load every part (as the built exe has them), write what
    was found to FILE and stop, with no window and no switches - so a build can
    be checked while another SwitchMorse is running."""
    lines = ["SwitchMorse %s selftest, frozen=%s" % (VERSION, paths.FROZEN)]
    sys.path.append(os.path.join(os.path.dirname(paths.APP), "tools"))     # run from source
    try:
        import serial  # noqa: F401
        import settings_window  # noqa: F401
        import settings_tabs  # noqa: F401
        import make_cheatsheet  # noqa: F401
        lines.append("work folder: " + paths.work_folder())
        lines.append("defaults: " + config.DEFAULTS_FILE)
        codes, problems = mapload.load()
        lines.append("map: %d codes, %d problems" % (len(codes), len(problems)))
        lines.append("config problems: %d" % len(config.PROBLEMS))
        lines.append("OK")
    except Exception as ex:
        lines.append("FAILED: %r" % ex)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(sys.argv[sys.argv.index("--selftest") + 1])
        sys.exit(0)
    if already_running():
        sys.exit(0)
    App().run()
