
"""
Dash callbacks for the SWAXS Merging tab.
"""

from __future__ import annotations
import os
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, callback, html, no_update
from dash.exceptions import PreventUpdate

from utils.merging_utils import (
    list_csv_files,
    read_1d_csv,
    average_profiles,
    merge_profiles,
    write_1d_csv,
)
from utils.batch_utils import filter_excluded

_UNIT_LABELS = {
    "q_A^-1":  "q (Å⁻¹)",
    "q_nm^-1": "q (nm⁻¹)",
    "2th_deg": "2θ (°)",
    "r_mm":    "r (mm)",
}


def _log_axes_layout(unit: str, **extra) -> dict:
    """Shared log-log axis layout with a proper q-unit label."""
    layout = dict(
        xaxis_title=_UNIT_LABELS.get(unit, unit),
        yaxis_title="Intensity",
        xaxis_type="log",
        yaxis_type="log",
        margin=dict(l=10, r=10, t=20, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    layout.update(extra)
    return layout


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Per-detector-type averaging callbacks (registered for "saxs" and "waxs")
# ─────────────────────────────────────────────────────────────────────────────

def _register_average_callbacks(prefix: str):

    @callback(
        Output(f"merge-{prefix}-all-files", "data"),
        Output(f"merge-{prefix}-folder-status", "children"),
        Input(f"merge-{prefix}-load-folder-btn", "n_clicks"),
        State(f"merge-{prefix}-folder-input", "value"),
        prevent_initial_call=True,
    )
    def load_folder(n_clicks, folder_path):
        if not n_clicks:
            raise PreventUpdate
        try:
            files = list_csv_files(folder_path)
        except Exception as exc:
            return [], f"✘ {exc}"
        if not files:
            return [], f"No CSV files found in '{folder_path}'."
        return files, f"✔ Found {len(files)} file(s)."

    @callback(
        Output(f"merge-{prefix}-file-checklist", "options"),
        Output(f"merge-{prefix}-file-checklist", "value"),
        Output(f"merge-{prefix}-file-count", "children"),
        Input(f"merge-{prefix}-all-files", "data"),
        Input(f"merge-{prefix}-exclude-input", "value"),
    )
    def apply_exclusion_filter(all_files, exclude_text):
        if not all_files:
            return [], [], "No files loaded yet."

        keywords = (exclude_text or "").split(",")
        kept = filter_excluded(all_files, keywords)

        options = [{"label": f, "value": f} for f in kept]
        count_text = f"{len(kept)} of {len(all_files)} file(s) selected."
        return options, kept, count_text

    @callback(
        Output(f"merge-{prefix}-avg-store", "data"),
        Output(f"merge-{prefix}-avg-graph", "figure"),
        Output(f"merge-{prefix}-folder-status", "children", allow_duplicate=True),
        Input(f"merge-{prefix}-average-btn", "n_clicks"),
        State(f"merge-{prefix}-file-checklist", "value"),
        State(f"merge-{prefix}-folder-input", "value"),
        prevent_initial_call=True,
    )
    def average_selected(n_clicks, selected, folder_path):
        if not n_clicks:
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

    @callback(
        Output(f"merge-{prefix}-avg-store", "data", allow_duplicate=True),
        Output(f"merge-{prefix}-avg-graph", "figure", allow_duplicate=True),
        Output(f"merge-{prefix}-folder-status", "children", allow_duplicate=True),
        Input(f"merge-{prefix}-load-file-btn", "n_clicks"),
        State(f"merge-{prefix}-load-file-input", "value"),
        prevent_initial_call=True,
    )
    def load_averaged_file(n_clicks, file_path):
        if not n_clicks:
            raise PreventUpdate
        if not file_path:
            return no_update, no_update, "✘ Enter a file path first."

        try:
            profile = read_1d_csv(file_path)
        except Exception as exc:
            return no_update, no_update, f"✘ Could not load file: {exc}"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=profile["q"], y=profile["I"], mode="lines",
            line=dict(width=2, color="crimson"), name="Loaded",
        ))
        fig.update_layout(**_log_axes_layout(profile["unit"]))

        data = {"q": profile["q"].tolist(), "I": profile["I"].tolist(), "unit": profile["unit"]}
        return data, fig, f"✔ Loaded '{os.path.basename(file_path)}'."


_register_average_callbacks("saxs")
_register_average_callbacks("waxs")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Live overlay of scaled SAXS + WAXS curves
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
# 3.  Auto-fill splice q with the SAXS profile's max q
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
# 4.  Merge button
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
# 5.  Save selected outputs
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("merge-save-status", "children"),
    Input("merge-save-btn", "n_clicks"),
    State("merge-save-checklist", "value"),
    State("merge-save-output-folder", "value"),
    State("merge-saxs-avg-store", "data"),
    State("merge-waxs-avg-store", "data"),
    State("merge-merged-store", "data"),
    prevent_initial_call=True,
)
def save_selected(n_clicks, selected, output_folder, saxs_data, waxs_data, merged_data):
    if not n_clicks:
        raise PreventUpdate
    if not selected or not output_folder:
        return "✘ Select at least one item and an output folder."

    mapping = {
        "avg_saxs": (saxs_data, "averaged_SAXS.csv"),
        "avg_waxs": (waxs_data, "averaged_WAXS.csv"),
        "merged":   (merged_data, "merged_SWAXS.csv"),
    }

    lines = []
    for key in selected:
        data, filename = mapping[key]
        if not data:
            lines.append(f"✘ {filename}: no data available yet")
            continue
        profile = {"q": np.array(data["q"]), "I": np.array(data["I"]), "unit": data["unit"]}
        try:
            out_path = write_1d_csv(profile, output_folder, filename)
            lines.append(f"✔ Saved {os.path.basename(out_path)}")
        except Exception as exc:
            lines.append(f"✘ {filename}: {exc}")

    return [html.Div(line) for line in lines]
