
"""
Dash layout for the SWAXS Merging tab: average repeated SAXS/WAXS
1-D scans, scale and splice them together, and save the results.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

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


def _average_section(prefix: str, label: str):
    """Folder-scan + average UI for one detector type (saxs / waxs)."""
    return dbc.Col(
        _section(
            f"📊 Average {label}",

            dcc.Store(id=f"merge-{prefix}-all-files", data=[]),

            dcc.Input(
                id=f"merge-{prefix}-folder-input", type="text",
                placeholder="/path/to/folder", style={"width": "100%"},
            ),
            dbc.Button(
                "Load Folder", id=f"merge-{prefix}-load-folder-btn",
                color="primary", size="sm", className="mt-2",
            ),
            html.Div(id=f"merge-{prefix}-folder-status",
                     style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

            html.Div("Exclude files containing:",
                     style={"fontSize": "0.8rem", "color": "#6c757d", "marginTop": "10px"}),
            dcc.Input(
                id=f"merge-{prefix}-exclude-input", type="text",
                placeholder="e.g. dry, beamstop", debounce=True,
                style={"width": "100%"},
            ),

            html.Div(id=f"merge-{prefix}-file-count",
                     style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "10px"}),
            dcc.Checklist(
                id=f"merge-{prefix}-file-checklist",
                options=[], value=[],
                inputStyle={"marginRight": "6px"},
                labelStyle={"display": "block"},
                style={"maxHeight": "160px", "overflowY": "auto", "fontSize": "0.85rem"},
            ),

            dbc.Button(
                "Average Selected", id=f"merge-{prefix}-average-btn",
                color="success", size="sm", className="mt-3 mb-2",
            ),

            dcc.Graph(
                id=f"merge-{prefix}-avg-graph",
                style={"height": "320px"},
                config={"displayModeBar": False},
            ),

            html.Hr(),
            html.Div("Or load a previously averaged CSV:",
                     style={"fontSize": "0.8rem", "color": "#6c757d", "marginBottom": "6px"}),
            dcc.Input(
                id=f"merge-{prefix}-load-file-input", type="text",
                placeholder="/path/to/averaged_file.csv", style={"width": "100%"},
            ),
            dbc.Button(
                "Load File", id=f"merge-{prefix}-load-file-btn",
                color="secondary", size="sm", outline=True, className="mt-2",
            ),
        ),
        width=6,
    )


def _merge_section():
    return _section(
        "🔗 Merge",

        dcc.Graph(
            id="merge-overlay-graph",
            style={"height": "380px"},
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
            style={"height": "380px"},
            config={"displayModeBar": True},
        ),
    )


def _save_section():
    return _section(
        "💾 Save",

        dcc.Checklist(
            id="merge-save-checklist",
            options=[
                {"label": " Averaged SAXS", "value": "avg_saxs"},
                {"label": " Averaged WAXS", "value": "avg_waxs"},
                {"label": " Merged profile", "value": "merged"},
            ],
            value=[],
            inputStyle={"marginRight": "6px"},
            labelStyle={"display": "block", "marginBottom": "4px"},
        ),

        dcc.Input(
            id="merge-save-output-folder", type="text",
            placeholder="/path/to/output", style={"width": "100%", "marginTop": "8px"},
        ),

        dbc.Button("Save Selected", id="merge-save-btn", color="success", className="mt-3"),

        html.Div(id="merge-save-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "10px"}),
    )


def layout():
    return dbc.Container(
        fluid=True,
        children=[

            dcc.Store(id="merge-saxs-avg-store"),
            dcc.Store(id="merge-waxs-avg-store"),
            dcc.Store(id="merge-merged-store"),

            html.H4("SWAXS Merging", style={"margin": "16px 0 4px"}),
            html.P(
                "Average repeated SAXS/WAXS 1-D scans, scale and splice them "
                "into one continuous profile, then save the results.",
                style={"color": "#6c757d"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            dbc.Row([
                _average_section("saxs", "SAXS"),
                _average_section("waxs", "WAXS"),
            ]),

            _merge_section(),
            _save_section(),
        ],
    )


layout = layout()
