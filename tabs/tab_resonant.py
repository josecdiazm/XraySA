
"""
Dash layout for the Resonant Scattering tab: load a folder of detector
images spanning an energy series (energy parsed from each filename), and
run per-file 2D/1D previews, a NEXAFS ROI sweep, and an energy-colored 1-D
overlay across the whole series.

Base geometry, masking, display options, and azimuthal wedge regions are
all reused live from the Scattering 2D & 1D tab's `scat-*` components via
cross-tab State/Input — only the energy-series-specific controls are new.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

from tabs._shared import folder_picker
from utils.resonant_utils import DEFAULT_ENERGY_PATTERN

# ── Reusable style constants (mirrors tab_gisaxs.py) ──────────────────────────
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

def _folder_section():
    return _section(
        "📂 Data folder",
        folder_picker("reson-folder-input"),
        html.Div([
            _label("Exclude containing"),
            dcc.Input(
                id="reson-exclude-input", type="text", placeholder="e.g. beamstop, dry",
                debounce=True, style={"width": "100%"},
            ),
        ], style={**_ROW_STYLE, "marginTop": "8px"}),
        html.Div([
            _label("Energy pattern"),
            dcc.Input(
                id="reson-energy-pattern", type="text", value=DEFAULT_ENERGY_PATTERN,
                debounce=True, style={"width": "100%"},
            ),
        ], style=_ROW_STYLE),
        html.Div(
            "Regex applied to each filename; its first capture group is the "
            "energy in eV.",
            style={"fontSize": "0.78rem", "color": "#6c757d", "marginBottom": "8px"},
        ),
        dbc.Button("Load Folder", id="reson-load-folder-btn", color="primary", size="sm"),
        html.Div(id="reson-folder-status",
                 style={"fontSize": "0.85rem", "color": "#495057", "marginTop": "8px"}),

        dcc.Upload(
            id="reson-upload-files",
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
    )


def _preview_section():
    return _section(
        "🖼 File preview",
        html.Div([
            _label("File (energy)"),
            dcc.Dropdown(
                id="reson-file-select",
                options=[],
                clearable=False,
                style={"width": "100%"},
            ),
        ], style=_ROW_STYLE),
        dbc.Button("Integrate 1-D", id="reson-integrate-btn", color="primary", size="sm"),
    )


def _qrange_section():
    return _section(
        "🔍 Q Range",
        html.Div([
            _label("Q min"),
            dcc.Input(
                id="reson-qrange-min", type="number", value=None, step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Q max"),
            dcc.Input(
                id="reson-qrange-max", type="number", value=None, step="0.001",
                style=_INPUT_STYLE,
            ),
        ], style=_ROW_STYLE),
        dbc.Button(
            "Apply Q Range", id="reson-qrange-apply-btn",
            color="primary", size="sm", className="w-100",
        ),
    )


def _roi_section():
    return _section(
        "🎯 ROI regions (for NEXAFS)",
        html.Div([
            _label("Name"),
            dcc.Input(id="reson-roi-name", type="text", placeholder="auto",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Row min"),
            dcc.Input(id="reson-roi-row-min", type="number", placeholder="row0",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Row max"),
            dcc.Input(id="reson-roi-row-max", type="number", placeholder="row1",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Col min"),
            dcc.Input(id="reson-roi-col-min", type="number", placeholder="col0",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Col max"),
            dcc.Input(id="reson-roi-col-max", type="number", placeholder="col1",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),

        html.Div([
            dbc.Button("+ Add region", id="reson-roi-add-btn", color="secondary",
                       size="sm", className="me-2"),
            dbc.Button("Clear all", id="reson-roi-clear-btn", color="danger",
                       outline=True, size="sm"),
        ], style={"marginBottom": "10px"}),

        html.Div(id="reson-roi-list"),
    )


def _nexafs_section():
    return _section(
        "▶ NEXAFS (ROI sum vs. energy)",
        html.Div(
            "Sums each ROI's intensity across every loaded file and plots "
            "it against that file's energy.",
            style={"fontSize": "0.78rem", "color": "#6c757d", "marginBottom": "8px"},
        ),
        dbc.Button("Run NEXAFS", id="reson-nexafs-btn", color="success", size="sm"),
        dbc.Progress(id="reson-nexafs-progress", value=0, label="", striped=True,
                     animated=True, style={"height": "20px", "marginTop": "10px"}),
        html.Div(id="reson-nexafs-progress-text",
                 style={"fontSize": "0.8rem", "color": "#495057", "marginTop": "6px"}),
    )


def _energy_series_section():
    return _section(
        "🌈 Energy-series 1-D overlay",
        html.Div([
            _label("Azimuthal region"),
            dcc.Dropdown(
                id="reson-energy-region-select",
                options=[{"label": "Unrestricted (full)", "value": "full"}],
                value="full",
                clearable=False,
                style={"width": "100%"},
            ),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Start index"),
            dcc.Input(id="reson-energy-start-idx", type="number", value=0, min=0,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("End index"),
            dcc.Input(id="reson-energy-end-idx", type="number", placeholder="last",
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        html.Div([
            _label("Step"),
            dcc.Input(id="reson-energy-step", type="number", value=1, min=1,
                      style=_INPUT_STYLE),
        ], style=_ROW_STYLE),
        dbc.Button("Run Energy Series", id="reson-energy-run-btn", color="success", size="sm"),
        dbc.Progress(id="reson-energy-progress", value=0, label="", striped=True,
                     animated=True, style={"height": "20px", "marginTop": "10px"}),
        html.Div(id="reson-energy-progress-text",
                 style={"fontSize": "0.8rem", "color": "#495057", "marginTop": "6px"}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main layout function
# ─────────────────────────────────────────────────────────────────────────────

def layout():
    return dbc.Container(
        fluid=True,
        children=[

            dcc.Store(id="reson-file-store", data=[]),
            dcc.Store(id="reson-roi-store", data=[]),
            dcc.Store(id="reson-nexafs-store", data={}),
            dcc.Store(id="reson-energy-store", data={}),
            dcc.Store(id="reson-1d-data-store", data={}),
            dcc.Store(id="reson-qrange-store", data=None),
            dcc.Store(id="reson-upload-tempdir-store", data=None),

            html.Hr(style={"marginTop": "4px"}),

            dbc.Row([

                # ── Left column: controls ─────────────────────────────────
                dbc.Col(
                    [
                        _folder_section(),
                        _preview_section(),
                        _qrange_section(),
                        _roi_section(),
                        _nexafs_section(),
                        _energy_series_section(),
                    ],
                    width=3,
                    style={"overflowY": "auto", "maxHeight": "92vh", "paddingRight": "8px"},
                ),

                # ── Right column: graphs ──────────────────────────────────
                dbc.Col(
                    [
                        dbc.Row([
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("Detector image (pixel space)"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="reson-2d-graph",
                                            style={"height": "480px"},
                                            config={"scrollZoom": True, "displayModeBar": True,
                                                    "toImageButtonOptions": {"format": "png", "scale": 4}},
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
                                            id="reson-2d-q-graph",
                                            style={"height": "480px"},
                                            config={"scrollZoom": True, "displayModeBar": True,
                                                    "toImageButtonOptions": {"format": "png", "scale": 4}},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("1-D profile (selected file)"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="reson-1d-graph",
                                            style={"height": "420px"},
                                            config={"displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader("Energy-series 1-D overlay"),
                                    dbc.CardBody(
                                        dcc.Graph(
                                            id="reson-energy-graph",
                                            style={"height": "420px"},
                                            config={"displayModeBar": True},
                                        )
                                    ),
                                ]),
                                width=6,
                            ),
                        ], className="mb-3"),

                        dbc.Card([
                            dbc.CardHeader("NEXAFS (ROI intensity vs. energy)"),
                            dbc.CardBody(
                                dcc.Graph(
                                    id="reson-nexafs-graph",
                                    style={"height": "420px"},
                                    config={"displayModeBar": True},
                                )
                            ),
                        ]),
                    ],
                    width=9,
                ),
            ]),
        ],
    )


layout = layout()
