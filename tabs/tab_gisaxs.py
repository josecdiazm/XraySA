
"""
Dash layout for the Grazing Incidence (GI-SWAXS) tab.

Geometry (distance, wavelength/energy, beam centre, pixel size, detector
rotations), the uploaded image, and masking are all reused live from the
Scattering 2D & 1D tab via cross-tab Dash State/Input on its `scat-*`
components — the same pattern Batch SWAXS already uses — rather than
duplicated here. Only the grazing-incidence-specific geometry (incident
angle, tilt angle, sample orientation) and the three integration schemes
are new.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

# ── Reusable style constants (mirrors tab_scattering_2d.py) ───────────────────
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

def _gi_geometry_section():
    return _section(
        "📐 Grazing-incidence geometry",

        html.Div([
            _label("Incident angle (°)"),
            dcc.Input(id="gi-incident-angle", type="number", value=0.15, step="any",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Tilt angle (°)"),
            dcc.Input(id="gi-tilt-angle", type="number", value=0.0, step="any",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Sample orientation"),
            dcc.Dropdown(
                id="gi-sample-orientation",
                options=[{"label": str(i), "value": i} for i in range(1, 9)],
                value=4,
                clearable=False,
                style={"width": "160px"},
            ),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Points (in-plane)"),
            dcc.Input(id="gi-npt-ip", type="number", value=500, min=10, max=4000,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Points (out-of-plane)"),
            dcc.Input(id="gi-npt-oop", type="number", value=500, min=10, max=4000,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
    )


def _gi_display_range_section():
    return _section(
        "🖼️ 2-D display range",
        html.Div(
            "Sets the qxy/qz plot axis limits (like matplotlib's set_xlim/"
            "set_ylim) — display only, doesn't affect any integration. "
            "Leave a field blank to use the full computed extent.",
            style={"fontSize": "0.78rem", "color": "#6c757d", "marginBottom": "8px"},
        ),

        html.Div([
            _label("qxy min (Å⁻¹)"),
            dcc.Input(id="gi-display-qxy-min", type="number", placeholder="auto", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("qxy max (Å⁻¹)"),
            dcc.Input(id="gi-display-qxy-max", type="number", placeholder="auto", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("qz min (Å⁻¹)"),
            dcc.Input(id="gi-display-qz-min", type="number", value=0, debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("qz max (Å⁻¹)"),
            dcc.Input(id="gi-display-qz-max", type="number", placeholder="auto", debounce=True,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
    )


def _gi_azimuthal_section():
    return _section(
        "🔺 Azimuthal integration",

        html.Div([
            _label("Azimuth min (°)"),
            dcc.Input(id="gi-azimuth-min", type="number", placeholder="-180",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Azimuth max (°)"),
            dcc.Input(id="gi-azimuth-max", type="number", placeholder="180",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Wedge q min (Å⁻¹)"),
            dcc.Input(id="gi-wedge-qmin", type="number", value=0.0, min=0.0, step=0.01,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Wedge q max (Å⁻¹)"),
            dcc.Input(id="gi-wedge-qmax", type="number", value=1.0, min=0.0, step=0.01,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button("+ Add region", id="gi-azimuth-add-btn", color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Clear all", id="gi-azimuth-clear-btn", color="danger",
                       outline=True, size="sm"),
        ], style={"marginBottom": "10px"}),

        html.Div(id="gi-azimuth-list"),
    )


def _gi_vertical_section():
    return _section(
        "📏 Vertical integration regions (qxy bands → I vs qz)",

        html.Div([
            _label("qxy min (Å⁻¹)"),
            dcc.Input(id="gi-vert-qxy-min", type="number", placeholder="min",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("qxy max (Å⁻¹)"),
            dcc.Input(id="gi-vert-qxy-max", type="number", placeholder="max",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Side"),
            dcc.Dropdown(
                id="gi-vert-side",
                options=[
                    {"label": "Upper (qz ≥ 0)", "value": "upper"},
                    {"label": "Lower (qz ≤ 0)", "value": "lower"},
                    {"label": "Both",           "value": "both"},
                ],
                value="upper",
                clearable=False,
                style={"width": "160px"},
            ),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button("+ Add region", id="gi-vert-add-btn", color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Clear all", id="gi-vert-clear-btn", color="danger",
                       outline=True, size="sm"),
        ], style={"marginBottom": "10px"}),

        html.Div(id="gi-vert-list"),
    )


def _gi_horizontal_section():
    return _section(
        "📐 Horizontal integration regions (qz bands → I vs qxy)",

        html.Div([
            _label("qz min (Å⁻¹)"),
            dcc.Input(id="gi-horiz-qz-min", type="number", placeholder="min",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("qz max (Å⁻¹)"),
            dcc.Input(id="gi-horiz-qz-max", type="number", placeholder="max",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Side"),
            dcc.Dropdown(
                id="gi-horiz-side",
                options=[
                    {"label": "Right (qxy ≥ 0)", "value": "right"},
                    {"label": "Left (qxy ≤ 0)",  "value": "left"},
                    {"label": "Both",            "value": "both"},
                ],
                value="right",
                clearable=False,
                style={"width": "160px"},
            ),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button("+ Add region", id="gi-horiz-add-btn", color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Clear all", id="gi-horiz-clear-btn", color="danger",
                       outline=True, size="sm"),
        ], style={"marginBottom": "10px"}),

        html.Div(id="gi-horiz-list"),
    )


def _gi_qrange_section():
    return _section(
        "🔍 Q Range",

        html.Div([
            _label("Q min"),
            dcc.Input(
                id="gi-qrange-min",
                type="number",
                value=None,
                step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        html.Div([
            _label("Q max"),
            dcc.Input(
                id="gi-qrange-max",
                type="number",
                value=None,
                step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button(
                "Apply Q Range",
                id="gi-qrange-apply-btn",
                color="primary",
                size="sm",
                className="w-100",
            ),
        ], style={"marginTop": "6px"}),
    )


def _gi_run_section():
    return _section(
        "▶ Run",
        html.Div(
            "Runs every accumulated azimuthal/vertical/horizontal region, "
            "and refreshes the combined 1-D plot.",
            style={"fontSize": "0.78rem", "color": "#6c757d", "marginBottom": "8px"},
        ),
        dbc.Button("Integrate", id="gi-integrate-btn", color="primary", size="sm"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main layout function
# ─────────────────────────────────────────────────────────────────────────────

def layout():
    return dbc.Container(
        fluid=True,
        children=[

            dcc.Store(id="gi-azimuth-regions-store", data=[]),
            dcc.Store(id="gi-vert-regions-store", data=[]),
            dcc.Store(id="gi-horiz-regions-store", data=[]),
            dcc.Store(id="gi-integration-store", data={}),
            dcc.Store(id="gi-qrange-store", data=None),

            html.H4(
                "Grazing Incidence Scattering (GI-SWAXS)",
                style={"margin": "16px 0 4px"},
            ),
            html.Hr(style={"marginTop": "4px"}),

            dbc.Row([

                # ── Left column: controls ─────────────────────────────────
                dbc.Col(
                    [
                        _gi_geometry_section(),
                        _gi_display_range_section(),
                        _gi_azimuthal_section(),
                        _gi_vertical_section(),
                        _gi_horizontal_section(),
                        _gi_qrange_section(),
                        _gi_run_section(),
                    ],
                    width=3,
                    style={"overflowY": "auto", "maxHeight": "92vh", "paddingRight": "8px"},
                ),

                # ── Right column: graphs ──────────────────────────────────
                dbc.Col(
                    dbc.Row([
                        dbc.Col(
                            dbc.Card([
                                dbc.CardHeader("Detector image (qxy / qz)"),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id="gi-2d-graph",
                                        style={"height": "550px"},
                                        config={"scrollZoom": True, "displayModeBar": True},
                                    )
                                ),
                            ]),
                            width=6,
                        ),
                        dbc.Col(
                            dbc.Card([
                                dbc.CardHeader("1-D integrations (azimuthal / vertical / horizontal)"),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id="gi-1d-graph",
                                        style={"height": "550px"},
                                        config={"displayModeBar": True},
                                    )
                                ),
                            ]),
                            width=6,
                        ),
                    ]),
                    width=9,
                ),
            ]),
        ],
    )


layout = layout()
