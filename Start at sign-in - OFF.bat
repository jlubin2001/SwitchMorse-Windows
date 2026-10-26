@echo off
rem SwitchMorse Windows - stop starting by itself at sign-in.
rem Removes the "SwitchMorse" shortcut from your Startup folder. Nothing else
rem is changed; you can still start it with "Start SwitchMorse.bat".
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SwitchMorse.lnk"
if exist "%LNK%" (
    del "%LNK%"
    echo SwitchMorse will no longer start by itself at sign-in.
) else (
    echo SwitchMorse was not set to start at sign-in.
)
timeout /t 5 >nul
