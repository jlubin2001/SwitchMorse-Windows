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
        where = ttk.Frame(look)
        where.pack(anchor="w", padx=8, pady=8)
        _label(where, "Move it, normal size:", style="Bold.TLabel").grid(
            row=0, column=0, rowspan=2, padx=(0, 12), sticky="w")
        for i, (corner, text) in enumerate((("top-left", "Top left"), ("top-right", "Top right"),
                                            ("bottom-left", "Bottom left"),
                                            ("bottom-right", "Bottom right"))):
            ttk.Button(where, text=text, width=13, command=lambda c=corner: self.corner(c)).grid(
                row=i // 2, column=1 + i % 2, padx=4, pady=3)

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

    def corner(self, corner):
        self.win.to_corner(corner)
        self.host.status("Moved to the %s corner - remembered for next time."
                         % corner.replace("-", " "), OK)


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

    def dirty(self):
        """A value typed in but not saved (Settings asks before leaving)."""
        value = self.v_value.get()
        return bool(value) and self.secrets.get(self.v_name.get().strip()) != value

    def discard(self):
        self.v_value.set("")
        self.pick()

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


# ---- Start here (the first-run guide) ---------------------------------------------------------
GUIDE_STEPS = ["Your switches", "Test them", "Pick a speed", "Try typing", "Try the mouse", "Done"]
ARROW = {"up": "↑", "down": "↓", "left": "←", "right": "→",
         "up-left": "↖", "up-right": "↗", "down-left": "↙", "down-right": "↘"}
KEYPAD = [["up-left", "up", "up-right"], ["left", None, "right"],
          ["down-left", "down", "down-right"]]
MOUSE_TASKS = [("left", 3), ("right", 1)]        # (button, how many targets)
TARGET = 70                                      # target size, pixels
PRACTICE_GOAL = 3               # letters typed before "well done"
PRACTICE_PAUSE_MS = 5000        # ... then this long without typing goes on


class GuideTab:
    """Five short steps for someone new: which switches, press each one, a
    speed, type a few letters, the codes to remember. It opens by itself the
    first time SwitchMorse starts (no map yet). Steps that wait for the
    switches go on by themselves, so no other way to press Next is needed."""
    title = "Start here"

    def __init__(self, f, host):
        self.host, self.app = host, host.app
        self.step = 0
        self.pressed = set()
        self.head = _label(f, "", style="Big.TLabel")
        self.head.pack(anchor="w", padx=16, pady=(14, 2))
        self.l_steps = _label(f, "", style="Dim.TLabel")
        self.l_steps.pack(anchor="w", padx=16)
        self.body = ttk.Frame(f)
        self.body.pack(fill="both", expand=True, padx=16, pady=10)
        nav = ttk.Frame(f)
        nav.pack(fill="x", padx=16, pady=(0, 10))
        self.b_back = ttk.Button(nav, text="Back", command=lambda: self.go(self.step - 1))
        self.b_next = ttk.Button(nav, text="Next", command=lambda: self.go(self.step + 1))
        self.b_back.pack(side="left")
        self.b_next.pack(side="left", padx=8)
        ttk.Button(nav, text="Skip the guide", command=self.finish).pack(side="right")
        f.after_idle(lambda: self.go(0))     # once the other tabs (Switches, Speed) exist

    def go(self, step):
        if step >= len(GUIDE_STEPS):
            self.finish()
            return
        self.step = max(0, step)
        self.host.status("", DIM)
        for w in self.body.winfo_children():
            w.destroy()
        self.head.configure(text=GUIDE_STEPS[self.step])
        self.l_steps.configure(text="Step %d of %d" % (self.step + 1, len(GUIDE_STEPS)))
        self.b_next.configure(text="Finish" if self.step == len(GUIDE_STEPS) - 1 else "Next")
        [self.s_switches, self.s_test, self.s_speed, self.s_practice, self.s_mouse,
         self.s_done][self.step](self.body)
        try:
            if self.host.nb.tab(self.host.nb.select(), "text").strip() == self.title:
                (getattr(self, "practice", None) if self.step == 3 else self.b_next).focus_set()
        except tk.TclError:
            pass

    def finish(self):
        self.go(0)
        self.host.show_tab("Keyboard")
        self.host.status("The guide is on the 'Start here' tab whenever you want it again.", DIM)

    def text(self, parent, words, **kw):
        return _label(parent, words, wraplength=860, justify="left", **kw)

    def code_for(self, group, text):
        """The code that does `text` in `group` of the user's map, or None."""
        for e in mapload.entries(self.host.map_path):
            if e["group"] == group and mapload._norm(e["text"]) == mapload._norm(text):
                return e["code"]
        return None

    def code_line(self, parent, code, words):
        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=3)
        if code:
            ttk.Label(row, image=self.host.code_image(code)).pack(side="left", padx=(0, 12))
        _label(row, words).pack(side="left")

    # -- the steps
    def s_switches(self, b):
        self.text(b, "SwitchMorse turns two switches into a whole keyboard and mouse: one switch "
                     "sends a dot, the other a dash (on an AeroMorse: sip = dot, puff = dash), and "
                     "each pattern of dots and dashes does one thing. What will you use?").pack(
            anchor="w", pady=(0, 10))
        sw = self.host.extra.get("Switches")
        for key, label, help_ in INPUTS:
            row = ttk.Frame(b)
            row.pack(anchor="w", pady=2)
            ttk.Radiobutton(row, text=label, value=key, variable=sw.v_input,
                            command=sw.pick_input).pack(side="left")
            _label(row, "  " + help_, style="Dim.TLabel").pack(side="left")
        self.l_using = _label(b, "", style="Bold.TLabel")
        self.l_using.pack(anchor="w", pady=(12, 0))
        self.tick_using()

    def tick_using(self):
        try:
            if self.step != 0 or not self.l_using.winfo_exists():
                return
        except tk.TclError:
            return
        a = self.app
        if a and a.link_ok:
            self.l_using.configure(text="Found: %s. %s" % (
                a.reader.source or "?",
                "Click Next." if a.actions.group == 2 else "Press either switch to go on."),
                foreground=OK)
        else:
            self.l_using.configure(text=(a.link if a else "SwitchMorse isn't running here."),
                                   foreground=WARN)
        self.l_using.after(500, self.tick_using)

    def s_test(self, b):
        self.pressed = set()
        self.text(b, "Press each switch once. Its box lights up and gets a tick. When both "
                     "have a tick, the guide goes on by itself.").pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(b)
        row.pack(anchor="w")
        self.lights = {}
        for sw in ("dot", "dash"):
            lab = tk.Label(row, text=" DOT " if sw == "dot" else " DASH ", font=BIG, width=8,
                           bg="#333", fg=DIM)
            lab.pack(side="left", padx=(0, 16))
            self.lights[sw] = lab
        if not self.app:
            self.text(b, "(The test needs SwitchMorse running.)", style="Dim.TLabel").pack(anchor="w")

    def switch_event(self, sw, pressed):
        """Steps 1 and 3 go on with a switch press, so someone new needs no Next
        button - but not in the Mouse group, where a press is a click (on Back,
        say). The last step waits for Finish, so it can be read."""
        try:
            if self.host.nb.tab(self.host.nb.select(), "text").strip() != self.title:
                return
        except tk.TclError:
            return
        if self.step in (0, 2):
            if not pressed and not (self.app and self.app.actions.group == 2):
                self.go(self.step + 1)
            return
        if self.step != 1:
            return
        lab = self.lights.get(sw)
        if not lab:
            return
        if pressed:
            self.pressed.add(sw)
        lab.configure(text=("✓ " if sw in self.pressed else " ") + sw.upper() + " ",
                      bg=OK if pressed else ("#2f5e34" if sw in self.pressed else "#333"),
                      fg="black" if pressed else (FG if sw in self.pressed else DIM))
        if not pressed and self.pressed == {"dot", "dash"}:
            self.host.status("Both switches work.", OK)
            lab.after(1200, lambda: self.step == 1 and self.go(2))

    def s_speed(self, b):
        self.text(b, "How long SwitchMorse waits after your last dot or dash before it takes "
                     "the letter. New to Morse? Start with Learning - you can change it any "
                     "time on the Speed tab. Or press a switch to keep the speed you have "
                     "(Learning, when new) - except in the Mouse group, where a press clicks."
                ).pack(anchor="w", pady=(0, 10))
        sp = self.host.extra.get("Speed")
        for name, vals in PRESETS:
            row = ttk.Frame(b)
            row.pack(anchor="w", pady=3)
            ttk.Button(row, text=name, width=12,
                       command=lambda n=name, v=vals: self.pick_speed(n, v, sp)).pack(side="left")
            _label(row, "   waits %.2f s; hold %.1f s to change group"
                   % (vals["ACCEPT_DELAY"], vals["LONG_PRESS"]), style="Dim.TLabel").pack(side="left")

    def pick_speed(self, name, vals, sp):
        if sp:
            sp.preset(vals)
        self.go(3)
        self.host.status("Speed: %s." % name, OK)

    def s_practice(self, b):
        top = ttk.Frame(b)
        top.pack(fill="x")
        self.text(top, "Type a few letters - your name, or e (one dot) and t (one dash). What "
                       "you send appears in the box.").pack(anchor="w")
        self.l_group = ttk.Frame(top)               # words and a code picture
        self.l_group.pack(anchor="w", pady=(4, 0))
        v = tk.StringVar()
        self.practice = tk.Entry(b, textvariable=v, width=30, font=("Consolas", 20), bg=BG2, fg=FG,
                                 insertbackground=FG, relief="flat", highlightthickness=3,
                                 highlightbackground="#555", highlightcolor=ACCENT)
        self.practice.pack(anchor="w", pady=8)
        v.trace_add("write", lambda *a: self.typed(v.get()))
        grid = ttk.Frame(b)
        grid.pack(anchor="w")
        letters = sorted((e["text"].strip(), e["code"]) for e in mapload.entries(self.host.map_path)
                         if e["group"] == 1 and re.fullmatch(r"[a-z]", e["text"].strip())
                         and not isinstance(e["action"], str))
        for i, (ch, code) in enumerate(letters):
            cell = ttk.Frame(grid)
            cell.grid(row=i % 7, column=i // 7, sticky="w", padx=(0, 22), pady=1)
            _label(cell, ch, style="Bold.TLabel", width=2).pack(side="left")
            ttk.Label(cell, image=self.host.code_image(code, small=True)).pack(side="left")
        self.tick_group()

    def typed(self, s):
        """Enough letters, then a few quiet seconds: on to the last step."""
        if getattr(self, "_next_job", None):
            self.practice.after_cancel(self._next_job)
            self._next_job = None
        if len(s.strip()) >= PRACTICE_GOAL:
            self.host.status("Well done - that's typing in Morse! Type more, or stop for a "
                             "moment to go on.", OK)
            self._next_job = self.practice.after(PRACTICE_PAUSE_MS,
                                                 lambda: self.step == 3 and self.go(4))

    def tick_group(self):
        try:
            if self.step != 3 or not self.l_group.winfo_exists():
                return
        except tk.TclError:
            return
        a = self.app
        if a and a.actions.group != 1:
            code = self.code_for(0, "group Keyboard")
            self.host.rich(self.l_group, "You are in the %s group: first send %s to go to "
                           "Keyboard." % ({2: "Mouse", 3: "Macros"}.get(a.actions.group, "Base"),
                                          "\x00%s\x00" % code if code else "the Keyboard code"),
                           WARN, BOLD)
        else:
            for w in self.l_group.winfo_children():
                w.destroy()
        self.l_group.after(500, self.tick_group)

    def s_mouse(self, b):
        """The move codes laid out like a number keypad (from the user's own
        map), and targets to reach and click: left-click, then right-click."""
        top = ttk.Frame(b)
        top.pack(fill="x")
        self.l_mgroup = ttk.Frame(top)                # go to Mouse / back to Keyboard
        self.l_mgroup.pack(anchor="w")
        row = ttk.Frame(b)
        row.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(row)
        left.pack(side="left", anchor="n")
        moves, codes = {}, {}
        for e in mapload.entries(self.host.map_path):
            if e["group"] != 2 or isinstance(e["action"], str):
                continue
            t = e["text"].strip().lower()
            m = re.fullmatch(r"move (\S+)", t)
            if m and m.group(1) in ARROW:
                moves.setdefault(m.group(1), []).append(e["code"])
            elif t in ("click left", "click right", "repeat") and t not in codes:
                codes[t] = e["code"]
        pad = ttk.Frame(left)
        pad.pack(anchor="w")
        for r, line in enumerate(KEYPAD):
            for c, d in enumerate(line):
                cell = tk.Frame(pad, bg=BG2, width=150, height=84, highlightthickness=1,
                                highlightbackground="#555")
                cell.grid(row=r, column=c, padx=3, pady=3)
                cell.pack_propagate(False)
                if d is None:
                    tk.Label(cell, text="repeat", bg=BG2, fg=DIM, font=FONT).pack(pady=(10, 2))
                    if "repeat" in codes:
                        tk.Label(cell, image=self.host.code_image(codes["repeat"], small=True),
                                 bg=BG2).pack()
                    continue
                tk.Label(cell, text=ARROW[d], bg=BG2, fg="#00e5ff", font=("Segoe UI Symbol", 20)
                         ).pack()
                for code in sorted(moves.get(d, []), key=len)[:2]:      # short step, big step
                    tk.Label(cell, image=self.host.code_image(code, small=True), bg=BG2).pack()
        for name, words in (("click left", "Left click"), ("click right", "Right click")):
            line = ttk.Frame(left)
            line.pack(anchor="w", pady=(6, 0))
            _label(line, words, style="Bold.TLabel", width=11).pack(side="left")
            if name in codes:
                ttk.Label(line, image=self.host.code_image(codes[name])).pack(side="left")
        _label(left, "Short code = a small step, long code = a big one.\n'repeat' keeps the "
                     "last move going until\nyour next press.", style="Dim.TLabel").pack(
            anchor="w", pady=(8, 0))

        right = ttk.Frame(row)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))
        self.l_task = _label(right, "", style="Bold.TLabel", wraplength=480)
        self.l_task.pack(anchor="w")
        self.canvas = tk.Canvas(right, bg="#111", highlightthickness=1, highlightbackground="#555",
                                width=480, height=380)
        self.canvas.pack(fill="both", expand=True, pady=(6, 0))
        self.tasks = [btn for btn, n in MOUSE_TASKS for _ in range(n)]
        self.done_tasks = 0
        self.canvas.after(50, self.new_target)
        self.tick_mgroup()

    def new_target(self, last=None):
        """The next target, somewhere well away from the last one."""
        import random
        cv = self.canvas
        try:
            cv.delete("all")
            w, h = max(cv.winfo_width(), 300), max(cv.winfo_height(), 250)
        except tk.TclError:
            return
        if self.done_tasks >= len(self.tasks):
            cv.create_text(w // 2, h // 2, text="Well done!", fill=OK, font=BIG)
            self.l_task.configure(text="That's the mouse. Click Next.", foreground=OK)
            return
        btn = self.tasks[self.done_tasks]
        for _ in range(50):
            x = random.randint(10, w - TARGET - 10)
            y = random.randint(10, h - TARGET - 10)
            if not last or abs(x - last[0]) + abs(y - last[1]) > 180:
                break
        if btn == "left":
            item = cv.create_oval(x, y, x + TARGET, y + TARGET, fill="#3ddc84", outline="")
            word = "Left-click the green circle"
        else:
            item = cv.create_rectangle(x, y, x + TARGET, y + TARGET, fill="#ffb84d", outline="")
            word = "Right-click the orange square"
        self.l_task.configure(text="%s  (%d of %d)" % (word, self.done_tasks + 1, len(self.tasks)),
                              foreground=FG)
        hit = lambda e, b=btn: self.target_hit(b, (x, y))
        cv.tag_bind(item, "<Button-1>" if btn == "left" else "<Button-3>", hit)
        miss = "<Button-3>" if btn == "left" else "<Button-1>"
        cv.tag_bind(item, miss, lambda e: self.host.status(
            "That was a %s click - this one wants a %s click." % (
                "right" if btn == "left" else "left", btn), WARN))

    def target_hit(self, btn, where):
        self.done_tasks += 1
        self.host.status("Got it!", OK)
        self.new_target(where)

    def tick_mgroup(self):
        try:
            if self.step != 4 or not self.l_mgroup.winfo_exists():
                return
        except tk.TclError:
            return
        a = self.app
        for w in self.l_mgroup.winfo_children():
            w.destroy()
        finished = self.done_tasks >= len(self.tasks)
        if a and not finished and a.actions.group != 2:
            code = self.code_for(0, "group Mouse")
            self.host.rich(self.l_mgroup, "First send %s to go to the Mouse group." % (
                "\x00%s\x00" % code if code else "the Mouse code"), WARN, BOLD)
        elif a and finished and a.actions.group != 1:
            code = self.code_for(0, "group Keyboard")
            self.host.rich(self.l_mgroup, "Send %s to go back to the Keyboard group." % (
                "\x00%s\x00" % code if code else "the Keyboard code"), OK, BOLD)
        self.l_mgroup.after(500, self.tick_mgroup)

    def s_done(self, b):
        self.text(b, "You're ready. These work in every group - worth remembering:").pack(
            anchor="w", pady=(0, 8))
        for text, words in (("group Keyboard", "Keyboard: letters, numbers, keys"),
                            ("group Mouse", "Mouse: move, click, scroll"),
                            ("group Macros", "Macros: phrases and passwords"),
                            ("settings", "this Settings window"),
                            ("show window", "bring the SwitchMorse window to the front")):
            self.code_line(b, self.code_for(0, text), words)
        self.text(b, "Holding a switch for the long-press time and letting go also moves to the "
                     "next group. The Cheat sheet tab prints every code; the Keyboard, Mouse "
                     "and Macros tabs let you change them. Press Finish to start.",
                  style="Dim.TLabel").pack(
            anchor="w", pady=(10, 0))


# ---- Practice ---------------------------------------------------------------------------------------
PRACTICE_FILE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SwitchMorse",
                             "practice.json")
WORDS = ("the and you that was for are with his they this have from one had word but not what "
         "all were when your can said there use each which she how their will other about out "
         "many then them these some her would make like him into time has look two more write "
         "see number way could people than first water been call who its now find long down day "
         "did get come made may part over new sound take only little work know place year live "
         "back give most very after thing our just name good sentence man think say great where "
         "help through much before line right too mean old any same tell boy follow came want "
         "show also around form three small set put end does another well large must big even "
         "such because turn here why ask went men read need land different home us move try "
         "kind hand picture again change off play spell air away animal house point page letter "
         "mother answer found study still learn should world high").split()
SENTENCES = ["the quick brown fox jumps over the lazy dog",
             "pack my box with five dozen liquor jugs",
             "how vexingly quick daft zebras jump",
             "sphinx of black quartz judge my vow",
             "the five boxing wizards jump quickly",
             "please call me when you get home",
             "can you turn the lights off please",
             "i would like a cup of tea",
             "see you tomorrow morning",
             "thank you for your help today"]
PRACTICE_SETS = [("short", "Short codes"), ("letters", "Letters"),
                 ("numbers", "+ numbers"), ("words", "Words"),
                 ("sentences", "Sentences"), ("trouble", "My trouble letters")]
LINE_GROUPS = 4                 # groups of 5 random letters on a line
NEXT_LINE_MS = 2500             # a finished line: this long, then a new one


class PracticeTab:
    """Copy a line: random letters, words or sentences. Each letter turns
    green or red as it is typed (by Morse, into the box), the next letter's
    code is shown, and the speed, accuracy and most-missed letters are kept.
    Everything works with the switches alone: a finished line is followed by
    a new one by itself."""
    title = "Practice"

    def __init__(self, f, host):
        self.host, self.app = host, host.app
        self.stats = self._load()
        self.line, self.started, self.typed_n, self.right_n = "", None, 0, 0
        self.prev = ""
        self.line_job = None

        top = ttk.Frame(f)
        top.pack(fill="x", padx=12, pady=(12, 4))
        _label(top, "Practise", style="Bold.TLabel").pack(side="left", padx=(0, 10))
        self.v_set = tk.StringVar(value=self.stats.get("set", "short"))
        for key, text in PRACTICE_SETS:
            ttk.Radiobutton(top, text=text, value=key, variable=self.v_set,
                            command=self.new_line).pack(side="left", padx=4)
        opt = ttk.Frame(f)
        opt.pack(fill="x", padx=12)
        self.v_hint = tk.BooleanVar(value=self.stats.get("hint", True))
        ttk.Checkbutton(opt, text="Show the code for the next letter", variable=self.v_hint,
                        command=self.show).pack(side="left")
        self.l_group = ttk.Frame(opt)                   # "send ... to go to Keyboard"
        self.l_group.pack(side="left", padx=16)

        self.target = tk.Text(f, height=2, font=("Consolas", 26), bg=BG, fg=DIM, relief="flat",
                              wrap="word", highlightthickness=0, cursor="arrow", takefocus=0)
        self.target.pack(fill="x", padx=12, pady=(14, 2))
        self.target.tag_configure("right", foreground=OK)
        self.target.tag_configure("wrong", foreground="black", background=BAD)
        self.target.tag_configure("next", foreground=FG, underline=True)
        self.v_typed = tk.StringVar()
        self.box = tk.Entry(f, textvariable=self.v_typed, font=("Consolas", 26), bg=BG2, fg=FG,
                            insertbackground=FG, relief="flat", highlightthickness=3,
                            highlightbackground="#555", highlightcolor=ACCENT)
        self.box.pack(fill="x", padx=12, pady=4)
        self.v_typed.trace_add("write", lambda *a: self.typed())
        self.box.bind("<Return>", lambda e: self.new_line())      # Enter: skip to a new line
        self.f_next = ttk.Frame(f)                      # "Next: s  ..."
        self.f_next.pack(anchor="w", padx=12, pady=(6, 0))

        st = ttk.LabelFrame(f, text=" How it's going ")
        st.pack(fill="x", padx=12, pady=10)
        self.l_now = _label(st, "", style="Value.TLabel")
        self.l_now.pack(anchor="w", padx=8, pady=(6, 2))
        self.l_best = _label(st, "", style="Dim.TLabel")
        self.l_best.pack(anchor="w", padx=8)
        self.f_missed = ttk.Frame(st)
        self.f_missed.pack(anchor="w", padx=8, pady=(2, 8))

        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Button(bar, text="New line", command=self.new_line).pack(side="left")
        self.f_enter = ttk.Frame(bar)                   # "or send <Enter's code> for a new line"
        self.f_enter.pack(side="left", padx=12)
        ttk.Button(bar, text="Forget my trouble letters", command=self.forget).pack(side="right")
        f.after_idle(self.new_line)

    # -- the codes, from the user's own Keyboard group
    def codes(self):
        out = {}
        for e in mapload.entries(self.host.map_path):
            a = e["action"]
            if e["group"] != 1 or isinstance(a, str):
                continue
            if a.kind == "char" and a.text not in out:
                out[a.text] = e["code"]
            elif a.kind == "key" and a.label.lower() == "space" and " " not in out:
                out[" "] = e["code"]
        return out

    def make_line(self, which, codes):
        import random
        letters = [c for c in codes if "a" <= c <= "z"]
        if which == "short":
            pool = [c for c in letters if len(codes[c]) <= 3]
        elif which == "numbers":
            pool = letters + [c for c in codes if c.isdigit()]
        elif which == "trouble":                        # mostly those, with others mixed in
            worst = [c for c, n in sorted(self.stats.get("missed", {}).items(),
                                          key=lambda kv: -kv[1])[:8] if c in codes and c != " "]
            pool = worst * 4 + letters if worst else []
        else:
            pool = letters
        if which == "words":
            return " ".join(random.sample(WORDS, 6))
        if which == "sentences":
            return random.choice(SENTENCES)
        if not pool:
            return ""
        return " ".join("".join(random.choice(pool) for _ in range(5)) for _ in range(LINE_GROUPS))

    def new_line(self):
        if self.line_job:
            self.box.after_cancel(self.line_job)
            self.line_job = None
        which = self.v_set.get()
        self.stats["set"] = which
        self.line = self.make_line(which, self.codes())
        if not self.line:
            self.line = ""
            self.host.status("No trouble letters yet - they're collected as you practise.", DIM)
        self.started, self.typed_n, self.right_n, self.prev = None, 0, 0, ""
        self.v_typed.set("")
        self.show()
        self.show_enter()
        self.focus()

    def show_enter(self):
        """Under the line: the user's own code for Enter, which skips to a new line."""
        code = None
        for g in (1, 0):
            for e in mapload.entries(self.host.map_path):
                a = e["action"]
                if (e["group"] == g and not isinstance(a, str) and a.kind == "key"
                        and a.label.lower() == "enter"):
                    code = e["code"]
                    break
            if code:
                break
        self.host.rich(self.f_enter, "or send %s (Enter) for a new line" % (
            "\x00%s\x00" % code if code else "Enter"), DIM, FONT)

    def focus(self):
        try:
            if self.host.nb.tab(self.host.nb.select(), "text").strip() == self.title:
                self.box.focus_set()
        except tk.TclError:
            pass

    def on_show(self):
        self.focus()
        self.tick_group()

    # -- typing
    def typed(self):
        import time
        s = self.v_typed.get().lower()
        if len(s) > len(self.prev):                     # new letters (not a backspace)
            if self.started is None:
                self.started = time.monotonic()
            for i in range(len(self.prev), len(s)):
                want = self.line[i] if i < len(self.line) else None
                self.typed_n += 1
                if s[i] == want:
                    self.right_n += 1
                elif want is not None:
                    missed = self.stats.setdefault("missed", {})
                    missed[want] = missed.get(want, 0) + 1
        self.prev = s
        self.show()
        if self.line and s == self.line:
            self.finished()

    def finished(self):
        import time
        mins = max(time.monotonic() - (self.started or time.monotonic()), 1) / 60.0
        wpm = len(self.line) / 5.0 / mins
        acc = 100.0 * self.right_n / max(self.typed_n, 1)
        if wpm > self.stats.get("best_wpm", 0):
            self.stats["best_wpm"] = round(wpm, 1)
            note = " - your best yet!"
        else:
            note = "."
        self.stats["lines"] = self.stats.get("lines", 0) + 1
        self._save()
        self.show()
        self.host.status("Line done: %.1f words a minute, %d%% right%s A new line comes next."
                         % (wpm, acc, note), OK)
        self.line_job = self.box.after(NEXT_LINE_MS, self.new_line)

    # -- what's shown
    def show(self):
        t = self.target
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", self.line)
        s = self.v_typed.get().lower()
        for i, ch in enumerate(s[:len(self.line)]):
            t.tag_add("right" if ch == self.line[i] else "wrong", "1.0+%dc" % i, "1.0+%dc" % (i + 1))
        n = len(s)
        if n < len(self.line):
            t.tag_add("next", "1.0+%dc" % n, "1.0+%dc" % (n + 1))
        t.configure(state="disabled")

        for w in self.f_next.winfo_children():
            w.destroy()
        if n < len(self.line) and self.v_hint.get():
            ch = self.line[n]
            code = self.codes().get(ch)
            _label(self.f_next, "Next:", style="Dim.TLabel").pack(side="left")
            _label(self.f_next, "space" if ch == " " else ch, style="Bold.TLabel").pack(
                side="left", padx=(8, 10))
            if code:
                ttk.Label(self.f_next, image=self.host.code_image(code)).pack(side="left")
        elif n > len(self.line):
            _label(self.f_next, "That's more than the line - Backspace takes letters off.",
                   style="Dim.TLabel").pack(side="left")
        self.stats["hint"] = bool(self.v_hint.get())

        import time
        if self.started and self.typed_n:
            mins = max(time.monotonic() - self.started, 1) / 60.0
            self.l_now.configure(text="%.1f words a minute    %d of %d right (%d%%)" % (
                self.right_n / 5.0 / mins, self.right_n, self.typed_n,
                100 * self.right_n // self.typed_n))
        else:
            self.l_now.configure(text="Copy the line above.")
        self.l_best.configure(text="Your best: %.1f words a minute    Lines done: %d" % (
            self.stats.get("best_wpm", 0), self.stats.get("lines", 0)))
        self.show_missed()

    def show_missed(self):
        for w in self.f_missed.winfo_children():
            w.destroy()
        missed = sorted(((c, n) for c, n in self.stats.get("missed", {}).items() if c != " "),
                        key=lambda kv: -kv[1])[:6]
        if not missed:
            return
        _label(self.f_missed, "Most missed:", style="Dim.TLabel").pack(side="left", padx=(0, 8))
        codes = self.codes()
        for c, n in missed:
            _label(self.f_missed, "%s ×%d" % (c, n), style="Bold.TLabel").pack(side="left")
            if c in codes:
                ttk.Label(self.f_missed, image=self.host.code_image(codes[c], small=True)).pack(
                    side="left", padx=(4, 16))

    def tick_group(self):
        """Typing needs the Keyboard group: say how to get there when not in it."""
        try:
            if not self.l_group.winfo_exists():
                return
            if self.host.nb.tab(self.host.nb.select(), "text").strip() != self.title:
                return
        except tk.TclError:
            return
        for w in self.l_group.winfo_children():
            w.destroy()
        a = self.app
        if a and a.actions.group != 1:
            code = None
            for e in mapload.entries(self.host.map_path):
                if e["group"] == 0 and mapload._norm(e["text"]) == "groupkeyboard":
                    code = e["code"]
                    break
            self.host.rich(self.l_group, "Send %s to go to the Keyboard group first." % (
                "\x00%s\x00" % code if code else "the Keyboard code"), WARN, BOLD)
        self.l_group.after(500, self.tick_group)

    def forget(self):
        self.stats["missed"] = {}
        self._save()
        self.show()
        self.host.status("Trouble letters forgotten.", DIM)

    # -- kept between runs (only counts: no typed text is stored)
    def _load(self):
        try:
            import json
            with open(PRACTICE_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            import json
            os.makedirs(os.path.dirname(PRACTICE_FILE), exist_ok=True)
            with open(PRACTICE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self.stats, fh, indent=1, sort_keys=True)
        except OSError:
            pass


TAB_CLASSES = [GuideTab, PracticeTab, SpeedTab, SwitchesTab, WindowTab, PasswordsTab, CheatTab]
