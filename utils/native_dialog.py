
"""
Native "choose folder" dialog, used so folder-path fields can be filled
by browsing instead of typing a path. Only works when the app runs on
the same machine as the browser (i.e. localhost).

Uses tkinter's filedialog rather than an OS-specific tool (e.g.
osascript, which is macOS-only) — on Windows and macOS this calls the
platform's actual native folder browser; on Linux it falls back to a
generic Tk-styled dialog absent a desktop-specific integration library.
"""

from __future__ import annotations


def pick_folder(prompt: str = "Select a folder") -> str | None:
    """Open a native folder-picker dialog. Returns the chosen absolute
    path, or None if the user cancelled (or tkinter isn't available)."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()                    # hide the empty root window
    root.attributes("-topmost", True)  # bring the dialog to the front
    path = filedialog.askdirectory(title=prompt)
    root.destroy()

    return path or None
