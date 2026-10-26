# SwitchMorse Windows - the Settings window: the codes of each group.
# One tab per group (Base, Keyboard, Mouse, Macros) listing every code and what
# it does. Add, change or delete a code; the code can be typed as dots and
# dashes or RECORDED from the switches (the next code you send goes into the
# box instead of being typed). What a code does is picked from lists - no map
# syntax to learn - and clashes are shown before anything is saved.
#
# Opened from the SwitchMorse window's right-click menu (Settings...), with a
# "settings" code, or on its own (no recording then):
#
#   pythonw app\settings_window.py
#
# Made to be used with SwitchMorse itself: every control is reached with Tab /
# Shift+Tab, Enter or Space works it, Ctrl+Tab changes tab, nothing needs a
# drag, a double-click or a right-click, and there are no pop-up dialogs (a
# question is asked by the button itself: "Yes, delete"). Each change is saved
# to morse_map.txt at once (only that line changes; a backup is kept) and the
# running SwitchMorse uses it within a second. Undo takes changes back.
import ctypes
import os
import re
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import appicon          # noqa: E402
import filesave         # noqa: E402
import mapload          # noqa: E402

BG, BG2, FG, DIM, OK, WARN, BAD, ACCENT = ("#1e1e1e", "#2a2a2a", "#f0f0f0", "#9a9a9a",
                                           "#5fd068", "#ffb84d", "#ff6b6b", "#3a7bd5")
FONT = ("Segoe UI", 13)
BOLD = ("Segoe UI", 13, "bold")
CODE_FONT = ("Consolas", 16, "bold")
DOT_COLOUR, DASH_COLOUR = "#b388ff", "#3ddc84"      # as on the AeroMorse cheat sheet
ARROWS = {(0, -1): "↑", (0, 1): "↓", (-1, 0): "←", (1, 0): "→",
          (-1, -1): "↖", (1, -1): "↗", (-1, 1): "↙", (1, 1): "↘"}

# Keyboard: AeroMorse moves two letters so the short codes go to keys used
# all the time. (code, AeroMorse action, note, standard action, note)
AEROMORSE_FOUR = [
    ("--", "Backspace", "(freed from M)", "m", None),
    ("----", "m", "(non-standard; -- freed for BACKSPACE)", "Backspace",
     "(AeroMorse uses -- for Backspace)"),
    ("-.-.", "Ctrl", "(freed from C)", "c", None),
    ("---.", "c", "(non-standard; -.-. freed for LEFT_CONTROL)", "Ctrl",
     "(AeroMorse uses -.-. for Ctrl)"),
]
TABS = [(1, "Keyboard"), (2, "Mouse"), (3, "Macros"), (0, "Base")]   # the code tabs

# ---- what a code can do: the lists to pick from ----------------------------------
KINDS = ["Letter or character", "Key or key combination", "Sticky key (Ctrl, Shift...)",
         "Phrase (text to type)", "Password (secret)", "Mouse", "Media or app key",
         "Command", "Go to another group", "Other (as written in the map)"]
MODS = ["Ctrl", "Shift", "Alt", "Win"]
STICKY = ["Ctrl", "Shift", "Alt", "Win", "RCtrl", "RShift", "RAlt", "RWin"]
MOUSE = ["move up", "move down", "move left", "move right", "move up-left", "move up-right",
         "move down-left", "move down-right", "scroll up", "scroll down", "click left",
         "click right", "click middle", "double click left", "double click right",
         "double click middle", "drag left", "drag right", "mouse slow", "mouse fast",
         "centre pointer"]
COMMANDS = ["repeat", "pause", "release all", "show window", "settings"]
MEDIA = ["Play Pause", "Mute", "Volume Up", "Volume Down", "Next Track", "Previous Track",
         "Stop Media", "Calculator", "File Explorer", "Web Browser", "Mail"]
GROUPS = ["Keyboard", "Mouse", "Macros"]
_KEYS = (["Enter", "Tab", "Esc", "Backspace", "Delete", "Insert", "Space", "Home", "End",
          "Page Up", "Page Down", "Up", "Down", "Left", "Right"]
         + ["F%d" % i for i in range(1, 13)]
         + ["Print Screen", "Menu", "Caps Lock", "Num Lock", "Scroll Lock", "Pause Key"]
         + list("abcdefghijklmnopqrstuvwxyz0123456789")
         + ["Keypad %d" % i for i in range(10)] + ["Keypad Enter", "Keypad Plus", "Keypad Minus"])
KEYS = [k for k in _KEYS if mapload._key_part(k) and mapload._key_part(k)[1] is not None]

try:    # same screen coordinates as the SwitchMorse window (it is DPI-aware too)
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


MARK = "\x00"
HIGH = "\x01"          # text between two of these is shown in yellow
HIGH_COLOUR = "#ffe14d"


def pretty(code):
    """A code inside a message: marked, so the message shows it as a picture of
    coloured dots and dashes (SettingsWindow.rich)."""
    return MARK + code + MARK


def big(code):
    """'.-' -> '● ▬' : for the lists, where one font serves every column."""
    return " ".join("●" if c == "." else "▬" for c in code)


def clean_code(text):
    """What was typed in the Code box -> dots and dashes ('•—', '. -' work too)."""
    t = re.sub(r"\s", "", text or "")
    return t.replace("•", ".").replace("·", ".").replace("—", "-").replace("–", "-").replace("_", "-")


def char_text(c):
    """One character as written in the map (quoted when it has to be)."""
    return mapload.phrase(c) if c in " \"'#" else c


def pick_for(text):
    """The action as written in the map -> (kind, value, mods, tap), filling the
    pickers. Anything they can't show is kind 'Other'."""
    other = (KINDS[9], text, (), False)
    a = mapload.parse_action(text)
    if isinstance(a, str):
        return other
    low = text.strip().lower()
    if a.kind == "char":
        return KINDS[0], a.text, (), False
    if a.kind == "text":
        return KINDS[3], a.text, (), False
    if a.kind == "secret":
        return KINDS[4], a.text, (), False
    if a.kind == "group":
        return KINDS[8], GROUPS[a.group - 1], (), False
    if a.kind == "vk":
        hit = [m for m in MEDIA if mapload._norm(m) == mapload._norm(text)]
        return (KINDS[6], hit[0], (), False) if hit else other
    if a.kind == "cmd":
        for kind, names in ((KINDS[5], MOUSE), (KINDS[7], COMMANDS)):
            hit = [n for n in names if mapload.parse_action(n) == a]
            if hit:
                return kind, hit[0], (), False
        return other
    tap = low.startswith("tap ")
    body = text.strip()[4:].strip() if tap else text.strip()
    if a.kind == "mod" or (tap and not a.keys):
        hit = [s for s in STICKY if s.lower() == body.lower()]
        return (KINDS[2], hit[0], (), tap) if hit else other
    if a.kind == "key" and not tap and "++" not in body:
        parts = [p.strip() for p in body.split("+")]
        mods = [m for p in parts[:-1] for m in MODS if m.lower() == p.lower()]
        if len(mods) == len(parts) - 1 and len(a.keys) == 1:
            return KINDS[1], parts[-1], tuple(mods), False
    return other


def take_focus(win):
    """Bring a Tk window to the front WITH the keyboard focus, even when
    another program has it (Windows only lets the program the user last typed
    into do that, so borrow its input queue for a moment)."""
    win.deiconify()
    win.lift()
    try:
        u = ctypes.windll.user32
        h = u.GetAncestor(win.winfo_id(), 2) or win.winfo_id()
        fg = u.GetForegroundWindow()
        them = u.GetWindowThreadProcessId(fg, None)
        us = ctypes.windll.kernel32.GetCurrentThreadId()
        if them and them != us:
            u.AttachThreadInput(us, them, True)
        u.SetForegroundWindow(h)
        u.BringWindowToTop(h)
        if them and them != us:
            u.AttachThreadInput(us, them, False)
    except Exception:
        pass
    win.focus_force()


class SettingsWindow:
    def __init__(self, root=None, on_record=None, avoid=None, map_path=None, on_close=None,
                 app=None, tab=None):
        """root: a Tk or Toplevel to fill (made if None). on_record(callback):
        the next code sent on the switches goes to callback(code) instead of
        being carried out; on_record(None) stops that. app: the running
        SwitchMorse (its window and switches), or None. tab: open on this tab."""
        self.app = app
        self.on_record = on_record
        self.on_close = on_close
        self.map_path = map_path or mapload.default_path()
        self.undo = []                      # map file contents before each change
        self.editing = None                 # code being changed, or None = adding
        self.confirm = None                 # what a second press of Save / Delete would do
        self.recording = False
        if root is None:
            appicon.set_app_id()
            root = tk.Tk()
        self.root = r = root
        r.title("SwitchMorse Settings")
        appicon.set_icon(r)
        r.configure(bg=BG)
        self._style()
        r.option_add("*TCombobox*Listbox.font", FONT)
        r.option_add("*TCombobox*Listbox.background", BG2)
        r.option_add("*TCombobox*Listbox.foreground", FG)

        # -- the tabs: one list of codes per group
        self.nb = ttk.Notebook(r)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        self.trees = {}
        self.sort_by = "code"
        for g, title in TABS:
            f = ttk.Frame(self.nb)
            self.nb.add(f, text="  %s  " % title)
            t = ttk.Treeview(f, columns=("does", "note"), show="tree headings",
                             selectmode="browse", height=5)
            t.heading("#0", text="Code")            # the code, drawn as dots and dashes
            t.heading("does", text="Does")
            t.heading("note", text="Note")
            t.column("#0", width=240, stretch=False)
            t.column("does", width=300)
            t.column("note", width=340)
            t.tag_configure("bad", foreground=BAD)
            t.tag_configure("hidden", foreground=DIM)
            sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
            t.configure(yscrollcommand=sb.set)
            t.grid(row=0, column=0, sticky="nsew")
            sb.grid(row=0, column=1, sticky="ns")
            f.rowconfigure(0, weight=1)
            f.columnconfigure(0, weight=1)
            t.bind("<Return>", lambda e: self.start_change())
            t.bind("<Delete>", lambda e: self.delete())
            t.bind("<<TreeviewSelect>>", lambda e: self.reset_confirm())
            self.trees[g] = t
            if g == 1:                          # standard Morse or AeroMorse letters
                bar = ttk.Frame(f)
                bar.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
                self.b_layout = ttk.Button(bar, text="", command=self.toggle_layout)
                self.b_layout.pack(side="left")
                self.f_layout = ttk.Frame(bar)      # words and code pictures
                self.f_layout.pack(side="left", padx=10)
        self.nb.enable_traversal()          # Ctrl+Tab / Ctrl+Shift+Tab
        self.nb.bind("<<NotebookTabChanged>>", self.tab_changed)

        row = self.code_row = ttk.Frame(r)
        row.pack(fill="x", padx=10, pady=4)
        self.b_add = ttk.Button(row, text="Add a new code", command=self.start_add)
        self.b_change = ttk.Button(row, text="Change this code", command=self.start_change)
        self.b_delete = ttk.Button(row, text="Delete this code", command=self.delete)
        self.b_sort = ttk.Button(row, text="Sort by what it does", command=self.toggle_sort)
        for b in (self.b_add, self.b_change, self.b_delete, self.b_sort):
            b.pack(side="left", padx=(0, 8))

        # -- the editor
        self.f_title = ttk.Frame(r)               # the editor's title, with a code picture
        ed = self.editor = ttk.LabelFrame(r, labelwidget=self.f_title)
        ed.pack(fill="x", padx=10, pady=4)
        ed.columnconfigure(1, weight=1)
        ttk.Label(ed, text="Code").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        cf = ttk.Frame(ed)
        cf.grid(row=0, column=1, sticky="w", pady=6)
        self.v_code = tk.StringVar()
        self.e_code = self._entry(cf, self.v_code, width=12, font=CODE_FONT)
        self.e_code.pack(side="left")
        self.l_code = ttk.Label(cf, text="", style="Code.TLabel")
        self.l_code.pack(side="left", padx=10)
        self.b_record = ttk.Button(cf, text="Record from the switches", command=self.record)
        self.b_record.pack(side="left", padx=8)

        ttk.Label(ed, text="Does").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.v_kind = tk.StringVar(value=KINDS[0])
        self.c_kind = ttk.Combobox(ed, textvariable=self.v_kind, values=KINDS, state="readonly",
                                   width=30, font=FONT)
        self.c_kind.grid(row=1, column=1, sticky="w", pady=6)

        self.detail = ttk.Frame(ed)
        self.detail.grid(row=2, column=1, sticky="w", pady=6)
        self.v_value = tk.StringVar()
        self.v_tap = tk.BooleanVar()
        self.v_mods = {m: tk.BooleanVar() for m in MODS}
        self.v_raw = tk.StringVar()
        self.frames = {}
        self._details()

        ttk.Label(ed, text="Note").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self.v_note = tk.StringVar()
        self._entry(ed, self.v_note, width=50).grid(row=3, column=1, sticky="we", padx=(0, 10), pady=6)

        self.f_msg = ttk.Frame(ed)
        self.f_msg.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 6))
        bf = ttk.Frame(ed)
        bf.grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
        self.b_save = ttk.Button(bf, text="Save", command=self.save)
        self.b_cancel = ttk.Button(bf, text="Clear", command=self.start_add)
        self.b_save.pack(side="left", padx=(0, 8))
        self.b_cancel.pack(side="left")

        bottom = self.bottom = ttk.Frame(r)
        bottom.pack(fill="x", padx=10, pady=(4, 10))
        self.b_undo = ttk.Button(bottom, text="Undo last code change", command=self.do_undo)
        self.b_undo.pack(side="left")
        self.b_close = ttk.Button(bottom, text="Close", command=self.close)
        self.b_close.pack(side="right")
        self.l_status = ttk.Frame(bottom)          # (a line of words and code pictures)
        self.l_status.pack(side="left", padx=12)

        for v in (self.v_code, self.v_value, self.v_tap, self.v_raw, *self.v_mods.values()):
            v.trace_add("write", lambda *a: self.update_preview())
        self.v_kind.trace_add("write", lambda *a: self.kind_changed())
        r.bind("<Escape>", lambda e: self.start_add())
        for cls in ("TButton", "TCheckbutton", "TRadiobutton"):        # Enter works a button, as Space does
            r.bind_class(cls, "<Return>", lambda e: e.widget.invoke())
        r.protocol("WM_DELETE_WINDOW", self.close)

        # The list takes whatever room is left: the code buttons, the editor and
        # the bottom row are always shown whole, even on a small screen.
        for w in (self.nb, self.code_row, self.editor, self.bottom):
            w.pack_forget()
        self.bottom.pack(side="bottom", fill="x", padx=10, pady=(4, 10))
        self.editor.pack(side="bottom", fill="x", padx=10, pady=4)
        self.code_row.pack(side="bottom", fill="x", padx=10, pady=4)
        self.nb.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 4))

        # -- the other tabs (settings_tabs.py)
        import settings_tabs
        self.extra = {}
        for cls in settings_tabs.TAB_CLASSES:
            f = ttk.Frame(self.nb)
            self.nb.add(f, text="  %s  " % cls.title)
            self.extra[cls.title] = cls(f, self)

        self.load()
        self.start_add(focus=False)
        self.place(avoid)
        if tab:
            self.show_tab(tab)
        self.tab_changed()

    def show_tab(self, title):
        """Open on the tab called `title` (e.g. "Passwords")."""
        for i in range(self.nb.index("end")):
            if self.nb.tab(i, "text").strip() == title:
                self.nb.select(i)
                self.tab_changed()
                return

    def switch_event(self, sw, pressed):
        """From SwitchMorse: a switch went down or up (for the Switches tab's test)."""
        tab = self.extra.get("Switches")
        if tab:
            tab.switch_event(sw, pressed)

    # ---- look -------------------------------------------------------------------
    def _style(self):
        s = ttk.Style(self.root)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG, font=FONT, fieldbackground=BG2,
                    bordercolor="#555", lightcolor=BG2, darkcolor=BG2, focuscolor=ACCENT)
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Code.TLabel", font=CODE_FONT, foreground="#00e5ff")
        s.configure("Msg.TLabel", font=BOLD)
        s.configure("Status.TLabel", foreground=DIM)
        s.configure("Dim.TLabel", foreground=DIM)
        s.configure("Bold.TLabel", font=BOLD)
        s.configure("Value.TLabel", font=("Consolas", 16, "bold"), foreground="#00e5ff")
        s.configure("TRadiobutton", background=BG, foreground=FG, font=BOLD, padding=(4, 6),
                    indicatorsize=18)
        s.map("TRadiobutton", background=[("focus", ACCENT), ("active", BG2)],
              indicatorbackground=[("selected", BG2), ("!selected", BG2)],
              indicatorforeground=[("selected", "#00e5ff"), ("!selected", BG2)])
        s.configure("TLabelframe", background=BG, bordercolor="#555")
        s.configure("TLabelframe.Label", background=BG, foreground=FG, font=BOLD)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=DIM, padding=(12, 8), font=BOLD)
        s.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        s.configure("Treeview", background=BG2, foreground=FG, fieldbackground=BG2, rowheight=36,
                    font=("Segoe UI", 14))
        s.configure("Treeview.Heading", background="#333", foreground=FG, font=BOLD)
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        s.configure("TButton", background="#3a3a3a", foreground=FG, padding=(14, 8), font=BOLD,
                    borderwidth=2)
        s.map("TButton", background=[("focus", ACCENT), ("active", "#4a4a4a")],
              foreground=[("focus", "white")], bordercolor=[("focus", "white")])
        s.configure("TCombobox", fieldbackground=BG2, background="#3a3a3a", foreground=FG,
                    arrowcolor=FG, padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", BG2), ("focus", "#203a5c")],
              foreground=[("readonly", FG)], bordercolor=[("focus", "white")])
        s.configure("TCheckbutton", background=BG, foreground=FG, font=BOLD, padding=(4, 6),
                    indicatorsize=18)
        s.map("TCheckbutton", background=[("focus", ACCENT), ("active", BG2)],
              indicatorbackground=[("selected", "#00e5ff"), ("!selected", BG2)],
              indicatorforeground=[("selected", "black"), ("!selected", BG2)])
        s.configure("Vertical.TScrollbar", background="#3a3a3a", troughcolor=BG)

    def _entry(self, parent, var, width=30, font=FONT):
        e = tk.Entry(parent, textvariable=var, width=width, font=font, bg=BG2, fg=FG,
                     insertbackground=FG, relief="flat", highlightthickness=3,
                     highlightbackground="#555", highlightcolor=ACCENT)
        e.bind("<Return>", lambda ev: self.save())
        return e

    def _details(self):
        """One small panel per kind of action; only the chosen one is shown."""
        d = self.detail
        f = ttk.Frame(d)
        ttk.Label(f, text="Character").pack(side="left", padx=(0, 8))
        self._entry(f, self.v_value, width=6).pack(side="left")
        self.frames[KINDS[0]] = f

        f = ttk.Frame(d)
        for m in MODS:
            ttk.Checkbutton(f, text=m, variable=self.v_mods[m]).pack(side="left", padx=(0, 6))
        ttk.Label(f, text="+  key").pack(side="left", padx=8)
        ttk.Combobox(f, textvariable=self.v_value, values=KEYS, width=16, font=FONT).pack(side="left")
        self.frames[KINDS[1]] = f

        f = ttk.Frame(d)
        ttk.Combobox(f, textvariable=self.v_value, values=STICKY, state="readonly", width=10,
                     font=FONT).pack(side="left")
        ttk.Checkbutton(f, text="Tap: press and let go at once (not sticky)",
                        variable=self.v_tap).pack(side="left", padx=12)
        self.frames[KINDS[2]] = f

        f = ttk.Frame(d)
        ttk.Label(f, text="Text").pack(side="left", padx=(0, 8))
        self._entry(f, self.v_value, width=46).pack(side="left")
        self.frames[KINDS[3]] = f

        f = ttk.Frame(d)
        ttk.Label(f, text="Password name").pack(side="left", padx=(0, 8))
        self.c_secret = ttk.Combobox(f, textvariable=self.v_value, width=24, font=FONT)
        self.c_secret.pack(side="left")
        ttk.Label(f, text="(set its value in Passwords...)", style="Status.TLabel").pack(
            side="left", padx=8)
        self.frames[KINDS[4]] = f

        for kind, names, w in ((KINDS[5], MOUSE, 22), (KINDS[6], MEDIA, 18),
                               (KINDS[7], COMMANDS, 16), (KINDS[8], GROUPS, 12)):
            f = ttk.Frame(d)
            ttk.Combobox(f, textvariable=self.v_value, values=names, state="readonly", width=w,
                         font=FONT).pack(side="left")
            self.frames[kind] = f

        f = ttk.Frame(d)
        ttk.Label(f, text="As written in morse_map.txt").pack(side="left", padx=(0, 8))
        self._entry(f, self.v_raw, width=36).pack(side="left")
        self.frames[KINDS[9]] = f

    def place(self, avoid):
        r = self.root
        r.update_idletasks()
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = min(1000, sw - 40), min(max(r.winfo_reqheight(), 860), sh - 100)
        r.geometry("%dx%d" % (w, h))
        try:
            from secrets_window import place_clear_of
            place_clear_of(r, avoid)
        except Exception:
            r.geometry("+%d+%d" % ((sw - w) // 2, 20))

    # ---- the list ------------------------------------------------------------------
    @property
    def group(self):
        """The group of the code tab showing, or None on the other tabs."""
        i = self.nb.index(self.nb.select())
        return TABS[i][0] if i < len(TABS) else None

    def load(self):
        """(Re)read the map and fill every tab, keeping each tab's selection."""
        self.entries = mapload.entries(self.map_path)
        active = {}
        for e in self.entries:
            if not isinstance(e["action"], str):
                active.setdefault((e["group"], e["code"]), e)
        self.active = active
        for g, t in self.trees.items():
            keep = t.selection()
            t.delete(*t.get_children())
            rows = [e for e in self.entries if e["group"] == g]
            if self.sort_by == "code":
                rows.sort(key=lambda e: (len(e["code"]), e["code"].replace(".", "0").replace("-", "1")))
            else:
                rows.sort(key=lambda e: self.does(e).lower())
            for e in rows:
                tag = ()
                if isinstance(e["action"], str):
                    tag = ("bad",)
                elif g and (0, e["code"]) in active:
                    tag = ("hidden",)
                t.insert("", "end", iid="%d %s" % (g, e["code"]) if not tag == ("bad",)
                         else "bad %d" % e["line"], text="", image=self.code_image(e["code"]),
                         values=(self.does(e), self.note_text(e, active)), tags=tag)
            if keep and t.exists(keep[0]):
                t.selection_set(keep[0])
                t.see(keep[0])
        names = sorted({e["action"].text for e in self.entries
                        if not isinstance(e["action"], str) and e["action"].kind == "secret"})
        try:
            import secrets_store
            names = sorted(set(names) | set(secrets_store.load()))
        except Exception:
            pass
        self.c_secret.configure(values=names)
        self.show_layout()

    # ---- pictures of codes ------------------------------------------------------
    def code_image(self, code, small=False):
        """The code drawn as purple dots and green dashes (kept, one per code)."""
        if not hasattr(self, "_images"):
            self._images = {}
        img = self._images.get((code, small))
        if img is None:
            d, w, gap, h = (8, 16, 4, 14) if small else (12, 28, 7, 20)
            width = sum(d if c == "." else w for c in code) + gap * max(0, len(code) - 1) + 4
            img = tk.PhotoImage(master=self.root, width=max(width, 1), height=h)
            x = 2
            for c in code:
                if c == ".":
                    r = d / 2.0
                    for y in range(d):
                        half = int(round((r * r - (y + 0.5 - r) ** 2) ** 0.5))
                        if half:
                            img.put(DOT_COLOUR, to=(x + int(r) - half, (h - d) // 2 + y,
                                                    x + int(r) + half, (h - d) // 2 + y + 1))
                    x += d + gap
                else:
                    th = d - 2                              # dash thickness
                    img.put(DASH_COLOUR, to=(x, (h - th) // 2, x + w, (h - th) // 2 + th))
                    x += w + gap
            self._images[(code, small)] = img
        return img

    # ---- Keyboard: standard Morse or AeroMorse letters ------------------------------------
    def layout_now(self):
        """'aeromorse', 'standard', or None (those four codes were changed by hand)."""
        have = {(e["code"], mapload._norm(e["text"])) for e in self.entries
                if e["group"] == 1 and not isinstance(e["action"], str)}
        for name, i in (("aeromorse", 1), ("standard", 3)):
            if all((row[0], mapload._norm(row[i])) in have for row in AEROMORSE_FOUR):
                return name
        return None

    def show_layout(self):
        if not hasattr(self, "b_layout"):
            return
        now = self.layout_now()
        self.layout_confirm = False
        if now == "aeromorse":
            self.b_layout.configure(text="Use standard Morse for M and C", state="normal")
            parts = ["AeroMorse now:  M", "----", "C", "---.", "Backspace", "--", "Ctrl", "-.-."]
        elif now == "standard":
            self.b_layout.configure(text="Use AeroMorse codes for M and C", state="normal")
            parts = ["Standard now:  M", "--", "C", "-.-.", "Backspace", "----", "Ctrl", "---."]
        else:
            self.b_layout.configure(text="Standard / AeroMorse", state="disabled")
            parts = ["M, C, Backspace and Ctrl have been changed by hand - change them one by one."]
        for w in self.f_layout.winfo_children():
            w.destroy()
        for i, p in enumerate(parts):
            if i % 2:
                ttk.Label(self.f_layout, image=self.code_image(p, small=True)).pack(
                    side="left", padx=(4, 10))
            else:
                ttk.Label(self.f_layout, text=p, style="Status.TLabel").pack(side="left")

    def toggle_layout(self):
        """Swap M / Backspace and C / Ctrl between AeroMorse and standard Morse."""
        now = self.layout_now()
        if now is None:
            return
        if not self.layout_confirm:
            self.layout_confirm = True
            self.b_layout.configure(text="Yes, change these 4 codes")
            self.status("This changes M, C, Backspace and Ctrl in Keyboard. Press it again to do it.",
                        WARN)
            return
        i = 3 if now == "aeromorse" else 1
        self._remember()
        try:
            for row in AEROMORSE_FOUR:
                mapload.set_code(1, row[0], row[i], row[i + 1] or "", self.map_path, replace=True)
        except (ValueError, OSError) as ex:
            self.status("Not changed: %s" % ex, BAD)
            return
        self.load()
        self.status("Keyboard now uses %s for M and C. Undo takes it back."
                    % ("standard Morse" if now == "aeromorse" else "AeroMorse codes"), OK)

    @staticmethod
    def does(e):
        a = e["action"]
        if isinstance(a, str):
            return "⚠ %s - left out" % e["text"]
        if a.kind == "char" and a.text == " ":
            return "Space (character)"
        if a.kind == "cmd" and a.cmd[0] == "mmove":       # mouse moves and scrolls: an arrow
            dx, dy, wheel = a.cmd[1:4]
            arrow = ARROWS.get((dx, dy)) or ("⇡" if wheel > 0 else "⇣" if wheel < 0 else "")
            return "%s  %s" % (arrow, a.label)
        return a.label

    @staticmethod
    def note_text(e, active):
        a = e["action"]
        if isinstance(a, str):
            return a
        if e["group"] and (0, e["code"]) in active:
            return "hidden: Base uses this code (%s)" % active[(0, e["code"])]["action"].label
        return e["note"] or ""

    DUPLICATE = "already used above - left out"

    def selected(self, doing=None):
        """The entry selected in the current tab, or None. A second line with
        the same code can only be fixed in Notepad (the program would change
        the first one), so `doing` it is refused with a note."""
        e = self._selected()
        if e and doing and e["action"] == self.DUPLICATE:
            self.status("Line %d repeats a code used above - %s it in morse_map.txt with Notepad."
                        % (e["line"], doing), WARN)
            return None
        if not e and doing:
            self.status("Pick a code in the list first.", WARN)
        return e

    def _selected(self):
        sel = self.trees[self.group].selection()
        if not sel or sel[0].startswith("bad "):
            if sel:
                line = int(sel[0].split()[1])
                return next((e for e in self.entries if e["line"] == line), None)
            return None
        g, code = sel[0].split(" ", 1)
        return self.active.get((int(g), code))

    def tab_changed(self, ev=None):
        if self.group is None:              # not a code tab: no code buttons, editor, undo
            self.stop_recording()
            pw = self.extra.get("Passwords") if hasattr(self, "extra") else None
            if pw and self.nb.tab(self.nb.select(), "text").strip() == "Passwords":
                pw.refresh()
            self.code_row.pack_forget()
            self.editor.pack_forget()
            self.b_undo.pack_forget()
            return
        if not self.editor.winfo_ismapped():
            self.editor.pack(side="bottom", fill="x", padx=10, pady=4, before=self.nb)
            self.code_row.pack(side="bottom", fill="x", padx=10, pady=4, before=self.nb)
            self.b_undo.pack(side="left", before=self.l_status)
        t = self.trees[self.group]
        if not t.selection() and t.get_children():
            t.selection_set(t.get_children()[0])
            t.focus(t.get_children()[0])
        self.start_add(focus=False)         # an edit belongs to the tab it started in

    def toggle_sort(self):
        self.sort_by = "does" if self.sort_by == "code" else "code"
        self.b_sort.configure(text="Sort by code" if self.sort_by == "does" else "Sort by what it does")
        self.load()

    # ---- the editor ------------------------------------------------------------------
    def start_add(self, focus=True):
        if self.group is None:              # (Escape on another tab)
            return
        self.stop_recording()
        self.editing = None
        self.rich(self.f_title, "New code in %s" % dict(TABS)[self.group], FG, BOLD)
        self.b_cancel.configure(text="Clear")
        self.set_fields("", KINDS[0], "", (), False, "")
        self.reset_confirm()
        if focus:
            self.e_code.focus_set()

    def start_change(self):
        e = self.selected("change")
        if not e:
            return
        self.stop_recording()
        self.editing = e["code"]
        self.rich(self.f_title, "Change %s in %s" % (pretty(e["code"]), dict(TABS)[self.group]),
                  FG, BOLD)
        self.b_cancel.configure(text="Cancel")
        kind, value, mods, tap = pick_for(e["text"])
        self.set_fields(e["code"], kind, value, mods, tap, e["note"] or "", raw=e["text"])
        self.reset_confirm()
        self.c_kind.focus_set()

    def set_fields(self, code, kind, value, mods, tap, note, raw=""):
        self._quiet = True
        self.v_code.set(code)
        self.v_kind.set(kind)
        self.v_value.set(value)
        self.v_tap.set(tap)
        for m, v in self.v_mods.items():
            v.set(m in mods)
        self.v_raw.set(raw if kind == KINDS[9] else "")
        self.v_note.set(note)
        self._quiet = False
        self.show_detail()
        self.update_preview()

    def kind_changed(self):
        if getattr(self, "_quiet", False):
            return
        old = getattr(self, "_last_text", "")       # what the previous kind made
        self._quiet = True
        self.v_value.set("")
        self.v_tap.set(False)
        for v in self.v_mods.values():
            v.set(False)
        if self.v_kind.get() == KINDS[9]:
            self.v_raw.set(old or "")
        self._quiet = False
        self.show_detail()
        self.update_preview()

    def show_detail(self):
        for k, f in self.frames.items():
            if k == self.v_kind.get():
                f.pack(side="left")
            else:
                f.pack_forget()

    def action_text(self):
        """The action as it will be written in morse_map.txt ('' if none yet)."""
        kind, v = self.v_kind.get(), self.v_value.get()
        if kind == KINDS[0]:
            return char_text(v) if len(v) == 1 else v
        if kind == KINDS[1]:
            if not v.strip():
                return ""
            return "+".join([m for m in MODS if self.v_mods[m].get()] + [v.strip()])
        if kind == KINDS[2]:
            return ("tap " if self.v_tap.get() else "") + v if v else ""
        if kind == KINDS[3]:
            return mapload.phrase(v) if v else ""
        if kind == KINDS[4]:
            return "secret " + v.strip() if v.strip() else ""
        if kind == KINDS[8]:
            return "group " + v if v else ""
        if kind == KINDS[9]:
            return self.v_raw.get().strip()
        return v

    def check(self):
        """(code, action text, Action or None, problems that stop saving,
        warnings that need Save pressed twice)."""
        code = clean_code(self.v_code.get())
        text = self.action_text()
        errors, warns, a = [], [], None
        g = self.group
        if not re.fullmatch(r"[.\-]{1,8}", code):
            errors.append("Code: 1 to 8 dots and dashes (type . and -, or Record).")
        if self.v_kind.get() == KINDS[0] and len(self.v_value.get()) > 1:
            errors.append("One character only - for more, choose Phrase.")
        elif self.v_kind.get() == KINDS[3] and '"' in self.v_value.get() and "'" in self.v_value.get():
            errors.append("A phrase can't have both \" and ' in it.")
        elif not text:
            errors.append("Choose what the code does.")
        else:
            a = mapload.parse_action(text)
            if isinstance(a, str):
                errors.append(a[0].upper() + a[1:] + ".")
                a = None
        if not errors:
            other = self.active.get((g, code))
            if other and code != self.editing:
                warns.append("%s is already used here for %s - Save again to replace it."
                             % (pretty(code), other["action"].label))
            if g and (0, code) in self.active:
                warns.append("Base uses %s (%s) in every group, so this code would never work "
                             "here - Save again to save it anyway."
                             % (pretty(code), self.active[(0, code)]["action"].label))
            if g == 0:
                hidden = ["%s: %s" % (dict(TABS)[gg], self.active[(gg, code)]["action"].label)
                          for gg in (1, 2, 3) if (gg, code) in self.active]
                if hidden:
                    warns.append("A Base code works in every group, so it would hide %s - Save "
                                 "again to save it anyway." % "; ".join(hidden))
            if a and a.kind == "group" and a.group == g:
                warns.append("That goes to this same group - Save again to save it anyway.")
        return code, text, a, errors, warns

    def update_preview(self):
        if getattr(self, "_quiet", False):
            return
        code = clean_code(self.v_code.get())
        ok = re.fullmatch(r"[.\-]{1,8}", code)
        self.l_code.configure(image=self.code_image(code) if ok else "")
        code, text, a, errors, warns = self.check()
        self._last_text = text
        self.reset_confirm()
        if errors:
            self.msg(errors[0], BAD if self.v_code.get() or text else DIM)
        elif warns:
            self.msg(warns[0], WARN)
        else:
            self.msg("%s will do: %s%s%s" % (pretty(code), HIGH, self.does(dict(action=a, text=text)), HIGH),
                     FG)                # white (green is for dashes); what it does in yellow

    def msg(self, text, colour):
        self.rich(self.f_msg, text, colour, BOLD, wrap=780)

    def status(self, text, colour=DIM):
        self.rich(self.l_status, text, colour, FONT, wrap=560)

    def rich(self, frame, text, colour, font, wrap=0):
        """Show `text` in `frame`, each pretty() code in it as a picture."""
        for w in frame.winfo_children():
            w.destroy()
        for i, part in enumerate(text.split(MARK)):
            if i % 2:
                ttk.Label(frame, image=self.code_image(part, small=True)).pack(side="left", padx=4)
            else:
                for j, bit in enumerate(part.split(HIGH)):
                    if bit:
                        tk.Label(frame, text=bit, fg=HIGH_COLOUR if j % 2 else colour, bg=BG, font=font,
                                 wraplength=wrap, justify="left").pack(side="left")

    def reset_confirm(self):
        if self.confirm:
            self.confirm = None
            self.b_save.configure(text="Save")
            self.b_delete.configure(text="Delete this code")

    # ---- saving -----------------------------------------------------------------------------
    def _remember(self):
        with open(self.map_path, "rb") as f:
            self.undo.append(f.read())
        del self.undo[:-20]

    def save(self):
        code, text, a, errors, warns = self.check()
        if errors:
            self.msg(errors[0], BAD)
            return
        want = ("save", self.group, code, text, self.v_note.get(), self.editing)
        if warns and self.confirm != want:
            self.confirm = want
            self.msg(warns[0], WARN)
            self.b_save.configure(text="Yes, save it")
            return
        g, note = self.group, self.v_note.get().strip()
        self._remember()
        try:
            if self.editing:
                if code != self.editing and (g, code) in self.active:
                    mapload.delete_code(g, code, self.map_path)     # replacing that one
                mapload.set_code(g, code, text, note, self.map_path, old_code=self.editing)
            else:
                mapload.set_code(g, code, text, note, self.map_path,
                                 replace=(g, code) in self.active)
        except (ValueError, OSError) as ex:
            self.undo.pop()
            self.msg("Not saved: %s" % ex, BAD)
            return
        self.load()
        iid = "%d %s" % (g, code)
        t = self.trees[g]
        if t.exists(iid):
            t.selection_set(iid)
            t.see(iid)
        self.status("Saved: %s = %s. SwitchMorse uses it now." % (pretty(code), a.label), OK)
        self.start_add(focus=False)
        t.focus_set()

    def delete(self):
        e = self.selected("delete")
        if not e:
            return
        want = ("delete", e["group"], e["code"], e["line"])
        if self.confirm != want:
            self.reset_confirm()
            self.confirm = want
            self.b_delete.configure(text="Yes, delete it")
            self.status("Delete %s (%s)? Press it again to delete."
                        % (pretty(e["code"]), self.does(e)), WARN)
            self.b_delete.focus_set()
            return
        self.reset_confirm()
        self._remember()
        try:
            mapload.delete_code(e["group"], e["code"], self.map_path)
        except (ValueError, OSError) as ex:
            self.undo.pop()
            self.status("Not deleted: %s" % ex, BAD)
            return
        self.load()
        self.status("Deleted %s (%s)." % (pretty(e["code"]), self.does(e)), OK)
        self.trees[self.group].focus_set()
        self.tab_changed()

    def do_undo(self):
        if not self.undo:
            self.status("Nothing to undo.", DIM)
            return
        try:
            filesave.write_bytes(self.map_path, self.undo.pop())
        except OSError as ex:
            self.status("Undo failed: %s" % ex, BAD)
            return
        self.load()
        self.status("Undone. %d more change%s can be undone."
                    % (len(self.undo), "" if len(self.undo) == 1 else "s"), OK)

    # ---- recording a code from the switches ------------------------------------------------
    def record(self):
        if self.recording:
            self.stop_recording()
            self.msg("Recording stopped.", DIM)
            return
        if not self.on_record:
            self.msg("Recording needs SwitchMorse running - open Settings from its window.", WARN)
            return
        self.recording = True
        self.b_record.configure(text="Recording... send the code now")
        self.msg("Send the code on your switches: it goes into the Code box, nothing is typed.", WARN)
        self.on_record(self.recorded)

    def recorded(self, code):
        """Called by SwitchMorse with the code that was sent."""
        self.recording = False
        self.b_record.configure(text="Record from the switches")
        self.v_code.set(code)
        self.c_kind.focus_set()

    def stop_recording(self):
        if self.recording:
            self.recording = False
            self.b_record.configure(text="Record from the switches")
            if self.on_record:
                self.on_record(None)

    def close(self):
        self.stop_recording()
        if self.on_close:
            self.on_close()
        self.root.destroy()


def main():
    avoid = None
    if "--avoid" in sys.argv:
        try:
            avoid = tuple(int(v) for v in sys.argv[sys.argv.index("--avoid") + 1].split(","))
        except (IndexError, ValueError):
            pass
    w = SettingsWindow(avoid=avoid)
    take_focus(w.root)
    w.root.mainloop()


if __name__ == "__main__":
    main()
