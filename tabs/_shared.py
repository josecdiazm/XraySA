
"""
Small layout helpers shared across tabs.
"""

from dash import dcc, html
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


_SPIN_BTN_STYLE = {
    "border": "1px solid #ced4da", "background": "#f8f9fa", "cursor": "pointer",
    "fontSize": "0.5rem", "lineHeight": "1", "padding": "0px", "width": "14px", "height": "11px",
    "display": "flex", "alignItems": "center", "justifyContent": "center", "color": "#495057",
}


def spin_index_input(value_id: str, idx_id: str):
    """
    Value + index dual input with a RAW-style stacked up/down spin button
    on the index box (steps by one data point) — the q Min/q Max widget
    shared by Scattering 2D & 1D, GI-SWAXS, and Resonant Scattering's Q
    Range panels (and originally the SWAXS Merging tab's per-row controls).

    A paired callback is expected to keep {value_id} and {idx_id} in sync
    and to drive {idx_id}-up / {idx_id}-down's stepping.
    """
    return html.Div([
        dcc.Input(id=value_id, type="number", value=None, step="any",
                   style={"width": "90px", "marginRight": "8px"}),
        dcc.Input(id=idx_id, type="number", value=None, step=1, min=0,
                   style={"width": "55px", "marginRight": "2px"}),
        html.Div([
            html.Button("▲", id=f"{idx_id}-up", n_clicks=0,
                        style={**_SPIN_BTN_STYLE, "borderBottom": "none", "borderRadius": "2px 2px 0 0"}),
            html.Button("▼", id=f"{idx_id}-down", n_clicks=0,
                        style={**_SPIN_BTN_STYLE, "borderRadius": "0 0 2px 2px"}),
        ], style={"display": "flex", "flexDirection": "column"}),
    ], style={"display": "flex", "alignItems": "center"})
