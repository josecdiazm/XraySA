
"""
Small layout helpers shared across tabs.
"""

from dash import dcc
import dash_bootstrap_components as dbc


def folder_picker(input_id: str, placeholder: str = "/path/to/folder"):
    """A folder-path text input paired with a native Finder 'Browse...' button.

    The Browse button's id is f"{input_id}-browse-btn"; a callback should
    set the Input's value from utils.native_dialog.pick_folder().
    """
    return dbc.InputGroup([
        dbc.Input(id=input_id, type="text", placeholder=placeholder),
        dbc.Button("📁 Browse…", id=f"{input_id}-browse-btn", color="secondary", outline=True),
    ])
