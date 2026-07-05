
"""
Native "choose folder" dialog, used so folder-path fields can be filled
by browsing instead of typing a path. Only works when the app runs on
the same machine as the browser (i.e. localhost).

Uses tkinter's filedialog rather than an OS-specific tool (e.g.
osascript, which is macOS-only) — on Windows and macOS this calls the
platform's actual native folder browser; on Linux it falls back to a
generic Tk-styled dialog absent a desktop-specific integration library.

Tkinter windows must be created on a process's main thread (strictly
enforced on macOS's Cocoa backend); Flask/Dash handles each callback on
a worker thread, so creating the Tk window directly in-process can
silently fail to appear and hang that request forever, freezing the
whole app (since the dev server handles one request at a time). Instead
this spawns a short-lived subprocess dedicated to just the dialog —
that subprocess gets its own real main thread, so it behaves the same
regardless of which thread triggered the callback.
"""

from __future__ import annotations
import subprocess
import sys

_DIALOG_SCRIPT = """
import sys
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askdirectory(title=sys.argv[1])
print(path)
"""


def pick_folder(prompt: str = "Select a folder") -> str | None:
    """Open a native folder-picker dialog in a dedicated subprocess.
    Returns the chosen absolute path, or None if the user cancelled
    (or the dialog couldn't be shown, e.g. tkinter isn't available)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _DIALOG_SCRIPT, prompt],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    path = result.stdout.strip()
    return path or None
