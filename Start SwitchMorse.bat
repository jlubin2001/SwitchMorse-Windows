@echo off
rem Starts SwitchMorse Windows with no console window. Right-click its
rem window and choose "Quit SwitchMorse" (or click its X) to close it.
rem Uses pythonw if it is on the PATH, otherwise the Python launcher (pyw).
cd /d "%~dp0app"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0app\switchmorse.py"
) else (
    start "" pyw -3 "%~dp0app\switchmorse.py"
)
