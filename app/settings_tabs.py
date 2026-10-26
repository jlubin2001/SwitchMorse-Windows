# SwitchMorse Windows - settings_tabs.py
# The Settings window's tabs other than the codes (settings_window.py):
#   Speed      timing presets, each timing with - / + buttons, a practice box,
#              and how typing behaves
#   Switches   which switches, a live test (DOT / DASH light up), the two
#              keyboard keys, the port
#   Window     the SwitchMorse window's look, and sound
#   Passwords  the secret values that "secret NAME" codes type (encrypted)
#   Cheat sheet  make it, open it, make a PDF
# A setting is saved to config.txt a moment after the last change (only its
# line changes) and the running SwitchMorse uses it at once. Nothing here uses
# a slider, a drag or a pop-up: - and + buttons, Tab, Enter and Space do it all.
import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk

import config
import mapload
import secrets_store

BG, BG2, FG, DIM, OK, WARN, BAD, ACCENT = ("#1e1e1e", "#2a2a2a", "#f0f0f0", "#9a9a9a",
                                           "#5fd068", "#ffb84d", "#ff6b6b", "#3a7bd5")
FONT = ("Segoe UI", 13)
BOLD = ("Segoe UI", 13, "bold")
BIG = ("Segoe UI", 22, "bold")
SAVE_AFTER_MS = 900         # save this long after the last - / + press

# name, label, low, high, step, format, what it means
TIMINGS = [
    ("ACCEPT_DELAY", "Pause that ends a letter", 0.10, 1.50, 0.05, "%.2f s",
     "after your last dot or dash; too short cuts letters in two, too long feels slow"),
    ("MOUSE_ACCEPT_DELAY", "... in the Mouse group", 0.10, 1.50, 0.05, "%.2f s",
     "the same pause, only in Mouse (a little shorter makes clicks quicker)"),
    ("LONG_PRESS", "Hold to change group", 0.5, 3.0, 0.1, "%.1f s",
     "hold a switch this long, then let go = next group"),
    ("MOUSE_SPEED_FACTOR", "Mouse speed", 1, 20, 1, "%d",
     "how far one mouse move goes (7 = the AeroMorse default)"),
    ("RIGHT_CLICK_MOVE_RIGHT", "After a right-click, step into the menu", 0, 6, 1, "%d steps",
     "moves the pointer right into the menu that opens; 0 = off"),
]
BOUNCE = ("SWITCH_BOUNCE_MS", "Switch bounce", 0, 60, 5, "%d ms",
          "a switch that opens for less than this mid-press counts as one press")
PRESETS = [("Learning", {"ACCEPT_DELAY": 0.5, "MOUSE_ACCEPT_DELAY": 0.4, "LONG_PRESS": 1.5}),
           ("Comfortable", {"ACCEPT_DELAY": 0.35, "MOUSE_ACCEPT_DELAY": 0.3, "LONG_PRESS": 1.2}),
           ("Fast", {"ACCEPT_DELAY": 0.2, "MOUSE_ACCEPT_DELAY": 0.2, "LONG_PRESS": 1.0})]
CHOICES = [("MACRO_RETURN", "After a phrase or password, go back to Keyboard"),
           ("SHIFT_SELECT", "Shift then arrows keeps Shift on (to select text)"),
           ("MOUSE_CLICK_KEEPS_MODS", "Ctrl stays on after a click (Ctrl+click several things)"),
           ("LONG_PRESS_CYCLES_GROUP", "A long press changes group")]
INPUTS = [("auto", "Find them by itself", "a Trinkey if one is plugged in, otherwise an AeroMorse"),
          ("trinkey", "Adafruit TRRS Trinkey", "two switches plugged into the Trinkey"),
          ("aeromorse", "AeroMorse", "sip and puff; it types by itself whenever SwitchMorse stops"),
          ("keys", "Two keyboard keys", "a switch interface that types keys, or two keys on a keyboard")]


def settings_now():
    """(values, defaults) as config.txt says right now. Read here, not from the
    config module, which belongs to the running program: it notices the saved
    file by itself and reloads."""
    defaults, _ = config.read(config.DEFAULTS_FILE)
    mine = config.my_file()
    values, _ = config.read(config.DEFAULTS_FILE, mine if os.path.exists(mine) else None)
    return values, defaults


class Saver:
    """Collects changes and writes them to config.txt a moment after the last
    one (so ten presses of + make one save, one backup)."""

    def __init__(self, root, say):
        self.root, self.say = root, say
        self.pending = {}
        self.job = None

    def set(self, name, value, at_once=False):
        self.pending[name] = value
        if self.job:
            self.root.after_cancel(self.job)
        self.job = self.root.after(0 if at_once else SAVE_AFTER_MS, self.flush)

    def flush(self):
        self.job = None
        if not self.pending:
            return
        changes, self.pending = self.pending, {}
        try:
            config.save(changes)
        except (ValueError, OSError) as ex:
            self.say("Not saved: %s" % ex, BAD)
            return
        self.say("Saved: %s. SwitchMorse uses it now." % ", ".join(
            "%s %s" % (n.replace("_", " ").lower(), config.as_text(v)) for n, v in changes.items()), OK)


def _label(parent, text, style="TLabel", **kw):
    return ttk.Label(parent, text=text, style=style, **kw)


class Stepper:
    """Label   [-]  0.25 s  [+]   what it means"""

    def __init__(self, parent, row, spec, values, saver, on_change=None):
        self.name, label, self.lo, self.hi, self.step, self.fmt, help_ = spec
        self.saver, self.on_change = saver, on_change
        self.value = values[self.name]
        _label(parent, label, style="Bold.TLabel").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(parent, text="-", width=3, command=lambda: self.bump(-1)).grid(row=row, column=1, pady=4)
        self.l = _label(parent, "", style="Value.TLabel", width=9, anchor="center")
        self.l.grid(row=row, column=2, padx=4)
        ttk.Button(parent, text="+", width=3, command=lambda: self.bump(1)).grid(row=row, column=3, pady=4)
        _label(parent, help_, style="Dim.TLabel", wraplength=330).grid(row=row, column=4, sticky="w", padx=10)
        self.show()

    def show(self):
        self.l.configure(text=self.fmt % self.value)

    def bump(self, d):
        v = round(min(self.hi, max(self.lo, self.value + d * self.step)), 3)
        if isinstance(self.step, int):
            v = int(v)
        self.put(v)

    def put(self, v, save=True):
        if isinstance(self.value, float):
            v = float(v)
        self.value = v
        self.show()
        if save:
            self.saver.set(self.name, v)
        if self.on_change:
            self.on_change()


# ---- Speed ----------------------------------------------------------------------------------
class SpeedTab:
    title = "Speed"

    def __init__(self, f, host):
        self.host = host
        values, self.defaults = settings_now()
        self.saver = Saver(f, host.status)
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=(10, 4))
        _label(top, "Quick choice", style="Bold.TLabel").pack(side="left", padx=(0, 12))
        for name, vals in PRESETS:
            ttk.Button(top, text=name, command=lambda v=vals: self.preset(v)).pack(side="left", padx=4)
        self.l_preset = _label(top, "", style="Dim.TLabel")
        self.l_preset.pack(side="left", padx=12)

        grid = ttk.Frame(f)
        grid.pack(fill="x", padx=8, pady=4)
        self.steppers = {}
        for i, spec in enumerate(TIMINGS):
            self.steppers[spec[0]] = Stepper(grid, i, spec, values, self.saver, self.show_preset)

        pr = ttk.Frame(f)
        pr.pack(fill="x", padx=16, pady=(8, 4))
        _label(pr, "Practice here", style="Bold.TLabel").pack(side="left")
        self.practice = tk.Entry(pr, width=44, font=("Consolas", 16), bg=BG2, fg=FG,
                                 insertbackground=FG, relief="flat", highlightthickness=3,
                                 highlightbackground="#555", highlightcolor=ACCENT)
        self.practice.pack(side="left", padx=10)
        ttk.Button(pr, text="Clear", command=lambda: self.practice.delete(0, "end")).pack(side="left")
        _label(f, "Type here to feel a new speed - letters cut in two: make the pause longer; "
                  "waiting too long between letters: make it shorter.", style="Dim.TLabel",
               wraplength=900).pack(anchor="w", padx=16)

        ch = ttk.LabelFrame(f, text=" Typing ")
        ch.pack(fill="x", padx=8, pady=(12, 4))
        self.flags = {}
        for name, text in CHOICES:
            v = self.flags[name] = tk.BooleanVar(value=bool(values[name]))
            ttk.Checkbutton(ch, text=text, variable=v,
                            command=lambda n=name, v=v: self.saver.set(n, bool(v.get()), at_once=True)
                            ).pack(anchor="w", padx=8)
        row = ttk.Frame(ch)
        row.pack(anchor="w", padx=8, pady=(4, 6))
        _label(row, "Start in", style="Bold.TLabel").pack(side="left", padx=(0, 10))
        self.v_start = tk.IntVar(value=int(values["START_GROUP"]))
        for g, name in ((1, "Keyboard"), (2, "Mouse"), (3, "Macros")):
            ttk.Radiobutton(row, text=name, value=g, variable=self.v_start,
                            command=lambda: self.saver.set("START_GROUP", self.v_start.get(),
                                                           at_once=True)).pack(side="left", padx=4)
        _label(row, "  (the group SwitchMorse is in when it starts)", style="Dim.TLabel").pack(side="left")
        ttk.Button(f, text="Put the speed settings back to the defaults",
                   command=self.restore).pack(anchor="w", padx=8, pady=10)
        self.show_preset()

    def preset(self, vals):
        for name, v in vals.items():
            self.steppers[name].put(v)
        self.saver.flush()

    def restore(self):
        for name, st in self.steppers.items():
            st.put(self.defaults[name])
        self.saver.flush()

    def show_preset(self):
        now = {n: s.value for n, s in self.steppers.items()}
        hit = [name for name, vals in PRESETS
               if all(abs(now[k] - v) < 1e-9 for k, v in vals.items())]
        self.l_preset.configure(text="Now: %s" % (hit[0] if hit else "your own timing"))


# ---- Switches -------------------------------------------------------------------------------
class SwitchesTab:
    title = "Switches"

    def __init__(self, f, host):
        self.host, self.app = host, host.app
        values, _ = settings_now()
        self.saver = Saver(f, host.status)
        st = ttk.Frame(f)
        st.pack(fill="x", padx=12, pady=(12, 4))
        self.l_state = _label(st, "", style="Bold.TLabel")
        self.l_state.pack(side="left")
        lights = ttk.Frame(f)
        lights.pack(anchor="w", padx=12, pady=8)
        self.lights = {}
        for sw in ("dot", "dash"):
            lab = tk.Label(lights, text=" DOT " if sw == "dot" else " DASH ", font=BIG, width=7,
                           bg="#333", fg=DIM, relief="flat")
            lab.pack(side="left", padx=(0, 16))
            self.lights[sw] = lab
        self.l_test = _label(lights, "Press each switch: its box lights up.\nWhat you send is "
                                     "still carried out as usual.", style="Dim.TLabel")
        self.l_test.pack(side="left")
        if not self.app:
            self.l_test.configure(text="The test needs SwitchMorse running - open Settings from its window.")

        box = ttk.LabelFrame(f, text=" Which switches ")
        box.pack(fill="x", padx=8, pady=8)
        self.v_input = tk.StringVar(value=str(values["INPUT"]).lower())
        for key, text, help_ in INPUTS:
            row = ttk.Frame(box)
            row.pack(fill="x", padx=8, pady=2)
            ttk.Radiobutton(row, text=text, value=key, variable=self.v_input,
                            command=self.pick_input).pack(side="left")
            _label(row, "  " + help_, style="Dim.TLabel").pack(side="left")

        keys = ttk.LabelFrame(f, text=" Two keyboard keys (only for 'Two keyboard keys') ")
        keys.pack(fill="x", padx=8, pady=8)
        from settings_window import KEYS
        self.v_keys = {}
        for i, (name, text) in enumerate((("DOT_KEY", "Dot key"), ("DASH_KEY", "Dash key"))):
            _label(keys, text).grid(row=0, column=2 * i, padx=8, pady=6, sticky="w")
            v = self.v_keys[name] = tk.StringVar(value=str(values[name]))
            c = ttk.Combobox(keys, textvariable=v, values=KEYS, width=14, font=FONT)
            c.grid(row=0, column=2 * i + 1, padx=(0, 20), pady=6)
            c.bind("<<ComboboxSelected>>", lambda e, n=name: self.pick_key(n))
            c.bind("<Return>", lambda e, n=name: self.pick_key(n))

        adv = ttk.LabelFrame(f, text=" More ")
        adv.pack(fill="x", padx=8, pady=8)
        _label(adv, "Port").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.v_port = tk.StringVar(value="" if values["PORT"] in (None, "none") else str(values["PORT"]))
        e = tk.Entry(adv, textvariable=self.v_port, width=10, font=FONT, bg=BG2, fg=FG,
                     insertbackground=FG, relief="flat", highlightthickness=3,
                     highlightbackground="#555", highlightcolor=ACCENT)
        e.grid(row=0, column=1, sticky="w")
        e.bind("<Return>", lambda ev: self.pick_port())
        ttk.Button(adv, text="Use this port", command=self.pick_port).grid(row=0, column=2, padx=8)
        _label(adv, "empty = find it by itself (best); or e.g. COM19", style="Dim.TLabel").grid(
            row=0, column=3, sticky="w")
        b = ttk.Frame(adv)
        b.grid(row=1, column=0, columnspan=5, sticky="w")
        Stepper(b, 0, BOUNCE, values, self.saver)
        self.tick()

    def pick_input(self):
        self.saver.set("INPUT", self.v_input.get(), at_once=True)

    def pick_key(self, name):
        v = self.v_keys[name].get().strip()
        r = mapload._key_part(v) if v else None
        if not r or r[1] is None:
            self.host.status("%r is not a key name." % v, BAD)
            return
        self.saver.set(name, v, at_once=True)

    def pick_port(self):
        p = self.v_port.get().strip()
        if p and not re.fullmatch(r"(?i)COM\d{1,3}", p):
            self.host.status("A port looks like COM19 - or leave it empty.", BAD)
            return
        self.saver.set("PORT", p.upper() if p else None, at_once=True)

    def tick(self):
        """Which switches are in use now, every half second."""
        try:
            if not self.l_state.winfo_exists():
                return
        except tk.TclError:
            return
        a = self.app
        if a:
            if a.link_ok:
                self.l_state.configure(text="Now using: %s" % (a.reader.source or "?"), foreground=OK)
            else:
                self.l_state.configure(text=a.link, foreground=WARN)
        else:
            self.l_state.configure(text="SwitchMorse isn't running here.", foreground=DIM)
        self.l_state.after(500, self.tick)

    def switch_event(self, sw, pressed):
        lab = self.lights.get(sw)
        if lab:
            lab.configure(bg=OK if pressed else "#333", fg="black" if pressed else DIM)


# ---- Window & Sound ----------------------------------------------------------------------------
class WindowTab:
    title = "Window"

    def __init__(self, f, host):
        self.host, self.app = host, host.app
        import startup
        self.v_startup = tk.BooleanVar(value=startup.is_on())
        ttk.Checkbutton(f, text="Start SwitchMorse when I sign in to Windows",
                        variable=self.v_startup, command=self.pick_startup
                        ).pack(anchor="w", padx=16, pady=(12, 0))
        if not self.app:
            _label(f, "These change the SwitchMorse window - open Settings from it (right-click "
                      "it, Settings).", style="Dim.TLabel").pack(anchor="w", padx=12, pady=12)
            return
        w = self.win = self.app.win
        look = ttk.LabelFrame(f, text=" The SwitchMorse window ")
        look.pack(fill="x", padx=8, pady=(12, 8))
        for var, text, cmd in ((w.v_top, "Always on top", w.apply_look),
                               (w.v_bar, "Title bar (needed to resize it)", w.apply_look),
                               (w.v_hints, "Hints: what a half-sent code can still become", w.remember)):
            ttk.Checkbutton(look, text=text, variable=var, command=lambda c=cmd: (c(), self.done())
                            ).pack(anchor="w", padx=8)
        row = ttk.Frame(look)
        row.pack(anchor="w", padx=8, pady=6)
        _label(row, "See-through", style="Bold.TLabel").pack(side="left", padx=(0, 10))
        for pct in (100, 85, 70, 50, 35):
            ttk.Radiobutton(row, text="%d %%" % pct, value=pct, variable=w.v_alpha,
                            command=lambda: (w.apply_look(), self.done())).pack(side="left", padx=4)
        ttk.Button(look, text="Put the window back in the top-left corner, normal size",
                   command=self.reset_place).pack(anchor="w", padx=8, pady=8)

        snd = ttk.LabelFrame(f, text=" Sound ")
        snd.pack(fill="x", padx=8, pady=8)
        row = ttk.Frame(snd)
        row.pack(anchor="w", padx=8, pady=6)
        for name, text in (("off", "Off"), ("quiet", "Quiet"), ("medium", "Medium"), ("loud", "Loud")):
            ttk.Radiobutton(row, text=text, value=name, variable=w.v_sound,
                            command=lambda: (w.apply_sound(), self.done())).pack(side="left", padx=6)
        _label(snd, "A tone for each dot and dash, a blip for each action.", style="Dim.TLabel").pack(
            anchor="w", padx=8, pady=(0, 6))

    def done(self):
        self.host.status("Done - remembered for next time.", OK)

    def pick_startup(self):
        import startup
        want = self.v_startup.get()
        try:
            startup.on() if want else startup.off()
            self.host.status("SwitchMorse will start when you sign in." if want else
                             "SwitchMorse won't start by itself any more.", OK)
        except Exception as ex:
            self.v_startup.set(startup.is_on())
            self.host.status("Could not change it: %s" % ex, BAD)

    def reset_place(self):
        import window
        self.win.root.geometry(window.DEFAULT_GEOMETRY)
        self.win.remember()
        self.done()


# ---- Passwords -----------------------------------------------------------------------------------
class PasswordsTab:
    title = "Passwords"

    def __init__(self, f, host):
        self.host = host
        self.confirm = None
        self.secrets, self.error = {}, None
        _label(f, "What each 'secret NAME' code types. Stored encrypted for your Windows account, "
                  "never in the map. Values show as dots unless you tick Show.",
               style="Dim.TLabel", wraplength=900).pack(anchor="w", padx=12, pady=(12, 4))
        self.l_error = _label(f, "", style="Bold.TLabel", foreground=BAD, wraplength=900)
        self.l_error.pack(anchor="w", padx=12)
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        t = self.tree = ttk.Treeview(body, columns=("name", "set", "used"), show="headings",
                                     selectmode="browse", height=8)
        for col, text, w in (("name", "Name", 220), ("set", "Value", 120), ("used", "Used by", 300)):
            t.heading(col, text=text)
            t.column(col, width=w)
        t.tag_configure("unset", foreground=WARN)
        t.pack(side="left", fill="both", expand=True)
        t.bind("<<TreeviewSelect>>", lambda e: self.pick())
        right = ttk.Frame(body)
        right.pack(side="left", fill="y", padx=12)
        _label(right, "Name").pack(anchor="w")
        self.v_name = tk.StringVar()
        self.v_value = tk.StringVar()
        self.e_name = self._entry(right, self.v_name)
        _label(right, "Value (what it types)").pack(anchor="w", pady=(8, 0))
        self.e_value = self._entry(right, self.v_value, show="•")
        self.v_show = tk.BooleanVar()
        ttk.Checkbutton(right, text="Show", variable=self.v_show,
                        command=lambda: self.e_value.configure(show="" if self.v_show.get() else "•")
                        ).pack(anchor="w")
        bf = ttk.Frame(right)
        bf.pack(anchor="w", pady=8)
        ttk.Button(bf, text="Save", command=self.save).pack(side="left", padx=(0, 8))
        self.b_remove = ttk.Button(bf, text="Remove", command=self.remove)
        self.b_remove.pack(side="left")
        self.refresh()

    def refresh(self):
        """Read the saved passwords again (each time the tab is shown)."""
        try:
            self.secrets, self.error = secrets_store.load(), None
            text = "%d value%s saved, in %s" % (
                len(self.secrets), "" if len(self.secrets) == 1 else "s", secrets_store.PATH)
            if not self.secrets:                # (looking into a case that read none)
                p = secrets_store.PATH
                try:
                    raw = open(p, "rb").read()
                    text += "  [file %d bytes, opens to %d characters]" % (
                        len(raw), len(secrets_store._unprotect(raw)))
                except Exception as ex:
                    text += "  [%s: %s]" % (type(ex).__name__, ex)
            self.l_error.configure(text=text, foreground=DIM)
        except Exception as ex:
            self.secrets, self.error = {}, "%s: %s" % (type(ex).__name__, ex)
            self.l_error.configure(text="Could not read the saved passwords (%s) - they are "
                                        "NOT lost; don't save here until this is fixed." % self.error,
                                   foreground=BAD)
        self.fill()

    def _entry(self, parent, var, show=""):
        e = tk.Entry(parent, textvariable=var, width=26, font=FONT, bg=BG2, fg=FG, show=show,
                     insertbackground=FG, relief="flat", highlightthickness=3,
                     highlightbackground="#555", highlightcolor=ACCENT)
        e.pack(anchor="w")
        e.bind("<Return>", lambda ev: self.save())
        return e

    def used(self):
        out = {}
        try:
            for e in mapload.entries():
                a = e["action"]
                if not isinstance(a, str) and a.kind == "secret":
                    out.setdefault(a.text, []).append("%s %s" % (
                        mapload.SECTION_TITLES[e["group"]],
                        " ".join("●" if c == "." else "▬" for c in e["code"])))
        except Exception:
            pass
        return out

    def fill(self):
        used = self.used()
        t = self.tree
        keep = t.selection()
        t.delete(*t.get_children())
        for name in sorted(set(used) | set(self.secrets), key=str.lower):
            t.insert("", "end", iid=name, tags=() if name in self.secrets else ("unset",),
                     values=(name, "set" if name in self.secrets else "NOT SET",
                             ", ".join(used.get(name, [])) or "no code uses it"))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])

    def pick(self):
        sel = self.tree.selection()
        if sel:
            self.v_name.set(sel[0])
            self.v_value.set(self.secrets.get(sel[0], ""))
            self.reset_confirm()

    def reset_confirm(self):
        self.confirm = None
        self.b_remove.configure(text="Remove")

    def _write(self):
        try:
            secrets_store.save(self.secrets)
            return True
        except Exception as ex:
            self.host.status("NOT saved: %s" % ex, BAD)
            return False

    def save(self):
        if self.error:              # saving now would replace the file with only this one
            self.host.status("Not saved: the saved passwords could not be read.", BAD)
            return
        name, value = self.v_name.get().strip(), self.v_value.get()
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", name):
            self.host.status("A name is letters, numbers, _ - or . (no spaces), e.g. email_pw", BAD)
            return
        if not value:
            self.host.status("Type the value first (or Remove it).", BAD)
            return
        self.secrets[name] = value
        if self._write():
            self.fill()
            self.reset_confirm()
            extra = "" if name in self.used() else \
                " No code uses it yet: add one on the Macros tab (Does: Password)."
            self.host.status("Saved %s.%s" % (name, extra), OK)

    def remove(self):
        name = self.v_name.get().strip()
        if name not in self.secrets:
            self.host.status("%s has no value saved." % (name or "That"), WARN)
            return
        if self.confirm != name:
            self.confirm = name
            self.b_remove.configure(text="Yes, remove")
            self.host.status("Remove the value of %s? Press it again to remove." % name, WARN)
            return
        del self.secrets[name]
        if self._write():
            self.v_value.set("")
            self.fill()
            self.host.status("Removed %s." % name, OK)
        self.reset_confirm()


# ---- Cheat sheet --------------------------------------------------------------------------------
def _edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        p = os.path.join(base or "", "Microsoft", "Edge", "Application", "msedge.exe")
        if os.path.exists(p):
            return p
    return None


def _sheet_windows():
    """Handles of the visible windows showing a cheat sheet (title starts so)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    def each(h, _):
        if u.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(200)
            u.GetWindowTextW(h, buf, 200)
            if buf.value.startswith("SwitchMorse Cheat Sheet"):
                found.append(h)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each), 0)
    return found


class CheatTab:
    title = "Cheat sheet"

    def __init__(self, f, host):
        self.host = host
        _label(f, "A printable sheet of your codes, one page per group, made from your map as it "
                  "is now. Make it again after changing codes.", style="Dim.TLabel",
               wraplength=900).pack(anchor="w", padx=12, pady=(12, 8))
        for text, cmd in (("Make it and open it (Ctrl+P there to print)", self.make_open),
                          ("Make a PDF and open it", self.make_pdf),
                          ("Show the folder it is in", self.folder)):
            ttk.Button(f, text=text, command=cmd).pack(anchor="w", padx=12, pady=6)
        self.l_where = _label(f, "", style="Dim.TLabel")
        self.l_where.pack(anchor="w", padx=12, pady=8)

    def build(self):
        import importlib
        import sys
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        mk = importlib.import_module("make_cheatsheet")
        mk.build()
        self.l_where.configure(text=mk.OUT)
        return mk.OUT

    def show(self, path, what):
        """Open the sheet in a window of its own (Edge with no tabs), so closing
        it (Ctrl+W) lands back on Settings, not on some other browser tab."""
        edge = _edge()
        before = set(_sheet_windows())
        if edge:
            url = "file:///" + path.replace("\\", "/").replace(" ", "%20")
            subprocess.Popen([edge, "--app=" + url], creationflags=0x08000000)
        else:
            os.startfile(path)
        self.move_when_open(before, 60)
        back = ""
        for e in mapload.entries():
            if e["text"].strip().lower() == "settings":
                back = ", or send \x00%s\x00" % e["code"]
                break
        self.host.status("Opened %s. Ctrl+W closes it and comes back here%s." % (what, back), OK)

    def move_when_open(self, before, tries):
        """Edge puts a window where it likes (it ignores --window-position when
        it is already running), so wait for the sheet's window and move it."""
        new = [h for h in _sheet_windows() if h not in before]
        if new:
            import ctypes
            box = self.clear_of_switchmorse()
            if box:
                ctypes.windll.user32.ShowWindow(new[0], 9)          # un-maximize
                ctypes.windll.user32.MoveWindow(new[0], *box, True)
            self.back_when_closed(new[0])
        elif tries > 0:
            self.l_where.after(250, lambda: self.move_when_open(before, tries - 1))

    def back_when_closed(self, hwnd):
        """When the sheet's window closes, Settings comes back to the front."""
        import ctypes
        if ctypes.windll.user32.IsWindow(hwnd):
            self.l_where.after(300, lambda: self.back_when_closed(hwnd))
            return
        try:
            from settings_window import take_focus
            take_focus(self.host.root)
        except Exception:
            pass

    def clear_of_switchmorse(self):
        """(x, y, width, height) beside the SwitchMorse window (it stays on top,
        and would cover the print settings down the sheet's left side)."""
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            work, rect = wintypes.RECT(), wintypes.RECT()
            u.SystemParametersInfoW(48, 0, ctypes.byref(work), 0)
            r = self.host.app.win.root
            u.GetWindowRect(u.GetAncestor(r.winfo_id(), 2) or r.winfo_id(), ctypes.byref(rect))
            right, bottom, left = rect.right + 4, rect.bottom + 4, rect.left - 4
            if work.right - right >= 900 and work.right - right >= left - work.left:
                box = (right, work.top, work.right - right, work.bottom - work.top)
            elif left - work.left >= 900:            # it is on the right: go left of it
                box = (work.left, work.top, left - work.left, work.bottom - work.top)
            elif work.bottom - bottom >= 500:        # else below it
                box = (work.left, bottom, work.right - work.left, work.bottom - bottom)
            else:
                return None
            return box
        except Exception:
            return None                              # no SwitchMorse window (run on its own)

    def make_open(self):
        try:
            self.show(self.build(), "the cheat sheet")
        except Exception as ex:
            self.host.status("Could not make it: %s" % ex, BAD)

    def make_pdf(self):
        edge = _edge()
        if not edge:
            self.host.status("Making a PDF needs Microsoft Edge. Use 'Make it and open it', then "
                             "Ctrl+P and 'Save as PDF'.", WARN)
            return
        try:
            html = self.build()
        except Exception as ex:
            self.host.status("Could not make it: %s" % ex, BAD)
            return
        pdf = os.path.splitext(html)[0] + ".pdf"
        url = "file:///" + html.replace("\\", "/").replace(" ", "%20")
        self.host.status("Making the PDF...", DIM)
        result = []

        def run():          # Edge takes a few seconds: not on the program's own thread
            try:
                subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                                "--print-to-pdf=" + pdf, url], capture_output=True, timeout=60,
                               creationflags=0x08000000)
                result.append(None)
            except Exception as ex:
                result.append(ex)

        import threading
        threading.Thread(target=run, daemon=True).start()

        def done():
            if not result:
                self.l_where.after(200, done)
            elif result[0] is None and os.path.exists(pdf):
                self.show(pdf, os.path.basename(pdf))
            else:
                self.host.status("Could not make the PDF: %s" % (result[0] or "Edge made nothing"), BAD)
        done()

    def folder(self):
        try:
            path = self.build()
            subprocess.Popen(["explorer", "/select,", path])
        except Exception as ex:
            self.host.status("Could not open the folder: %s" % ex, BAD)


TAB_CLASSES = [SpeedTab, SwitchesTab, WindowTab, PasswordsTab, CheatTab]
