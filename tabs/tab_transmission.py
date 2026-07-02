
import numpy as np
import re
import xraydb
from xraydb import material_mu, xray_edges
from dash import html, dcc
import dash_bootstrap_components as dbc

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_all_edges(formula, emin, emax):
    elem_list = set(re.findall(r'([A-Z][a-z]?)', formula))
    edges_found = []
    for elem in elem_list:
        try:
            e_tbl = xray_edges(elem)
        except Exception:
            continue
        for edgename, edge in e_tbl.items():
            e_eV = edge.energy
            if emin <= e_eV <= emax:
                edges_found.append((elem, edgename, e_eV))
    return edges_found


def round_result(val):
    if isinstance(val, (float, int)):
        return f"{val:.3g}"
    return "" if val is None else str(val)


def make_sample_row(i, name="", formula="", density=1.0, thickness=1):
    """Build one sample input row, optionally pre-filled with existing values."""
    inp_style = {"marginRight": "10px"}
    return dbc.Card(
        dbc.CardBody(
            html.Div([
                html.Span(f"Sample {i+1}",
                          style={"fontSize": "13px", "fontWeight": "bold",
                                 "width": "75px", "display": "inline-block",
                                 "marginRight": "8px"}),

                html.Span("Name:", style={"fontSize": "12px", "marginRight": "3px"}),
                dcc.Input(id={"type": "xas-name", "index": i},
                          type="text", placeholder="e.g. Film",
                          value=name,
                          debounce=False,
                          style={"width": "200px", **inp_style}),

                html.Span("Formula:", style={"fontSize": "12px", "marginRight": "3px"}),
                dcc.Input(id={"type": "xas-formula", "index": i},
                          type="text", placeholder="e.g. SiO2",
                          value=formula,
                          debounce=False,
                          style={"width": "250px", **inp_style}),

                html.Span("Density (g/cm³):",
                          style={"fontSize": "12px", "marginRight": "3px"}),
                dcc.Input(id={"type": "xas-density", "index": i},
                        type="number", value=float(density) if density is not None else 1.0,
                        min=0.0001, max=25, step="any",
                        style={"width": "85px", **inp_style}),

                html.Span("Thickness (μm):",
                          style={"fontSize": "12px", "marginRight": "3px"}),
                dcc.Input(id={"type": "xas-thickness", "index": i},
                          type="number", value=thickness,
                          min=0, max=9000000, step=1,
                          style={"width": "90px", **inp_style}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"})
        ),
        className="mb-1 py-0"
    )

# ── Layout ────────────────────────────────────────────────────────────────────

layout = dbc.Container(
    fluid=True,
    className="mt-3",
    children=[

        # Store: preserves number of sample rows AND their values across tab switches
        dcc.Store(id="xas-store", data={
            "n_samples": 1,
            "values": [{"name": "", "formula": "", "density": 1.0, "thickness": 50}]
        }),

        # ── Energy range controls ─────────────────────────────────────────
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Span("Energy Range",
                          style={"fontWeight": "bold", "fontSize": "14px",
                                 "marginRight": "20px"}),
                html.Span("Min (eV):", style={"fontSize": "13px", "marginRight": "4px"}),
                dcc.Input(id="xas-emin", type="number", value=1000,
                          min=0, max=100000, step=100,
                          style={"width": "90px", "marginRight": "20px"}),
                html.Span("Max (eV):", style={"fontSize": "13px", "marginRight": "4px"}),
                dcc.Input(id="xas-emax", type="number", value=18000,
                          min=0, max=100000, step=100,
                          style={"width": "90px", "marginRight": "20px"}),
                html.Span("Points:", style={"fontSize": "13px", "marginRight": "4px"}),
                dcc.Input(id="xas-npts", type="number", value=1001,
                          min=10, max=5000, step=1,
                          style={"width": "80px"}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"}),
        ]), className="mb-3 py-1"),

        # ── Sample rows container ─────────────────────────────────────────
        dbc.Card(dbc.CardBody([
            html.Div(id="xas-sample-rows",
                     children=[make_sample_row(0)]),
            html.Div([
                dbc.Button("+ Add Sample", id="xas-add-btn",
                           color="secondary", size="sm",
                           className="mt-2 me-2"),
                dbc.Button("Update Plot", id="xas-update-btn",
                           color="primary", size="sm",
                           className="mt-2 me-2"),
                dbc.Button("Reset All", id="xas-reset-btn",
                           color="danger", outline=True, size="sm",
                           className="mt-2"),
            ], style={"display": "flex", "alignItems": "center"}),
        ]), className="mb-3"),

        # ── Plot ──────────────────────────────────────────────────────────
        dbc.Card(dbc.CardBody([
            dcc.Graph(id="xas-plot",
                      style={"height": "660px"},
                      config={"displayModeBar": True}),
        ]), className="mb-3"),

        # ── Edge table ────────────────────────────────────────────────────
        dbc.Card(dbc.CardBody([
            html.Div(id="xas-table"),
        ]), className="mb-3"),
    ],
)

