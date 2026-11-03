#!/usr/bin/env bash
# Start the athlete results finder in your browser (Linux / macOS / WSL).
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
# Inside WSL there is no Linux browser: open the page in the Windows browser instead.
if grep -qi microsoft /proc/version 2>/dev/null && command -v explorer.exe >/dev/null 2>&1; then
  (sleep 5; explorer.exe "http://localhost:8501" >/dev/null 2>&1) &
  exec uv run results-scraper --server.headless=true "$@"
fi
exec uv run results-scraper "$@"
