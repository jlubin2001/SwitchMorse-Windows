# SwitchMorse Windows — how it works

A Windows program decodes Morse code from switches or a sip-and-puff device
and turns it into keyboard and mouse input. The switches only report presses;
all timing, decoding and typing happen on the PC.

```
 switches ─► TRRS Trinkey ──USB serial──┐
                                         ├─► SwitchMorse (PC) ──► keyboard + mouse
 sip/puff ─► AeroMorse (PC_HANDOVER) ────┘    decodes Morse,        (SendInput)
                                              shows a small window
```

## Why decode on the PC

| | Decode on the device | Decode on the PC (this) |
|---|---|---|
| Memory / features | small microcontroller limits | none |
| Changing codes | edit, build, copy to the device | edit `morse_map.txt` and save: used within a second |
| Feedback | device screen / LED | a resizable window, sound |
| Passwords | hard on a small device | Windows-encrypted (DPAPI) |
| Sign-in screen, BIOS, other PCs | works | not by itself — see hand-over below |

## Inputs (`app/switches.py`)

- **TRRS Trinkey** with the reporter firmware (`trinkey/`): a second USB serial
  port (CircuitPython `usb_cdc.data`) sends one byte per change — `D`/`d` dot
  down/up, `A`/`a` dash down/up — a `.` heartbeat each second, and `!SMW 0.1`
  when the program connects. Switches are debounced on the Trinkey (a release
  counts after 15 ms of quiet).
- **AeroMorse** (v1.32+, `PC_HANDOVER = True`): the device prints `~HO 0` once a
  second on its normal serial port. SwitchMorse answers with the plain-text line
  `~SMW` twice a second; while those keep coming the device types nothing and
  prints `~HP D/d/A/a` for each sip/puff instead (sip = dot, puff = dash). If
  they stop for 2 s — program closed, crashed, PC asleep — the device types by
  itself again. SwitchMorse writes nothing to a port until it has seen `~HO`,
  never sends Ctrl+C (which would stop a CircuitPython program), and stops
  writing if it sees a traceback.

- **Two keyboard keys** (`app/keyinput.py`, `INPUT = keys`): a low-level
  keyboard hook turns `DOT_KEY` / `DASH_KEY` (default Enter / Space — what most
  USB switch interfaces send) into presses and swallows them. Key-repeats while
  held are ignored; keys SwitchMorse types itself (injected) pass through.

`INPUT = auto` in `config.txt` prefers a Trinkey, then an AeroMorse; keys are
used only when chosen.

## Decoding (`app/decoder.py`)

- A release of the dot switch adds a dot, the dash switch a dash.
- No switch held for `ACCEPT_DELAY` (0.2 s by default) = the code is finished.
- A press held `LONG_PRESS` (1 s) = next group, and drops the code so far.
- A switch that opens for less than `SWITCH_BOUNCE_MS` and closes again is one
  press (sip-and-puff switches can flicker mid-puff).

## Actions (`app/actions.py`, `app/sendinput.py`)

Same behaviour as AeroMorse: sticky modifiers (Ctrl/Shift/Alt/Win apply to the
next key), Shift + arrows keeps extending a selection, `repeat` keeps the last
key or mouse move going until the next press (which only stops it),
`NO_REPEAT_KEYS`, clicks with hold and gap, drag on/off, slow/fast mouse,
pause, release all. Characters are typed by asking Windows which key makes them
on the current keyboard layout (`VkKeyScanEx`), so UK, French, German… layouts
type correctly; characters with no key go in as Unicode.

## Admin windows and UAC (`app/blocked.py`)

Windows silently drops input from an ordinary program into an elevated window
or the UAC secure screen. SwitchMorse checks the foreground window; while one
of those is in front it stops asking the AeroMorse to hand over, so the device
— a real USB keyboard and mouse, never blocked — types by itself, then takes
over again 0.5 s after it is gone. With a Trinkey the window warns instead.

## Its own window

- Never takes the keyboard focus (`WS_EX_NOACTIVATE`) but keeps a taskbar
  button and its own icon / AppUserModelID.
- Holding a mouse button down on a Tk window's own title bar stops the Tk loop
  until it is released — and the release is sent by that loop. So a click on
  SwitchMorse's own window is pressed and released at once, and a drag that
  starts on it holds no button: the window follows the pointer instead.
- If the main loop stops turning anyway, the AeroMorse is handed back.

## The map (`app/morse_map.txt`)

Plain text, one code per line (`-...  b`), with a guide at the top. A bad line
is left out and listed in `morse_map_problems.txt`; everything else loads.
`morse_map.example.txt` ships with the program and is copied to
`morse_map.txt` on first start. `tools/convert_map.py` converts an AeroMorse
`morse_map.py`.

## Passwords (`app/secrets_store.py`, `app/secrets_window.py`)

`secret NAME` codes type text stored in `%APPDATA%\SwitchMorse\secrets.dat`,
encrypted with DPAPI for the Windows account. Values are never shown, logged
or repeated.

## Tests

`tools/test_decode.py` (map, decoder, actions — with a recorder instead of
SendInput), `tools/test_switches.py` (the AeroMorse hand-over protocol on a
pretend serial port), `tools/test_freeze.py` (the program's main loop
freezing), `tools/test_keys.py` (the keyboard-keys input). No hardware needed.
