
"""
Small callback helpers shared across callback modules.
"""

from dash import Input, Output, callback
from dash.exceptions import PreventUpdate

from utils.native_dialog import pick_folder


def register_folder_browse_callback(input_id: str):
    """Wire a folder_picker()'s Browse button to a native Finder dialog."""

    @callback(
        Output(input_id, "value"),
        Input(f"{input_id}-browse-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def browse(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        path = pick_folder()
        if path is None:
            raise PreventUpdate
        return path
