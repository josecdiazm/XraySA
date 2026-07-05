
"""
Dash layout for the SWAXS Merging tab:
  - Average panel: average any set of 1-D scans (SAXS, WAXS, or a mix)
    and save the result.
  - Merge panel: load two previously-saved averaged files from a folder,
    scale/splice them together, and save the merged profile.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

from tabs._shared import folder_picker

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


def _average_panel():
    return _section(
        "📊 Average",

        dcc.Store(id="merge-avg-all-files", data=[]),
        dcc.Store(id="merge-avg-store"),
        dcc.Store(id="merge-avg-upload-tempdir-store", data=None),

        folder_picker("merge-avg-folder-input"),
        dbc.Button(
            "Load Folder", id="merge-avg-load-folder-btn",
            color="primary", size="sm", className="mt-2",
        ),
        html.Div(id="merge-avg-folder-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

        dcc.Upload(
            id="merge-avg-upload-files",
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

        html.Div("Exclude files containing:",
                 style={"fontSize": "0.8rem", "color": "#6c757d", "marginTop": "10px"}),
        dcc.Input(
            id="merge-avg-exclude-input", type="text",
            placeholder="e.g. dry, beamstop", debounce=True,
            style={"width": "100%"},
        ),

        html.Div(id="merge-avg-file-count",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "10px"}),
        dcc.Checklist(
            id="merge-avg-file-checklist",
            options=[], value=[],
            inputStyle={"marginRight": "6px"},
            labelStyle={"display": "block"},
            style={"maxHeight": "160px", "overflowY": "auto", "fontSize": "0.85rem"},
        ),

        dbc.Button(
            "Average Selected", id="merge-avg-average-btn",
            color="success", size="sm", className="mt-3 mb-2",
        ),

        dcc.Graph(
            id="merge-avg-graph",
            style={"height": "600px"},
            config={"displayModeBar": True},
        ),

        html.Hr(),
        html.Div("Save average:", style={"fontSize": "0.85rem", "fontWeight": "500", "marginBottom": "6px"}),
        dbc.Row([
            dbc.Col(
                dcc.Input(id="merge-avg-filename", type="text", value="averaged.csv",
                          style={"width": "100%"}),
                width=4,
            ),
            dbc.Col(folder_picker("merge-avg-output-folder", "/path/to/output"), width=6),
            dbc.Col(
                dbc.Button("Save Average", id="merge-avg-save-btn", color="success",
                           className="w-100"),
                width=2,
            ),
        ], className="g-2"),
        html.Div(id="merge-avg-save-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),
    )


def _merge_panel():
    return _section(
        "🔗 Merge",

        dcc.Store(id="merge-files-all", data=[]),
        dcc.Store(id="merge-saxs-avg-store"),
        dcc.Store(id="merge-waxs-avg-store"),
        dcc.Store(id="merge-merged-store"),
        dcc.Store(id="merge-files-upload-tempdir-store", data=None),

        folder_picker("merge-files-folder-input", "/path/to/averaged files"),
        dbc.Button(
            "Load Folder", id="merge-files-load-folder-btn",
            color="primary", size="sm", className="mt-2",
        ),
        html.Div(id="merge-files-folder-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

        dcc.Upload(
            id="merge-files-upload-files",
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

        dbc.Row([
            dbc.Col([
                html.Label("SAXS file", style={"fontSize": "0.85rem"}),
                dcc.Dropdown(id="merge-saxs-select", options=[], placeholder="Select SAXS file"),
            ], width=6),
            dbc.Col([
                html.Label("WAXS file", style={"fontSize": "0.85rem"}),
                dcc.Dropdown(id="merge-waxs-select", options=[], placeholder="Select WAXS file"),
            ], width=6),
        ], className="mt-2"),

        dbc.Button(
            "Load Selected", id="merge-load-both-btn",
            color="secondary", size="sm", className="mt-2 mb-2",
        ),

        dcc.Graph(
            id="merge-overlay-graph",
            style={"height": "450px"},
            config={"displayModeBar": True},
        ),

        dbc.Row([
            dbc.Col([
                html.Label("SAXS scale factor", style={"fontSize": "0.85rem"}),
                dcc.Input(id="merge-saxs-scale", type="number", value=1.0, step="any",
                          style={"width": "100%"}),
            ], width=4),
            dbc.Col([
                html.Label("WAXS scale factor", style={"fontSize": "0.85rem"}),
                dcc.Input(id="merge-waxs-scale", type="number", value=1.0, step="any",
                          style={"width": "100%"}),
            ], width=4),
            dbc.Col([
                html.Label("Splice at q =", style={"fontSize": "0.85rem"}),
                dcc.Input(id="merge-splice-q", type="number", step="any",
                          style={"width": "100%"}),
            ], width=4),
        ], className="mt-2"),

        dbc.Button("Merge", id="merge-btn", color="primary", className="mt-3 mb-2"),

        dcc.Graph(
            id="merge-merged-graph",
            style={"height": "450px"},
            config={"displayModeBar": True},
        ),

        html.Hr(),
        html.Div("Save merged profile:", style={"fontSize": "0.85rem", "fontWeight": "500", "marginBottom": "6px"}),
        dbc.Row([
            dbc.Col(
                dcc.Input(id="merge-merged-filename", type="text", value="merged_SWAXS.csv",
                          style={"width": "100%"}),
                width=4,
            ),
            dbc.Col(folder_picker("merge-save-output-folder", "/path/to/output"), width=6),
            dbc.Col(
                dbc.Button("Save Merged", id="merge-save-merged-btn", color="success",
                           className="w-100"),
                width=2,
            ),
        ], className="g-2"),
        html.Div(id="merge-save-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),
    )


def layout():
    return dbc.Container(
        fluid=True,
        children=[

            html.P(
                "Average a set of 1-D scans and save the result, then merge "
                "previously-saved averaged SAXS/WAXS profiles into one "
                "continuous curve.",
                style={"color": "#6c757d"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            _average_panel(),
            _merge_panel(),
        ],
    )


layout = layout()
