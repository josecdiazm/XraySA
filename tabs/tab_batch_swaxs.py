
"""
Dash layout for the Batch SWAXS tab: pick a folder of detector images,
exclude files by keyword, then batch-process them all using the
Geometry / Integration / Q Range / Display parameters set on the
Scattering 2D & 1D tab.
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


def layout():
    return dbc.Container(
        fluid=True,
        children=[

            # Hidden stores
            dcc.Store(id="batch-all-files", data=[]),

            html.H4("Batch SWAXS", style={"margin": "16px 0 4px"}),
            html.P(
                "Batch-process a folder of detector images using the Geometry, "
                "Integration Options, Q Range, and Display Options currently set "
                "on the Scattering 2D & 1D tab.",
                style={"color": "#6c757d"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            dbc.Row([

                # ── Left column: controls ─────────────────────────────────
                dbc.Col(
                    [
                        _section(
                            "📁 Input folder",
                            dcc.Input(
                                id="batch-folder-input",
                                type="text",
                                placeholder="/path/to/folder",
                                style={"width": "100%"},
                            ),
                            dbc.Button(
                                "Load Folder", id="batch-load-folder-btn",
                                color="primary", size="sm", className="mt-2",
                            ),
                            html.Div(id="batch-folder-status",
                                     style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),
                        ),

                        _section(
                            "🚫 Exclude files containing",
                            dcc.Input(
                                id="batch-exclude-input",
                                type="text",
                                placeholder="e.g. SAXS, beamstop, WAXS, dry",
                                debounce=True,
                                style={"width": "100%"},
                            ),
                            html.Div(
                                "Comma-separated keywords, matched case-insensitively "
                                "against filenames.",
                                style={"fontSize": "0.8rem", "color": "#6c757d", "marginTop": "6px"},
                            ),
                        ),

                        _section(
                            "📋 Files to process",
                            html.Div(id="batch-file-count",
                                     style={"fontSize": "0.85rem", "color": "#495057", "marginBottom": "8px"}),
                            dcc.Checklist(
                                id="batch-file-checklist",
                                options=[],
                                value=[],
                                inputStyle={"marginRight": "6px"},
                                labelStyle={"display": "block"},
                                style={"maxHeight": "260px", "overflowY": "auto", "fontSize": "0.85rem"},
                            ),
                        ),

                        _section(
                            "⚙️ Processing mode",
                            dbc.RadioItems(
                                id="batch-mode",
                                options=[
                                    {"label": "Convert 2D detector images → 2D q-space images (PNG)",
                                     "value": "2d"},
                                    {"label": "Process 1D profile only (CSV)", "value": "1d"},
                                ],
                                value="1d",
                            ),
                        ),

                        _section(
                            "💾 Output folder",
                            dcc.Input(
                                id="batch-output-folder",
                                type="text",
                                placeholder="/path/to/output",
                                style={"width": "100%"},
                            ),
                        ),

                        dbc.Button(
                            "Run Batch", id="batch-run-btn",
                            color="success", className="w-100",
                        ),
                    ],
                    width=4,
                    style={"overflowY": "auto", "maxHeight": "92vh", "paddingRight": "8px"},
                ),

                # ── Right column: progress + log ──────────────────────────
                dbc.Col(
                    [
                        dbc.Card([
                            dbc.CardHeader("Progress"),
                            dbc.CardBody([
                                dbc.Progress(id="batch-progress", value=0, label="", striped=True,
                                             animated=True, style={"height": "24px"}),
                                html.Div(id="batch-progress-text",
                                         style={"marginTop": "10px", "fontSize": "0.9rem", "color": "#495057"}),
                            ]),
                        ], className="mb-3"),

                        dbc.Card([
                            dbc.CardHeader("Log"),
                            dbc.CardBody(
                                html.Pre(
                                    id="batch-log",
                                    style={
                                        "maxHeight": "500px",
                                        "overflowY": "auto",
                                        "fontSize": "0.8rem",
                                        "marginBottom": 0,
                                    },
                                )
                            ),
                        ]),
                    ],
                    width=8,
                ),
            ]),
        ],
    )


layout = layout()
