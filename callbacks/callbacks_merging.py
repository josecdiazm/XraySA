
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
_ROW_INPUT_STYLE = {"width": "56px", "fontSize": "0.75rem", "padding": "2px 4px", "marginRight": "6px"}
_ROW_CONTROL_ROW_STYLE = {"display": "flex", "alignItems": "center", "marginBottom": "2px", "flexWrap": "wrap"}


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
        row["scale"] = float(new_value)

    elif kind == "merge-row-offset":
        if new_value is None:
            raise PreventUpdate
        row["offset"] = float(new_value)

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
            dcc.Input(id={"type": "merge-row-qmin-idx", "index": rid}, type="number", step=1,
                      min=0, max=max(n - 1, 0), value=row["qmin_idx"], debounce=True,
                      style=_ROW_INPUT_STYLE),
            html.Span("q Max", style=_ROW_LABEL_STYLE),
            dcc.Input(id={"type": "merge-row-qmax-val", "index": rid}, type="number", step="any",
                      value=round(float(qmax_val), 6), debounce=True, style=_ROW_INPUT_STYLE),
            dcc.Input(id={"type": "merge-row-qmax-idx", "index": rid}, type="number", step=1,
                      min=0, max=max(n - 1, 0), value=row["qmax_idx"], debounce=True,
                      style=_ROW_INPUT_STYLE),
        ], style=_ROW_CONTROL_ROW_STYLE),
        html.Div([
            html.Span("Scale", style=_ROW_LABEL_STYLE),
            dcc.Input(id={"type": "merge-row-scale", "index": rid}, type="number", step="any",
                      value=row["scale"], debounce=True, style=_ROW_INPUT_STYLE),
            html.Span("Offset", style=_ROW_LABEL_STYLE),
            dcc.Input(id={"type": "merge-row-offset", "index": rid}, type="number", step="any",
                      value=row["offset"], debounce=True, style=_ROW_INPUT_STYLE),
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
    fig.update_layout(**_log_axes_layout(unit, showlegend=False))
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
