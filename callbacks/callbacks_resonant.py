
"""
Dash callbacks for the Resonant Scattering tab.

Base geometry, masking, display options, and azimuthal wedge regions are
all reused live from the Scattering 2D & 1D tab's `scat-*` components via
cross-tab State/Input, the same pattern callbacks_batch_swaxs.py and
callbacks_gisaxs.py already use.
"""

from __future__ import annotations
import os
import time
import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from dash import Input, Output, State, ALL, callback, ctx, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from utils.resonant_utils import (
    list_and_sort_by_energy,
    DEFAULT_ENERGY_PATTERN,
    compute_nexafs_series,
)
from utils.batch_utils import load_image_from_disk
from utils.scattering_utils import (
    apply_threshold_mask,
    build_pixel_mask,
    build_integrator,
    integrate_1d,
    integrate_2d_qxy,
    energy_to_wavelength,
    power_of_ten_ticks,
    cbar_zrange,
)
from callbacks._shared import (
    register_folder_browse_callback,
    wedge_overlay_trace,
    error_figure,
    azimuth_color,
)

register_folder_browse_callback("reson-folder-input")

_ROI_COLORS = ["#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"]


def _roi_color(index: int) -> str:
    return _ROI_COLORS[index % len(_ROI_COLORS)]


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Load folder → parse + sort by energy
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-file-store", "data"),
    Output("reson-folder-status", "children"),
    Input("reson-load-folder-btn", "n_clicks"),
    State("reson-folder-input", "value"),
    State("reson-exclude-input", "value"),
    State("reson-energy-pattern", "value"),
    prevent_initial_call=True,
)
def load_folder(n_clicks, folder_path, exclude_text, energy_pattern):
    if not n_clicks:
        raise PreventUpdate

    keywords = (exclude_text or "").split(",")
    try:
        entries = list_and_sort_by_energy(folder_path, keywords, energy_pattern or DEFAULT_ENERGY_PATTERN)
    except Exception as exc:
        return [], f"✘ {exc}"

    if not entries:
        return [], f"No files with a parseable energy found in '{folder_path}'."

    lo, hi = entries[0]["energy"], entries[-1]["energy"]
    return entries, f"✔ Found {len(entries)} file(s), energy range [{lo:g}, {hi:g}] eV."


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Populate the file-preview dropdown
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-file-select", "options"),
    Output("reson-file-select", "value"),
    Input("reson-file-store", "data"),
)
def populate_file_select(entries):
    if not entries:
        return [], None

    options = [
        {"label": f"{e['energy']:g} eV — {e['filename']}", "value": i}
        for i, e in enumerate(entries)
    ]
    return options, 0


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Render the selected file's pixel-space image (with ROI overlays)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-2d-graph", "figure"),
    Input("reson-file-select", "value"),
    Input("reson-file-store", "data"),
    Input("reson-roi-store", "data"),
    Input("scat-colorscale-dropdown", "value"),
    Input("scat-log-toggle", "value"),
    Input("scat-mask-low", "value"),
    Input("scat-mask-high", "value"),
    Input("scat-cbar-min", "value"),
    Input("scat-cbar-max", "value"),
    Input("scat-pixel-mask-store", "data"),
    Input("scat-show-beam-centre", "value"),
    Input("scat-bcx", "value"),
    Input("scat-bcy", "value"),
    State("reson-folder-input", "value"),
    prevent_initial_call=True,
)
def render_2d_pixel(file_idx, entries, roi_regions, colorscale, log_scale, mask_low, mask_high,
                     cbar_min, cbar_max, pixel_mask_regions, show_beam_centre, bcx, bcy, folder_path):
    if file_idx is None or not entries or not folder_path:
        raise PreventUpdate

    entry = entries[file_idx]
    try:
        arr = load_image_from_disk(os.path.join(folder_path, entry["filename"]))
    except Exception as exc:
        return error_figure(f"Error loading file: {exc}")

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)
    display = arr.copy()
    display[mask] = np.nan

    is_log = bool(log_scale and "log" in (log_scale or []))
    if is_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)

    zmin, zmax = cbar_zrange(cbar_min, cbar_max, is_log)

    colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if is_log:
        tickvals, ticktext = power_of_ten_ticks(display, vmin=zmin, vmax=zmax)
        if tickvals is not None:
            colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            z=display,
            zmin=zmin, zmax=zmax,
            colorscale=colorscale or "Viridis",
            colorbar=colorbar,
            hovertemplate="col: %{x}<br>row: %{y}<br>value: %{z:.3g}<extra></extra>",
        )
    )

    nrows, ncols = arr.shape

    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(
            autorange="reversed",
            scaleanchor="x",
            scaleratio=1,
            constrain="domain",
            range=[nrows, 0],
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        xaxis=dict(
            range=[0, ncols],
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        xaxis_title="Pixel (col)",
        yaxis_title="Pixel (row)",
        uirevision="reson-2d",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
    )

    for i, roi in enumerate(roi_regions or []):
        color = _roi_color(i)
        fig.add_shape(
            type="rect",
            x0=roi["col_min"], x1=roi["col_max"],
            y0=roi["row_min"], y1=roi["row_max"],
            line=dict(color=color, width=2.5),
        )
        fig.add_annotation(
            x=roi["col_min"], y=roi["row_min"],
            text=roi.get("name", f"ROI {i+1}"),
            showarrow=False, xanchor="left", yanchor="bottom",
            font=dict(color=color, size=17),
            bgcolor="rgba(0,0,0,0.5)",
        )

    if show_beam_centre and "show" in show_beam_centre and bcx is not None and bcy is not None:
        fig.add_trace(go.Scatter(
            x=[float(bcx)], y=[float(bcy)],
            mode="markers",
            marker=dict(symbol="circle", size=5, color="red", line=dict(color="red", width=0)),
            name="Beam centre",
            hovertemplate=f"Beam centre<br>x={bcx}, y={bcy}<extra></extra>",
        ))

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Integrate 1-D: q-space image + 1-D profile for the selected file
#
#     ai.wavelength is overridden from THIS file's own filename-parsed
#     energy right after construction — the geometry (distance, beam
#     centre, pixel size, rotations) comes from the poni-derived
#     Scattering 2D & 1D fields, but wavelength never does for this tab.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-2d-q-graph", "figure"),
    Output("reson-1d-data-store", "data"),
    Input("reson-integrate-btn", "n_clicks"),
    State("reson-file-select", "value"),
    State("reson-file-store", "data"),
    State("reson-folder-input", "value"),
    State("scat-distance", "value"),
    State("scat-bcx", "value"),
    State("scat-bcy", "value"),
    State("scat-px-x", "value"),
    State("scat-px-y", "value"),
    State("scat-rot1", "value"),
    State("scat-rot2", "value"),
    State("scat-rot3", "value"),
    State("scat-npts", "value"),
    State("scat-unit-dropdown", "value"),
    State("scat-mask-low", "value"),
    State("scat-mask-high", "value"),
    State("scat-pixel-mask-store", "data"),
    State("scat-cbar-min", "value"),
    State("scat-cbar-max", "value"),
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    State("scat-show-beam-centre", "value"),
    State("scat-azimuth-regions-store", "data"),
    prevent_initial_call=True,
)
def run_reson_integration(
    n_clicks, file_idx, entries, folder_path,
    distance_mm, bcx, bcy, px_x_um, px_y_um, rot1_deg, rot2_deg, rot3_deg,
    n_pts, unit,
    mask_low, mask_high, pixel_mask_regions,
    cbar_min, cbar_max, colorscale, log_scale, show_beam_centre,
    azimuth_regions,
):
    if not n_clicks or file_idx is None or not entries or not folder_path:
        raise PreventUpdate

    entry = entries[file_idx]
    energy_eV = entry["energy"]

    try:
        arr = load_image_from_disk(os.path.join(folder_path, entry["filename"]))
    except Exception as exc:
        return error_figure(f"Error loading file: {exc}"), {}

    try:
        ai = build_integrator(
            detector_distance_m=float(distance_mm) * 1e-3,
            wavelength_m=1e-10,  # placeholder — overridden immediately below
            beam_center_x=float(bcx),
            beam_center_y=float(bcy),
            pixel_size_x=float(px_x_um) * 1e-6,
            pixel_size_y=float(px_y_um) * 1e-6,
            rot1=np.deg2rad(float(rot1_deg or 0)),
            rot2=np.deg2rad(float(rot2_deg or 0)),
            rot3=np.deg2rad(float(rot3_deg or 0)),
        )
        wl_A = energy_to_wavelength(energy_eV / 1000.0)
        ai.wavelength = wl_A * 1e-10
    except Exception as exc:
        return error_figure(f"Integrator error: {exc}"), {}

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    # ── q-space image ────────────────────────────────────────────────────────
    try:
        I_qxy, qx, qy = integrate_2d_qxy(arr, ai, n_points=int(n_pts or 500), mask=mask)
    except Exception as exc:
        return error_figure(f"qx/qy error: {exc}"), {}

    display_qxy = I_qxy.copy()
    if mask_low is not None or mask_high is not None:
        qxy_mask = apply_threshold_mask(I_qxy, low=mask_low, high=mask_high)
        display_qxy[qxy_mask] = np.nan

    is_log = bool(log_scale and "log" in (log_scale or []))
    if is_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            display_qxy = np.where(display_qxy > 0, np.log10(display_qxy), np.nan)

    qxy_zmin, qxy_zmax = cbar_zrange(cbar_min, cbar_max, is_log)

    qxy_colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if is_log:
        tickvals, ticktext = power_of_ten_ticks(display_qxy, vmin=qxy_zmin, vmax=qxy_zmax)
        if tickvals is not None:
            qxy_colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig_qxy = go.Figure(
        go.Heatmap(
            x=qx, y=qy, z=display_qxy,
            zmin=qxy_zmin, zmax=qxy_zmax,
            colorscale=colorscale or "Viridis",
            colorbar=qxy_colorbar,
            hovertemplate="qx: %{x:.4g} Å⁻¹<br>qy: %{y:.4g} Å⁻¹<br>I: %{z:.3g}<extra></extra>",
        )
    )
    fig_qxy.update_layout(
        xaxis_title="q<sub>x</sub> (Å⁻¹)",
        yaxis_title="q<sub>y</sub> (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="reson-2d-q",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        xaxis=dict(
            range=[float(qx.min()), float(qx.max())],
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
            range=[float(qy.min()), float(qy.max())],
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
    )

    for i, region in enumerate(azimuth_regions or []):
        wedge = wedge_overlay_trace(
            region["az_min"], region["az_max"], region["q_min"], region["q_max"],
            color=azimuth_color(i),
        )
        if wedge is not None:
            fig_qxy.add_trace(wedge)

    if show_beam_centre and "show" in show_beam_centre:
        fig_qxy.add_trace(go.Scatter(
            x=[0.0], y=[0.0],
            mode="markers",
            marker=dict(symbol="circle", size=5, color="red", line=dict(color="red", width=0)),
            name="Beam centre",
            showlegend=False,
            hovertemplate="Beam centre<br>qx=0, qy=0<extra></extra>",
        ))

    # ── 1-D profile — one curve per azimuthal region, or one unrestricted
    #    integration when none are defined, mirroring Scattering 2D & 1D. Only
    #    curves are stored here; render_reson_1d_plot below turns them into
    #    the actual figure, so a Q Range trim can re-filter and redraw
    #    without re-running any of this.
    curves = []
    if azimuth_regions:
        for i, region in enumerate(azimuth_regions):
            q, I, _sigma = integrate_1d(
                arr, ai,
                n_points=int(n_pts or 1000),
                unit=unit or "q_A^-1",
                mask=mask,
                azimuth_range=(region["az_min"], region["az_max"]),
            )
            curves.append({
                "q": q.tolist(), "I": I.tolist(),
                "name": f"Azimuthal [{region['az_min']:.1f}°, {region['az_max']:.1f}°]",
                "color": azimuth_color(i),
            })
    else:
        q, I, _sigma = integrate_1d(
            arr, ai,
            n_points=int(n_pts or 1000),
            unit=unit or "q_A^-1",
            mask=mask,
            azimuth_range=None,
        )
        curves.append({"q": q.tolist(), "I": I.tolist(), "name": "I(q)", "color": "#1f77b4"})

    return fig_qxy, {"curves": curves, "unit": unit}


# ─────────────────────────────────────────────────────────────────────────────
# 4.5.  Render the 1-D profile from stored curves, applying the Q Range trim
#       live — no re-integration needed, mirrors update_1d_plot in
#       callbacks_scattering_2d.py.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-1d-graph", "figure"),
    Input("reson-1d-data-store", "data"),
    Input("reson-qrange-store", "data"),
    Input("scat-log-y-toggle", "value"),
    Input("scat-log-x-toggle", "value"),
    prevent_initial_call=True,
)
def render_reson_1d_plot(store_data, q_range, log_y, log_x):
    if not store_data or not store_data.get("curves"):
        raise PreventUpdate

    unit = store_data.get("unit", "q_A^-1")
    q_min = q_range.get("q_min") if q_range else None
    q_max = q_range.get("q_max") if q_range else None

    fig1d = go.Figure()
    for curve in store_data["curves"]:
        q = np.array(curve["q"])
        I = np.array(curve["I"])
        if q_min is not None and q_max is not None:
            keep = (q >= q_min) & (q <= q_max)
            q, I = q[keep], I[keep]
        fig1d.add_trace(go.Scatter(
            x=q, y=I,
            mode="lines",
            name=curve["name"],
            line=dict(width=2.0, color=curve["color"]),
        ))

    _unit_labels = {
        "q_A^-1": "q (Å⁻¹)", "q_nm^-1": "q (nm⁻¹)", "2th_deg": "2θ (°)", "r_mm": "r (mm)",
    }
    xlabel = _unit_labels.get(unit, unit or "q (Å⁻¹)")
    ytype = "log" if (log_y and "log" in log_y) else "linear"
    xtype = "log" if (log_x and "log" in log_x) else "linear"
    fig1d.update_layout(
        xaxis_title=xlabel,
        xaxis_type=xtype,
        yaxis_title="Intensity (a.u.)",
        yaxis_type=ytype,
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="reson-1d",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        legend=dict(font=dict(size=10)),
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
    return fig1d


@callback(
    Output("reson-qrange-store", "data", allow_duplicate=True),
    Input("reson-qrange-apply-btn", "n_clicks"),
    State("reson-qrange-min", "value"),
    State("reson-qrange-max", "value"),
    prevent_initial_call=True,
)
def apply_reson_qrange(n_clicks, q_min, q_max):
    if q_min is None or q_max is None:
        raise PreventUpdate
    return {"q_min": q_min, "q_max": q_max}


# ─────────────────────────────────────────────────────────────────────────────
# 5.  ROI region management (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-roi-store", "data"),
    Input("reson-roi-add-btn", "n_clicks"),
    Input("reson-roi-clear-btn", "n_clicks"),
    Input({"type": "reson-roi-remove", "index": ALL}, "n_clicks"),
    State("reson-roi-name", "value"),
    State("reson-roi-row-min", "value"),
    State("reson-roi-row-max", "value"),
    State("reson-roi-col-min", "value"),
    State("reson-roi-col-max", "value"),
    State("reson-roi-store", "data"),
    prevent_initial_call=True,
)
def manage_roi_regions(add_clicks, clear_clicks, remove_clicks,
                        name, row_min, row_max, col_min, col_max, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "reson-roi-clear-btn":
        return []

    if trigger == "reson-roi-add-btn":
        if None in (row_min, row_max, col_min, col_max):
            raise PreventUpdate
        regions.append({
            "name": (name or "").strip() or f"ROI_{len(regions) + 1}",
            "row_min": float(row_min), "row_max": float(row_max),
            "col_min": float(col_min), "col_max": float(col_max),
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "reson-roi-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("reson-roi-list", "children"),
    Input("reson-roi-store", "data"),
)
def render_roi_list(regions):
    if not regions:
        return html.Div(
            "No ROI regions defined.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, roi in enumerate(regions):
        color = _roi_color(i)
        rows.append(html.Div([
            html.Span(style={
                "display": "inline-block", "width": "10px", "height": "10px",
                "backgroundColor": color, "borderRadius": "2px", "marginRight": "6px",
            }),
            html.Span(
                f"{roi['name']}: rows=[{roi['row_min']:.0f}, {roi['row_max']:.0f}] "
                f"cols=[{roi['col_min']:.0f}, {roi['col_max']:.0f}]",
                style={"fontSize": "0.85rem"},
            ),
            dbc.Button("✕", id={"type": "reson-roi-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Run NEXAFS: sum each ROI across every loaded file (background job)
# ─────────────────────────────────────────────────────────────────────────────

_NEXAFS_PROGRESS_OUTPUTS = [
    Output("reson-nexafs-progress", "value"),
    Output("reson-nexafs-progress", "label"),
    Output("reson-nexafs-progress-text", "children"),
]


@callback(
    output=_NEXAFS_PROGRESS_OUTPUTS + [Output("reson-nexafs-store", "data")],
    inputs=Input("reson-nexafs-btn", "n_clicks"),
    state=[
        State("reson-file-store", "data"),
        State("reson-folder-input", "value"),
        State("reson-roi-store", "data"),
        State("scat-mask-low", "value"),
        State("scat-mask-high", "value"),
        State("scat-pixel-mask-store", "data"),
    ],
    background=True,
    progress=_NEXAFS_PROGRESS_OUTPUTS,
    running=[(Output("reson-nexafs-btn", "disabled"), True, False)],
    prevent_initial_call=True,
)
def run_nexafs(set_progress, n_clicks, entries, folder_path, rois, mask_low, mask_high, pixel_mask_regions):
    if not n_clicks:
        raise PreventUpdate
    if not entries or not folder_path:
        return 0, "", "Load a folder first.", {}
    if not rois:
        return 0, "", "Define at least one ROI region first.", {}

    total = len(entries)
    start = time.time()

    def _progress(i, _total):
        elapsed = time.time() - start
        pct = int(i / total * 100)
        set_progress((pct, f"{i}/{total}", f"{i}/{total} files — elapsed {elapsed:.1f}s"))

    nexafs_data = compute_nexafs_series(
        entries, folder_path, rois,
        mask_low=mask_low, mask_high=mask_high, pixel_mask_regions=pixel_mask_regions,
        progress_cb=_progress,
    )

    return 100, f"{total}/{total}", f"Done — {total} files in {time.time() - start:.1f}s", nexafs_data


@callback(
    Output("reson-nexafs-graph", "figure"),
    Input("reson-nexafs-store", "data"),
)
def render_nexafs_plot(store_data):
    if not store_data or not store_data.get("roi_sums"):
        raise PreventUpdate

    energies = np.array(store_data["energies"])
    fig = go.Figure()
    for i, (name, values) in enumerate(store_data["roi_sums"].items()):
        y = np.array([v if v is not None else np.nan for v in values], dtype=float)
        fig.add_trace(go.Scatter(
            x=energies, y=y,
            mode="lines+markers",
            name=name,
            line=dict(width=1.5, color=_roi_color(i)),
            marker=dict(size=5),
        ))

    fig.update_layout(
        xaxis_title="Energy (eV)",
        yaxis_title="Intensity (a.u.)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="reson-nexafs",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        legend=dict(font=dict(size=10)),
        xaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True, ticks="outside"),
        yaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True, ticks="outside"),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Energy-series 1-D overlay (background job)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("reson-energy-region-select", "options"),
    Output("reson-energy-region-select", "value"),
    Input("scat-azimuth-regions-store", "data"),
)
def populate_energy_region_select(azimuth_regions):
    options = [{"label": "Unrestricted (full)", "value": "full"}]
    for i, region in enumerate(azimuth_regions or []):
        options.append({
            "label": f"az=[{region['az_min']:.1f}°, {region['az_max']:.1f}°]",
            "value": i,
        })
    return options, "full"


_ENERGY_PROGRESS_OUTPUTS = [
    Output("reson-energy-progress", "value"),
    Output("reson-energy-progress", "label"),
    Output("reson-energy-progress-text", "children"),
]


@callback(
    output=_ENERGY_PROGRESS_OUTPUTS + [Output("reson-energy-store", "data")],
    inputs=Input("reson-energy-run-btn", "n_clicks"),
    state=[
        State("reson-file-store", "data"),
        State("reson-folder-input", "value"),
        State("reson-energy-region-select", "value"),
        State("scat-azimuth-regions-store", "data"),
        State("reson-energy-start-idx", "value"),
        State("reson-energy-end-idx", "value"),
        State("reson-energy-step", "value"),
        State("scat-distance", "value"),
        State("scat-bcx", "value"),
        State("scat-bcy", "value"),
        State("scat-px-x", "value"),
        State("scat-px-y", "value"),
        State("scat-rot1", "value"),
        State("scat-rot2", "value"),
        State("scat-rot3", "value"),
        State("scat-npts", "value"),
        State("scat-unit-dropdown", "value"),
        State("scat-mask-low", "value"),
        State("scat-mask-high", "value"),
        State("scat-pixel-mask-store", "data"),
    ],
    background=True,
    progress=_ENERGY_PROGRESS_OUTPUTS,
    running=[(Output("reson-energy-run-btn", "disabled"), True, False)],
    prevent_initial_call=True,
)
def run_energy_series(
    set_progress, n_clicks, entries, folder_path, region_choice, azimuth_regions,
    start_idx, end_idx, step,
    distance_mm, bcx, bcy, px_x_um, px_y_um, rot1_deg, rot2_deg, rot3_deg,
    n_pts, unit, mask_low, mask_high, pixel_mask_regions,
):
    if not n_clicks:
        raise PreventUpdate
    if not entries or not folder_path:
        return 0, "", "Load a folder first.", {}

    start_idx = max(0, int(start_idx or 0))
    end_idx = int(end_idx) if end_idx is not None else len(entries) - 1
    end_idx = min(end_idx, len(entries) - 1)
    step = max(1, int(step or 1))
    indices = list(range(start_idx, end_idx + 1, step))
    if not indices:
        return 0, "", "No files in the selected index range.", {}

    az_range = None
    if region_choice != "full" and azimuth_regions:
        region = azimuth_regions[int(region_choice)]
        az_range = (region["az_min"], region["az_max"])

    curves = []
    total = len(indices)
    start_time = time.time()

    for i, idx in enumerate(indices, start=1):
        entry = entries[idx]
        try:
            arr = load_image_from_disk(os.path.join(folder_path, entry["filename"]))
            ai = build_integrator(
                detector_distance_m=float(distance_mm) * 1e-3,
                wavelength_m=1e-10,
                beam_center_x=float(bcx),
                beam_center_y=float(bcy),
                pixel_size_x=float(px_x_um) * 1e-6,
                pixel_size_y=float(px_y_um) * 1e-6,
                rot1=np.deg2rad(float(rot1_deg or 0)),
                rot2=np.deg2rad(float(rot2_deg or 0)),
                rot3=np.deg2rad(float(rot3_deg or 0)),
            )
            wl_A = energy_to_wavelength(entry["energy"] / 1000.0)
            ai.wavelength = wl_A * 1e-10

            mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
            mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

            q, I, _sigma = integrate_1d(
                arr, ai,
                n_points=int(n_pts or 1000),
                unit=unit or "q_A^-1",
                mask=mask,
                azimuth_range=az_range,
            )
            curves.append({"q": q.tolist(), "I": I.tolist(), "energy": entry["energy"]})
        except Exception:
            pass

        elapsed = time.time() - start_time
        pct = int(i / total * 100)
        set_progress((pct, f"{i}/{total}", f"{i}/{total} files — elapsed {elapsed:.1f}s"))

    return (
        100, f"{total}/{total}", f"Done — {total} files in {time.time() - start_time:.1f}s",
        {"curves": curves, "unit": unit},
    )


@callback(
    Output("reson-energy-graph", "figure"),
    Input("reson-energy-store", "data"),
    Input("reson-qrange-store", "data"),
    Input("scat-log-y-toggle", "value"),
    Input("scat-log-x-toggle", "value"),
)
def render_energy_series_plot(store_data, q_range, log_y, log_x):
    if not store_data or not store_data.get("curves"):
        raise PreventUpdate

    curves = store_data["curves"]
    unit = store_data.get("unit", "q_A^-1")
    energies = np.array([c["energy"] for c in curves])
    e_min, e_max = float(energies.min()), float(energies.max())

    q_min = q_range.get("q_min") if q_range else None
    q_max = q_range.get("q_max") if q_range else None

    fig = go.Figure()
    for c in curves:
        e = c["energy"]
        t = 0.0 if e_max == e_min else (e - e_min) / (e_max - e_min)
        color = sample_colorscale("Viridis", [t])[0]
        q_arr, I_arr = np.array(c["q"]), np.array(c["I"])
        if q_min is not None and q_max is not None:
            keep = (q_arr >= q_min) & (q_arr <= q_max)
            q_arr, I_arr = q_arr[keep], I_arr[keep]
        fig.add_trace(go.Scatter(
            x=q_arr, y=I_arr,
            mode="lines",
            line=dict(width=1.2, color=color),
            showlegend=False,
            hovertemplate=f"E={e:g} eV<br>q=%{{x:.4g}}<br>I=%{{y:.3g}}<extra></extra>",
        ))

    # Dummy invisible trace purely to host the energy colorbar.
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(
            colorscale="Viridis", cmin=e_min, cmax=e_max, color=[e_min],
            showscale=True,
            colorbar=dict(title=dict(text="Energy (eV)", side="right"),
                          x=1.02, thickness=20, ticks="outside",
                          outlinecolor="black", outlinewidth=1),
        ),
        showlegend=False,
        hoverinfo="skip",
    ))

    _unit_labels = {
        "q_A^-1": "q (Å⁻¹)", "q_nm^-1": "q (nm⁻¹)", "2th_deg": "2θ (°)", "r_mm": "r (mm)",
    }
    xlabel = _unit_labels.get(unit, unit or "q (Å⁻¹)")
    ytype = "log" if (log_y and "log" in log_y) else "linear"
    xtype = "log" if (log_x and "log" in log_x) else "linear"
    fig.update_layout(
        xaxis_title=xlabel,
        xaxis_type=xtype,
        yaxis_title="Intensity (a.u.)",
        yaxis_type=ytype,
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="reson-energy",
        hovermode="closest",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
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
    return fig
