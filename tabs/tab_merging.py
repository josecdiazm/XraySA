
"""
Dash layout for the SWAXS Merging tab: a single RAW-style "Profiles"
workspace — load files (folder or drag-and-drop) into one list, click
rows to select them, tune each row's q range / scale / offset inline,
and Average / Subtract / Merge / Save / Remove whatever's selected. All
per-row interaction and the main plot are rendered by callbacks in
callbacks/callbacks_merging.py from a single dcc.Store; this file only
lays out the static shell.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

from tabs._shared import folder_picker

_PANEL_HEIGHT = 650  # shared height for the scrolling file list and the plot, RAW-style

_SECTION_STYLE = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "6px",
    "padding": "14px 18px",
    "marginBottom": "16px",
}


def _section(title, *children):
    return html.Div(
        [html.H6(title, style={"marginBottom": "12px", "color": "#495057"}), *children],
        style=_SECTION_STYLE,
    )


def _profiles_workspace():
    return _section(
        "📊 Profiles",

        dcc.Store(id="merge-profile-store", data=[]),
        dcc.Store(id="merge-upload-tempdir-store", data=None),

        folder_picker("merge-folder-input", "/path/to/profiles"),
        dbc.Button(
            "Load Folder", id="merge-load-folder-btn",
            color="primary", size="sm", className="mt-2",
        ),
        html.Div(id="merge-folder-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

        dcc.Upload(
            id="merge-upload-files",
            children=html.Div(
                ["Or drag & drop files here, or ", html.A("select files")],
                style={"textAlign": "center", "padding": "14px", "color": "#6c757d"},
            ),
            style={
                "border": "2px dashed #ced4da",
                "borderRadius": "6px",
                "cursor": "pointer",
                "marginTop": "8px",
            },
            multiple=True,
        ),

        html.Div("Exclude files containing (applied at load time):",
                 style={"fontSize": "0.8rem", "color": "#6c757d", "marginTop": "10px"}),
        dcc.Input(
            id="merge-exclude-input", type="text",
            placeholder="e.g. dry, beamstop", debounce=True,
            style={"width": "100%"},
        ),

        html.Hr(),

        dbc.Row([
            # Left: the accumulating file list (its own scrollable panel,
            # matching the plot's height, RAW-style) plus the action buttons.
            dbc.Col([
                html.Div([
                    html.Button(
                        "☐", id="merge-select-all-btn", n_clicks=0,
                        style={
                            "border": "1px solid #ced4da", "background": "#f8f9fa",
                            "cursor": "pointer", "fontSize": "0.85rem", "lineHeight": "1",
                            "padding": "2px 6px", "borderRadius": "3px", "marginRight": "6px",
                        },
                        title="Select all / Deselect all",
                    ),
                    html.Span("Select all", style={"fontSize": "0.75rem", "color": "#6c757d", "marginRight": "14px"}),

                    html.Button(
                        "👁", id="merge-toggle-visible-btn", n_clicks=0,
                        style={
                            "border": "1px solid #ced4da", "background": "#f8f9fa",
                            "cursor": "pointer", "fontSize": "0.85rem", "lineHeight": "1",
                            "padding": "2px 6px", "borderRadius": "3px", "marginRight": "6px",
                        },
                        title="Show/hide all selected",
                    ),
                    html.Span("Show/hide selected", style={"fontSize": "0.75rem", "color": "#6c757d"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),

                html.Div(
                    id="merge-profile-list",
                    style={
                        "height": f"{_PANEL_HEIGHT}px", "overflowY": "auto",
                        "marginBottom": "10px", "border": "1px solid #dee2e6",
                        "borderRadius": "4px", "padding": "6px", "backgroundColor": "#ffffff",
                    },
                ),

                dbc.Row([
                    dbc.Col(dbc.Button("Save", id="merge-save-btn", color="secondary", size="sm", className="w-100"), width=4),
                    dbc.Col(dbc.Button("Average", id="merge-average-btn", color="success", size="sm", className="w-100"), width=4),
                    dbc.Col(dbc.Button("Remove", id="merge-remove-btn", color="danger", size="sm", className="w-100"), width=4),
                ], className="g-2 mb-2"),
                dbc.Row([
                    dbc.Col(dbc.Button("Subtract", id="merge-subtract-btn", color="warning", size="sm", className="w-100"), width=4),
                    dbc.Col(dbc.Button("Merge", id="merge-merge-btn", color="primary", size="sm", className="w-100"), width=4),
                    dbc.Col(
                        dcc.Input(id="merge-splice-q-input", type="number", step="any",
                                  placeholder="Splice q =", style={"width": "100%"}),
                        width=4,
                    ),
                ], className="g-2 mb-2"),

                html.Div(id="merge-status",
                         style={"fontSize": "0.85rem", "color": "#495057", "marginBottom": "10px"}),
            ], width=5),

            # Right: the shared plot.
            dbc.Col([
                dcc.Graph(
                    id="merge-graph",
                    style={"height": f"{_PANEL_HEIGHT}px"},
                    config={"displayModeBar": True},
                ),
            ], width=7),
        ]),
    )


def layout():
    return dbc.Container(
        fluid=True,
        children=[

            html.P(
                "Load 1-D profiles, select rows to tune their q range / scale / "
                "offset, and Average, Subtract, Merge, Save, or Remove whatever's "
                "selected — averaged/subtracted/merged results are appended back "
                "into the same list as new profiles.",
                style={"color": "#6c757d"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            _profiles_workspace(),
        ],
    )


layout = layout()
