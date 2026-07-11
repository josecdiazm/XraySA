
"""
Dash callbacks for the SWAXS Merging tab: a single RAW-style "Profiles"
workspace. Everything (loaded files, per-row q range/scale/offset,
selection/visibility/star state, and derived Average/Subtract/Merge
results) lives in one dcc.Store (`merge-profile-store`); every other
piece of UI (the row list, the plot) is a pure render of that store.
"""

from __future__ import annotations
import os
import uuid
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, ALL, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from utils.merging_utils import (
    list_csv_files,
    read_1d_csv,
    apply_view,
    average_profiles,
    subtract_profiles,
    merge_profiles_pairwise,
    write_1d_csv,
)
from utils.batch_utils import filter_excluded
from utils.native_dialog import pick_folder, pick_save_file
from callbacks._shared import register_folder_browse_callback, stage_dropped_files, azimuth_color

register_folder_browse_callback("merge-folder-input")

_UNIT_LABELS = {
    "q_A^-1":  "q (Å⁻¹)",
    "q_nm^-1": "q (nm⁻¹)",
    "2th_deg": "2θ (°)",
}

_ICON_BTN_STYLE = {
    "border": "none", "background": "transparent", "cursor": "pointer",
    "fontSize": "0.9rem", "padding": "0px 3px", "lineHeight": "1",
}
_ROW_LABEL_STYLE = {"fontSize": "0.75rem", "color": "#6c757d", "width": "34px", "flexShrink": "0"}
_ROW_INPUT_VPAD = 3 / 1.1  # vertical padding (px) for q Min/q Max/Scale/Offset input boxes
_ROW_INPUT_STYLE = {
    "width": "70px", "fontSize": "0.8rem",
    "padding": f"{_ROW_INPUT_VPAD:.3g}px 5px", "marginRight": "6px",
}
_ROW_CONTROL_ROW_STYLE = {"display": "flex", "alignItems": "center", "marginBottom": "2px", "flexWrap": "wrap"}

_SPIN_BTN_STYLE = {
    "border": "1px solid #ced4da", "background": "#f8f9fa", "cursor": "pointer",
    "fontSize": "0.5rem", "lineHeight": "1", "padding": "0px", "width": "14px", "height": "11px",
    "display": "flex", "alignItems": "center", "justifyContent": "center", "color": "#495057",
}


def _spin_input(field_type: str, rid: str, value, **input_kwargs):
    """
    A dcc.Input paired with a RAW-style stacked up/down spin button — RAW's
    own q-index/Scale/Offset controls are a wx.SpinButton next to a plain
    text box (RAWCustomCtrl.py's IntSpinCtrl/FloatSpinCtrl), not a native
    HTML number-input spinner, so we build the same explicit widget here.
    """
    return html.Div([
        dcc.Input(id={"type": field_type, "index": rid}, value=value, debounce=True,
                   style={**_ROW_INPUT_STYLE, "marginRight": "2px"}, **input_kwargs),
        html.Div([
            html.Button("▲", id={"type": f"{field_type}-up", "index": rid}, n_clicks=0,
                        style={**_SPIN_BTN_STYLE, "borderBottom": "none", "borderRadius": "2px 2px 0 0"}),
            html.Button("▼", id={"type": f"{field_type}-down", "index": rid}, n_clicks=0,
                        style={**_SPIN_BTN_STYLE, "borderRadius": "0 0 2px 2px"}),
        ], style={"display": "flex", "flexDirection": "column", "marginRight": "6px"}),
    ], style={"display": "flex", "alignItems": "center"})


def _parse_decimals(text: str) -> int:
    """Digits after the decimal point in *text* (0 if there isn't one) —
    mirrors RAW's FloatSpinCtrl.OnScaleChange, which recomputes this from
    whatever's currently typed every time the field is edited."""
    text = text.strip().replace(",", ".")
    return len(text.split(".", 1)[1]) if "." in text else 0


def _step_for(decimals: int) -> float:
    """The spin-button step implied by *decimals* — RAW's `1 / ScaleDivider`,
    where ScaleDivider = 10**decimals (or 1 for a whole-number field)."""
    return 10 ** -decimals if decimals > 0 else 1.0


def _log_axes_layout(unit: str, **extra) -> dict:
    """
    Shared log-log axis layout with a proper q-unit label, matching the
    tick/exponent styling used everywhere else in the app (major + minor
    ticks, power-of-ten scientific notation).
    """
    layout = dict(
        xaxis_title=_UNIT_LABELS.get(unit, unit),
        yaxis_title="Intensity",
        xaxis_type="log",
        yaxis_type="log",
        margin=dict(l=10, r=10, t=20, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(
            showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True,
            ticks="outside", exponentformat="power", showexponent="all",
            minor=dict(ticks="outside"),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True,
            ticks="outside", exponentformat="power", showexponent="all",
            minor=dict(ticks="outside"),
        ),
    )
    layout.update(extra)
    return layout


# ─────────────────────────────────────────────────────────────────────────────
# Row <-> profile-dict helpers
# ─────────────────────────────────────────────────────────────────────────────

def _new_row(filename: str, profile: dict, *, source: str, color: str) -> dict:
    """Build a new profile-store row from a {"q","I","sigma","unit"} dict."""
    n = len(profile["q"])
    sigma = profile.get("sigma")
    return {
        "id": uuid.uuid4().hex[:8],
        "filename": filename,
        "q_raw": list(np.asarray(profile["q"], dtype=float)),
        "i_raw": list(np.asarray(profile["I"], dtype=float)),
        "err_raw": list(np.asarray(sigma, dtype=float)) if sigma is not None else None,
        "unit": profile["unit"],
        "qmin_idx": 0,
        "qmax_idx": max(n - 1, 0),
        "scale": 1.0,
        "offset": 0.0,
        "scale_decimals": 1,   # matches RAW's own default display "1.0" / "0.0"
        "offset_decimals": 1,
        "visible": True,
        "selected": False,
        "starred": False,
        "located": False,
        "color": color,
        "source": source,
    }


def _row_to_profile(row: dict) -> dict:
    return {
        "q": np.array(row["q_raw"]),
        "I": np.array(row["i_raw"]),
        "sigma": np.array(row["err_raw"]) if row.get("err_raw") is not None else None,
        "unit": row["unit"],
    }


def _row_view(row: dict) -> dict:
    """The profile's currently-displayed (q-trimmed, scaled/offset) view."""
    return apply_view(_row_to_profile(row), row["qmin_idx"], row["qmax_idx"], row["scale"], row["offset"])


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Load files: folder browse or drag-and-drop, both append to the store
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-profile-store", "data"),
    Output("merge-folder-status", "children"),
    Input("merge-load-folder-btn", "n_clicks"),
    State("merge-folder-input", "value"),
    State("merge-exclude-input", "value"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def load_merge_folder(n_clicks, folder_path, exclude_text, store):
    if not n_clicks:
        raise PreventUpdate

    try:
        files = list_csv_files(folder_path)
    except Exception as exc:
        return no_update, f"✘ {exc}"

    kept = filter_excluded(files, (exclude_text or "").split(","))
    if not kept:
        return no_update, f"No CSV/TXT files found in '{folder_path}' after exclusions."

    store = list(store or [])
    added = 0
    for fname in kept:
        try:
            profile = read_1d_csv(os.path.join(folder_path, fname))
        except Exception:
            continue
        store.append(_new_row(fname, profile, source="uploaded", color=azimuth_color(len(store))))
        added += 1

    return store, f"✔ Loaded {added} of {len(kept)} file(s)."


@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Output("merge-upload-tempdir-store", "data"),
    Output("merge-folder-status", "children", allow_duplicate=True),
    Input("merge-upload-files", "contents"),
    State("merge-upload-files", "filename"),
    State("merge-upload-tempdir-store", "data"),
    State("merge-exclude-input", "value"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def handle_dropped_files(contents_list, filenames_list, prev_tempdir, exclude_text, store):
    if not contents_list or not filenames_list:
        raise PreventUpdate

    tempdir = stage_dropped_files(contents_list, filenames_list, prev_tempdir, prefix="xraysa_merge_upload_")
    files = list_csv_files(tempdir)
    kept = filter_excluded(files, (exclude_text or "").split(","))
    if not kept:
        return no_update, tempdir, "✘ None of the dropped files were a supported CSV/TXT profile."

    store = list(store or [])
    added = 0
    for fname in kept:
        try:
            profile = read_1d_csv(os.path.join(tempdir, fname))
        except Exception:
            continue
        store.append(_new_row(fname, profile, source="uploaded", color=azimuth_color(len(store))))
        added += 1

    return store, tempdir, f"✔ Received {added} dropped file(s) — staged for this session."


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Per-row interactions: select / eye / star, q-range index+value, scale/offset
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Input({"type": "merge-row-select", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-eye", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-star", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-locate", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-qmin-idx", "index": ALL}, "value"),
    Input({"type": "merge-row-qmin-val", "index": ALL}, "value"),
    Input({"type": "merge-row-qmax-idx", "index": ALL}, "value"),
    Input({"type": "merge-row-qmax-val", "index": ALL}, "value"),
    Input({"type": "merge-row-scale", "index": ALL}, "value"),
    Input({"type": "merge-row-offset", "index": ALL}, "value"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def manage_row_interactions(select_clicks, eye_clicks, star_clicks, locate_clicks,
                             qmin_idxs, qmin_vals, qmax_idxs, qmax_vals,
                             scales, offsets, store):
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict):
        raise PreventUpdate

    kind, rid = trigger["type"], trigger["index"]
    new_value = ctx.triggered[0]["value"]

    store = list(store or [])
    row = next((r for r in store if r["id"] == rid), None)
    if row is None:
        raise PreventUpdate

    if kind == "merge-row-select":
        if not new_value:
            raise PreventUpdate
        row["selected"] = not row["selected"]

    elif kind == "merge-row-eye":
        if not new_value:
            raise PreventUpdate
        row["visible"] = not row["visible"]

    elif kind == "merge-row-star":
        if not new_value:
            raise PreventUpdate
        newly_starred = not row["starred"]
        for r in store:
            r["starred"] = False
        row["starred"] = newly_starred

    elif kind == "merge-row-locate":
        if not new_value:
            raise PreventUpdate
        row["located"] = not row["located"]

    elif kind in ("merge-row-qmin-idx", "merge-row-qmax-idx"):
        if new_value is None:
            raise PreventUpdate
        n = len(row["q_raw"])
        idx = max(0, min(int(new_value), n - 1))
        if kind == "merge-row-qmin-idx":
            row["qmin_idx"] = min(idx, row["qmax_idx"])
        else:
            row["qmax_idx"] = max(idx, row["qmin_idx"])

    elif kind in ("merge-row-qmin-val", "merge-row-qmax-val"):
        if new_value is None:
            raise PreventUpdate
        q_raw = np.array(row["q_raw"])
        idx = int(np.argmin(np.abs(q_raw - float(new_value))))
        if kind == "merge-row-qmin-val":
            row["qmin_idx"] = min(idx, row["qmax_idx"])
        else:
            row["qmax_idx"] = max(idx, row["qmin_idx"])

    elif kind == "merge-row-scale":
        if new_value is None:
            raise PreventUpdate
        text = str(new_value)
        row["scale"] = float(text.replace(",", "."))
        row["scale_decimals"] = _parse_decimals(text)

    elif kind == "merge-row-offset":
        if new_value is None:
            raise PreventUpdate
        text = str(new_value)
        row["offset"] = float(text.replace(",", "."))
        row["offset_decimals"] = _parse_decimals(text)

    else:
        raise PreventUpdate

    return store


# ─────────────────────────────────────────────────────────────────────────────
# 2.5.  RAW-style spin buttons (▲/▼) for q-index / Scale / Offset — see
#       _spin_input()'s docstring for why these are explicit buttons rather
#       than a native HTML number-input spinner. Scale/Offset's step tracks
#       the number of decimals currently typed in that field (see
#       _parse_decimals/_step_for), exactly like RAW's FloatSpinCtrl.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Input({"type": "merge-row-qmin-idx-up", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-qmin-idx-down", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-qmax-idx-up", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-qmax-idx-down", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-scale-up", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-scale-down", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-offset-up", "index": ALL}, "n_clicks"),
    Input({"type": "merge-row-offset-down", "index": ALL}, "n_clicks"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def handle_spin_buttons(qmin_up, qmin_down, qmax_up, qmax_down,
                         scale_up, scale_down, offset_up, offset_down, store):
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict) or not ctx.triggered[0]["value"]:
        raise PreventUpdate

    kind, rid = trigger["type"], trigger["index"]
    store = list(store or [])
    row = next((r for r in store if r["id"] == rid), None)
    if row is None:
        raise PreventUpdate

    n = len(row["q_raw"])
    if kind == "merge-row-qmin-idx-up":
        row["qmin_idx"] = min(row["qmin_idx"] + 1, row["qmax_idx"])
    elif kind == "merge-row-qmin-idx-down":
        row["qmin_idx"] = max(row["qmin_idx"] - 1, 0)
    elif kind == "merge-row-qmax-idx-up":
        row["qmax_idx"] = min(row["qmax_idx"] + 1, n - 1)
    elif kind == "merge-row-qmax-idx-down":
        row["qmax_idx"] = max(row["qmax_idx"] - 1, row["qmin_idx"])
    elif kind == "merge-row-scale-up":
        step = _step_for(row["scale_decimals"])
        row["scale"] = round(row["scale"] + step, max(row["scale_decimals"], 0))
    elif kind == "merge-row-scale-down":
        step = _step_for(row["scale_decimals"])
        newval = round(row["scale"] - step, max(row["scale_decimals"], 0))
        if newval <= 0.0:
            # Scale is never_negative in RAW too — rather than land on/below
            # zero, refine to one more decimal and step by that instead
            # (0.1 -> 0.09, 0.01 -> 0.009, ...).
            row["scale_decimals"] += 1
            step = _step_for(row["scale_decimals"])
            newval = round(row["scale"] - step, row["scale_decimals"])
        row["scale"] = newval
    elif kind == "merge-row-offset-up":
        step = _step_for(row["offset_decimals"])
        row["offset"] = round(row["offset"] + step, max(row["offset_decimals"], 0))
    elif kind == "merge-row-offset-down":
        step = _step_for(row["offset_decimals"])
        row["offset"] = round(row["offset"] - step, max(row["offset_decimals"], 0))
    else:
        raise PreventUpdate

    return store


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Render the profile list and the main plot from the store (pure renders)
# ─────────────────────────────────────────────────────────────────────────────

def _row_component(row: dict):
    rid = row["id"]
    bg = "#dbe4ff" if row["selected"] else "#ffffff"
    eye_icon = "👁" if row["visible"] else "🚫"
    star_icon = "★" if row["starred"] else "☆"
    name = ("★ " if row["starred"] else "") + row["filename"]

    q_raw = row["q_raw"]
    n = len(q_raw)
    qmin_val = q_raw[row["qmin_idx"]]
    qmax_val = q_raw[row["qmax_idx"]]

    locate_style = dict(_ICON_BTN_STYLE)
    locate_style["color"] = "#f1c40f" if row["located"] else "#adb5bd"

    header = html.Div([
        html.Button(eye_icon, id={"type": "merge-row-eye", "index": rid}, n_clicks=0,
                    style=_ICON_BTN_STYLE, title="Show/hide"),
        html.Button("⌖", id={"type": "merge-row-locate", "index": rid}, n_clicks=0,
                    style=locate_style, title="Locate: bolden this curve on the plot"),
        html.Button(star_icon, id={"type": "merge-row-star", "index": rid}, n_clicks=0,
                    style=_ICON_BTN_STYLE, title="Mark as reference for Subtract/Merge"),
        html.Span(style={
            "display": "inline-block", "width": "10px", "height": "10px",
            "backgroundColor": row["color"], "borderRadius": "2px",
            "marginRight": "6px", "flexShrink": "0",
        }),
        html.Span(
            name,
            id={"type": "merge-row-select", "index": rid}, n_clicks=0,
            style={
                "cursor": "pointer", "flexGrow": "1", "fontSize": "0.85rem",
                "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
            },
            title="Click to select",
        ),
    ], style={"display": "flex", "alignItems": "center", "gap": "2px"})

    controls = html.Div([
        html.Div([
            html.Span("q Min", style=_ROW_LABEL_STYLE),
            dcc.Input(id={"type": "merge-row-qmin-val", "index": rid}, type="number", step="any",
                      value=round(float(qmin_val), 6), debounce=True, style=_ROW_INPUT_STYLE),
            _spin_input("merge-row-qmin-idx", rid, row["qmin_idx"],
                        type="number", step=1, min=0, max=max(n - 1, 0)),
            html.Span("q Max", style={**_ROW_LABEL_STYLE, "marginLeft": "22px"}),
            dcc.Input(id={"type": "merge-row-qmax-val", "index": rid}, type="number", step="any",
                      value=round(float(qmax_val), 6), debounce=True, style=_ROW_INPUT_STYLE),
            _spin_input("merge-row-qmax-idx", rid, row["qmax_idx"],
                        type="number", step=1, min=0, max=max(n - 1, 0)),
        ], style=_ROW_CONTROL_ROW_STYLE),
        html.Div([
            html.Span("Scale", style=_ROW_LABEL_STYLE),
            _spin_input("merge-row-scale", rid, f"{row['scale']:.{row['scale_decimals']}f}",
                        type="number", step="any"),
            html.Span("Offset", style={**_ROW_LABEL_STYLE, "marginLeft": "128px"}),
            _spin_input("merge-row-offset", rid, f"{row['offset']:.{row['offset_decimals']}f}",
                        type="number", step="any"),
        ], style=_ROW_CONTROL_ROW_STYLE),
    ], style={"marginTop": "4px", "marginLeft": "18px"})

    return html.Div([header, controls], style={
        "backgroundColor": bg, "borderRadius": "4px", "border": "1px solid #dee2e6",
        "padding": "6px 8px", "marginBottom": "6px",
    })


@callback(
    Output("merge-profile-list", "children"),
    Input("merge-profile-store", "data"),
)
def render_profile_list(store):
    if not store:
        return html.Div(
            "No profiles loaded yet — load a folder or drag & drop files above.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )
    return [_row_component(row) for row in store]


@callback(
    Output("merge-select-all-btn", "children"),
    Input("merge-profile-store", "data"),
)
def render_select_all_icon(store):
    return "☑" if any(r["selected"] for r in (store or [])) else "☐"


@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Input("merge-select-all-btn", "n_clicks"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def toggle_select_all(n_clicks, store):
    if not n_clicks:
        raise PreventUpdate
    store = list(store or [])
    if not store:
        raise PreventUpdate

    select = not any(r["selected"] for r in store)
    for r in store:
        r["selected"] = select
    return store


@callback(
    Output("merge-toggle-visible-btn", "children"),
    Input("merge-profile-store", "data"),
)
def render_toggle_visible_icon(store):
    selected = [r for r in (store or []) if r["selected"]]
    if not selected:
        return "👁"
    return "👁" if all(r["visible"] for r in selected) else "🚫"


@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Input("merge-toggle-visible-btn", "n_clicks"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def toggle_selected_visibility(n_clicks, store):
    if not n_clicks:
        raise PreventUpdate
    store = list(store or [])
    selected = [r for r in store if r["selected"]]
    if not selected:
        raise PreventUpdate

    show = not all(r["visible"] for r in selected)
    for r in selected:
        r["visible"] = show
    return store


@callback(
    Output("merge-graph", "figure"),
    Input("merge-profile-store", "data"),
)
def render_main_plot(store):
    fig = go.Figure()
    unit = "q_A^-1"
    for row in (store or []):
        view = _row_view(row)
        unit = view["unit"] or unit
        name = ("★ " if row["starred"] else "") + row["filename"]
        fig.add_trace(go.Scatter(
            x=view["q"], y=view["I"], mode="lines",
            name=name, visible=row["visible"],
            line=dict(width=3.0 if row["located"] else 1.5, color=row["color"]),
        ))
    fig.update_layout(**_log_axes_layout(
        unit, showlegend=False, margin=dict(l=10, r=10, t=40, b=10),
    ))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Average / Subtract / Merge / Remove — act on whatever's selected
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-profile-store", "data", allow_duplicate=True),
    Output("merge-status", "children"),
    Input("merge-average-btn", "n_clicks"),
    Input("merge-subtract-btn", "n_clicks"),
    Input("merge-merge-btn", "n_clicks"),
    Input("merge-remove-btn", "n_clicks"),
    State("merge-profile-store", "data"),
    State("merge-splice-q-input", "value"),
    prevent_initial_call=True,
)
def handle_combine_buttons(avg_clicks, sub_clicks, merge_clicks, remove_clicks, store, splice_q):
    trigger = ctx.triggered_id
    if trigger not in ("merge-average-btn", "merge-subtract-btn", "merge-merge-btn", "merge-remove-btn"):
        raise PreventUpdate

    store = list(store or [])
    selected = [r for r in store if r["selected"]]
    starred = next((r for r in store if r["starred"]), None)

    if trigger == "merge-remove-btn":
        if not selected:
            return no_update, "✘ Select at least one profile to remove."
        removed_ids = {r["id"] for r in selected}
        store = [r for r in store if r["id"] not in removed_ids]
        return store, f"✔ Removed {len(removed_ids)} profile(s)."

    if trigger == "merge-average-btn":
        if not selected:
            return no_update, "✘ Select at least one profile to average."
        avg = average_profiles([_row_view(r) for r in selected])
        new_row = _new_row(f"A_{selected[0]['filename']}", avg, source="average",
                            color=azimuth_color(len(store)))
        store.append(new_row)
        return store, f"✔ Averaged {len(selected)} profile(s) → {new_row['filename']}."

    if trigger == "merge-subtract-btn":
        if starred is None:
            return no_update, "✘ Star a reference profile (☆) first, then select the profile(s) to subtract it from."
        others = [r for r in selected if r["id"] != starred["id"]]
        if not others:
            return no_update, "✘ Select at least one profile (besides the starred one) to subtract."
        base_view = _row_view(starred)
        added = []
        for other in others:
            result = subtract_profiles(base_view, _row_view(other))
            new_row = _new_row(f"S_{starred['filename']}", result, source="subtract",
                                color=azimuth_color(len(store)))
            store.append(new_row)
            added.append(new_row["filename"])
        return store, f"✔ Subtracted → {', '.join(added)}."

    if trigger == "merge-merge-btn":
        if starred is None:
            return no_update, "✘ Star a base profile (☆) first, then select the profile(s) to merge into it."
        if splice_q is None:
            return no_update, "✘ Enter a splice q value."
        others = [r for r in selected if r["id"] != starred["id"]]
        if not others:
            return no_update, "✘ Select at least one profile (besides the starred one) to merge."
        merged = merge_profiles_pairwise(_row_view(starred), [_row_view(r) for r in others], float(splice_q))
        new_row = _new_row(f"M_{starred['filename']}", merged, source="merge",
                            color=azimuth_color(len(store)))
        store.append(new_row)
        return store, f"✔ Merged {len(others) + 1} profile(s) → {new_row['filename']}."

    raise PreventUpdate


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Save — single selection prompts a Save-As dialog, multiple prompt a folder
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-status", "children", allow_duplicate=True),
    Input("merge-save-btn", "n_clicks"),
    State("merge-profile-store", "data"),
    prevent_initial_call=True,
)
def handle_save(n_clicks, store):
    if not n_clicks:
        raise PreventUpdate

    selected = [r for r in (store or []) if r["selected"]]
    if not selected:
        return "✘ Select at least one profile to save."

    if len(selected) == 1:
        row = selected[0]
        path = pick_save_file(initial_filename=row["filename"])
        if not path:
            raise PreventUpdate
        folder, filename = os.path.split(path)
        try:
            out_path = write_1d_csv(_row_view(row), folder, filename)
        except Exception as exc:
            return f"✘ {exc}"
        return f"✔ Saved {out_path}"

    folder = pick_folder("Choose a folder to save the selected profiles into")
    if not folder:
        raise PreventUpdate

    saved = []
    for row in selected:
        try:
            saved.append(write_1d_csv(_row_view(row), folder, row["filename"]))
        except Exception as exc:
            return f"✘ Failed on '{row['filename']}': {exc}"
    return f"✔ Saved {len(saved)} file(s) to {folder}"
