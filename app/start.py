#!/usr/bin/env python3
"""
Simple launcher for the AI Usage Logger.
Handles venv setup, dependency installation, and browser opening.
Works on Windows, macOS, and Linux.
"""

import os
import sys
import subprocess
import webbrowser
import time
import platform
from pathlib import Path

def create_venv():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path("venv")
    if venv_path.exists():
        print("[OK] Virtual environment found")
        return

    print("Creating virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", "venv"])
    print("[OK] Virtual environment created")

def get_venv_python():
    """Get path to Python executable in venv (OS-specific)."""
    venv_path = Path("venv")
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"

def install_dependencies():
    """Install required packages into venv."""
    python_exe = get_venv_python()

    # Check if packages are already installed
    try:
        subprocess.check_output(
            [str(python_exe), "-c", "import flask, yaml"],
            stderr=subprocess.DEVNULL
        )
        print("[OK] Dependencies already installed")
        return
    except subprocess.CalledProcessError:
        pass

    print("Installing dependencies (Flask, PyYAML)...")
    subprocess.check_call([str(python_exe), "-m", "pip", "install", "-q", "flask", "pyyaml"])
    print("[OK] Dependencies installed")

def start_server():
    """Start Flask development server."""
    python_exe = get_venv_python()

    print("\n" + "="*60)
    print("Starting AI Usage Logger...")
    print("Opening http://localhost:5000 in your browser")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")

    # Open browser after a brief delay to let server start
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:5000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # CREATE_NO_WINDOW keeps this from popping a second console: harmless
    # when we already have one (inherits it), and required when launched
    # windowless (e.g. via Start.vbs) so Windows doesn't allocate
    # a fresh one for the child process.
    creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0

    # Pass sys.stdout/stderr explicitly rather than relying on handle
    # inheritance: under pythonw (windowless) the inherited console handle
    # is invalid, which crashes the child the instant it tries to print().
    # sys.stdout/stderr here are always real, valid streams by this point
    # (either the normal console, or the log file set up below).
    subprocess.call(
        [str(python_exe), "app.py"],
        creationflags=creationflags,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

def show_error_box(message):
    """Best-effort native error dialog for headless (no-console) launches."""
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "AI Usage Logger - Error", 0x10)
        except Exception:
            pass

if __name__ == "__main__":
    # Always run relative to this script's own folder, regardless of how
    # (or from where) it was launched.
    os.chdir(Path(__file__).resolve().parent)

    # Under pythonw.exe (used by Start.vbs for a windowless launch)
    # there is no console, so sys.stdout/stderr are None. Redirect to a
    # log file so print() doesn't crash and errors are still recoverable.
    headless = sys.stdout is None
    if headless:
        log_file = open("launch_log.txt", "a", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"\n--- Launch at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    try:
        create_venv()
        install_dependencies()
        start_server()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nIf you're having trouble, try:")
        print("  - Deleting the 'venv' folder and running start.py again")
        print("  - Making sure Python 3.7+ is installed")
        if headless:
            show_error_box(
                f"AI Usage Logger failed to start:\n\n{e}\n\n"
                f"See launch_log.txt in this folder for details."
            )
        sys.exit(1)
