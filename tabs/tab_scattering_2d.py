
"""
Dash layout for the 2-D scattering viewer / 1-D integrator panel.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

# ── Reusable style constants ──────────────────────────────────────────────────
_LABEL_STYLE  = {"width": "160px", "flexShrink": "0", "fontWeight": "500"}
_ROW_STYLE    = {"display": "flex", "alignItems": "center", "marginBottom": "8px"}
_INPUT_STYLE  = {"width": "160px"}
_SECTION_STYLE = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "6px",
    "padding": "14px 18px",
    "marginBottom": "16px",
}


def _label(text):
    return html.Span(text, style=_LABEL_STYLE)


def _section(title, *children):
    return html.Div(
        [html.H6(title, style={"marginBottom": "12px", "color": "#495057"}), *children],
        style=_SECTION_STYLE,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sub-sections
# ─────────────────────────────────────────────────────────────────────────────

def _upload_section():
    return _section(
        "📂 Data",
        dcc.Upload(
            id="scat-upload",
            children=html.Div(
                ["Drag & drop or ", html.A("select a file")],
                style={"textAlign": "center", "padding": "18px", "color": "#6c757d"},
            ),
            style={
                "border": "2px dashed #ced4da",
                "borderRadius": "6px",
                "cursor": "pointer",
                "marginBottom": "8px",
            },
            multiple=False,
        ),
        html.Div(id="scat-upload-status", style={"fontSize": "0.85rem", "color": "#495057"}),
    )


def _poni_section():
    return _section(
        "📡 Calibration (poni file)",
        dcc.Upload(
            id="scat-poni-upload",
            children=html.Div(
                ["Drag & drop or ", html.A("select a .poni file")],
                style={"textAlign": "center", "padding": "12px", "color": "#6c757d"},
            ),
            style={
                "border": "2px dashed #ced4da",
                "borderRadius": "6px",
                "cursor": "pointer",
                "marginBottom": "8px",
            },
            multiple=False,
        ),
        html.Div(id="scat-poni-status", style={"fontSize": "0.85rem", "color": "#495057"}),
    )


def _geometry_section():
    return _section(
        "📐 Geometry",

        # Sample-to-detector distance
        html.Div([
            _label("Distance (mm)"),
            dcc.Input(id="scat-distance", type="number", value=200, min=1, style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Wavelength / energy toggle
        html.Div([
            _label("Input type"),
            dcc.RadioItems(
                id="scat-wavelength-or-energy",
                options=[
                    {"label": "Wavelength", "value": "wavelength"},
                    {"label": "Energy",     "value": "energy"},
                ],
                value="energy",
                inline=True,
                inputStyle={"marginRight": "4px"},
                labelStyle={"marginRight": "14px"},
            ),
        ], style=_ROW_STYLE),

        # Wavelength input (shown by default)
        html.Div([
            _label("Wavelength (Å)"),
            dcc.Input(id="scat-wavelength", type="number", value=1.0, min=0.001, step="any",
                      style=_INPUT_STYLE),
        ], id="scat-wavelength-row", style={"display": "none"}),

        # Energy input (hidden by default)
        html.Div([
            _label("Energy (keV)"),
            dcc.Input(id="scat-energy", type="number", value=12.4, min=0.1, step="any",
                      style=_INPUT_STYLE),
        ], id="scat-energy-row", style=_ROW_STYLE),

        # Beam centre
        html.Div([
            _label("Beam centre X (px)"),
            dcc.Input(id="scat-bcx", type="number", value=512, style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Beam centre Y (px)"),
            dcc.Input(id="scat-bcy", type="number", value=512, style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Pixel sizes
        html.Div([
            _label("Pixel size X (μm)"),
            dcc.Input(id="scat-px-x", type="number", value=172, min=1, style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Pixel size Y (μm)"),
            dcc.Input(id="scat-px-y", type="number", value=172, min=1, style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Detector rotations (pyFAI/poni convention, entered/displayed in degrees)
        html.Div([
            _label("↔ Rot1 (°)"),
            dcc.Input(id="scat-rot1", type="number", value=0, step="any", style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("↕ Rot2 (°)"),
            dcc.Input(id="scat-rot2", type="number", value=0, step="any", style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("↻ Rot3 (°)"),
            dcc.Input(id="scat-rot3", type="number", value=0, step="any", style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
    )


def _integration_section():
    return _section(
        "⚙️ Integration options",

        # Number of points
        html.Div([
            _label("Points"),
            dcc.Input(id="scat-npts", type="number", value=1000, min=10, max=10000,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Output unit
        html.Div([
            _label("Unit"),
            dcc.Dropdown(
                id="scat-unit-dropdown",
                options=[
                    {"label": "q (Å⁻¹)",  "value": "q_A^-1"},
                    {"label": "q (nm⁻¹)", "value": "q_nm^-1"},
                    {"label": "2θ (°)",   "value": "2th_deg"},
                    {"label": "r (mm)",   "value": "r_mm"},
                ],
                value="q_A^-1",
                clearable=False,
                style={"width": "150px"},
            ),
        ], style=_ROW_STYLE),

        # Colorbar range (display only — does not mask/exclude any pixels)
        html.Div([
            _label("Cbar min"),
            dcc.Input(id="scat-cbar-min", type="number", placeholder="auto", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Cbar max"),
            dcc.Input(id="scat-cbar-max", type="number", placeholder="auto", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Azimuthal range
        html.Div([
            _label("Azimuth min (°)"),
            dcc.Input(id="scat-azimuth-min", type="number", placeholder="-180",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Azimuth max (°)"),
            dcc.Input(id="scat-azimuth-max", type="number", placeholder="180",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        # Error model
        html.Div([
            _label("Error model"),
            dcc.Dropdown(
                id="scat-error-model",
                options=[
                    {"label": "None",     "value": ""},
                    {"label": "Poisson",  "value": "poisson"},
                    {"label": "Azimuthal","value": "azimuthal"},
                ],
                value="",
                clearable=False,
                style={"width": "150px"},
            ),
        ], style=_ROW_STYLE),

        # Action buttons
        html.Div([
            dbc.Button("Integrate 1-D", id="scat-integrate-btn", color="primary",
                       size="sm", className="me-2"),
            dbc.Button("Cake plot",     id="scat-cake-btn",      color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Download CSV",  id="scat-download-btn",  color="success",
                       size="sm", outline=True),
        ], style={"marginTop": "10px"}),
    )


def _display_section():
    return _section(
        "🎨 Display options",

        # Colorscale
        html.Div([
            _label("Colorscale"),
            dcc.Dropdown(
                id="scat-colorscale-dropdown",
                options=[{"label": c, "value": c}
                         for c in ["Viridis", "Inferno", "Plasma", "Hot", "Greys", "Jet"]],
                value="Viridis",
                clearable=False,
                style={"width": "150px"},
            ),
        ], style=_ROW_STYLE),

        # Log scale toggle for 2-D image
        html.Div([
            _label("2-D log scale"),
            dcc.Checklist(
                id="scat-log-toggle",
                options=[{"label": " log₁₀", "value": "log"}],
                value=["log"],
                inputStyle={"marginRight": "4px"},
            ),
        ], style=_ROW_STYLE),

        # Log scale toggle for 1-D y-axis
        html.Div([
            _label("1-D log y-axis"),
            dcc.Checklist(
                id="scat-log-y-toggle",
                options=[{"label": " log₁₀", "value": "log"}],
                value=["log"],
                inputStyle={"marginRight": "4px"},
            ),
        ], style=_ROW_STYLE),

        # Log scale toggle for 1-D q-axis
        html.Div([
            _label("1-D log q-axis"),
            dcc.Checklist(
                id="scat-log-x-toggle",
                options=[{"label": " log₁₀", "value": "log"}],
                value=["log"],
                inputStyle={"marginRight": "4px"},
            ),
        ], style=_ROW_STYLE),

        # Show beam centre
        html.Div([
            _label("Show beam centre"),
            dcc.Checklist(
                id="scat-show-beam-centre",
                options=[{"label": " show", "value": "show"}],
                value=["show"],
                inputStyle={"marginRight": "4px"},
            ),
        ], style=_ROW_STYLE),
    )


def _wedge_section():
    return _section(
        "🔺 Azimuthal wedge",

        # Inner q radius
        html.Div([
            _label("q min (Å⁻¹)"),
            dcc.Input(
                id="scat-wedge-qmin",
                type="number",
                value=0.0,
                min=0.0,
                step=0.01,
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        # Outer q radius
        html.Div([
            _label("q max (Å⁻¹)"),
            dcc.Input(
                id="scat-wedge-qmax",
                type="number",
                value=1.0,
                min=0.0,
                step=0.01,
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        # # Draw button
        # html.Div([
        #     dbc.Button("Draw wedge", id="scat-draw-wedge-btn", color="warning",
        #                size="sm", outline=True, n_clicks=1),
        # ], style={"marginTop": "6px"}),
    )


def _pixel_mask_section():
    return _section(
        "🎭 Hot Pixel Masking",

        # Mask thresholds
        html.Div([
            _label("Mask below"),
            dcc.Input(id="scat-mask-low", type="number", placeholder="min", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Mask above"),
            dcc.Input(id="scat-mask-high", type="number", placeholder="max",  debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Shape"),
            dcc.RadioItems(
                id="scat-pixmask-shape",
                options=[
                    {"label": " Square", "value": "square"},
                    {"label": " Circle", "value": "circle"},
                ],
                value="square",
                inline=True,
                inputStyle={"marginRight": "4px"},
                labelStyle={"marginRight": "14px"},
            ),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Center row (px)"),
            dcc.Input(id="scat-pixmask-row", type="number", placeholder="row",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Center col (px)"),
            dcc.Input(id="scat-pixmask-col", type="number", placeholder="col",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Size (px)"),
            dcc.Input(id="scat-pixmask-size", type="number", value=3, min=1, step=1,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div(
            "Size = half-width for square, radius for circle.",
            style={"fontSize": "0.78rem", "color": "#6c757d", "marginBottom": "8px"},
        ),

        html.Div([
            dbc.Button("+ Add region", id="scat-pixmask-add-btn", color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Clear all", id="scat-pixmask-clear-btn", color="danger",
                       outline=True, size="sm"),
        ], style={"marginBottom": "10px"}),

        html.Div(id="scat-pixmask-list"),
    )


def _q_range_section():
    return _section(
        "🔍 Q Range",

        html.Div([
            _label("Q min"),
            dcc.Input(
                id="scat-qrange-min",
                type="number",
                value=None,
                step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Q max"),
            dcc.Input(
                id="scat-qrange-max",
                type="number",
                value=None,
                step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button(
                "Apply Q Range",
                id="scat-apply-qrange-btn",
                color="primary",
                size="sm",
                className="w-100",
            ),
        ], style={"marginTop": "6px"}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main layout function
# ─────────────────────────────────────────────────────────────────────────────

def layout():
    return dbc.Container(
        fluid=True,
        children=[

            # Hidden stores and download component
            dcc.Store(id="scat-image-store"),
            dcc.Store(id="scat-integration-store"),
            dcc.Store(id="scat-q-data-store"),    # full q and I arrays from integration
            dcc.Store(id="scat-qrange-store"),    # currently applied q min/max
            dcc.Store(id="scat-pixel-mask-store", data=[]),  # hot-pixel mask regions
            dcc.Download(id="scat-download"),
            

            html.H4(
                "2-D Scattering Viewer & Integrator",
                style={"margin": "16px 0 4px"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            dbc.Row([

                # ── Left column: controls ─────────────────────────────────
                dbc.Col(
                    [
                        _upload_section(),
                        _poni_section(),
                        _geometry_section(),
                        _integration_section(),
                        _q_range_section(),
                        _display_section(),
                        _wedge_section(),
                        _pixel_mask_section(),
                    ],
                    width=3,
                    style={"overflowY": "auto", "maxHeight": "92vh", "paddingRight": "8px"},
                ),

                # ── Right column: graphs ──────────────────────────────────
                dbc.Col(
                    [
                        # Top row: pixel-space and q-space 2-D images
                        dbc.Row([
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("Detector image (pixel space)"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="scat-2d-graph",
                                            style={"height": "550px"},
                                            config={"scrollZoom": True, "displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("Detector image (q-space)"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="scat-2d-q-graph",
                                            style={"height": "550px"},
                                            config={"scrollZoom": True, "displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                        ], className="mb-3"),

                        # Bottom row: 1-D integration and cake plot
                        dbc.Row([
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("1-D integration"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="scat-1d-graph",
                                            style={"height": "380px"},
                                            config={"displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("Cake plot (q vs χ)"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="scat-cake-graph",
                                            style={"height": "380px"},
                                            config={"scrollZoom": True, "displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                        ]),
                    ],
                    width=9,
                ),
            ]),
        ],
    )


layout = layout()