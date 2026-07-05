
"""
Dash callbacks for the SWAXS Merging tab: a generic Average panel and a
separate Merge panel that loads two previously-saved averaged files.
"""

from __future__ import annotations
import os
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from utils.merging_utils import (
    list_csv_files,
    read_1d_csv,
    average_profiles,
    merge_profiles,
    write_1d_csv,
)
from utils.batch_utils import filter_excluded
from callbacks._shared import register_folder_browse_callback, stage_dropped_files

register_folder_browse_callback("merge-avg-folder-input")
register_folder_browse_callback("merge-avg-output-folder")
register_folder_browse_callback("merge-files-folder-input")
register_folder_browse_callback("merge-save-output-folder")

_UNIT_LABELS = {
    "q_A^-1":  "q (Å⁻¹)",
    "q_nm^-1": "q (nm⁻¹)",
    "2th_deg": "2θ (°)",
    "r_mm":    "r (mm)",
}


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
# 1.  Average panel: load folder → select files → average → save
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-avg-all-files", "data"),
    Output("merge-avg-folder-status", "children"),
    Input("merge-avg-load-folder-btn", "n_clicks"),
    State("merge-avg-folder-input", "value"),
    prevent_initial_call=True,
)
def load_avg_folder(n_clicks, folder_path):
    if not n_clicks:
        raise PreventUpdate
    try:
        files = list_csv_files(folder_path)
    except Exception as exc:
        return [], f"✘ {exc}"
    if not files:
        return [], f"No CSV/TXT files found in '{folder_path}'."
    return files, f"✔ Found {len(files)} file(s)."


@callback(
    Output("merge-avg-all-files", "data", allow_duplicate=True),
    Output("merge-avg-folder-input", "value", allow_duplicate=True),
    Output("merge-avg-folder-status", "children", allow_duplicate=True),
    Output("merge-avg-upload-tempdir-store", "data"),
    Input("merge-avg-upload-files", "contents"),
    State("merge-avg-upload-files", "filename"),
    State("merge-avg-upload-tempdir-store", "data"),
    prevent_initial_call=True,
)
def handle_avg_dropped_files(contents_list, filenames_list, prev_tempdir):
    if not contents_list or not filenames_list:
        raise PreventUpdate

    tempdir = stage_dropped_files(contents_list, filenames_list, prev_tempdir, prefix="xraysa_merge_upload_")
    files = list_csv_files(tempdir)
    if not files:
        return no_update, tempdir, "✘ None of the dropped files were a supported CSV/TXT profile.", tempdir

    status = f"✔ Received {len(files)} dropped file(s) — staged in a temporary folder for this session."
    return files, tempdir, status, tempdir


@callback(
    Output("merge-avg-file-checklist", "options"),
    Output("merge-avg-file-checklist", "value"),
    Output("merge-avg-file-count", "children"),
    Input("merge-avg-all-files", "data"),
    Input("merge-avg-exclude-input", "value"),
)
def apply_avg_exclusion_filter(all_files, exclude_text):
    if not all_files:
        return [], [], "No files loaded yet."

    keywords = (exclude_text or "").split(",")
    kept = filter_excluded(all_files, keywords)

    options = [{"label": f, "value": f} for f in kept]
    count_text = f"{len(kept)} of {len(all_files)} file(s) selected."
    return options, kept, count_text


# A single callback owns merge-avg-graph/-avg-store so there's never more
# than one writer per output (avoids allow_duplicate entirely).
@callback(
    Output("merge-avg-store", "data"),
    Output("merge-avg-graph", "figure"),
    Output("merge-avg-folder-status", "children", allow_duplicate=True),
    Input("merge-avg-file-checklist", "value"),
    Input("merge-avg-average-btn", "n_clicks"),
    State("merge-avg-folder-input", "value"),
    prevent_initial_call=True,
)
def update_avg_graph(selected, avg_clicks, folder_path):
    trigger = ctx.triggered_id

    if trigger == "merge-avg-file-checklist":
        if not selected:
            return no_update, go.Figure(), no_update
        try:
            profiles = [read_1d_csv(os.path.join(folder_path, f)) for f in selected]
        except Exception:
            raise PreventUpdate

        fig = go.Figure()
        unit = "q"
        for p, fname in zip(profiles, selected):
            unit = p["unit"]
            fig.add_trace(go.Scatter(x=p["q"], y=p["I"], mode="lines", name=fname))
        fig.update_layout(**_log_axes_layout(
            unit,
            legend=dict(orientation="v", x=1.02, y=1, xanchor="left", font=dict(size=10)),
            margin=dict(l=10, r=140, t=20, b=10),
        ))
        return no_update, fig, no_update

    if trigger == "merge-avg-average-btn":
        if not avg_clicks:
            raise PreventUpdate
        if not selected:
            return no_update, no_update, "✘ Select at least one file to average."

        try:
            profiles = [read_1d_csv(os.path.join(folder_path, f)) for f in selected]
            avg = average_profiles(profiles)
        except Exception as exc:
            return no_update, no_update, f"✘ Averaging failed: {exc}"

        fig = go.Figure()
        for p, fname in zip(profiles, selected):
            fig.add_trace(go.Scatter(
                x=p["q"], y=p["I"], mode="lines",
                line=dict(width=1, color="steelblue"),
                opacity=0.35,
                name=fname, showlegend=False,
            ))
        fig.add_trace(go.Scatter(
            x=avg["q"], y=avg["I"], mode="lines",
            line=dict(width=2, color="crimson"), name="Average",
        ))
        fig.update_layout(**_log_axes_layout(avg["unit"]))

        data = {"q": avg["q"].tolist(), "I": avg["I"].tolist(), "unit": avg["unit"]}
        return data, fig, f"✔ Averaged {len(selected)} file(s)."

    raise PreventUpdate


@callback(
    Output("merge-avg-save-status", "children"),
    Input("merge-avg-save-btn", "n_clicks"),
    State("merge-avg-store", "data"),
    State("merge-avg-filename", "value"),
    State("merge-avg-output-folder", "value"),
    prevent_initial_call=True,
)
def save_average(n_clicks, avg_data, filename, output_folder):
    if not n_clicks:
        raise PreventUpdate
    if not avg_data:
        return "✘ Nothing to save yet — average some files first."
    if not filename or not output_folder:
        return "✘ Enter a filename and an output folder."

    profile = {"q": np.array(avg_data["q"]), "I": np.array(avg_data["I"]), "unit": avg_data["unit"]}
    try:
        out_path = write_1d_csv(profile, output_folder, filename)
    except Exception as exc:
        return f"✘ {exc}"
    return f"✔ Saved {out_path}"


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Merge panel: browse folder → pick SAXS/WAXS files → load
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-files-all", "data"),
    Output("merge-files-folder-status", "children"),
    Output("merge-saxs-select", "options"),
    Output("merge-waxs-select", "options"),
    Input("merge-files-load-folder-btn", "n_clicks"),
    State("merge-files-folder-input", "value"),
    prevent_initial_call=True,
)
def load_files_folder(n_clicks, folder_path):
    if not n_clicks:
        raise PreventUpdate
    try:
        files = list_csv_files(folder_path)
    except Exception as exc:
        return [], f"✘ {exc}", [], []
    if not files:
        return [], f"No CSV/TXT files found in '{folder_path}'.", [], []

    options = [{"label": f, "value": f} for f in files]
    return files, f"✔ Found {len(files)} file(s).", options, options


@callback(
    Output("merge-files-all", "data", allow_duplicate=True),
    Output("merge-files-folder-input", "value", allow_duplicate=True),
    Output("merge-files-folder-status", "children", allow_duplicate=True),
    Output("merge-saxs-select", "options", allow_duplicate=True),
    Output("merge-waxs-select", "options", allow_duplicate=True),
    Output("merge-files-upload-tempdir-store", "data"),
    Input("merge-files-upload-files", "contents"),
    State("merge-files-upload-files", "filename"),
    State("merge-files-upload-tempdir-store", "data"),
    prevent_initial_call=True,
)
def handle_files_dropped_files(contents_list, filenames_list, prev_tempdir):
    if not contents_list or not filenames_list:
        raise PreventUpdate

    tempdir = stage_dropped_files(contents_list, filenames_list, prev_tempdir, prefix="xraysa_merge_upload_")
    files = list_csv_files(tempdir)
    if not files:
        return no_update, tempdir, "✘ None of the dropped files were a supported CSV/TXT profile.", no_update, no_update, tempdir

    options = [{"label": f, "value": f} for f in files]
    status = f"✔ Received {len(files)} dropped file(s) — staged in a temporary folder for this session."
    return files, tempdir, status, options, options, tempdir


@callback(
    Output("merge-saxs-avg-store", "data"),
    Output("merge-waxs-avg-store", "data"),
    Output("merge-files-folder-status", "children", allow_duplicate=True),
    Input("merge-load-both-btn", "n_clicks"),
    State("merge-saxs-select", "value"),
    State("merge-waxs-select", "value"),
    State("merge-files-folder-input", "value"),
    prevent_initial_call=True,
)
def load_both_files(n_clicks, saxs_file, waxs_file, folder_path):
    if not n_clicks:
        raise PreventUpdate
    if not saxs_file or not waxs_file:
        return no_update, no_update, "✘ Select both a SAXS file and a WAXS file."

    try:
        saxs = read_1d_csv(os.path.join(folder_path, saxs_file))
        waxs = read_1d_csv(os.path.join(folder_path, waxs_file))
    except Exception as exc:
        return no_update, no_update, f"✘ Could not load file(s): {exc}"

    saxs_data = {"q": saxs["q"].tolist(), "I": saxs["I"].tolist(), "unit": saxs["unit"]}
    waxs_data = {"q": waxs["q"].tolist(), "I": waxs["I"].tolist(), "unit": waxs["unit"]}
    return saxs_data, waxs_data, f"✔ Loaded '{saxs_file}' and '{waxs_file}'."


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Live overlay of scaled SAXS + WAXS curves
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-overlay-graph", "figure"),
    Input("merge-saxs-avg-store", "data"),
    Input("merge-waxs-avg-store", "data"),
    Input("merge-saxs-scale", "value"),
    Input("merge-waxs-scale", "value"),
)
def update_overlay(saxs_data, waxs_data, saxs_scale, waxs_scale):
    fig = go.Figure()
    unit = "q_A^-1"

    if saxs_data:
        unit = saxs_data.get("unit", unit)
        q = np.array(saxs_data["q"])
        I = np.array(saxs_data["I"]) * (saxs_scale if saxs_scale is not None else 1.0)
        fig.add_trace(go.Scatter(x=q, y=I, mode="lines", name="SAXS (scaled)",
                                  line=dict(color="royalblue", width=2)))

    if waxs_data:
        unit = waxs_data.get("unit", unit)
        q = np.array(waxs_data["q"])
        I = np.array(waxs_data["I"]) * (waxs_scale if waxs_scale is not None else 1.0)
        fig.add_trace(go.Scatter(x=q, y=I, mode="lines", name="WAXS (scaled)",
                                  line=dict(color="darkorange", width=2)))

    fig.update_layout(**_log_axes_layout(unit, legend=dict(orientation="h", y=1.1)))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Auto-fill splice q with the SAXS profile's max q
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-splice-q", "value"),
    Input("merge-saxs-avg-store", "data"),
    prevent_initial_call=True,
)
def autofill_splice_q(saxs_data):
    if not saxs_data:
        raise PreventUpdate
    return round(float(np.max(saxs_data["q"])), 4)


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Merge button
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-merged-store", "data"),
    Output("merge-merged-graph", "figure"),
    Input("merge-btn", "n_clicks"),
    State("merge-saxs-avg-store", "data"),
    State("merge-waxs-avg-store", "data"),
    State("merge-saxs-scale", "value"),
    State("merge-waxs-scale", "value"),
    State("merge-splice-q", "value"),
    prevent_initial_call=True,
)
def do_merge(n_clicks, saxs_data, waxs_data, saxs_scale, waxs_scale, splice_q):
    if not n_clicks:
        raise PreventUpdate
    if not saxs_data or not waxs_data or splice_q is None:
        raise PreventUpdate

    saxs = {
        "q": np.array(saxs_data["q"]),
        "I": np.array(saxs_data["I"]) * (saxs_scale if saxs_scale is not None else 1.0),
        "unit": saxs_data["unit"],
    }
    waxs = {
        "q": np.array(waxs_data["q"]),
        "I": np.array(waxs_data["I"]) * (waxs_scale if waxs_scale is not None else 1.0),
        "unit": waxs_data["unit"],
    }

    merged = merge_profiles(saxs, waxs, float(splice_q))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged["q"], y=merged["I"], mode="lines",
                              line=dict(color="seagreen", width=2), name="Merged"))
    fig.update_layout(**_log_axes_layout(merged["unit"]))

    data = {"q": merged["q"].tolist(), "I": merged["I"].tolist(), "unit": merged["unit"]}
    return data, fig


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Save merged profile
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-save-status", "children"),
    Input("merge-save-merged-btn", "n_clicks"),
    State("merge-merged-store", "data"),
    State("merge-merged-filename", "value"),
    State("merge-save-output-folder", "value"),
    prevent_initial_call=True,
)
def save_merged(n_clicks, merged_data, filename, output_folder):
    if not n_clicks:
        raise PreventUpdate
    if not merged_data:
        return "✘ Nothing to save yet — merge the profiles first."
    if not filename or not output_folder:
        return "✘ Enter a filename and an output folder."

    profile = {"q": np.array(merged_data["q"]), "I": np.array(merged_data["I"]), "unit": merged_data["unit"]}
    try:
        out_path = write_1d_csv(profile, output_folder, filename)
    except Exception as exc:
        return f"✘ {exc}"
    return f"✔ Saved {out_path}"
