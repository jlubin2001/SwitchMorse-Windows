# SwitchMorse Windows - make_cheatsheet.py
# Makes "SwitchMorse Cheat Sheet.html" from morse_map.txt, in the look of the
# AeroMorse cheat sheet: one page per group, dots and dashes drawn large, keys
# as key caps, commands as coloured badges - made to be read at a glance and
# printed (open it, Ctrl+P; one group per sheet). Click a row to hear its tones.
#
#   py tools\make_cheatsheet.py          (or "Make cheat sheet.bat" in your work folder)
#   py tools\make_cheatsheet.py --example   (docs\ copy, from the example map)
#
# Written into your work folder, next to the map it is made from. Secret codes
# show their NAME only - never the saved value.
import html
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import mapload  # noqa: E402
import paths  # noqa: E402

_work = paths.work_folder()
OUT = os.path.join(_work if _work != paths.APP else ROOT, "SwitchMorse Cheat Sheet.html")

TITLES = {0: "Base: works in every group", 1: "Keyboard", 2: "Mouse & Windows", 3: "Macros"}
GROUP_BADGE = {1: "Keyboard", 2: "Mouse", 3: "Macros"}
KEY_SYMBOLS = {"Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
               "Enter": "⏎", "Tab": "⇥", "Backspace": "⌫", "Space": "Space",
               "Esc": "Esc", "Win": "⊞ Win", "RWin": "⊞ RWin",
               "Keypad Forward Slash": "Keypad /", "Keypad Period": "Keypad .",
               "Keypad Asterisk": "Keypad *", "Keypad Minus": "Keypad -", "Keypad Plus": "Keypad +",
               "Equals": "=", "Minus": "-"}
MOUSE_CMDS = {"mmove", "mclick", "mdrag", "mslow", "mfast", "mcenter"}
FIT_ROWS, DENSE_ROWS, FIT_MIN = 16, 23, 0.78     # rows per printed column, as AeroMorse


def key_text(label):
    """'Ctrl+Alt+Left' -> 'Ctrl + Alt + ←' with arrow / Enter symbols."""
    return " + ".join(KEY_SYMBOLS.get(p, p) for p in label.split("+"))


def row_for(a):
    """(text, badge class or None) for one Action, as on the AeroMorse sheet."""
    if a.kind == "char":
        t = a.text.upper() if len(a.text) == 1 and a.text.isalpha() else a.label
        return t, None
    if a.kind == "text":
        return a.label, None
    if a.kind == "secret":
        return "\U0001F512 " + a.text, "sec"
    if a.kind == "mod":
        return key_text(a.label) + " (sticky)", "mod"
    if a.kind == "vk":
        return a.label, "med"
    if a.kind == "group":
        return "→ " + GROUP_BADGE.get(a.group, str(a.group)), "grp"
    if a.kind == "key":
        t = key_text(a.label)
        mods = ("Ctrl", "Shift", "Alt", "Win", "RCtrl", "RShift", "RAlt", "RWin", "Caps Lock",
                "Num Lock", "Scroll Lock", "Print Screen", "Tap")
        return t, ("mod" if any(m in a.label for m in mods) else None)
    if a.kind == "cmd":
        if a.cmd[0] in MOUSE_CMDS:
            return "\U0001F5B1︎ " + a.label, "mse"
        return a.label, "sys"
    return a.label, None


def natural(text):
    """Sort key with numbers in number order: F2 before F10."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def rank(text, cls):
    order = {"mse": 50, "med": 51, "sec": 53, "mod": 54, "sys": 55, "grp": 56}
    if cls in order:
        return order[cls]
    if text in ("←", "↑", "↓", "→"):
        return 4
    if len(text) == 1 and text.isalpha():
        return 1
    if len(text) == 1 and text.isdigit():
        return 2
    if len(text) == 1:
        return 3
    return 5


def build(map_path=None, out=None):
    out = out or OUT
    codes, problems = mapload.load(map_path)
    groups = {}
    for (g, n, p), a in codes.items():
        text, cls = row_for(a)
        groups.setdefault(g, []).append((mapload.code_str(n, p), text, cls))
    arrows = {"←": 1, "↑": 2, "↓": 3, "→": 4}
    pages = []
    for g in sorted(groups):
        rows = sorted(groups[g], key=lambda r: (rank(r[1], r[2]), arrows.get(r[1], 0),
                                                 natural(r[1]), len(r[0])))
        cols = 3 if g == 1 else 2
        need = -(-len(rows) // cols)
        extra, style = "", ""
        if need > FIT_ROWS and DENSE_ROWS / need >= FIT_MIN:
            extra = " dense"
            if need > DENSE_ROWS:
                style = ' style="zoom:%.3f"' % (DENSE_ROWS / need)
        items = []
        for code, text, cls in rows:
            seq = "".join("<dot></dot>" if c == "." else "<dash></dash>" for c in code)
            # only a long LABEL is made smaller, so it still fits beside its code
            limit = 9 if cols == 3 else 14
            small = (' style="font-size:%s"' % ("0.8em" if len(text) > limit + 6 else "0.9em")
                     if len(text) > limit else "")
            if cls:
                label = '<cmd class="%s"%s>%s</cmd>' % (cls, small, html.escape(text))
            else:
                label = "<keybd%s>%s</keybd>" % (small, html.escape(text))
            items.append('<div class="item" data-morse="%s" title="Click to hear its Morse tones">'
                         '<div class="morse-seq">%s</div><div class="key-output">%s</div></div>'
                         % (code, seq, label))
        legend = LEGEND_PRINT if not pages else ""
        pages.append('<div class="page"><h2>%s</h2><div class="columns cols-%d%s"%s>%s</div>%s</div>'
                     % (html.escape(TITLES.get(g, "Group %d" % g)), cols, extra, style,
                        "\n".join(items), legend))
    page = TEMPLATE.replace("{{PAGES}}", "\n".join(pages)).replace(
        "{{DATE}}", time.strftime("%Y-%m-%d")).replace("{{COUNT}}", str(len(codes)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    for p in problems:
        print("map note:", p)
    print("wrote", out, "-", len(codes), "codes")


LEGEND_ITEMS = """<span class="legend-item"><dot></dot> dot (sip / dot switch) &nbsp; <dash></dash> dash (puff / dash switch)</span>
    <span class="legend-item"><keybd>Key</keybd> key or text it types</span>
    <span class="legend-item"><cmd class="grp">→ Group</cmd> change group</span>
    <span class="legend-item"><cmd class="mse">\U0001F5B1︎ Mouse</cmd> mouse</span>
    <span class="legend-item"><cmd class="mod">Mod</cmd> Ctrl / Shift / Alt / Win</span>
    <span class="legend-item"><cmd class="sec">\U0001F512 Secret</cmd> password (name only)</span>
    <span class="legend-item"><cmd class="med">Media</cmd> media / app key</span>
    <span class="legend-item"><cmd class="sys">System</cmd> repeat, pause...</span>"""

LEGEND_PRINT = """<div class="legend-print"><h3>Key to the colours</h3>
  <div class="legend-print-strip">%s</div>
  <p class="tip">Hold a press for the long-press time (1.5 s by default), then let go = next group.
  Send <b>........</b> for Keyboard, <b>--------</b> for Mouse, <b>....----</b> for Macros,
  <b>.-.-.-</b> to bring the SwitchMorse window to the front.</p></div>""" % LEGEND_ITEMS

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SwitchMorse Cheat Sheet</title>
<style>
  /* The look of the AeroMorse cheat sheet (aeromorse_cheatsheet.htm). */
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         margin: 20px; background: #e9ecef; color: #333; }
  h2 { text-align: center; border-bottom: 2px solid #ccc; padding-bottom: 10px; margin: 0 0 20px; color: #2c3e50; }
  dot  { width: 15px; height: 15px; display: inline-block; background-color: #7806ec;
         border-radius: 50%; vertical-align: middle; }
  dash { width: 16px; height: 9px; display: inline-block; background-color: #009832;
         border-radius: 2px; vertical-align: middle; }
  cmd { border-radius: 10px; display: inline-block; font-size: 1.0em; font-weight: bold;
        padding: 0.15em 0.65em; white-space: nowrap; border: 1px solid transparent; }
  cmd.grp { background: #d4edda; color: #155724; border-color: #c3e6cb; }
  cmd.mse { background: #f8d7da; color: #721c24; border-color: #f5c6cb; }
  cmd.med { background: #cce5ff; color: #004085; border-color: #b8daff; }
  cmd.mod { background: #fff3cd; color: #856404; border-color: #ffc107; }
  cmd.sys { background: #e2e3e5; color: #383d41; border-color: #d6d8db; }
  cmd.sec { background: #d6d8db; color: #1b1e21; border-color: #b9bcc0; }
  keybd { border: 1px solid #ccc; border-radius: 3px;
          box-shadow: 0 1px 0 rgba(0,0,0,0.2), 0 0 0 2px #fff inset; color: #000; display: inline-block;
          font-family: Consolas, "Lucida Console", "Courier New", monospace; line-height: 1.4em;
          padding: 0.1em 0.6em; text-shadow: 0 1px 0 #fff; white-space: nowrap; font-size: 1.2em;
          font-weight: bold; background: #f8f9fa; }
  .head { background: white; padding: 16px 20px; margin: 0 auto 20px; max-width: 1000px; border-radius: 8px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; }
  .head h1 { margin: 0 0 6px; font-size: 1.5em; color: #2c3e50; }
  .head p { margin: 4px 0; color: #555; }
  button.print-btn { background: #007bff; color: white; border: none; padding: 10px 22px; font-size: 16px;
                     border-radius: 4px; cursor: pointer; margin-top: 8px; }
  .legend { margin: 0 auto 15px; max-width: 1000px; display: flex; flex-wrap: wrap; gap: 12px;
            justify-content: center; background: white; padding: 12px 20px; border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.9em; }
  .page { background: white; padding: 40px; margin: 0 auto 30px; max-width: 1000px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-radius: 8px; }
  .columns { column-gap: 40px; column-rule: 1px solid #eee; }
  .cols-3 { column-count: 3; }
  .cols-2 { column-count: 2; }
  .columns.dense .item { margin-bottom: 3px; padding-bottom: 2px; }
  .item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
          break-inside: avoid; border-bottom: 1px dashed #f0f0f0; padding: 0 2px 6px; cursor: pointer;
          border-radius: 4px; }
  .item:hover { background: #f0f4ff; }
  .morse-seq { display: flex; align-items: center; gap: 3px; flex-shrink: 0; }
  .key-output { flex-grow: 1; text-align: right; display: flex; justify-content: flex-end;
                align-items: center; margin-left: 10px; }
  .legend-print { display: none; }
  .tip { text-align: center; font-size: 0.85em; color: #444; margin: 10px 0 0; }
  @media print {
    body { background: white; margin: 0; -webkit-print-color-adjust: exact !important;
           print-color-adjust: exact !important; }
    .head, .legend { display: none !important; }
    .page { box-shadow: none; margin: 0; padding: 10px 0; max-width: 100%; page-break-after: always;
            border-radius: 0; }
    .columns { column-gap: 20px; }
    .item { page-break-inside: avoid; cursor: default; }
    .legend-print { display: block; margin-top: 22px; padding-top: 12px; border-top: 2px solid #ccc;
                    page-break-inside: avoid; }
    .legend-print h3 { text-align: center; margin: 0 0 10px; color: #2c3e50; font-size: 1em; }
    .legend-print-strip { display: flex; flex-wrap: wrap; gap: 10px 18px; justify-content: center; }
    .legend-print-strip .legend-item { font-size: 0.8em; }
  }
</style>
</head>
<body>
  <div class="head">
    <h1>SwitchMorse Cheat Sheet</h1>
    <p>{{COUNT}} codes from your morse_map.txt, made {{DATE}}. Click a row to hear its Morse tones.</p>
    <button class="print-btn" onclick="window.print()">&#x1F5A8;&#xFE0E; Print (one group per sheet)</button>
  </div>
  <div class="legend">
    {{LEGEND}}
  </div>
  {{PAGES}}
<script>
  /* Click a row: play its dots and dashes (dot higher, dash lower - as SwitchMorse's sound). */
  let ctx = null;
  function play(code) {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    let t = ctx.currentTime + 0.05;
    for (const c of code) {
      const len = c === '.' ? 0.12 : 0.36;
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = c === '.' ? 1200 : 800;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.25, t + 0.005);
      g.gain.setValueAtTime(0.25, t + len - 0.005);
      g.gain.linearRampToValueAtTime(0, t + len);
      o.connect(g).connect(ctx.destination);
      o.start(t); o.stop(t + len);
      t += len + 0.1;
    }
  }
  document.querySelectorAll('.item').forEach(el =>
    el.addEventListener('click', () => play(el.dataset.morse)));
</script>
</body>
</html>
""".replace("{{LEGEND}}", LEGEND_ITEMS)


if __name__ == "__main__":
    if "--example" in sys.argv:
        # the sheet that ships with SwitchMorse: made from the example map
        build(os.path.join(ROOT, "app", "morse_map.example.txt"),
              os.path.join(ROOT, "docs", "SwitchMorse Cheat Sheet.html"))
    else:
        build()
