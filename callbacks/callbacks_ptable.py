
"""
Dash callbacks for the periodic table X-ray edge explorer.
"""

from __future__ import annotations

import json

import dash
from dash import html, Input, Output, State, callback, no_update, ctx
from dash.exceptions import PreventUpdate

import xraydb

from tabs.tab_ptable import (
    periodic_table,
    element_names,
    get_tile_colors,
    shell_headroom_details,
    l_edge_gaps,
    headroom_to_k,
)
from utils.notes_store import load_notes, add_note


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Store the currently-selected element on button click
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("ptable-store", "data"),
    Input({"type": "element-btn", "index": dash.ALL}, "n_clicks"),
    State("pt-emin", "value"),
    State("pt-emax", "value"),
    State("ptable-store", "data"),
    prevent_initial_call=True,
)
def store_selected_element(n_clicks_list, emin, emax, store_data):
    triggered_ctx = dash.callback_context
    if not triggered_ctx.triggered:
        return store_data

    triggered = triggered_ctx.triggered[0]["prop_id"]
    try:
        btn_info = json.loads(triggered.replace(".n_clicks", ""))
        symbol = btn_info["index"]
    except Exception:
        return store_data

    store_data["selected"] = symbol
    store_data["emin"] = emin or 2100
    store_data["emax"] = emax or 5500
    return store_data


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Recolor the grid whenever the energy range or selection changes
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("pt-grid", "children"),
    Input("pt-emin", "value"),
    Input("pt-emax", "value"),
    State("ptable-store", "data"),
)
def update_grid_colors(emin, emax, store_data):
    emin = emin or 0
    emax = emax or 100000
    selected = store_data.get("selected") if store_data else None

    rows = []
    for row in periodic_table:
        cells = []
        for sym in row:
            if not sym:
                cells.append(
                    html.Div(style={"flex": "1", "aspectRatio": "1", "margin": "1px",
                                    "visibility": "hidden"})
                )
            elif sym in ("*", "**"):
                cells.append(
                    html.Div(sym, style={
                        "flex": "1", "aspectRatio": "1",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center",
                        "fontSize": "clamp(8px, 0.8vw, 12px)",
                        "color": "#555", "margin": "1px",
                    })
                )
            else:
                bg, badge = get_tile_colors(sym, emin, emax)
                border = "2.5px solid #2d6a4f" if sym == selected else "1.5px solid #888"
                cells.append(
                    html.Div([
                        html.Button(
                            sym,
                            id={"type": "element-btn", "index": sym},
                            n_clicks=0,
                            style={
                                "width": "100%", "height": "100%",
                                "margin": "0", "padding": "0",
                                "fontWeight": "bold",
                                "fontSize": "clamp(10px, 1.1vw, 18px)",
                                "border": border,
                                "borderRadius": "5px",
                                "cursor": "pointer",
                                "backgroundColor": bg,
                                "color": "#111",
                            }
                        ),
                        # Reference swatch (the shell's pure legend color) as a
                        # folded-corner bookmark, so it can be compared against
                        # the tile's gradient shade.
                        html.Div(style={
                            "position": "absolute", "top": "3px", "right": "3px",
                            "width": "0", "height": "0",
                            "borderStyle": "solid",
                            "borderWidth": "0 13px 13px 0",
                            "borderColor": f"transparent {badge} transparent transparent",
                            "pointerEvents": "none",
                        }),
                    ], style={"flex": "1", "aspectRatio": "1", "margin": "1px",
                              "position": "relative"})
                )
        rows.append(
            html.Div(cells, style={"display": "flex", "flexWrap": "nowrap",
                                   "width": "100%", "marginBottom": "2px"})
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Populate the element detail panel
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("pt-detail-panel", "children"),
    Input("ptable-store", "data"),
)
def update_detail_panel(store_data):
    if not store_data or not store_data.get("selected"):
        return html.Div("Click an element to see details.",
                         style={"color": "#888", "fontSize": "13px"})

    symbol = store_data["selected"]
    name   = element_names.get(symbol, symbol)

    try:
        z     = xraydb.atomic_number(symbol)
        edges = xraydb.xray_edges(symbol)
    except Exception:
        z, edges = "N/A", {}

    # ── Header: name + symbol + Z ────────────────────────────────────────
    header = html.Div([
        html.Div([
            html.Span(name,   style={"fontSize": "20px", "fontWeight": "bold"}),
            html.Span(symbol, style={"fontSize": "32px", "fontWeight": "bold",
                                     "float": "right", "color": "#333"}),
        ]),
        html.Div(f"Z = {z}",
                 style={"textAlign": "center", "fontWeight": "bold",
                        "fontSize": "18px", "color": "#444", "marginTop": "4px"}),
        html.Hr(style={"margin": "8px 0"}),
    ])

    # ── Edge list ────────────────────────────────────────────────────────
    if edges:
        edge_items = []
        for edge_name, obj in edges.items():
            energy = getattr(obj, "energy", None)
            edge_items.append((edge_name, energy))
        # Sort by descending energy
        edge_items.sort(key=lambda x: (x[1] is None, -(x[1] or 0)))

        total = len(edge_items)
        chunk_size = 9
        columns = []

        for c_idx, start in enumerate(range(0, total, chunk_size)):
            if c_idx >= 3:
                break
            chunk = edge_items[start:start + chunk_size]
            col_children = []
            for rank, (ename, eenergy) in enumerate(chunk):
                global_rank = start + rank
                # Color gradient red → blue (high → low energy)
                t = global_rank / max(total - 1, 1)
                r = int(231 + (52  - 231) * t)
                g = int(76  + (152 - 76)  * t)
                b = int(60  + (219 - 60)  * t)
                color = f"rgb({r},{g},{b})"
                text  = (f"{ename}: {int(eenergy)} eV"
                         if eenergy is not None else f"{ename}: N/A")
                col_children.append(
                    html.Div(text, style={
                        "color": color, "fontWeight": "bold",
                        "fontSize": "15px", "padding": "2px 0",
                        "whiteSpace": "nowrap",
                    })
                )
            columns.append(
                html.Div(col_children, style={"minWidth": "0"})
            )

        edges_block = html.Div(columns,
                       style={
                           "display": "grid",
                           "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                           "columnGap": "10px",
                       })
    else:
        edges_block = html.Div("No edge data available.",
                               style={"color": "#888", "fontSize": "13px"})

    return html.Div([header, edges_block])


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Populate the K/L/M headroom panel
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("pt-headroom-panel", "children"),
    Input("ptable-store", "data"),
    Input("pt-emin", "value"),
    Input("pt-emax", "value"),
)
def update_headroom_panel(store_data, emin, emax):
    symbol = (store_data or {}).get("selected")
    if not symbol:
        return html.Div("Click an element to see headroom details.",
                         style={"color": "#888", "fontSize": "13px"})

    emin = emin if emin is not None else 0
    emax = emax if emax is not None else 100000

    status_text = {"above": "not in range", "below": "below range", "none": "no edge data"}

    rows = []
    for shell, status, headroom, k in shell_headroom_details(symbol, emin, emax):
        if status == "ok":
            text = f"{shell}: {headroom:.0f} eV headroom (k = {k:.2f} Å⁻¹)"
        else:
            text = f"{shell}: {status_text[status]}"
        rows.append(html.Div(text, style={"fontSize": "13px", "color": "#555",
                                           "padding": "2px 0"}))

        # Already passed every L-edge at this range ("below") -- nothing
        # actionable, so skip the breakdown; show it for every other status.
        if shell == "L" and status != "below":
            for name, energy, next_name, gap in l_edge_gaps(symbol, emin, emax):
                if gap is None:
                    sub_text = f"{name}: {energy:.0f} eV — no higher edge"
                else:
                    gap_k = headroom_to_k(gap)
                    sub_text = (f"{name}: {energy:.0f} eV — {gap:.0f} eV to {next_name} "
                                f"(k = {gap_k:.2f} Å⁻¹)")
                rows.append(html.Div(sub_text, style={
                    "fontSize": "12px", "color": "#888",
                    "padding": "1px 0 1px 14px",
                }))

    return html.Div(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Render + add per-element notes (persisted to data/ptable_notes.json)
# ─────────────────────────────────────────────────────────────────────────────

def render_notes(symbol):
    if not symbol:
        return html.Div("", style={"color": "#666", "fontSize": "13px"})

    entries = load_notes().get(symbol, [])
    if not entries:
        return html.Div("—", style={"fontSize": "13px", "color": "#555"})

    items = []
    for entry in reversed(entries):  # newest first
        items.append(html.Div([
            html.Div(entry["date"], style={"fontSize": "11px", "color": "#999"}),
            html.Div(entry["text"], style={"fontSize": "13px", "color": "#555",
                                            "lineHeight": "1.4"}),
        ], style={"marginBottom": "8px", "paddingBottom": "8px",
                  "borderBottom": "1px solid #eee"}))
    return html.Div(items)


@callback(
    Output("pt-notes-panel", "children"),
    Output("pt-notes-input", "value"),
    Input("ptable-store", "data"),
    Input("pt-notes-add-btn", "n_clicks"),
    State("pt-notes-input", "value"),
)
def update_notes_panel(store_data, n_clicks, note_text):
    symbol = (store_data or {}).get("selected")

    if ctx.triggered_id == "pt-notes-add-btn" and symbol and note_text and note_text.strip():
        add_note(symbol, note_text.strip())
        return render_notes(symbol), ""

    return render_notes(symbol), no_update