"""
Oyster – Multi-Camera CCTV Facial Recognition System
Entry point: starts the Flask server in a background thread and opens the
default browser so the user can interact with the UI immediately.
Double-clicking the compiled .exe will launch everything automatically.
"""

import os
import sys
import threading
import webbrowser
import time

# Resolve base directory whether running as script or PyInstaller bundle
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    # Tell the app where the bundled resources live
    os.environ["OYSTER_BASE_DIR"] = BASE_DIR
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    os.environ["OYSTER_BASE_DIR"] = BASE_DIR

os.chdir(BASE_DIR)

from app import create_app  # noqa: E402  (import after path setup)

HOST = "0.0.0.0"
PORT = 5000
URL = f"http://127.0.0.1:{PORT}"


def _open_browser():
    """Wait briefly for Flask to start, then open the browser."""
    time.sleep(2)
    webbrowser.open(URL)


def main():
    app = create_app()

    # Open browser in a daemon thread so it doesn't block shutdown
    browser_thread = threading.Thread(target=_open_browser, daemon=True)
    browser_thread.start()

    print(f"[Oyster] Server running at {URL}")
    print("[Oyster] Press Ctrl+C to stop.")

    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
