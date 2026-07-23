import os
import sys
import json
import subprocess

def agent_scraping_skill(url: str) -> dict:
    """
    Safe, isolated scraping tool executed cleanly within your existing venv.
    Executes the micro_scraper.py using the exact same venv Python executable.

    Returns {"status": "success", "markdown": ...} for the fetched page. There is no
    selector/CSS-extraction path: micro_scraper returns the page markdown and every caller
    parses that. A `selectors` argument used to exist here and was passed through to the
    subprocess, but micro_scraper never used it — so it was a silent no-op and was removed.
    """
    # Force the script to execute using your CURRENT venv's python binary
    venv_python = sys.executable

    # Path to your micro-scraper script
    script_path = os.path.join(os.path.dirname(__file__), "micro_scraper.py")

    try:
        # Run as a separate operating system process capped by a hard timeout
        process = subprocess.run(
            [venv_python, script_path, url],
            capture_output=True,
            text=True,
            # text=True alone decodes with the SYSTEM codec (cp1252 on Windows), which
            # raises UnicodeDecodeError on the UTF-8 Arabic the scraper returns — the page
            # fetches fine and the result is then lost in the pipe. Decode explicitly.
            encoding="utf-8",
            errors="replace",
            timeout=90  # Safety boundary: prevents hangs. Browser cold-start alone is ~5-15s.
        )
        
        # Parse the clean JSON stdout returned by crawl4ai
        if process.stdout:
            try:
                return json.loads(process.stdout)
            except json.JSONDecodeError:
                return {"status": "error", "message": f"Failed to parse JSON. Stdout: {process.stdout}"}
        else:
            return {"status": "error", "message": f"Scraper crashed: {process.stderr}"}
            
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Scraping task timed out. Process killed safely."}
