
"""
Dash callbacks for the 2-D scattering viewer / 1-D integrator panel.
"""

from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, ALL, callback, no_update, ctx, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

import io
import base64
import tempfile
import os
import pyFAI


from utils.scattering_utils import (
    decode_upload,
    apply_threshold_mask,
    build_pixel_mask,
    build_integrator,
    fit2d_beam_center_to_poni_pixels,
    integrate_1d,
    integrate_2d,
    integrate_2d_qxy,
    q_to_twotheta,
    energy_to_wavelength,
    power_of_ten_ticks as _power_of_ten_ticks,
    cbar_zrange as _cbar_zrange,
)
from callbacks._shared import (
    wedge_overlay_trace,
    error_figure as _error_figure,
    azimuth_color as _azimuth_color,
    DEFAULT_1D_COLOR as _DEFAULT_1D_COLOR,
)

# ── Constants ─────────────────────────────────────────────────────────────────
_COLORSCALES = ["Viridis", "Inferno", "Plasma", "Hot", "Greys", "Jet"]
_UNITS       = ["q_A^-1", "q_nm^-1", "2th_deg"]
_UNIT_LABELS = {
    "q_A^-1":  "q (Å⁻¹)",
    "q_nm^-1": "q (nm⁻¹)",
    "2th_deg": "2θ (°)",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Store raw image data when a file is uploaded
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-image-store", "data"),
    Output("scat-upload-status", "children"),
    Input("scat-upload", "contents"),
    State("scat-upload", "filename"),
    prevent_initial_call=True,
)
def store_uploaded_image(contents, filename):
    if contents is None:
        raise PreventUpdate

    try:
        arr = decode_upload(contents, filename)
        # Serialise as nested list so it can live in a dcc.Store (JSON)
        return arr.tolist(), f"✔ Loaded '{filename}'  ({arr.shape[0]} × {arr.shape[1]})"
    except Exception as exc:
        return no_update, f"✘ Error: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Render the 2-D detector image
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-2d-graph", "figure"),
    Input("scat-image-store", "data"),
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
    prevent_initial_call=True,
)
def render_2d_image(image_data, colorscale, log_scale, mask_low, mask_high, cbar_min, cbar_max,
                     pixel_mask_regions, show_beam_centre, bcx, bcy):
    if image_data is None:
        raise PreventUpdate

    arr = np.array(image_data, dtype=float)

    # Apply threshold + hot-pixel mask — set masked pixels to NaN so they show as blank
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)
    display = arr.copy()
    display[mask] = np.nan

    is_log = bool(log_scale and "log" in (log_scale or []))
    if is_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)

    zmin, zmax = _cbar_zrange(cbar_min, cbar_max, is_log)

    colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if is_log:
        tickvals, ticktext = _power_of_ten_ticks(display, vmin=zmin, vmax=zmax)
        if tickvals is not None:
            colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            z=display,
            zmin=zmin,
            zmax=zmax,
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
            range=[nrows, 0],       # exact image height, reversed
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        xaxis=dict(
            range=[0, ncols],       # exact image width
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        xaxis_title="Pixel (col)",
        yaxis_title="Pixel (row)",
        uirevision="scat-2d",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
    )

    # Outline each defined hot-pixel region so its placement is visible
    # even where the NaN gap alone would be hard to spot.
    for region in (pixel_mask_regions or []):
        row, col, size = region.get("row"), region.get("col"), region.get("size")
        if row is None or col is None or not size:
            continue
        fig.add_shape(
            type="circle" if region.get("shape") == "circle" else "rect",
            x0=col - size, x1=col + size,
            y0=row - size, y1=row + size,
            line=dict(color="red", width=1.5, dash="dot"),
        )

    # Beam centre marker — baked into the figure itself (rather than a
    # separate overlay callback) so it survives every redraw, regardless
    # of what triggered it (mask change, colorscale, new image, etc.).
    if show_beam_centre and "show" in show_beam_centre and bcx is not None and bcy is not None:
        fig.add_trace(
            go.Scatter(
                x=[float(bcx)],
                y=[float(bcy)],
                mode="markers",
                marker=dict(symbol="circle", size=5, color="red", line=dict(color="red", width=0)),
                name="Beam centre",
                hovertemplate=f"Beam centre<br>x={bcx}, y={bcy}<extra></extra>",
            )
        )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Run 1-D integration and render the result
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    #Output("scat-1d-graph", "figure"),
    Output("scat-q-data-store", "data"),       # ← was scat-1d-graph
    # scat-qrange-store is no longer touched here — it's kept in sync with
    # scat-qrange-idx-store by render_qrange_fields on every integration
    # (see that callback's docstring for why this one used to fight it).
    Output("scat-integration-store", "data"),
    Output("scat-2d-q-graph", "figure"),
    Input("scat-integrate-btn", "n_clicks"),
    State("scat-image-store", "data"),
    # Geometry
    State("scat-distance", "value"),
    State("scat-wavelength-or-energy", "value"),
    State("scat-wavelength", "value"),
    State("scat-energy", "value"),
    State("scat-bcx", "value"),
    State("scat-bcy", "value"),
    State("scat-px-x", "value"),
    State("scat-px-y", "value"),
    State("scat-rot1", "value"),
    State("scat-rot2", "value"),
    State("scat-rot3", "value"),
    # Integration options
    State("scat-npts", "value"),
    State("scat-unit-dropdown", "value"),
    State("scat-mask-low", "value"),
    State("scat-mask-high", "value"),
    State("scat-cbar-min", "value"),
    State("scat-cbar-max", "value"),
    State("scat-azimuth-regions-store", "data"),
    State("scat-error-model", "value"),
    # Display options
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    State("scat-pixel-mask-store", "data"),
    State("scat-show-beam-centre", "value"),
    prevent_initial_call=True,
)
def run_integration(
    n_clicks,
    image_data,
    distance_mm,
    wl_or_e,
    wavelength_A,
    energy_keV,
    bcx, bcy,
    px_x_um, px_y_um,
    rot1_deg, rot2_deg, rot3_deg,
    n_pts,
    unit,
    mask_low, mask_high,
    cbar_min, cbar_max,
    azimuth_regions,
    error_model,
    colorscale,
    log_scale,
    pixel_mask_regions,
    show_beam_centre,
):
    if not n_clicks or image_data is None:
        raise PreventUpdate

    arr = np.array(image_data, dtype=float)

    # ── Resolve wavelength ────────────────────────────────────────────────────
    if wl_or_e == "energy":
        if not energy_keV:
            raise PreventUpdate
        wl_A = energy_to_wavelength(float(energy_keV))
    else:
        if not wavelength_A:
            raise PreventUpdate
        wl_A = float(wavelength_A)

    wl_m = wl_A * 1e-10

    # ── Build integrator ─────────────────────────────────────────────────────
    try:
        dist_m = float(distance_mm) * 1e-3
        px_x_m = float(px_x_um) * 1e-6
        px_y_m = float(px_y_um) * 1e-6
        rot1_rad = np.deg2rad(float(rot1_deg or 0))
        rot2_rad = np.deg2rad(float(rot2_deg or 0))
        rot3_rad = np.deg2rad(float(rot3_deg or 0))

        # bcx/bcy are the Fit2D-style (physical) beam centre; convert to
        # the PONI point the current tilt implies before building.
        poni_x, poni_y = fit2d_beam_center_to_poni_pixels(
            float(bcx), float(bcy), px_x_m, px_y_m, dist_m, rot1_rad, rot2_rad,
        )

        ai = build_integrator(
            detector_distance_m=dist_m,
            wavelength_m=wl_m,
            beam_center_x=poni_x,
            beam_center_y=poni_y,
            pixel_size_x=px_x_m,
            pixel_size_y=px_y_m,
            rot1=rot1_rad,
            rot2=rot2_rad,
            rot3=rot3_rad,
        )
    except Exception as exc:
        empty = _error_figure(f"Integrator error: {exc}")
        return no_update, no_update, empty

    # ── Mask ─────────────────────────────────────────────────────────────────
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    # ── 1-D integration — one curve per azimuthal region, or a single
    #    unrestricted (full-azimuth) integration when none are defined ────────
    curves = []
    if azimuth_regions:
        for i, region in enumerate(azimuth_regions):
            try:
                q, I, sigma = integrate_1d(
                    arr, ai,
                    n_points=int(n_pts or 1000),
                    unit=unit or "q_A^-1",
                    mask=mask,
                    azimuth_range=(region["az_min"], region["az_max"]),
                    error_model=error_model or None,
                )
            except Exception as exc:
                return no_update, no_update, _error_figure(f"Integration error: {exc}")
            curves.append({
                "q": q.tolist(), "I": I.tolist(),
                "sigma": sigma.tolist() if sigma is not None else None,
                "name": f"Azimuthal [{region['az_min']:.1f}°, {region['az_max']:.1f}°]",
                "color": _azimuth_color(i),
            })
    else:
        try:
            q, I, sigma = integrate_1d(
                arr, ai,
                n_points=int(n_pts or 1000),
                unit=unit or "q_A^-1",
                mask=mask,
                azimuth_range=None,
                error_model=error_model or None,
            )
        except Exception as exc:
            return no_update, no_update, _error_figure(f"Integration error: {exc}")
        curves.append({
            "q": q.tolist(), "I": I.tolist(),
            "sigma": sigma.tolist() if sigma is not None else None,
            "name": "I(q)",
            "color": _DEFAULT_1D_COLOR,
        })

    # ── qx/qy remapped 2-D image ──────────────────────────────────────────────
    try:
        I_qxy, qx, qy = integrate_2d_qxy(
            arr, ai,
            n_points=int(n_pts or 500),
            mask=mask,
        )
    except Exception as exc:
        return no_update, no_update, _error_figure(f"Integrator error: {exc}")

    
    # Apply threshold mask (same logic as pixel-space image)
    display_qxy = I_qxy.copy()
    if mask_low is not None or mask_high is not None:
        qxy_mask = apply_threshold_mask(I_qxy, low=mask_low, high=mask_high)
        display_qxy[qxy_mask] = np.nan

    is_log = bool(log_scale and "log" in (log_scale or []))
    if is_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            display_qxy = np.where(display_qxy > 0, np.log10(display_qxy), np.nan)

    qxy_zmin, qxy_zmax = _cbar_zrange(cbar_min, cbar_max, is_log)

    qxy_colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if is_log:
        tickvals, ticktext = _power_of_ten_ticks(display_qxy, vmin=qxy_zmin, vmax=qxy_zmax)
        if tickvals is not None:
            qxy_colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig_qxy = go.Figure(
        go.Heatmap(
            x=qx,
            y=qy,
            z=display_qxy,
            zmin=qxy_zmin,
            zmax=qxy_zmax,
            colorscale=colorscale or "Viridis",
            colorbar=qxy_colorbar,
            hovertemplate="qx: %{x:.4g} Å⁻¹<br>qy: %{y:.4g} Å⁻¹<br>I: %{z:.3g}<extra></extra>",
        )
    )

    fig_qxy.update_layout(
        xaxis_title="q<sub>x</sub> (Å⁻¹)",
        yaxis_title="q<sub>y</sub> (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-2d-q",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        # Stashes the intended "home" range for assets/qspace_reset_axes_fix.js:
        # meta is untouched by Plotly's own zoom/pan/reset machinery, so it's
        # a reliable place for the client to read the true detector-only
        # bounds back from, regardless of how the user has since zoomed/panned.
        meta={"homeRangeX": [float(qx.min()), float(qx.max())],
              "homeRangeY": [float(qy.min()), float(qy.max())]},
        xaxis=dict(
            range=[float(qx.min()), float(qx.max())],
            autorange=False,   # lock to the heatmap's own data extent — the
            constrain="domain",  # wedge/beam-centre overlays must not stretch this
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

    
    # ── Wedge overlays — one per azimuthal region ────────────────────────────
    for i, region in enumerate(azimuth_regions or []):
        wedge = wedge_overlay_trace(
            region["az_min"], region["az_max"], region["q_min"], region["q_max"],
            color=_azimuth_color(i),
        )
        if wedge is not None:
            fig_qxy.add_trace(wedge)

    # Beam centre marker — in q-space the beam centre is always the origin,
    # since integration is performed relative to it.
    if show_beam_centre and "show" in show_beam_centre:
        fig_qxy.add_trace(go.Scatter(
            x=[0.0],
            y=[0.0],
            mode="markers",
            marker=dict(symbol="circle", size=5, color="red", line=dict(color="red", width=0)),
            name="Beam centre",
            showlegend=False,
            hovertemplate="Beam centre<br>qx=0, qy=0<extra></extra>",
        ))

    store_data = {"curves": curves, "unit": unit, "wavelength_A": wl_A}

    return (
        store_data,
        store_data,
        fig_qxy,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3.5.  1-D plot from the store
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-1d-graph", "figure"),
    Input("scat-q-data-store", "data"),
    Input("scat-qrange-store", "data"),
    Input("scat-log-y-toggle", "value"),
    Input("scat-log-x-toggle", "value"),
    State("scat-unit-dropdown", "value"),
    prevent_initial_call=True,
)
def update_1d_plot(q_data, q_range, log_y, log_x, unit):
    if not q_data:
        raise PreventUpdate

    curves = q_data.get("curves", [])
    unit = q_data.get("unit", unit)

    q_min = q_range.get("q_min") if q_range else None
    q_max = q_range.get("q_max") if q_range else None

    fig = go.Figure()
    for curve in curves:
        q     = np.array(curve["q"])
        I     = np.array(curve["I"])
        sigma = np.array(curve["sigma"]) if curve["sigma"] is not None else None

        if q_min is not None and q_max is not None:
            keep = (q >= q_min) & (q <= q_max)
        else:
            keep = np.ones_like(q, dtype=bool)   # no filter — show full range

        q_plot, I_plot = q[keep], I[keep]
        s_plot = sigma[keep] if sigma is not None else None

        name = curve.get("name", "I(q)")
        color = curve.get("color", "#1f77b4")
        fig.add_trace(go.Scatter(
            x=q_plot, y=I_plot,
            error_y=(
                dict(type="data", array=s_plot, visible=True, thickness=1)
                if s_plot is not None else None
            ),
            mode="lines",
            name=f"{name} ± σ" if s_plot is not None else name,
            line=dict(width=2.25, color=color),
        ))

    xlabel = _UNIT_LABELS.get(unit, unit or "q (Å⁻¹)")
    ytype  = "log" if (log_y and "log" in log_y) else "linear"
    xtype  = "log" if (log_x and "log" in log_x) else "linear"

    fig.update_layout(
        xaxis_title=xlabel,
        xaxis_type=xtype,
        yaxis_title="Intensity (a.u.)",
        yaxis_type=ytype,
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-1d",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        showlegend=False,
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


# ─────────────────────────────────────────────────────────────────────────────
# 3.6.  Click-to-read-out: Q/2θ + d-spacing at the clicked point
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-click-q-value", "value"),
    Output("scat-click-d-value", "value"),
    Output("scat-click-q-label", "children"),
    Input("scat-1d-graph", "clickData"),
    State("scat-q-data-store", "data"),
    prevent_initial_call=True,
)
def show_clicked_d_spacing(click_data, q_data):
    if not click_data or not q_data:
        raise PreventUpdate

    x = click_data["points"][0]["x"]
    unit = q_data.get("unit", "q_A^-1")
    wavelength_A = q_data.get("wavelength_A")

    d = None
    if x:
        if unit == "q_A^-1":
            d = 2 * np.pi / x
        elif unit == "q_nm^-1":
            d = 20 * np.pi / x
        elif unit == "2th_deg" and wavelength_A:
            sin_theta = np.sin(np.deg2rad(x / 2.0))
            if sin_theta > 0:
                d = wavelength_A / (2 * sin_theta)

    q_text = f"{x:.5g}"
    d_text = f"{d:.5g}" if d is not None else "—"
    q_label = _UNIT_LABELS.get(unit, unit or "q (Å⁻¹)")
    return q_text, d_text, q_label


# ─────────────────────────────────────────────────────────────────────────────
# 3.5.4b.  Q Range value <-> index dual-widget sync (RAW-style, matching the
#          SWAXS Merging tab's per-row q Min/q Max controls). A small
#          scat-qrange-idx-store holds {"min_idx","max_idx"} as the single
#          source of truth; the value/index display fields are pure renders
#          of it (never both an Input and Output of the same callback),
#          matching the store-driven pattern used throughout this app.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-qrange-idx-store", "data"),
    Input("scat-q-data-store", "data"),
    State("scat-qrange-idx-store", "data"),
    prevent_initial_call=True,
)
def reset_qrange_idx(q_data, idx_store):
    """
    The Q Range fields reset to the full q extent only the first time
    (empty store, e.g. right after a page load) or when the point count
    actually changes (old indices wouldn't mean the same thing against a
    differently-sized array). Otherwise a re-integration at the same
    point count keeps whatever range the user already dialed in.
    """
    curves = (q_data or {}).get("curves") or []
    if not curves:
        raise PreventUpdate
    n = len(curves[0]["q"])
    if idx_store and idx_store.get("n") == n:
        raise PreventUpdate
    return {"min_idx": 0, "max_idx": max(n - 1, 0), "n": n}


@callback(
    Output("scat-qrange-idx-store", "data", allow_duplicate=True),
    Input("scat-qrange-min", "value"),
    Input("scat-qrange-max", "value"),
    Input("scat-qrange-min-idx", "value"),
    Input("scat-qrange-max-idx", "value"),
    Input("scat-qrange-min-idx-up", "n_clicks"),
    Input("scat-qrange-min-idx-down", "n_clicks"),
    Input("scat-qrange-max-idx-up", "n_clicks"),
    Input("scat-qrange-max-idx-down", "n_clicks"),
    State("scat-qrange-idx-store", "data"),
    State("scat-q-data-store", "data"),
    prevent_initial_call=True,
)
def manage_qrange_idx_interaction(min_val, max_val, min_idx_typed, max_idx_typed,
                                   min_up, min_down, max_up, max_down,
                                   idx_store, q_data):
    trigger = ctx.triggered_id
    curves = (q_data or {}).get("curves") or []
    if not curves or trigger is None:
        raise PreventUpdate

    q_raw = curves[0]["q"]
    n = len(q_raw)
    idx_store = dict(idx_store or {})
    min_idx = idx_store.get("min_idx", 0)
    max_idx = idx_store.get("max_idx", max(n - 1, 0))

    if trigger == "scat-qrange-min":
        if min_val is None:
            raise PreventUpdate
        min_idx = min(int(np.argmin(np.abs(np.array(q_raw) - float(min_val)))), max_idx)

    elif trigger == "scat-qrange-max":
        if max_val is None:
            raise PreventUpdate
        max_idx = max(int(np.argmin(np.abs(np.array(q_raw) - float(max_val)))), min_idx)

    elif trigger == "scat-qrange-min-idx":
        if min_idx_typed is None:
            raise PreventUpdate
        min_idx = max(0, min(int(min_idx_typed), max_idx))

    elif trigger == "scat-qrange-max-idx":
        if max_idx_typed is None:
            raise PreventUpdate
        max_idx = min(n - 1, max(int(max_idx_typed), min_idx))

    elif trigger == "scat-qrange-min-idx-up":
        if not min_up:
            raise PreventUpdate
        min_idx = min(min_idx + 1, max_idx)

    elif trigger == "scat-qrange-min-idx-down":
        if not min_down:
            raise PreventUpdate
        min_idx = max(min_idx - 1, 0)

    elif trigger == "scat-qrange-max-idx-up":
        if not max_up:
            raise PreventUpdate
        max_idx = min(max_idx + 1, n - 1)

    elif trigger == "scat-qrange-max-idx-down":
        if not max_down:
            raise PreventUpdate
        max_idx = max(max_idx - 1, min_idx)

    else:
        raise PreventUpdate

    return {"min_idx": min_idx, "max_idx": max_idx, "n": n}


@callback(
    Output("scat-qrange-min", "value"),
    Output("scat-qrange-max", "value"),
    Output("scat-qrange-min-idx", "value"),
    Output("scat-qrange-max-idx", "value"),
    Output("scat-qrange-store", "data"),
    Input("scat-qrange-idx-store", "data"),
    Input("scat-q-data-store", "data"),
    prevent_initial_call=True,
)
def render_qrange_fields(idx_store, q_data):
    """
    Renders the value/index display fields AND applies the filter live —
    there's no separate "Apply Q Range" button/step anymore, since the
    fields are already always valid (cross-clamped, snapped to real data
    points), so every edit (typing, spin-click, or a fresh Integrate) both
    displays and applies in the same step.

    Also the sole writer of scat-qrange-store (run_integration no longer
    touches it) — this must fire on *every* Integrate click, not just ones
    where scat-qrange-idx-store's value actually changes, otherwise a
    same-point-count re-integration (which correctly leaves the idx-store
    alone, keeping your dialed-in range) would leave scat-qrange-store
    stuck at whatever run_integration last set it to, showing unfiltered
    data instead of your range. Watching scat-q-data-store directly is
    what guarantees that.
    """
    curves = (q_data or {}).get("curves") or []
    if not curves or not idx_store:
        raise PreventUpdate

    q_raw = curves[0]["q"]
    n = len(q_raw)
    # Defensive clamp: normally n-tracking in reset_qrange_idx guarantees
    # idx_store's bounds already match this q_raw, but don't index past the
    # end if they ever fall out of sync.
    max_idx = min(idx_store.get("max_idx", n - 1), n - 1)
    min_idx = min(idx_store.get("min_idx", 0), max_idx)
    q_min = round(float(q_raw[min_idx]), 6)
    q_max = round(float(q_raw[max_idx]), 6)
    return q_min, q_max, min_idx, max_idx, {"q_min": q_min, "q_max": q_max}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Cake (2-D integration) plot
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-cake-graph", "figure"),
    Input("scat-cake-btn", "n_clicks"),
    State("scat-image-store", "data"),
    State("scat-distance", "value"),
    State("scat-wavelength-or-energy", "value"),
    State("scat-wavelength", "value"),
    State("scat-energy", "value"),
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
    State("scat-cbar-min", "value"),
    State("scat-cbar-max", "value"),
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    State("scat-pixel-mask-store", "data"),
    prevent_initial_call=True,
)
def run_cake(
    n_clicks,
    image_data,
    distance_mm, wl_or_e, wavelength_A, energy_keV,
    bcx, bcy, px_x_um, px_y_um,
    rot1_deg, rot2_deg, rot3_deg,
    n_pts, unit,
    mask_low, mask_high,
    cbar_min, cbar_max,
    colorscale, log_scale,
    pixel_mask_regions,
):
    if not n_clicks or image_data is None:
        raise PreventUpdate

    arr = np.array(image_data, dtype=float)

    if wl_or_e == "energy":
        if not energy_keV:
            raise PreventUpdate
        wl_A = energy_to_wavelength(float(energy_keV))
    else:
        if not wavelength_A:
            raise PreventUpdate
        wl_A = float(wavelength_A)

    try:
        dist_m = float(distance_mm) * 1e-3
        px_x_m = float(px_x_um) * 1e-6
        px_y_m = float(px_y_um) * 1e-6
        rot1_rad = np.deg2rad(float(rot1_deg or 0))
        rot2_rad = np.deg2rad(float(rot2_deg or 0))
        rot3_rad = np.deg2rad(float(rot3_deg or 0))

        # bcx/bcy are the Fit2D-style (physical) beam centre; convert to
        # the PONI point the current tilt implies before building.
        poni_x, poni_y = fit2d_beam_center_to_poni_pixels(
            float(bcx), float(bcy), px_x_m, px_y_m, dist_m, rot1_rad, rot2_rad,
        )

        ai = build_integrator(
            detector_distance_m=dist_m,
            wavelength_m=wl_A * 1e-10,
            beam_center_x=poni_x,
            beam_center_y=poni_y,
            pixel_size_x=px_x_m,
            pixel_size_y=px_y_m,
            rot1=rot1_rad,
            rot2=rot2_rad,
            rot3=rot3_rad,
        )
    except Exception as exc:
        return _error_figure(f"Integrator error: {exc}")

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    try:
        I2d, q_ax, chi_ax = integrate_2d(
            arr, ai,
            n_radial=int(n_pts or 500),
            n_azimuth=360,
            unit=unit or "q_A^-1",
            mask=mask,
        )
    except Exception as exc:
        return _error_figure(f"Cake error: {exc}")

    display = I2d.copy()
    is_log = bool(log_scale and "log" in (log_scale or []))
    if is_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)

    cake_zmin, cake_zmax = _cbar_zrange(cbar_min, cbar_max, is_log)

    cake_colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if is_log:
        tickvals, ticktext = _power_of_ten_ticks(display, vmin=cake_zmin, vmax=cake_zmax)
        if tickvals is not None:
            cake_colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            x=q_ax,
            y=chi_ax,
            z=display,
            zmin=cake_zmin,
            zmax=cake_zmax,
            colorscale=colorscale or "Viridis",
            colorbar=cake_colorbar,
            hovertemplate=f"{_UNIT_LABELS.get(unit, unit)}: %{{x:.4g}}<br>χ: %{{y:.1f}}°<br>I: %{{z:.3g}}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title=_UNIT_LABELS.get(unit, unit or "q (Å⁻¹)"),
        yaxis_title="Azimuthal angle χ (°)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-cake",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        xaxis=dict(
            showgrid=False, zeroline=False, linecolor="black", mirror=True,
            ticks="outside", tickcolor="black",
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, linecolor="black", mirror=True,
            ticks="outside", tickcolor="black",
            minor=dict(ticks="outside", tickcolor="black"),
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Download the 1-D integration result as CSV
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-download", "data"),
    Input("scat-download-btn", "n_clicks"),
    State("scat-integration-store", "data"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, store):
    if not n_clicks or not store:
        raise PreventUpdate

    curves = store.get("curves", [])
    if not curves:
        raise PreventUpdate

    unit = store.get("unit", "q")
    has_sigma = any(c["sigma"] is not None for c in curves)

    header = f"region,{unit},I" + (",sigma" if has_sigma else "")
    rows = []
    for curve in curves:
        region_label = curve.get("name", "I(q)").replace('"', "'")
        q, I, sigma = curve["q"], curve["I"], curve["sigma"]
        for i, (qi, Ii) in enumerate(zip(q, I)):
            row = f'"{region_label}",{qi:.6g},{Ii:.6g}'
            if has_sigma:
                row += f",{sigma[i]:.6g}" if sigma is not None else ","
            rows.append(row)

    content = header + "\n" + "\n".join(rows)

    return dict(content=content, filename="integration_1d.csv", type="text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Toggle wavelength / energy input visibility
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-wavelength-row", "style"),
    Output("scat-energy-row", "style"),
    Input("scat-wavelength-or-energy", "value"),
)
def toggle_wavelength_energy(choice):
    show = {"display": "flex", "alignItems": "center", "marginBottom": "8px"}
    hide = {"display": "none"}
    if choice == "energy":
        return hide, show
    return show, hide


# ─────────────────────────────────────────────────────────────────────────────
# 7.  (Beam-centre overlay is now baked directly into render_2d_image / the
#      q-space figure in run_integration, so it survives every redraw.)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# 7.5.  Azimuthal wedge region management (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-azimuth-regions-store", "data"),
    Input("scat-azimuth-add-btn", "n_clicks"),
    Input("scat-azimuth-clear-btn", "n_clicks"),
    Input({"type": "scat-azimuth-remove", "index": ALL}, "n_clicks"),
    State("scat-azimuth-min", "value"),
    State("scat-azimuth-max", "value"),
    State("scat-wedge-qmin", "value"),
    State("scat-wedge-qmax", "value"),
    State("scat-azimuth-regions-store", "data"),
    prevent_initial_call=True,
)
def manage_azimuth_regions(add_clicks, clear_clicks, remove_clicks,
                            az_min, az_max, q_min, q_max, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "scat-azimuth-clear-btn":
        return []

    if trigger == "scat-azimuth-add-btn":
        if az_min is None or az_max is None or q_min is None or q_max is None:
            raise PreventUpdate
        regions.append({
            "az_min": float(az_min), "az_max": float(az_max),
            "q_min": float(q_min), "q_max": float(q_max),
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "scat-azimuth-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("scat-azimuth-list", "children"),
    Input("scat-azimuth-regions-store", "data"),
)
def render_azimuth_list(regions):
    if not regions:
        return html.Div(
            "No azimuthal regions defined — Integrate 1-D will run one "
            "unrestricted (full-azimuth) integration.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, region in enumerate(regions):
        color = _azimuth_color(i)
        rows.append(html.Div([
            html.Span(style={
                "display": "inline-block", "width": "10px", "height": "10px",
                "backgroundColor": color, "borderRadius": "2px", "marginRight": "6px",
            }),
            html.Span(
                f"az=[{region['az_min']:.1f}°, {region['az_max']:.1f}°] "
                f"q=[{region['q_min']:.3g}, {region['q_max']:.3g}]",
                style={"fontSize": "0.85rem"},
            ),
            dbc.Button("✕", id={"type": "scat-azimuth-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Hot-pixel mask region management (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-pixel-mask-store", "data"),
    Input("scat-pixmask-add-btn", "n_clicks"),
    Input("scat-pixmask-clear-btn", "n_clicks"),
    Input({"type": "scat-pixmask-remove", "index": ALL}, "n_clicks"),
    State("scat-pixmask-shape", "value"),
    State("scat-pixmask-row", "value"),
    State("scat-pixmask-col", "value"),
    State("scat-pixmask-size", "value"),
    State("scat-pixel-mask-store", "data"),
    prevent_initial_call=True,
)
def manage_pixel_mask_regions(add_clicks, clear_clicks, remove_clicks,
                               shape, row, col, size, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "scat-pixmask-clear-btn":
        return []

    if trigger == "scat-pixmask-add-btn":
        if row is None or col is None or not size:
            raise PreventUpdate
        regions.append({
            "shape": shape or "square",
            "row": float(row),
            "col": float(col),
            "size": float(size),
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "scat-pixmask-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("scat-pixmask-list", "children"),
    Input("scat-pixel-mask-store", "data"),
)
def render_pixel_mask_list(regions):
    if not regions:
        return html.Div(
            "No hot-pixel regions defined.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, region in enumerate(regions):
        icon = "●" if region.get("shape") == "circle" else "■"
        rows.append(html.Div([
            html.Span(
                f"{icon} row={region['row']:.0f}, col={region['col']:.0f}, "
                f"size={region['size']:.0f}",
                style={"fontSize": "0.85rem"},
            ),
            dbc.Button("✕", id={"type": "scat-pixmask-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 8.5.
# ─────────────────────────────────────────────────────────────────────────────





# ─────────────────────────────────────────────────────────────────────────────
# 9.  
# ─────────────────────────────────────────────────────────────────────────────




# # ─────────────────────────────────────────────────────────────────────────────
# # 10.  Azimuthal wedge overlay on the q-space image
# # ─────────────────────────────────────────────────────────────────────────────

# @callback(
#     Output("scat-2d-q-graph", "figure", allow_duplicate=True),
#     Input("scat-draw-wedge-btn", "n_clicks"),
#     State("scat-azimuth-min", "value"),
#     State("scat-azimuth-max", "value"),
#     State("scat-wedge-qmin", "value"),
#     State("scat-wedge-qmax", "value"),
#     State("scat-2d-q-graph", "figure"),
#     prevent_initial_call='initial_duplicate',
# )

# def draw_wedge(n_clicks, az_min, az_max, q_min, q_max, current_fig):
#     if not n_clicks or current_fig is None:
#         raise PreventUpdate

#     # All four inputs are required
#     if any(v is None for v in [az_min, az_max, q_min, q_max]):
#         raise PreventUpdate

#     az_min  = float(az_min)
#     az_max  = float(az_max)
#     q_min   = float(q_min)
#     q_max   = float(q_max)

#     fig = go.Figure(current_fig)

#     # Drop any previously drawn wedge traces
#     fig.data = tuple(
#         t for t in fig.data
#         if not str(getattr(t, "name", "")).startswith("Wedge")
#     )

#     # ── Build wedge outline as a closed polygon in qx/qy space ───────────────
#     # A wedge is defined by:
#     #   - two straight edges from the origin along az_min and az_max
#     #   - an inner arc at q_min
#     #   - an outer arc at q_max
#     # Angles in pyFAI chi convention: we negate to match the qx/qy plot

#     ang_min = np.deg2rad(-az_max)   # note swap + negate to match pyFAI convention
#     ang_max = np.deg2rad(-az_min)

#     # Arc angles
#     arc_angles = np.linspace(ang_min, ang_max, 120)

#     # Outer arc (q_max), traced forward
#     outer_x = q_max * np.cos(arc_angles)
#     outer_y = q_max * np.sin(arc_angles)

#     # Inner arc (q_min), traced backward to close the shape
#     inner_x = q_min * np.cos(arc_angles[::-1])
#     inner_y = q_min * np.sin(arc_angles[::-1])

#     # Close the polygon
#     wedge_x = np.concatenate([outer_x, inner_x, [outer_x[0]]])
#     wedge_y = np.concatenate([outer_y, inner_y, [outer_y[0]]])

#     fig.add_trace(
#         go.Scatter(
#             x=wedge_x,
#             y=wedge_y,
#             mode="lines",
#             line=dict(color="white", width=1.5, dash="dash"),
#             fill="none",
#             name="Wedge",
#             hovertemplate=(
#                 f"az: [{az_min:.1f}°, {az_max:.1f}°]<br>"
#                 f"q: [{q_min:.3g}, {q_max:.3g}] Å⁻¹<extra></extra>"
#             ),
#         )
#     )

#     return fig


# ─────────────────────────────────────────────────────────────────────────────
# 11.  Parse poni file and populate geometry fields
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-distance",   "value"),
    Output("scat-energy",     "value"),
    Output("scat-wavelength", "value"),
    Output("scat-bcx",        "value"),
    Output("scat-bcy",        "value"),
    Output("scat-px-x",       "value"),
    Output("scat-px-y",       "value"),
    Output("scat-rot1",       "value"),
    Output("scat-rot2",       "value"),
    Output("scat-rot3",       "value"),
    Output("scat-poni-status","children"),
    Input("scat-poni-upload", "contents"),
    State("scat-poni-upload", "filename"),
    prevent_initial_call=True,
)
def parse_poni(contents, filename):
    if contents is None:
        raise PreventUpdate

    # ── Decode the uploaded file ──────────────────────────────────────────────
    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string).decode("utf-8")
    except Exception as exc:
        return (no_update,) * 10 + (f"✘ Could not decode file: {exc}",)


    # ── Load with pyFAI ───────────────────────────────────────────────────────
    try:
        # pyFAI.load() requires a file path, not a StringIO object
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".poni",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(decoded)
            tmp_path = tmp.name

        ai = pyFAI.load(tmp_path)

    except Exception as exc:
        return (no_update,) * 10 + (f"✘ pyFAI could not parse poni: {exc}",)
    finally:
        # Clean up the temp file whether or not loading succeeded
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


    # ── Extract geometry ──────────────────────────────────────────────────────
    try:
        # Distance
        distance_mm = round(ai.dist * 1000, 4)

        # Wavelength and energy
        h   = 6.62607015e-34
        c   = 2.99792458e8
        eV  = 1.60217663e-19
        wavelength_A = round(ai.wavelength * 1e10, 6)           # m → Å
        energy_keV   = round((h * c) / (eV * ai.wavelength) / 1000, 4)  # m → keV

        # Beam centre via getFit2D (pixels) -- the physical pixel where the
        # direct beam actually hits the detector, i.e. what looks like "the
        # beam centre" when you inspect the image. This is NOT the same
        # point as the PONI once the detector is tilted (rot1/rot2 != 0);
        # run_integration()/run_cake() convert this back to the PONI point
        # via fit2d_beam_center_to_poni_pixels() before building the
        # integrator, using whatever Rot1/Rot2 currently say.
        fit2d = ai.getFit2D()
        bcx   = round(fit2d["centerX"], 2)
        bcy   = round(fit2d["centerY"], 2)

        # Pixel sizes μm
        px_x_um = round(ai.detector.pixel2 * 1e6, 4)   # pixel2 → X
        px_y_um = round(ai.detector.pixel1 * 1e6, 4)   # pixel1 → Y

        # Detector rotations: pyFAI stores rot1/rot2/rot3 in radians — display in degrees
        rot1_deg = round(np.degrees(ai.rot1), 4)
        rot2_deg = round(np.degrees(ai.rot2), 4)
        rot3_deg = round(np.degrees(ai.rot3), 4)

        status = (
            f"✔ Loaded '{filename}' — "
            f"{ai.detector.__class__.__name__}, "
            f"SDD={distance_mm:.1f} mm, "
            f"E={energy_keV:.4f} keV"
        )

    except Exception as exc:
        return (no_update,) * 10 + (f"✘ Error reading geometry: {exc}",)

    return (
        distance_mm,
        energy_keV,
        wavelength_A,
        bcx,
        bcy,
        px_x_um,
        px_y_um,
        rot1_deg,
        rot2_deg,
        rot3_deg,
        status,
    )