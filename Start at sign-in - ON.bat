@echo off
rem SwitchMorse Windows - start by itself when you sign in to Windows.
rem Puts a shortcut "SwitchMorse" in your Startup folder (no admin rights
rem needed). Run "Start at sign-in - OFF.bat" to stop it again.
rem Uses pythonw if it is on the PATH, otherwise the Python launcher (pyw).
setlocal
set "APP=%~dp0app"
set "PYW="
set "ARGS="
for /f "delims=" %%p in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%p"
if not defined PYW (
    if exist "%SystemRoot%\pyw.exe" (
        set "PYW=%SystemRoot%\pyw.exe"
        set "ARGS=-3 "
    )
)
if not defined PYW (
    echo Python was not found. Install Python 3 from python.org, then run this again.
    pause
    exit /b 1
)
powershell -NoProfile -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\SwitchMorse.lnk');" ^
  "$s.TargetPath = '%PYW%';" ^
  "$s.Arguments = '%ARGS%\"%APP%\switchmorse.py\"';" ^
  "$s.WorkingDirectory = '%APP%';" ^
  "$s.Description = 'SwitchMorse Windows - Morse code keyboard and mouse';" ^
  "$s.Save()"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SwitchMorse.lnk" (
    echo SwitchMorse will now start by itself when you sign in.
) else (
    echo Something went wrong - the shortcut was not made.
)
timeout /t 5 >nul
