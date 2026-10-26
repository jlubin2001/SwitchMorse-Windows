# SwitchMorse Windows - build_exe.py
# Builds SwitchMorse.exe for people without Python:
#   dist\SwitchMorse\                    the program (SwitchMorse.exe + _internal\)
#   dist\SwitchMorse-<version>.zip       the same folder, zipped
#   dist\SwitchMorse-Setup-<version>.exe the installer (only if Inno Setup 6 is
#                                        installed: jrsoftware.org, free)
#
#   py tools\build_exe.py
#
# Needs PyInstaller and Pillow (pip install pyinstaller pillow). The exe keeps
# the user's files in Documents\SwitchMorse (app\paths.py), never next to itself.
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
ICON = os.path.join(BUILD, "switchmorse.ico")
EXTRAS = ["README.md", "LICENSE", "docs/SwitchMorse Cheat Sheet.pdf"]


def version():
    with open(os.path.join(APP, "switchmorse.py"), encoding="utf-8") as f:
        return re.search(r'^VERSION = "([^"]+)"', f.read(), re.M).group(1)


def make_icon():
    """The SwitchMorse icon (a cyan dot and dash on black, as app\\appicon.py
    draws it), as an .ico for the exe and the shortcuts."""
    from PIL import Image, ImageDraw
    big = Image.new("RGBA", (256, 256), "#000000")
    d = ImageDraw.Draw(big)
    s = 256 / 64.0
    d.ellipse([(17 - 8) * s, (32 - 8) * s, (17 + 8) * s, (32 + 8) * s], fill="#00FFFF")
    d.rectangle([31 * s, 26 * s, 57 * s - 1, 38 * s - 1], fill="#00FFFF")
    os.makedirs(BUILD, exist_ok=True)
    big.save(ICON, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def pyinstaller():
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
                    "--name", "SwitchMorse", "--icon", ICON,
                    "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"),
                    "--specpath", BUILD,
                    "--paths", APP, "--paths", os.path.join(ROOT, "tools"),
                    "--hidden-import", "make_cheatsheet",      # imported by name (Cheat sheet tab)
                    "--add-data", os.path.join(APP, "config.txt") + os.pathsep + ".",
                    "--add-data", os.path.join(APP, "morse_map.example.txt") + os.pathsep + ".",
                    os.path.join(APP, "switchmorse.py")], check=True)
    out = os.path.join(DIST, "SwitchMorse")
    for name in EXTRAS:
        shutil.copy(os.path.join(ROOT, name), out)
    return out


def make_zip(folder, ver):
    path = os.path.join(DIST, "SwitchMorse-%s.zip" % ver)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(folder):
            for f in files:
                full = os.path.join(dirpath, f)
                z.write(full, os.path.join("SwitchMorse", os.path.relpath(full, folder)))
    return path


def iscc():
    for pattern in (r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe", r"%ProgramFiles%\Inno Setup 6\ISCC.exe",
                    r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"):
        found = glob.glob(os.path.expandvars(pattern))
        if found:
            return found[0]
    return None


def installer(ver):
    exe = iscc()
    if not exe:
        print("Inno Setup 6 not found - no installer made (the zip is there).")
        return None
    subprocess.run([exe, "/Q", "/DVERSION=" + ver, "/DROOT=" + ROOT,
                    os.path.join(ROOT, "installer", "SwitchMorse.iss")], check=True)
    return os.path.join(DIST, "SwitchMorse-Setup-%s.exe" % ver)


def main():
    ver = version()
    make_icon()
    folder = pyinstaller()
    print("Built", folder)
    print("Zip  ", make_zip(folder, ver))
    setup = installer(ver)
    if setup:
        print("Setup", setup)


if __name__ == "__main__":
    main()
