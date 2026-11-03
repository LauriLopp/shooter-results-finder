@echo off
REM Start the athlete results finder in your browser (Windows).
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. Install it from https://docs.astral.sh/uv/ and run this file again.
  pause
  exit /b 1
)
uv run results-scraper
pause
