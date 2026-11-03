"""Find all competition results of shooting athletes across Estonian and international result sites."""

from __future__ import annotations


def main() -> None:
    """Start the browser UI (`results-scraper`)."""
    import sys
    from pathlib import Path

    from streamlit.web import cli as stcli

    app = Path(__file__).with_name("app.py")
    sys.argv = [
        "streamlit",
        "run",
        str(app),
        "--browser.gatherUsageStats=false",
        "--server.headless=false",
        "--server.address=localhost",
        *sys.argv[1:],
    ]
    sys.exit(stcli.main())
