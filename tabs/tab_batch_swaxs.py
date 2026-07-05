
"""
Dash layout for the Batch SWAXS tab: pick a folder of detector images,
exclude files by keyword, then batch-process them all using the
Geometry / Integration / Q Range / Display parameters set on the
Scattering 2D & 1D tab.
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


def layout():
    return dbc.Container(
        fluid=True,
        children=[

            # Hidden stores
            dcc.Store(id="batch-all-files", data=[]),
            dcc.Store(id="batch-upload-tempdir-store", data=None),

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
                        html.Div(
                            [
                                _section(
                                    "📁 Input folder",
                                    folder_picker("batch-folder-input"),
                                    dbc.Button(
                                        "Load Folder", id="batch-load-folder-btn",
                                        color="primary", size="sm", className="mt-2",
                                    ),
                                    html.Div(id="batch-folder-status",
                                             style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

                                    dcc.Upload(
                                        id="batch-upload-files",
                                        children=html.Div(
                                            ["Drag & drop files here, or ", html.A("select files")],
                                            style={"textAlign": "center", "padding": "18px", "color": "#6c757d"},
                                        ),
                                        style={
                                            "border": "2px dashed #ced4da",
                                            "borderRadius": "6px",
                                            "cursor": "pointer",
                                            "marginTop": "12px",
                                        },
                                        multiple=True,
                                    ),
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
                            ],
                            id="batch-folder-section",
                        ),

                        _section(
                            "🔬 Integrator",
                            dbc.RadioItems(
                                id="batch-integrator-mode",
                                options=[
                                    {"label": "Scattering 2D & 1D (azimuthal integrator)",
                                     "value": "scattering"},
                                    {"label": "Grazing Incidence (fiber integrator)",
                                     "value": "gisaxs"},
                                    {"label": "Resonant Scattering (energy series)",
                                     "value": "resonant"},
                                ],
                                value="scattering",
                            ),
                        ),

                        html.Div(
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
                            id="batch-mode-section",
                        ),

                        html.Div(
                            _section(
                                "📊 Resonant output",
                                dbc.RadioItems(
                                    id="batch-resonant-output-mode",
                                    options=[
                                        {"label": "Energy-series 1-D profiles (one CSV per energy)",
                                         "value": "energy_series"},
                                        {"label": "XANES/NEXAFS (ROI vs. energy, one CSV)",
                                         "value": "nexafs"},
                                    ],
                                    value="energy_series",
                                ),
                                html.Div(
                                    "Energy-series uses the region and start/end/step currently "
                                    "set in Resonant Scattering's Energy-series section. XANES/"
                                    "NEXAFS sums the ROIs currently defined there across the "
                                    "whole loaded series, same as clicking Run NEXAFS.",
                                    style={"fontSize": "0.8rem", "color": "#6c757d", "marginTop": "6px"},
                                ),
                            ),
                            id="batch-resonant-output-section",
                            style={"display": "none"},
                        ),

                        _section(
                            "💾 Output folder",
                            folder_picker("batch-output-folder", "/path/to/output"),
                        ),

                        dbc.Button(
                            "Run Batch", id="batch-run-btn",
                            color="success", className="w-100",
                        ),
                        dbc.Progress(id="batch-progress", value=0, label="", striped=True,
                                     animated=True, style={"height": "20px", "marginTop": "10px"}),
                        html.Div(id="batch-progress-text",
                                 style={"fontSize": "0.8rem", "color": "#495057", "marginTop": "6px"}),
                    ],
                    width=4,
                    style={"overflowY": "auto", "maxHeight": "92vh", "paddingRight": "8px"},
                ),

                # ── Right column: files + log ──────────────────────────────
                dbc.Col(
                    [
                        html.Div(
                            dbc.Card([
                                dbc.CardHeader("📋 Files to process"),
                                dbc.CardBody([
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
                                ]),
                            ]),
                            id="batch-files-card",
                            className="mb-3",
                        ),

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
