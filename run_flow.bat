@echo off
cd /d "%~dp0"

:: Try pythonw first (runs silently, no CMD window)
where pythonw >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw flow_local.py
    exit
)

:: Fallback: use python with a VBS trick to hide the window
echo Set WshShell = CreateObject("WScript.Shell") > "%temp%\run_hidden.vbs"
echo WshShell.Run "python ""%~dp0flow_local.py""", 0, False >> "%temp%\run_hidden.vbs"
wscript "%temp%\run_hidden.vbs"
del "%temp%\run_hidden.vbs"
