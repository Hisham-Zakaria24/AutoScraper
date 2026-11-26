@echo off
REM AutoScraper - made by Hisham-Zakaria
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || goto :error
)
.venv\Scripts\python.exe -m pip install -q -r requirements.txt || goto :error
.venv\Scripts\python.exe app.py
pause
exit /b 0
:error
echo Setup fail hua. Python 3.9+ install hai aur PATH me hai, check karein.
pause
exit /b 1
