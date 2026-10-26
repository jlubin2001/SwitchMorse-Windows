# SwitchMorse Windows - window.py
# The feedback window, in the look of AeroMorse Display: a black panel with
#   [ GROUP ]          in the group's colour
#   .-..               the dots and dashes so far (cyan)
#   = l   -:x .:b      hints: what the code is now, and what one or two more
#                      symbols would make (grey)
#   RPT Down           the last action (yellow; RPT in orange while repeating)
#   Ctrl DRAG          armed keys, DRAG, PAUSED... (orange)
# and a small line at the bottom: which switches are in use, and any warning.
#
# The text grows and shrinks with the window. Right-click for the menu. The
# window never takes the keyboard focus, so what SwitchMorse types goes to the
# window you were using. Its size, place and menu choices are remembered in
# %APPDATA%\SwitchMorse\window.json.
import ctypes
import json
import os
import re
import tkinter as tk
import tkinter.font as tkfont

import appicon



GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000          # a taskbar button

BG = "#000000"
GROUP_COLOURS = {1: "#00FF00", 2: "#00A0FF", 3: "#FF00FF", 0: "#FFFFFF"}
BUF_FG, HINT_FG, ACT_FG, RPT_FG, MODS_FG = "#00FFFF", "#A0A0A0", "#FFFF00", "#FF8000", "#FF8000"
STATE_FG, WARN_FG = "#8090A0", "#FF6060"

SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SwitchMorse",
                        "window.json")
MIN_W, MIN_H = 200, 110
DEFAULT_GEOMETRY = "340x190+80+80"


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_settings(d):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except Exception:
        pass


def _on_a_screen(x, y):
    try:
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.MonitorFromPoint.restype = ctypes.c_void_p
        u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        return bool(u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 0))
    except Exception:
        return True


def safe_geometry(saved, sw, sh):
    """The saved size and place, never too small and never off every screen
    (e.g. last shown on a monitor that is no longer plugged in)."""
    m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(saved or ""))
    if not m:
        return DEFAULT_GEOMETRY
    w, h, x, y = (int(v) for v in m.groups())
    w = max(MIN_W, min(w, sw))
    h = max(MIN_H, min(h, sh))
    if not _on_a_screen(x + w // 2, y + h // 2):
        x, y = 80, 80
    return "%dx%d+%d+%d" % (w, h, x, y)


class Window:
    def __init__(self, on_top=True, on_reload=None, on_quit=None, on_passwords=None,
                 on_sound=None, on_settings=None):
        self.cfg = load_settings()
        self.on_quit = on_quit
        self.on_sound = on_sound
        appicon.set_app_id()                # its own taskbar button, not Python's
        r = self.root = tk.Tk()
        r.title("SwitchMorse")
        appicon.set_icon(r)
        r.configure(bg=BG)
        r.geometry(safe_geometry(self.cfg.get("geometry"), r.winfo_screenwidth(),
                                 r.winfo_screenheight()))
        r.minsize(MIN_W, MIN_H)
        self.font = tkfont.Font(family="Consolas", size=20, weight="bold")
        self.hfont = tkfont.Font(family="Consolas", size=12, weight="bold")
        self.small = tkfont.Font(family="Segoe UI", size=9)

        self.rows = tk.Frame(r, bg=BG)
        self.rows.place(relx=0.5, rely=0.47, anchor="center")
        self.l_group = tk.Label(self.rows, bg=BG, font=self.font)
        self.l_buf = tk.Label(self.rows, bg=BG, fg=BUF_FG, font=self.font)
        self.l_hint = tk.Label(self.rows, bg=BG, fg=HINT_FG, font=self.hfont)
        act = tk.Frame(self.rows, bg=BG)
        self.l_rpt = tk.Label(act, bg=BG, fg=RPT_FG, font=self.font)
        self.l_act = tk.Label(act, bg=BG, fg=ACT_FG, font=self.font)
        self.l_mods = tk.Label(self.rows, bg=BG, fg=MODS_FG, font=self.font)
        self.l_group.pack()
        self.l_buf.pack()
        self.l_hint.pack()
        act.pack()
        self.l_rpt.pack(side="left")
        self.l_act.pack(side="left")
        self.l_mods.pack()
        self.l_state = tk.Label(r, bg=BG, fg=STATE_FG, font=self.small)
        self.l_state.place(relx=0.5, rely=1.0, anchor="s")

        self.v_top = tk.BooleanVar(value=self.cfg.get("on_top", bool(on_top)))
        self.v_bar = tk.BooleanVar(value=self.cfg.get("title_bar", True))
        self.v_alpha = tk.IntVar(value=int(self.cfg.get("opacity", 100)))
        self.v_hints = tk.BooleanVar(value=self.cfg.get("hints", True))    # on for new users (learning);
                                                                   # the menu choice is remembered
        self.v_sound = tk.StringVar(value=self.cfg.get("sound", "off"))

        m = self.menu = tk.Menu(r, tearoff=0)
        m.add_checkbutton(label="Always on top", variable=self.v_top, command=self.apply_look)
        m.add_checkbutton(label="Title bar (needed to resize; untick for a plain panel)",
                          variable=self.v_bar, command=self.apply_look)
        sub = tk.Menu(m, tearoff=0)
        for pct in (100, 85, 70, 50, 35):
            sub.add_radiobutton(label="%d %%" % pct, value=pct, variable=self.v_alpha,
                                command=self.apply_look)
        m.add_cascade(label="See-through", menu=sub)
        snd = tk.Menu(m, tearoff=0)
        for name, text in (("off", "Off"), ("quiet", "Quiet"), ("medium", "Medium"), ("loud", "Loud")):
            snd.add_radiobutton(label=text, value=name, variable=self.v_sound,
                                command=self.apply_sound)
        m.add_cascade(label="Sound", menu=snd)
        m.add_checkbutton(label="Hints (what the code can still become)",
                          variable=self.v_hints, command=self.remember)
        m.add_separator()
        if on_settings:
            m.add_command(label="Start here (guide)...", command=lambda: on_settings("Start here"))
            m.add_command(label="Settings...", command=on_settings)
        if on_reload:
            m.add_command(label="Reload map", command=on_reload)
        if on_passwords:
            m.add_command(label="Passwords...", command=on_passwords)
        m.add_separator()
        m.add_command(label="Quit SwitchMorse", command=self.quit)

        r.bind("<Button-3>", self.popup)
        r.bind("<ButtonPress-1>", self.drag_start)
        r.bind("<B1-Motion>", self.drag_move)
        r.bind("<ButtonRelease-1>", self.drag_end)
        r.bind("<Configure>", self.on_resize)
        r.protocol("WM_DELETE_WINDOW", self.quit)
        self.apply_look()
        r.update_idletasks()
        self.fit()

    # ---- never take the keyboard focus ------------------------------------------------
    def _hwnd(self):
        try:
            return ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2) or self.root.winfo_id()
        except Exception:
            return 0

    def _no_focus(self):
        """Never take the keyboard focus, but keep a taskbar button (a window
        that never takes the focus otherwise has none, and is easy to lose)."""
        try:
            h = self._hwnd()
            u = ctypes.windll.user32
            old = u.GetWindowLongW(h, GWL_EXSTYLE)
            new = old | WS_EX_NOACTIVATE | WS_EX_APPWINDOW
            if new != old:
                u.SetWindowLongW(h, GWL_EXSTYLE, new)
                if u.IsWindowVisible(h):            # the taskbar notices on the next show
                    u.ShowWindow(h, 0)              # SW_HIDE
                    u.ShowWindow(h, 4)              # SW_SHOWNOACTIVATE
        except Exception:
            pass

    def bring_to_front(self):
        """In front of every window (and on the screen), without taking the
        focus. Stays always-on-top only if that is ticked in the menu."""
        try:
            u = ctypes.windll.user32
            h = self._hwnd()
            if u.IsIconic(h):
                u.ShowWindow(h, 4)                  # restore, no focus
            flags = 0x0001 | 0x0002 | 0x0010 | 0x0040   # NOSIZE NOMOVE NOACTIVATE SHOWWINDOW
            u.SetWindowPos(ctypes.c_void_p(h), ctypes.c_void_p(-1), 0, 0, 0, 0, flags)   # HWND_TOPMOST: to the very front
            if not self.v_top.get():
                u.SetWindowPos(ctypes.c_void_p(h), ctypes.c_void_p(-2), 0, 0, 0, 0, flags)  # HWND_NOTOPMOST: but don't stay there
        except Exception:
            pass
        r = self.root                               # if it is off every screen, bring it back
        if not _on_a_screen(r.winfo_x() + r.winfo_width() // 2, r.winfo_y() + r.winfo_height() // 2):
            r.geometry("+80+80")
            self.remember()

    # ---- look ---------------------------------------------------------------------------
    def apply_look(self):
        r = self.root
        r.attributes("-topmost", bool(self.v_top.get()))
        r.attributes("-alpha", max(0.2, min(1.0, self.v_alpha.get() / 100.0)))
        plain = not self.v_bar.get()
        if bool(r.overrideredirect()) != plain:
            r.overrideredirect(plain)
        r.update_idletasks()
        self._no_focus()                    # the outer window changes with the title bar
        self.remember()

    def apply_sound(self):
        self.remember()
        if self.on_sound:
            self.on_sound(self.v_sound.get())

    @property
    def sound_level(self):
        return self.v_sound.get()

    @property
    def hints_on(self):
        return bool(self.v_hints.get())

    def remember(self):
        self.cfg.update(on_top=bool(self.v_top.get()), title_bar=bool(self.v_bar.get()),
                        opacity=int(self.v_alpha.get()), hints=bool(self.v_hints.get()),
                        sound=self.v_sound.get())
        geo = self.root.geometry()
        if not geo.startswith("1x1+"):
            self.cfg["geometry"] = geo
        save_settings(self.cfg)

    def fit(self):
        """Text as large as fits: 20 characters across, about 4.6 rows down."""
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w < 10 or h < 10:
            return
        px = max(8, int(min((w - 12) / 20.0 / 0.56, (h - 24) / 4.6 / 1.22)))
        if self.font.cget("size") != -px:
            self.font.configure(size=-px)
            self.hfont.configure(size=-max(8, int(px * 0.55)))

    def on_resize(self, ev):
        if ev.widget is self.root:
            self.fit()

    # ---- menu and moving -------------------------------------------------------------------
    def popup(self, ev):
        try:
            self.menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            self.menu.grab_release()

    # Click and hold anywhere on the panel, then move, to move the window -
    # with or without the title bar. (Holding the button down on the TITLE
    # BAR makes Windows stop this program until it is let go, so SwitchMorse
    # itself could not move the pointer or let go of the button. Dragging the
    # panel is handled here and nothing stops.)
    def drag_start(self, ev):
        self._drag = (ev.x_root - self.root.winfo_x(), ev.y_root - self.root.winfo_y())

    def drag_move(self, ev):
        if getattr(self, "_drag", None):
            dx, dy = self._drag
            self.root.geometry("+%d+%d" % (ev.x_root - dx, ev.y_root - dy))

    def drag_end(self, ev):
        self._drag = None
        self.remember()

    def pointer_on_panel(self):
        """True if the pointer is inside the black panel (not the title bar or
        edges): the panel's own place on the screen, from Tk."""
        r = self.root
        x, y = r.winfo_pointerxy()
        rx, ry = r.winfo_rootx(), r.winfo_rooty()
        return rx <= x < rx + r.winfo_width() and ry <= y < ry + r.winfo_height()

    # SwitchMorse moving its own window: no mouse button is held (on our own
    # title bar that would stop this program); the window just keeps the same
    # offset from the pointer, checked every 15 ms, until stop_follow().
    def start_follow(self):
        r = self.root
        x, y = r.winfo_pointerxy()
        self._follow = (x - r.winfo_x(), y - r.winfo_y())
        self._follow_tick()

    def _follow_tick(self):
        if not getattr(self, "_follow", None):
            return
        x, y = self.root.winfo_pointerxy()
        dx, dy = self._follow
        self.root.geometry("+%d+%d" % (x - dx, y - dy))
        self.root.after(15, self._follow_tick)

    def stop_follow(self):
        if getattr(self, "_follow", None):
            self._follow = None
            self.remember()

    # ---- what to show ------------------------------------------------------------------------
    def show(self, group_no, group_name, buffer, hints, action, repeating, status, state,
             warn=False):
        self.l_group.config(text="[ %s ]" % group_name, fg=GROUP_COLOURS.get(group_no, "#FFFFFF"))
        self.l_buf.config(text=buffer or " ")
        self.l_hint.config(text=(hints if self.hints_on else "") or " ")
        if repeating and action.startswith("Repeat "):
            self.l_rpt.config(text="RPT ")
            self.l_act.config(text=action[7:] or " ")
        else:
            self.l_rpt.config(text="")
            self.l_act.config(text=action or " ")
        self.l_mods.config(text=status or " ")
        self.l_state.config(text=state or " ", fg=WARN_FG if warn else STATE_FG)

    def quit(self):
        self.remember()
        if self.on_quit:
            self.on_quit()
        self.root.destroy()
