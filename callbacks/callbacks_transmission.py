
"""
Dash callbacks for the XAS transmission calculator tab.
"""

from __future__ import annotations

import numpy as np
from xraydb import material_mu
from dash import html, dcc, callback, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from tabs.tab_transmission import get_all_edges, round_result, make_sample_row


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Add / remove / reset sample rows
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("xas-store",       "data"),
    Output("xas-sample-rows", "children"),
    Input("xas-add-btn",   "n_clicks"),
    Input("xas-reset-btn", "n_clicks"),
    State({"type": "xas-name",      "index": ALL}, "value"),
    State({"type": "xas-formula",   "index": ALL}, "value"),
    State({"type": "xas-density",   "index": ALL}, "value"),
    State({"type": "xas-thickness", "index": ALL}, "value"),
    State("xas-store", "data"),
    prevent_initial_call=True,
)
def manage_sample_rows(n_add, n_reset, names, formulas, densities, thicknesses, store):
    if store is None:
        store = {
            "n_samples": 1,
            "values": [{"name": "", "formula": "", "density": 1.0, "thickness": 50}]
        }

    triggered = ctx.triggered_id

    # ── Reset: go back to one blank row ──────────────────────────────────
    if triggered == "xas-reset-btn":
        store["n_samples"] = 1
        store["values"] = [{"name": "", "formula": "", "density": 1.0, "thickness": 50}]
        rows = [make_sample_row(0)]
        return store, rows

    # ── Add sample: save current inputs first, then append a new blank row ──
    if triggered == "xas-add-btn":
        current_values = []
        for i in range(len(formulas)):
            current_values.append({
                "name":      names[i]      if names[i]      is not None else "",
                "formula":   formulas[i]   if formulas[i]   is not None else "",
                "density":   float(densities[i])  if densities[i]  is not None else 1.0,
                "thickness": thicknesses[i] if thicknesses[i] is not None else 50,
            })

        if len(current_values) < 7:
            current_values.append({
                "name": "", "formula": "", "density": 1.0, "thickness": 50
            })

        store["n_samples"] = len(current_values)
        store["values"]    = current_values

        rows = [
            make_sample_row(
                i,
                name      = v["name"],
                formula   = v["formula"],
                density   = v["density"],
                thickness = v["thickness"],
            )
            for i, v in enumerate(current_values)
        ]
        return store, rows

    return store, [make_sample_row(i) for i in range(store.get("n_samples", 1))]


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Compute transmission plot + edge table
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("xas-plot",  "figure"),
    Output("xas-table", "children"),
    Input("xas-update-btn", "n_clicks"),
    State("xas-emin",   "value"),
    State("xas-emax",   "value"),
    State("xas-npts",   "value"),
    State({"type": "xas-name",      "index": ALL}, "value"),
    State({"type": "xas-formula",   "index": ALL}, "value"),
    State({"type": "xas-density",   "index": ALL}, "value"),
    State({"type": "xas-thickness", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def update_plot_and_table(n_clicks, emin, emax, npts,
                          names, formulas, densities, thicknesses):

    emin   = emin  or 1000
    emax   = emax  or 18000
    npts   = int(npts) if npts else 401
    energy = np.linspace(emin, emax, npts)

    # ── Collect valid samples ─────────────────────────────────────────────
    samples = []
    for i, formula in enumerate(formulas):
        if not formula or not formula.strip():
            continue
        name      = (names[i] or "").strip() or f"Sample {i+1}"
        density   = densities[i]    if densities[i]   is not None else 1.0
        thickness = thicknesses[i]  if thicknesses[i] is not None else 50.0
        samples.append({
            "label":     name,
            "formula":   formula.strip(),
            "density":   density,
            "thickness": thickness,
        })

    # ── Empty state ───────────────────────────────────────────────────────
    if not samples:
        fig = go.Figure()
        fig.update_layout(
            title="Enter at least one sample formula and click Update Plot.",
            xaxis_title="Energy (keV)",
            yaxis_title="Transmitted Fraction",
            template="plotly_white",
        )
        return fig, dbc.Alert("No samples entered yet.", color="warning")

    # ── Build plot ────────────────────────────────────────────────────────
    fig = go.Figure()

    for s in samples:
        try:
            mu    = material_mu(s["formula"], energy,
                                density=s["density"], kind="total")
            trans = np.exp(-(s["thickness"] / 10000) * mu)
            fig.add_trace(go.Scatter(
                x=energy / 1000,
                y=trans,
                mode="lines",
                name=f"{s['label']} ({s['thickness']} μm, {s['density']} g/cm³)",
            ))
        except Exception as e:
            fig.add_trace(go.Scatter(
                x=[], y=[],
                mode="lines",
                name=f"{s['label']}: Error — {e}",
            ))

    # Reference lines using shapes + annotations so full text is visible
    ref_lines = [
        (1.0,       "T = 1"),
        (1/np.e,    "T = 1/e ≈ 0.368"),
        (1/np.e**2, "T = 1/e² ≈ 0.135"),
    ]
    for y_val, label in ref_lines:
        fig.add_shape(
            type="line",
            x0=0, x1=1, xref="paper",
            y0=y_val, y1=y_val,
            line=dict(color="black", width=1, dash="dash"),
        )
        fig.add_annotation(
            x=1, xref="paper",
            y=y_val,
            text=label,
            showarrow=False,
            xanchor="left",
            font=dict(size=11, color="black"),
            bgcolor="white",
            borderpad=2,
        )

    fig.update_layout(
        title="X-ray Transmission",
        xaxis_title="Energy (keV)",
        yaxis_title="Transmitted Fraction",
        yaxis=dict(range=[0, 1.05]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0),
        margin=dict(l=60, r=160, t=80, b=60),
        hovermode="x unified",
        template="plotly_white",
    )

    # ── Build edge table ──────────────────────────────────────────────────
    table_rows = []
    for s in samples:
        for elem, edgename, edge_e in get_all_edges(s["formula"], emin, emax):
            try:
                mu_edge   = material_mu(s["formula"], [edge_e],
                                        density=s["density"])[0]
                abs_len   = 10000 / mu_edge if mu_edge != 0 else None
                t_abs     = abs_len / s["thickness"] if abs_len and s["thickness"] else None

                mu_before = material_mu(s["formula"], [edge_e - 5],
                                        density=s["density"])[0]
                mu_after  = material_mu(s["formula"], [edge_e + 5],
                                        density=s["density"])[0]
                denom     = abs(mu_after - mu_before)
                step_len  = 10000 / denom if denom != 0 else None
                t_step    = step_len / s["thickness"] if step_len and s["thickness"] else None

            except Exception:
                abs_len = t_abs = step_len = t_step = None

            table_rows.append({
                "Sample":           s["label"],
                "Element":          elem,
                "Edge":             edgename,
                "Edge Energy (eV)": round(edge_e, 1),
                "Abs Length (μm)":  round_result(abs_len),
                "t / Abs Length":   round_result(t_abs),
                "Edge Step (μm)":   round_result(step_len),
                "t / Edge Step":    round_result(t_step),
            })

    if not table_rows:
        table_content = dbc.Alert(
            "No absorption edges found in the selected energy range.",
            color="info"
        )
    else:
        cols = ["Sample", "Element", "Edge", "Edge Energy (eV)",
                "Abs Length (μm)", "t / Abs Length",
                "Edge Step (μm)",  "t / Edge Step"]

        header = html.Thead(html.Tr([
            html.Th(c, style={
                "textAlign": "center", "fontSize": "12px",
                "fontWeight": "bold", "border": "1px solid #ccc",
                "padding": "4px 8px", "whiteSpace": "nowrap",
            }) for c in cols
        ]))

        body_rows = []
        for row in table_rows:
            body_rows.append(html.Tr([
                html.Td(row[c], style={
                    "textAlign": "center", "fontSize": "12px",
                    "border": "1px solid #ccc", "padding": "3px 8px",
                    "whiteSpace": "nowrap",
                }) for c in cols
            ]))

        table_content = html.Div([
            html.P(
                "Guidance:  t / Abs Length: 0.5–1.5   |   t / Edge Step: 0.1–1.0",
                style={"fontSize": "12px", "color": "#666",
                       "fontStyle": "italic", "marginBottom": "6px"}
            ),
            html.Div(
                dbc.Table([header, html.Tbody(body_rows)],
                          bordered=True, hover=True,
                          responsive=True, size="sm"),
                style={"overflowX": "auto"},
            ),
        ])

    return fig, table_content