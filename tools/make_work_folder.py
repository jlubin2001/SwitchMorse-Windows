# SwitchMorse Windows - make_work_folder.py
# Makes your own work folder: just the files you use, kept apart from the
# program. SwitchMorse then reads your map and settings from there.
#
#   py tools\make_work_folder.py "D:\Documents\SwitchMorse"
#
# In the work folder:
#   morse_map.txt            your codes (your current map, or the example)
#   config.txt               your settings (only what you change matters; the
#                            program's own app\config.txt supplies the rest)
#   Start SwitchMorse.bat    Start at sign-in - ON.bat / - OFF.bat
#   Passwords.bat            Make cheat sheet.bat
#   README.txt
# Files already in the folder are never overwritten. The program learns where
# the folder is from app\workfolder.txt (written here; delete it to go back).
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

FIND_PY = r'''where pythonw >nul 2>nul
if %errorlevel%==0 (set "PY=pythonw") else (set "PY=pyw -3")'''

BATS = {
    "Start SwitchMorse.bat": r'''@echo off
rem Start SwitchMorse (the program is in "{root}").
call "{root}\Start SwitchMorse.bat"
''',
    "Start at sign-in - ON.bat": r'''@echo off
rem SwitchMorse starts by itself when you sign in to Windows.
call "{root}\Start at sign-in - ON.bat"
''',
    "Start at sign-in - OFF.bat": r'''@echo off
rem SwitchMorse no longer starts by itself at sign-in.
call "{root}\Start at sign-in - OFF.bat"
''',
    "Passwords.bat": r'''@echo off
rem The SwitchMorse Passwords window: set what "secret NAME" codes type.
''' + FIND_PY + r'''
start "" %PY% "{root}\app\secrets_window.py"
''',
    "Make cheat sheet.bat": r'''@echo off
rem Makes "SwitchMorse Cheat Sheet.html" here from morse_map.txt, then opens it.
where python >nul 2>nul
if %errorlevel%==0 (python "{root}\tools\make_cheatsheet.py") else (py -3 "{root}\tools\make_cheatsheet.py")
start "" "%~dp0SwitchMorse Cheat Sheet.html"
''',
}

README = """SwitchMorse - your work folder
==============================

Your own SwitchMorse files. The program itself is in:
  {root}

morse_map.txt
  Your codes, one per line - open it in Notepad. The guide at the top says
  what a line can do. Save it and SwitchMorse uses the new codes within a
  second. If a line has a mistake, it is left out and listed in
  morse_map_problems.txt here.

config.txt
  Your settings (timing, mouse speed, which switches...), one per line - open
  it in Notepad. Each one is explained in the file. A change is used within a
  second of saving. A line with a mistake is left out and listed in
  morse_map_problems.txt.

Start SwitchMorse.bat              start it now
Start at sign-in - ON.bat / OFF    start it every time you sign in, or not
Passwords.bat                      set what "secret NAME" codes type (the
                                   values are encrypted for your Windows
                                   account, never stored in this folder)
Make cheat sheet.bat               a printable list of all your codes

Handy codes (work in every group)
  ........   Keyboard          --------   Mouse          ....----   Macros
  .-.-.-     bring the SwitchMorse window to the front
  -.-.-.-.   pause / start again          .-.-.-.-   release everything
"""


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    work = os.path.abspath(sys.argv[1])
    if os.path.normcase(work).startswith(os.path.normcase(ROOT)):
        print("Choose a folder outside the program folder.")
        return 1
    os.makedirs(work, exist_ok=True)
    made = []

    def write(name, text):
        p = os.path.join(work, name)
        if os.path.exists(p):
            return
        with open(p, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        made.append(name)

    def copy(name, src):
        p = os.path.join(work, name)
        if not os.path.exists(p) and os.path.exists(src):
            shutil.copyfile(src, p)
            made.append(name)

    # the map: the one in use now, else the example
    current = os.path.join(APP, "morse_map.txt")
    copy("morse_map.txt", current if os.path.exists(current)
         else os.path.join(APP, "morse_map.example.txt"))
    write("config.txt", open(os.path.join(APP, "config.txt"), encoding="utf-8").read().replace(
        "# This copy, in the program's app folder, holds every setting with its default.\n"
        "# Your own copy is config.txt in your work folder (tools\\make_work_folder.py):\n"
        "# whatever you set there wins; anything you leave out uses the default here.",
        "# This is YOUR copy (in your work folder). Whatever you set here wins; a\n"
        "# setting you delete uses the default from the program's app\\config.txt."))
    for name, text in BATS.items():
        write(name, text.format(root=ROOT))
    write("README.txt", README.format(root=ROOT))

    with open(os.path.join(APP, "workfolder.txt"), "w", encoding="utf-8") as f:
        f.write(work + "\n")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_cheatsheet.py")],
                   capture_output=True)
    print("Work folder: %s" % work)
    print("Made: %s" % (", ".join(made) or "nothing new (all there already)"))
    print("SwitchMorse now reads morse_map.txt and config.txt from there - restart it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
