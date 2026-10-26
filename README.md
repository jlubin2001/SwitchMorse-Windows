# SwitchMorse Windows

Use Morse code — sips and puffs, or two switches — as a complete keyboard and
mouse for Windows. A small program on the PC decodes the Morse and types,
clicks and scrolls; the switches only report each press.

It uses the same codes as **[AeroMorse](https://github.com/jlubin2001/AeroMorse)**,
the sip-and-puff Morse keyboard, and works together with it.

## What you need

One of these, to send the dots and dashes:
- **An [Adafruit TRRS Trinkey](https://www.adafruit.com/product/5954)** (#5954) — the least expensive switch interface:
  a small USB stick that two assistive switches plug into. You need **two
  switches** (dot and dash, with 3.5 mm mono plugs) and a **headset splitter
  cable**: one 3.5 mm 4-pole (TRRS) plug to two sockets, **CTIA** type — e.g.
  the [MillSO headset splitter](https://www.amazon.com/dp/B071DMCZQF), or
  [search for others](https://www.amazon.com/s?k=3.5mm+headset+splitter+CTIA+TRRS+male+to+2+female).
  Plug the **dot** switch into the headphone socket (often green) and the
  **dash** switch into the mic socket (often pink). (Inside: dot = TIP,
  dash = SLEEVE, ground = RING_2.) Copy the reporter firmware in `trinkey\`
  (`boot.py` and `code.py`) to its CIRCUITPY drive, then unplug and replug it.
- **An AeroMorse device** (v1.32 or later) with `PC_HANDOVER = True` in its
  `config.py`. While SwitchMorse runs, the AeroMorse only reports sips and puffs
  and its display shows **PC MODE**. When SwitchMorse stops, it types by itself
  again within 2 seconds — so you are never left without a keyboard.
- **Two keyboard keys** — for a switch interface that plugs in as a USB keyboard
  (most send Enter and Space), or anyone who can press two keys. Set
  `INPUT = keys` in `config.txt`; by default **Enter = dot, Space = dash**
  (`DOT_KEY`, `DASH_KEY`). While SwitchMorse runs this way those two keys don't
  type themselves; Morse codes for Enter and Space still work.

## Installing

**The easy way: no Python needed.** From the latest
[release](https://github.com/jlubin2001/SwitchMorse-Windows/releases), run
**SwitchMorse-Setup-<version>.exe**. It installs for your Windows account only
(no admin rights) and asks whether SwitchMorse should start when you sign in.
It adds Start menu entries for SwitchMorse, the cheat sheet and your files.
Or unzip **SwitchMorse-<version>.zip** anywhere and run `SwitchMorse.exe`.

Your map and settings are kept in **Documents\SwitchMorse**, made at the first
start. Updating or uninstalling the program never touches them.

Windows may say *"Windows protected your PC"* the first time, because the
program isn't signed. Click **More info → Run anyway**. Some antivirus programs
are wary of new programs made with PyInstaller too.

**From the source** (to change the program): install **Python 3** (from
[python.org](https://www.python.org/)) and the `pyserial` package, then use the
.bat files below:

```
py -m pip install pyserial
```

## Your work folder (running from source)

Keep your own files apart from the program:

```
py tools\make_work_folder.py "%USERPROFILE%\Documents\SwitchMorse"
```

That folder then holds your map (`morse_map.txt`), your settings (`config.txt`),
Start / sign-in / Passwords / cheat-sheet shortcuts and a short README — and
SwitchMorse reads your map and settings from there. Updating the program never
touches it.

## Starting and stopping

| To | Installed | From source |
|---|---|---|
| Start it now | Start menu → **SwitchMorse** | Double-click **Start SwitchMorse.bat** |
| Start it every time you sign in, or stop that | Settings → Window → **Start SwitchMorse when I sign in** (or tick it when installing) | The same check box, or **Start at sign-in - ON.bat** / **- OFF.bat** |
| Close it | Right-click the SwitchMorse window → **Quit SwitchMorse** (or its X) |

Only one copy runs at a time; starting it again while it runs does nothing.

## The window

A small black panel, always on top, that never takes the keyboard focus — what
you type goes to the window you were using.

- **[ KEYBOARD ]**, **[ MOUSE ]** or **[ MACRO ]** — the group, in its colour.
- The dots and dashes as you send them (cyan).
- What the last code did (yellow; **RPT** in orange while repeating).
- Armed Ctrl / Shift / Alt / Win, PAUSED, DRAG, REPEAT, SLOW / FAST (orange).
- Small bottom line: **Input:** which switches are in use, e.g.
  *AeroMorse (PC mode)* or *Trinkey*, and any warning.

**Right-click** it for the menu: Always on top, Title bar, See-through, Sound
(Off / Quiet / Medium / Loud: a tone for each dot and dash, a blip for each
action), Hints (what a half-sent code can still become — for learning the
codes), Reload map, Passwords…, Quit. The text grows and shrinks with the
window; your choices, size and place are remembered.

**To move it:** point at it (title bar or panel), send *drag* (`-.` in the Mouse
group), move, then *drag* again. The window follows the pointer.

## Learning Morse

The settings start slow, for learning: SwitchMorse waits **0.5 s** after your
last press before it sends the code, and a press must be held **1.5 s** to
change group. The **hints** line under the dots and dashes shows what the code
you are sending can still become — e.g. after `-..` it shows `= d   .:b  -:x`
(stop now for *d*, one more dot for *b*, one more dash for *x*).

- Keep the printed cheat sheet next to you (see below).
- Start with the short letters: `.` e, `-` t, `..` i, `.-` a, `-.` n, `--` is
  Backspace, `..--` Space, `.-.-` Enter.
- When letters start coming out cut in two, you are pausing too long inside a
  letter — slow down a little, or raise `ACCEPT_DELAY`.
- As you get faster, lower `ACCEPT_DELAY` in `config.txt` step by step
  (0.4, 0.3, 0.25 — practised users type at 0.2) and `LONG_PRESS` to 1.0. Turn
  hints off in the right-click menu when you no longer need them.

## Settings window

Right-click the SwitchMorse window → **Settings...**, or send the *settings*
code (`...-.-.` in Base). Its tabs:

| Tab | What's on it |
|---|---|
| Keyboard, Mouse, Macros, Base | the codes of each group (below) |
| Speed | Learning / Comfortable / Fast, each timing with − / + buttons, a practice box, how typing behaves |
| Switches | which switches; DOT and DASH light up as you press them; the two keyboard keys; the port |
| Window | always on top, title bar, hints, see-through, sound; put the window back where it can be seen |
| Passwords | the values that `secret NAME` codes type |
| Cheat sheet | make it and open it, or make a PDF |

A change is saved to `config.txt` (only that line) and used at once.

**Changing codes:** one tab per group lists every code and what it does.
**Add a new code**, **Change this code** or **Delete this code**:

- **Code** — type the dots and dashes, or press **Record from the switches** and
  send the code: it goes into the box instead of being typed.
- **Does** — pick what it does (a letter, a key or combination, a phrase, a
  password, a mouse action...) from the lists.
- Clashes are shown before saving ("already used here for n", "Base uses this
  code"); Save then asks a second time. Delete asks a second time too.
- Each change is saved straight away (only that line of `morse_map.txt`
  changes; a backup is kept) and works at once. **Undo last change** takes it back.

Everything works from the keyboard — Tab / Shift+Tab to move, Enter or Space to
press, Ctrl+Tab for the next tab — so it can be used with SwitchMorse itself.
It also opens without SwitchMorse running (`pythonw app\settings_window.py`),
but then can't record.

## Codes

All the codes are in **`app\morse_map.txt`**, one per line, with a guide at the
top — the same codes as AeroMorse. On first start it is made from
`app\morse_map.example.txt`; after that it is yours to change (updates never
overwrite it). Save it and SwitchMorse uses the new codes within a second — no
restart. A copy of the old file goes to `Backups\` (the newest 10) whenever
SwitchMorse itself changes it.

**Cheat sheet:** a ready-made one for the standard codes is in `docs\` —
[SwitchMorse Cheat Sheet.pdf](docs/SwitchMorse%20Cheat%20Sheet.pdf) to print
(one page per group) and
[SwitchMorse Cheat Sheet.html](docs/SwitchMorse%20Cheat%20Sheet.html) (download
and open it in a browser; click a row to hear its tones). For a sheet of *your*
codes, run `py tools\make_cheatsheet.py` (or **Make cheat sheet.bat** in your
work folder): it writes **SwitchMorse Cheat Sheet.html** next to your map. Run
it again after changing the map.

| Code | Does |
|---|---|
| `........` | Keyboard group |
| `--------` | Mouse group |
| `....----` | Macros group (phrases and passwords) |
| `-.-.-.-.` | Pause / start again |
| `.-.-.-.-` | Release everything (keys, buttons, drag) |
| hold 1 second | Next group |

After a right-click, the pointer steps into the menu by itself
(`RIGHT_CLICK_MOVE_RIGHT` in `config.txt`).

## Passwords (Macros group)

A line like `.-   secret name` types what is saved under *name*. Set the values
in the **Passwords** window (right-click the SwitchMorse window →
**Passwords...**). They are stored encrypted for your Windows account in
`%APPDATA%\SwitchMorse\secrets.dat` — never in the map, the window or git. On a
new PC they have to be entered again.

## Admin windows and UAC prompts

Windows doesn't let an ordinary program type into a window running as
administrator (e.g. Task Manager, some installers and camera apps) or into a
UAC "Do you want to allow…" prompt. While one of those is in front, SwitchMorse
hands control back to the AeroMorse, which types and moves the mouse itself
(about a 2-second switch-over), and takes over again when you leave it. With
the Trinkey there is nothing to hand back to: the window warns instead.

## Settings

`config.txt` (in your work folder; every setting and its default is in
`app\config.txt`): timing (`ACCEPT_DELAY`), mouse speed, which switches to
use (`INPUT`), and more — one per line, each explained there. A line with a
mistake is left out and the window says so. A change is used within a second
of saving — no restart.

## For developers

- `app\` — the program: `switchmorse.py` (main), `switches.py` (Trinkey /
  AeroMorse input), `decoder.py`, `actions.py`, `sendinput.py`, `mapload.py`,
  `blocked.py`, `secrets_store.py`, `secrets_window.py`, `window.py`,
  `sound.py`, `hints.py`, `settings_window.py`, `filesave.py` (saving the map and settings, with backups).
- `tools\test_decode.py`, `tools\test_switches.py`, `tools\test_freeze.py`,
  `tools\test_keys.py`, `tools\test_settings.py` — tests (no hardware needed).
- `tools\convert_map.py` — turns an AeroMorse `morse_map.py` into `morse_map.txt`.
- `tools\build_exe.py` — builds `dist\SwitchMorse\SwitchMorse.exe` and a zip
  (`pip install pyinstaller pillow`), and the installer from
  `installer\SwitchMorse.iss` when [Inno Setup 6](https://jrsoftware.org/isinfo.php)
  is installed. `SwitchMorse.exe --selftest out.txt` checks a build without
  opening a window.
- `DESIGN.md` — how it works, and why it is built that way.

## Licence

**Free for any non-commercial use** under the
[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)
(see `LICENSE`). Use it, share it and change it at home, at school, in a
charity, hospital or care home. Do not sell it or use it to make money
without asking first. Versions up to 0.9.1 were released under the MIT licence.
