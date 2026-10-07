@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
  echo Install Node.js 22 or newer, then reopen this installer.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Ready. Open OVERLAY.cmd for Scifica or START.cmd for the sandbox.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.10 or newer with Tcl/Tk and pip, then retry.
pause
exit /b 1
