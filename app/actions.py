# SwitchMorse Windows - actions.py
# Carries out a finished code: looks it up (Group 0 first, then the current
# group) and presses keys, moves / clicks the mouse, arms modifiers, changes
# group, pauses... Behaves like AeroMorse:
#   - "repeat" starts a CONTINUOUS repeat of the last key (every
#     MOUSE_REPEAT_DELAY) or a smooth glide of the last mouse move, until the
#     next press (which only stops it) or "repeat" again
#   - Shift + navigation keys keep Shift armed, so Shift, arrow, arrow... (or
#     Shift, arrow, repeat) keeps extending a highlight (SHIFT_SELECT)
#   - clicks are scheduled steps (press, hold, release), never a sleep
# Keeps the state the window shows: group, armed modifiers, paused, speed, drag.
import time

import hid_names
import mapload
import sendinput

NAV_KEYS = {0x4F, 0x50, 0x51, 0x52, 0x4A, 0x4D, 0x4B, 0x4E}   # arrows, Home, End, PgUp, PgDn
SHIFT_BITS = 0x02 | 0x20


class Actions:
    def __init__(self, codes, start_group=1, out=None, cfg=None, clock=time.perf_counter,
                 secrets=None):
        self.out = out or sendinput.Output()
        self.clock = clock
        self.secrets = secrets      # .get(name) -> value or None (secrets_store.Secrets)
        self.configure(cfg)
        self.set_codes(codes)
        self.group = start_group if start_group in self.groups else self.groups[0]
        self.armed = 0              # sticky modifier bits
        self.nav_hold = False       # armed mods kept on for Shift + arrows
        self.paused = False
        self.speed = "normal"
        self.drag = None            # button a drag is holding
        self.last = None            # last repeatable key Action
        self.vec = (0, 0, 0)        # last mouse move, already scaled
        self.repeat_label = ""
        self.repeating = False
        self._rep_t0 = 0.0
        self._rep_last = 0.0
        self._moved = [0, 0, 0]
        self.steps = []             # click steps: (wait, function)
        self._down = set()          # mouse buttons we are holding down
        self._step_due = 0.0
        self.action = ""            # last thing done, for the window
        self.blocked = False        # Windows refused the last keys

    # ---- setup ---------------------------------------------------------------
    def configure(self, cfg):
        """Take the settings from `cfg` (config.py) - at the start, and again
        whenever config.txt changes."""
        c = lambda name, default: getattr(cfg, name, default)      # noqa: E731
        self.speeds = {"slow": c("MOUSE_SPEED_SLOW", 1), "normal": c("MOUSE_SPEED_NORMAL", 2),
                       "fast": c("MOUSE_SPEED_FAST", 3)}
        self.factor = c("MOUSE_SPEED_FACTOR", 2)
        self.scroll_factor = c("MOUSE_SCROLL_FACTOR", 1)
        self.repeat_delay = c("MOUSE_REPEAT_DELAY", 0.040)
        self.click_hold = c("MOUSE_CLICK_HOLD", 0.060)
        self.click_gap = c("MOUSE_CLICK_GAP", 0.040)
        self.mod_delay = c("MOUSE_CLICK_MOD_DELAY", 0.030)
        self.click_keeps_mods = c("MOUSE_CLICK_KEEPS_MODS", True)
        self.shift_select = c("SHIFT_SELECT", True)
        self.no_repeat = self._no_repeat(c("NO_REPEAT_KEYS", ()))
        self.macro_return = c("MACRO_RETURN", True)
        self.rclick_moves = c("RIGHT_CLICK_MOVE_RIGHT", 0)

    @staticmethod
    def _no_repeat(names):
        """NO_REPEAT_KEYS -> {(mods, keys)}. Key names as in morse_map.txt
        ("Page Up", "Win+Tab"), or the AeroMorse ones ("PAGE_UP", "GUI+TAB")."""
        out = set()
        if isinstance(names, str):
            names = (names,)
        for nm in names:
            mods, keys, ok = 0, [], True
            for part in str(nm).split("+"):
                r = mapload._key_part(part.strip())
                if r is None or (r[1] is None and r[0] == 0):
                    ok = False
                    break
                mods |= r[0]
                if r[1] is not None:
                    keys.append(r[1])
            if ok:
                out.add((mods, tuple(sorted(keys))))
        return out

    def set_codes(self, codes):
        self.codes = codes
        self.groups = mapload.groups_in(codes) or [1]

    # ---- for the window --------------------------------------------------------
    @property
    def armed_names(self):
        return [hid_names.MOD_LABELS[i] for i in range(8) if self.armed & (1 << i)]

    @property
    def group_name(self):
        return mapload.GROUP_NAMES[self.group]

    def status_bits(self):
        bits = []
        if self.paused:
            bits.append("PAUSED")
        if self.armed:
            bits.append(" ".join(self.armed_names))
        if self.drag:
            bits.append("DRAG")
        if self.repeating:
            bits.append("REPEAT " + self.repeat_label)
        if self.group == 2 and self.speed != "normal":
            bits.append(self.speed.upper())
        return bits

    # ---- codes -------------------------------------------------------------------
    def next_group(self):
        g = self.groups
        self._set_group(g[(g.index(self.group) + 1) % len(g)] if self.group in g else g[0])
        self.action = "Group %d %s" % (self.group, self.group_name.title())

    def _set_group(self, g):
        self.group = g
        self.last = None            # AeroMorse: after a group change, repeat needs a new action
        self.stop_repeat()

    def code(self, n, p):
        """A finished code of n symbols. Returns the Action done, or None."""
        code = mapload.code_str(n, p)
        if n > 8:
            self.action = "? too long"
            return None
        a = self.codes.get((0, n, p)) or self.codes.get((self.group, n, p))
        if a is None:
            self.action = "? " + code
            return None
        if self.paused and not (a.kind == "cmd" and a.cmd[0] == "pause"):
            self.action = "(paused) " + code
            return None
        self.do(a)
        # As in AeroMorse: after typing something from Macros, back to Keyboard.
        if (self.macro_return and self.group == 3 and 1 in self.groups
                and a.kind in ("char", "text", "secret", "key", "vk")):
            self._set_group(1)
        return a

    def do(self, a):
        if a.kind == "secret":
            # A password or other private text, from secrets_store. Its value
            # is typed but never shown, logged or repeated.
            value = self.secrets.get(a.text) if self.secrets else None
            self._drop_nav_hold()
            self.armed = 0
            self.last = None
            self.vec = (0, 0, 0)
            if value is None:
                self.action = a.label + " (not set)"
            else:
                ok = all([self.out.char(ch, 0) is not False for ch in value])
                self.blocked = not ok
                self.action = a.label
        elif a.kind in ("char", "text"):
            pre = "".join(n + "+" for n in self.armed_names)
            self._fire(a)
            self.last = a
            self.repeat_label = pre + a.label
            self.vec = (0, 0, 0)
            self.action = pre + a.label
        elif a.kind == "key":
            pre = "".join(n + "+" for n in self.armed_names)
            self._press(a.mods, a.keys)
            if (a.mods, tuple(sorted(a.keys))) in self.no_repeat:
                self.last = None
            else:
                self.last = a
                self.repeat_label = pre + a.label
            self.vec = (0, 0, 0)
            self.action = pre + a.label
        elif a.kind == "vk":
            self.out.vk(a.keys[0])
            self.last = None
            self.vec = (0, 0, 0)
            self.action = a.label
        elif a.kind == "mod":
            if self.armed & a.mods:
                self.armed &= ~a.mods
                if not self.armed:
                    self.nav_hold = False
                self.action = a.label + " off"
            else:
                self._drop_nav_hold()       # a new modifier starts afresh
                self.armed |= a.mods
                self.action = a.label + " on"
        elif a.kind == "group":
            self._set_group(a.group)
            self.action = a.label
        elif a.kind == "cmd":
            self._command(a)

    def _press(self, mods, keys):
        nav = bool(keys) and all(k in NAV_KEYS for k in keys)
        if not nav:
            self._drop_nav_hold()
        ev = sendinput.combo_events(mods | self.armed, keys)
        sent = self.out.keys(ev)
        self.blocked = sent is not None and sent < len(ev)
        if self.armed:
            if self.shift_select and nav and self.armed & SHIFT_BITS:
                self.nav_hold = True
            else:
                self.armed = 0
                self.nav_hold = False

    def _fire(self, a):
        """Type a key or character Action once (also used by repeat)."""
        if a.kind == "char":
            self._drop_nav_hold()           # a character is never part of Shift + arrows
            ok = self.out.char(a.text, self.armed)
            self.blocked = ok is False
            self.armed = 0
        elif a.kind == "text":
            # A phrase: armed modifiers are dropped (as in AeroMorse), each
            # character typed on the current layout.
            self._drop_nav_hold()
            self.armed = 0
            ok = all([self.out.char(ch, 0) is not False for ch in a.text])
            self.blocked = not ok
        else:
            self._press(a.mods, a.keys)

    def _drop_nav_hold(self):
        if self.nav_hold:
            self.armed = 0
            self.nav_hold = False

    def _command(self, a):
        verb = a.cmd[0]
        if verb == "repeat":
            if self.repeating:
                self.stop_repeat()
                self.action = "Repeat off"
            elif self.last is not None or self.vec != (0, 0, 0):
                self.repeating = True
                self._rep_t0 = 0.0
                self._rep_last = 0.0
                self._moved = [0, 0, 0]
                self.action = "Repeat " + self.repeat_label
            else:
                self.action = "Nothing to repeat"
            return
        if verb == "pause":
            self.release_all()
            self.paused = not self.paused
            self.action = "Paused" if self.paused else "Started again"
            return
        if verb == "releaseall":
            self.release_all()
            self.action = "Released all"
            return
        if verb == "mmove":
            s = self.speeds[self.speed]
            dx, dy = a.cmd[1] * s * self.factor, a.cmd[2] * s * self.factor
            sc = a.cmd[3] * s * self.scroll_factor
            if dx or dy:
                self.out.move(dx, dy)
            if sc:
                self.out.wheel(sc)
            self.vec = (dx, dy, sc)
            self.last = None
            self.repeat_label = a.label
        elif verb == "mclick":
            self._click(a.cmd[1], a.cmd[2])
        elif verb == "mdrag":
            if self.drag:
                self._end_drag()
                a = a._replace(label="Drag off")
            elif self._on_own_window():
                # On SwitchMorse's own window (title bar, panel...): never hold
                # a button - a held button on our own title bar would stop this
                # program. Instead the window follows the pointer until drag
                # is sent again (if the window offers that).
                if self.window_follow:
                    self.drag = "window"
                    self.window_follow[0]()
                    a = a._replace(label="Moving this window - drag again to stop")
                else:
                    a = a._replace(label="No drag on the SwitchMorse window")
            else:
                self.drag = a.cmd[1]
                self._button(self.drag, True)
                a = a._replace(label="Drag on")
            self.vec = (0, 0, 0)
            self.last = None
        elif verb in ("mslow", "mfast"):
            want = "slow" if verb == "mslow" else "fast"
            self.speed = "normal" if self.speed == want else want
            a = a._replace(label="Mouse speed " + self.speed)
        elif verb == "showwindow":
            if self.window_show:
                self.window_show()
            else:
                a = a._replace(label="No window to bring to the front")
        elif verb == "settings":
            if self.open_settings:
                self.open_settings()
            else:
                a = a._replace(label="No Settings window here")
        elif verb == "mcenter":
            self.out.center()
            self.vec = (0, 0, 0)
            self.last = None
        self.action = a.label

    # ---- clicks ------------------------------------------------------------------
    def _on_own_window(self):
        """Pointer over SwitchMorse's own window? A button held down there (on
        the X or title bar) freezes this program's main loop until it comes up,
        but the release is sent by that same loop - so it never comes. There,
        a click is pressed and released at once, and a drag is not started."""
        f = getattr(self.out, "pointer_on_own_window", None)
        return bool(f and f())

    # (start, stop) from the program: make SwitchMorse's own window follow the
    # pointer, for a drag that starts on it. None = no such window (tests).
    window_follow = None
    window_show = None     # brings SwitchMorse's own window to the front
    open_settings = None   # opens the Settings window

    def _end_drag(self):
        """End a drag: let go of the held button, or stop the window following."""
        if self.drag == "window":
            if self.window_follow:
                self.window_follow[1]()
        elif self.drag:
            self._button(self.drag, False)
        self.drag = None

    def _add_step(self, wait, fn):
        if not self.steps:
            self._step_due = self.clock() + wait
        self.steps.append((wait, fn))

    def _click(self, button, count):
        wait = self.click_gap if self.steps else 0.0
        if self.drag == "window":
            self._end_drag()                # a click just stops moving our window
        elif self.drag:
            # A click while dragging ends the drag. With the same button, the
            # release IS the click (so a highlight made by the drag stays).
            held = self.drag
            self._end_drag()
            wait = self.click_gap
            if button == held:
                count -= 1
        mods = self.armed
        if count > 0 and mods:
            down = [(vk, ext, False) for i, (vk, ext) in enumerate(sendinput.MOD_VK)
                    if mods & (1 << i)]
            self._add_step(wait, lambda: self.out.keys(down))
            wait = self.mod_delay
        own = self._on_own_window()
        for _ in range(count):
            if own:                 # press + release together: see _on_own_window
                self._add_step(wait, lambda: self.out.click(button))
            else:
                self._add_step(wait, lambda: self._button(button, True))
                self._add_step(self.click_hold, lambda: self._button(button, False))
            wait = self.click_gap
        if count > 0 and mods:
            up = [(vk, ext, True) for i, (vk, ext) in enumerate(sendinput.MOD_VK)
                  if mods & (1 << i)]
            self._add_step(self.mod_delay, lambda: self.out.keys(up))
            if not self.click_keeps_mods:
                self.armed = 0
        if button == "right" and count > 0 and self.rclick_moves:
            # A right-click menu opens with its top-left corner AT the pointer:
            # step into the menu (RIGHT_CLICK_MOVE_RIGHT "move right"s, at the
            # current speed) once it has had a moment to open. Saves a code.
            dx = self.rclick_moves * self.speeds[self.speed] * self.factor
            self._add_step(0.12, lambda: self.out.move(dx, 0))
        self.vec = (0, 0, 0)
        self.last = None
        self.tick()                 # a step due now goes out now

    # ---- time ----------------------------------------------------------------------
    def tick(self, now=None):
        """Call often (every ~10 ms): runs click steps and the repeat."""
        now = self.clock() if now is None else now
        while self.steps and now >= self._step_due:
            _, fn = self.steps.pop(0)
            fn()
            if self.steps:
                self._step_due = now + self.steps[0][0]
        if not self.repeating or self.paused:
            return
        if self.last is not None:
            if now - self._rep_last >= self.repeat_delay:
                self._rep_last = now
                self._fire(self.last)
            return
        if self.vec == (0, 0, 0):
            self.stop_repeat()
            return
        if not self._rep_t0:
            self._rep_t0 = now
            return
        scale = (now - self._rep_t0) / self.repeat_delay
        target = [int(round(scale * v)) for v in self.vec]
        d = [target[i] - self._moved[i] for i in range(3)]
        if d[0] or d[1]:
            self.out.move(d[0], d[1])
        if d[2]:
            self.out.wheel(d[2])
        for i in range(3):
            self._moved[i] += d[i]

    def _button(self, name, down):
        """A mouse button, remembering which are down so release_all can let go."""
        if down:
            self._down.add(name)
        else:
            self._down.discard(name)
        self.out.button(name, down)

    def stop_repeat(self):
        self.repeating = False

    def release_all(self):
        """Let go of everything: modifiers, mouse buttons, drag, repeat, clicks."""
        self.stop_repeat()
        self.steps = []
        self.armed = 0
        self.nav_hold = False
        if self.drag == "window" and self.window_follow:
            self.window_follow[1]()
        self.drag = None
        for b in list(self._down):
            self._button(b, False)
        self.out.keys(sendinput.release_events())
