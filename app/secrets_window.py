# SwitchMorse Windows - the Passwords window.
# Set, change or remove the private text that "secret NAME" codes in
# morse_map.txt type (passwords, phone numbers, addresses...). Opened from the
# SwitchMorse window's right-click menu, or:
#
#   pythonw app\secrets_window.py
#
# Values are stored encrypted for this Windows account (secrets_store.py) and
# are shown as dots unless "Show" is ticked. Every change is saved at once;
# SwitchMorse picks it up straight away, no restart needed.
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import appicon          # noqa: E402
import mapload          # noqa: E402
import secrets_store    # noqa: E402

BG, FG, DIM, OK, WARN = "#1e1e1e", "#f0f0f0", "#9a9a9a", "#5fd068", "#ff8a65"

try:    # same screen coordinates as the SwitchMorse window (it is DPI-aware too)
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def place_clear_of(root, avoid):
    """Put the window where it doesn't overlap `avoid` (x, y, w, h - the
    SwitchMorse window, which is always on top): below it, above it, to its
    right or left, whichever fits on the screen; else the screen's centre."""
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    gap = 16
    if avoid:
        ax, ay, aw, ah = avoid
        for x, y in ((ax, ay + ah + gap + 30), (ax, ay - h - gap - 40),
                     (ax + aw + gap, ay), (ax - w - gap, ay)):
            x = min(max(0, x), sw - w)
            if 0 <= y and y + h <= sh - 40:
                overlaps = not (x + w <= ax or ax + aw <= x or y + h <= ay or ay + ah <= y)
                if not overlaps:
                    root.geometry("+%d+%d" % (x, y))
                    return
    root.geometry("+%d+%d" % (max(0, (sw - w) // 2), max(0, (sh - h) // 3)))


class PasswordsWindow:
    def __init__(self, avoid=None):
        appicon.set_app_id()
        self.root = tk.Tk()
        self.root.title("SwitchMorse Passwords")
        appicon.set_icon(self.root)
        self.root.configure(bg=BG)
        f = ("Segoe UI", 14)
        self.secrets = {}
        self.error = None
        try:
            self.secrets = secrets_store.load()
        except Exception as ex:
            self.error = str(ex)
        self.used = self._names_in_map()

        left = tk.Frame(self.root, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        tk.Label(left, text="Secrets", font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
                 anchor="w").pack(fill="x")
        self.listbox = tk.Listbox(left, font=f, width=34, height=14, bg="#2a2a2a", fg=FG,
                                  selectbackground="#3d6fb5", activestyle="none")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.pick)

        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="y", padx=12, pady=12)
        tk.Label(right, text="Name", font=f, bg=BG, fg=DIM, anchor="w").pack(fill="x")
        self.name = tk.Entry(right, font=f, width=24)
        self.name.pack(fill="x", pady=(0, 10))
        tk.Label(right, text="Value (what it types)", font=f, bg=BG, fg=DIM,
                 anchor="w").pack(fill="x")
        self.value = tk.Entry(right, font=f, width=24, show="•")
        self.value.pack(fill="x")
        self.show = tk.BooleanVar(value=False)
        tk.Checkbutton(right, text="Show", variable=self.show, font=f, bg=BG, fg=FG,
                       selectcolor=BG, activebackground=BG, activeforeground=FG,
                       command=lambda: self.value.config(show="" if self.show.get() else "•")
                       ).pack(anchor="w", pady=(0, 10))
        for text, cmd in (("Save", self.save), ("Remove", self.remove), ("Close", self.root.destroy)):
            tk.Button(right, text=text, font=f, width=12, command=cmd).pack(pady=4)
        self.status = tk.Label(self.root, font=("Segoe UI", 12), bg=BG, fg=DIM, anchor="w",
                               wraplength=640, justify="left")
        self.status.pack(side="bottom", fill="x", padx=12, pady=(0, 10))
        self.fill()
        # In front of everything (the SwitchMorse window is always on top) and
        # ready to type into.
        place_clear_of(self.root, avoid)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(150, self.root.focus_force)
        self.root.after(200, self.name.focus_set)
        if self.error:
            self.say("Could not open the saved secrets: %s. Saving now would start a "
                     "new, empty file." % self.error, WARN)

    @staticmethod
    def _names_in_map():
        """{name: "code (group)"} for every secret code in morse_map.txt."""
        out = {}
        try:
            codes, _ = mapload.load()
        except Exception:
            return out
        for (g, n, p), a in sorted(codes.items()):
            if a.kind == "secret":
                out.setdefault(a.text, "%s %s" % (mapload.SECTION_TITLES[g], mapload.code_str(n, p)))
        return out

    def fill(self):
        self.rows = sorted(set(self.used) | set(self.secrets), key=str.lower)
        self.listbox.delete(0, "end")
        for name in self.rows:
            mark = "set" if name in self.secrets else "NOT SET"
            where = self.used.get(name, "not in the map")
            self.listbox.insert("end", "%-16s %-8s %s" % (name, mark, where))
            self.listbox.itemconfig("end", fg=OK if name in self.secrets else WARN)
        if not self.rows:
            self.say("No secrets yet. Type a name and a value, then Save.")

    def pick(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.rows[sel[0]]
        self.name.delete(0, "end")
        self.name.insert(0, name)
        self.value.delete(0, "end")
        self.value.insert(0, self.secrets.get(name, ""))
        self.value.focus_set()

    def say(self, text, colour=DIM):
        self.status.config(text=text, fg=colour)

    def _write(self):
        try:
            secrets_store.save(self.secrets)
            self.error = None
            return True
        except Exception as ex:
            self.say("NOT saved: %s" % ex, WARN)
            return False

    def save(self):
        name = self.name.get().strip()
        value = self.value.get()
        if not mapload.re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", name):
            self.say("A name is letters, numbers, _ - or . (no spaces), e.g. email_pw", WARN)
            return
        if not value:
            self.say("Type the value first (or use Remove to delete it).", WARN)
            return
        self.secrets[name] = value
        if self._write():
            self.fill()
            extra = "" if name in self.used else " (no code uses it yet - add 'secret %s' to the map)" % name
            self.say("Saved %s.%s" % (name, extra), OK)

    def remove(self):
        name = self.name.get().strip()
        if name not in self.secrets:
            self.say("%s has no value saved." % (name or "That"), WARN)
            return
        del self.secrets[name]
        if self._write():
            self.value.delete(0, "end")
            self.fill()
            self.say("Removed %s." % name, OK)


def _avoid_arg():
    """--avoid x,y,w,h from the SwitchMorse window, or None."""
    if "--avoid" in sys.argv:
        try:
            return tuple(int(v) for v in sys.argv[sys.argv.index("--avoid") + 1].split(","))
        except (IndexError, ValueError):
            pass
    return None


if __name__ == "__main__":
    PasswordsWindow(_avoid_arg()).root.mainloop()
