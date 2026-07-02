
"""
Native macOS "choose folder" dialog, used so folder-path fields can be
filled by browsing instead of typing a path. Only works when the app
runs on the same machine as the browser (i.e. localhost).
"""

from __future__ import annotations
import subprocess


def pick_folder(prompt: str = "Select a folder") -> str | None:
    """Open a native Finder folder-picker dialog. Returns the chosen
    absolute path, or None if the user cancelled."""
    script = f'POSIX path of (choose folder with prompt "{prompt}")'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()
