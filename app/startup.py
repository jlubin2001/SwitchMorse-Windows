# SwitchMorse Windows - startup.py
# "Start SwitchMorse when I sign in": a SwitchMorse shortcut in the Startup
# folder - the same one the installer and "Start at sign-in - ON.bat" make.
# Task Manager's Startup apps can switch it off without deleting it (a value
# under StartupApproved); on() clears that too, so the box here tells the truth.
import os
import subprocess
import sys

NAME = "SwitchMorse.lnk"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"


def folder():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup")


def _approved(delete=False):
    """False if Task Manager has switched the shortcut off (first byte 2 = on, 3 = off)."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            if delete:
                winreg.DeleteValue(k, NAME)
                return True
            data, _ = winreg.QueryValueEx(k, NAME)
            return not data or data[0] in (0, 2)
    except OSError:
        return True


def is_on(where=None):
    return os.path.exists(os.path.join(where or folder(), NAME)) and (where is not None or _approved())


def target():
    """(program, arguments, start-in folder) that start this SwitchMorse."""
    if getattr(sys, "frozen", False):
        return sys.executable, "", os.path.dirname(sys.executable)
    app = os.path.dirname(os.path.abspath(__file__))
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return (pyw if os.path.exists(pyw) else sys.executable,
            '"%s"' % os.path.join(app, "switchmorse.py"), app)


def on(where=None):
    exe, args, cwd = target()
    lnk = os.path.join(where or folder(), NAME)
    q = lambda s: "'" + s.replace("'", "''") + "'"       # a PowerShell string
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut(%s); $s.TargetPath = %s; "
          "$s.Arguments = %s; $s.WorkingDirectory = %s; "
          "$s.Description = 'SwitchMorse - Morse code keyboard and mouse'; $s.Save()"
          % (q(lnk), q(exe), q(args), q(cwd)))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                   timeout=30, creationflags=0x08000000)
    if not where:
        _approved(delete=True)
    if not os.path.exists(lnk):
        raise OSError("the shortcut was not made")


def off(where=None):
    lnk = os.path.join(where or folder(), NAME)
    if os.path.exists(lnk):
        os.remove(lnk)
