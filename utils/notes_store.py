"""
Persistent per-element notes for the PTable tab.

Stored as JSON on disk (not just in memory) so notes added through the UI
survive app restarts and get committed to the repo like any other file,
instead of disappearing the moment the server stops.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "ptable_notes.json"


def load_notes() -> dict[str, list[dict]]:
    """Return {symbol: [{"text": ..., "date": ...}, ...]} for all elements with notes."""
    if not _NOTES_PATH.exists():
        return {}
    with open(_NOTES_PATH) as f:
        return json.load(f)


def add_note(symbol: str, text: str) -> None:
    """Append a new timestamped note for `symbol` and persist to disk."""
    notes = load_notes()
    notes.setdefault(symbol, []).append({
        "text": text,
        "date": date.today().isoformat(),
    })
    _NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_NOTES_PATH, "w") as f:
        json.dump(notes, f, indent=2)
