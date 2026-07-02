
"""
Dash callbacks for the 2-D scattering viewer / 1-D integrator panel.
"""

from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, callback, no_update, ctx
from dash.exceptions import PreventUpdate

import io
import base64
import tempfile
import os
import pyFAI


from utils.scattering_utils import (
    decode_upload,
    apply_threshold_mask,
    build_integrator,
    integrate_1d,
    integrate_2d,
    integrate_2d_qxy,
    q_to_twotheta,
    energy_to_wavelength,
)

# ── Constants ─────────────────────────────────────────────────────────────────
_COLORSCALES = ["Viridis", "Inferno", "Plasma", "Hot", "Greys", "Jet"]
_UNITS       = ["q_A^-1", "q_nm^-1", "2th_deg", "r_mm"]
_UNIT_LABELS = {
    "q_A^-1":  "q (Å⁻¹)",
    "q_nm^-1": "q (nm⁻¹)",
    "2th_deg": "2θ (°)",
    "r_mm":    "r (mm)",
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
    prevent_initial_call=True,
)
def render_2d_image(image_data, colorscale, log_scale, mask_low, mask_high):
    if image_data is None:
        raise PreventUpdate

    arr = np.array(image_data, dtype=float)

    # Apply threshold mask — set masked pixels to NaN so they show as blank
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    display = arr.copy()
    display[mask] = np.nan

    if log_scale and "log" in (log_scale or []):
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)
        colorbar_title = "log(I)"
    else:
        colorbar_title = "Intensity"

    fig = go.Figure(
        go.Heatmap(
            z=display,
            colorscale=colorscale or "Viridis",
            colorbar=dict(title=colorbar_title, x=1.01, thickness=20, len=0.87, lenmode="fraction"),
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
        ),
        xaxis=dict(
            range=[0, ncols],       # exact image width
            constrain="domain",
        ),
        xaxis_title="Pixel (col)",
        yaxis_title="Pixel (row)",
        uirevision="scat-2d",
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Run 1-D integration and render the result
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    #Output("scat-1d-graph", "figure"),
    Output("scat-q-data-store", "data"),       # ← was scat-1d-graph
    Output("scat-qrange-store", "data"),        # ← new
    # Output("scat-qrange-min", "value"),         # ← new (auto-populate)
    # Output("scat-qrange-max", "value"),         # ← new (auto-populate)
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
    State("scat-tilt", "value"),
    State("scat-tilt-rot", "value"),
    # Integration options
    State("scat-npts", "value"),
    State("scat-unit-dropdown", "value"),
    State("scat-mask-low", "value"),
    State("scat-mask-high", "value"),
    State("scat-azimuth-min", "value"),
    State("scat-azimuth-max", "value"),
    State("scat-error-model", "value"),
    # Display options
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    State("scat-log-y-toggle", "value"),
    State("scat-log-x-toggle", "value"),
    State("scat-wedge-qmin", "value"),
    State("scat-wedge-qmax", "value"),
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
    tilt, tilt_rot,
    n_pts,
    unit,
    mask_low, mask_high,
    az_min, az_max,
    error_model,
    colorscale,
    log_scale,
    log_y,
    log_x,
    wedge_qmin,
    wedge_qmax,
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
        ai = build_integrator(
            detector_distance_m=float(distance_mm) * 1e-3,
            wavelength_m=wl_m,
            beam_center_x=float(bcx),
            beam_center_y=float(bcy),
            pixel_size_x=float(px_x_um) * 1e-6,
            pixel_size_y=float(px_y_um) * 1e-6,
            tilt=float(tilt or 0),
            tilt_plane_rotation=float(tilt_rot or 0),
        )
    except Exception as exc:
        empty = _error_figure(f"Integrator error: {exc}")
        return empty, no_update, empty

    # ── Mask ─────────────────────────────────────────────────────────────────
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)

    # ── Azimuth range ────────────────────────────────────────────────────────
    az_range = None
    if az_min is not None and az_max is not None:
        az_range = (float(az_min), float(az_max))

    # ── 1-D integration ───────────────────────────────────────────────────────
    try:
        q, I, sigma = integrate_1d(
            arr, ai,
            n_points=int(n_pts or 1000),
            unit=unit or "q_A^-1",
            mask=mask,
            azimuth_range=az_range,
            error_model=error_model or None,
        )
    except Exception as exc:
        return _error_figure(f"Integration error: {exc}"), no_update, no_update

    # ── Build 1-D figure ──────────────────────────────────────────────────────
    fig_1d = go.Figure()
    if sigma is not None:
        fig_1d.add_trace(go.Scatter(
            x=q, y=I,
            error_y=dict(type="data", array=sigma, visible=True, thickness=1),
            mode="lines",
            name="I(q) ± σ",
            line=dict(width=1.5),
        ))
    else:
        fig_1d.add_trace(go.Scatter(
            x=q, y=I,
            mode="lines",
            name="I(q)",
            line=dict(width=1.5),
        ))

    xlabel = _UNIT_LABELS.get(unit, unit or "q (Å⁻¹)")
    ytype = "log" if (log_y and "log" in log_y) else "linear"
    xtype = "log" if (log_x and "log" in log_x) else "linear"
    fig_1d.update_layout(
        xaxis_title=xlabel,
        xaxis_type=xtype,
        yaxis_title="Intensity (a.u.)",
        yaxis_type=ytype,
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-1d",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
        yaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
    )

    # ── qx/qy remapped 2-D image ──────────────────────────────────────────────
    try:
        I_qxy, qx, qy = integrate_2d_qxy(
            arr, ai,
            n_points=int(n_pts or 500),
            mask=mask,
        )
    except Exception as exc:
        #return fig_1d, _build_store(q, I, sigma, unit), _error_figure(f"qx/qy error: {exc}")
        # return no_update, no_update, no_update, no_update, no_update, _error_figure(f"Integrator error: {exc}")
        return no_update, no_update, no_update, _error_figure(f"Integrator error: {exc}")

    
    # Apply threshold mask (same logic as pixel-space image)
    display_qxy = I_qxy.copy()
    if mask_low is not None or mask_high is not None:
        qxy_mask = apply_threshold_mask(I_qxy, low=mask_low, high=mask_high)
        display_qxy[qxy_mask] = np.nan

    if log_scale and "log" in (log_scale or []):
        with np.errstate(divide="ignore", invalid="ignore"):
            display_qxy = np.where(display_qxy > 0, np.log10(display_qxy), np.nan)
        cb_title = "log₁₀(I)"
    else:
        cb_title = "Intensity"

    fig_qxy = go.Figure(
        go.Heatmap(
            x=qx,
            y=qy,
            z=display_qxy,
            colorscale=colorscale or "Viridis",
            colorbar=dict(title=cb_title,  x=1.01, thickness=20, len=0.87, lenmode="fraction"),
            hovertemplate="qx: %{x:.4g} Å⁻¹<br>qy: %{y:.4g} Å⁻¹<br>I: %{z:.3g}<extra></extra>",
        )
    )

    fig_qxy.update_layout(
        xaxis_title="qx (Å⁻¹)",
        yaxis_title="qy (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-2d-q",
        xaxis=dict(
            range=[float(qx.min()), float(qx.max())],
            constrain="domain",
        ),
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
            constrain="domain",
            range=[float(qy.min()), float(qy.max())],
        ),
    )

    
    # ── Wedge overlay ─────────────────────────────────────────────────────────
    if all(v is not None for v in [az_min, az_max, wedge_qmin, wedge_qmax]):
        ang_min = np.deg2rad(-float(az_max))
        ang_max = np.deg2rad(-float(az_min))
        arc_angles = np.linspace(ang_min, ang_max, 120)

        q_min_w = float(wedge_qmin)
        q_max_w = float(wedge_qmax)

        outer_x = q_max_w * np.cos(arc_angles)
        outer_y = q_max_w * np.sin(arc_angles)
        inner_x = q_min_w * np.cos(arc_angles[::-1])
        inner_y = q_min_w * np.sin(arc_angles[::-1])

        wedge_x = np.concatenate([outer_x, inner_x, [outer_x[0]]])
        wedge_y = np.concatenate([outer_y, inner_y, [outer_y[0]]])

        fig_qxy.add_trace(go.Scatter(
            x=wedge_x,
            y=wedge_y,
            mode="lines",
            line=dict(color="white", width=1.5, dash="dash"),
            fill="none",
            name="Wedge",
            hovertemplate=(
                f"az: [{az_min:.1f}°, {az_max:.1f}°]<br>"
                f"q: [{q_min_w:.3g}, {q_max_w:.3g}] Å⁻¹<extra></extra>"
            ),
        ))

    q_min = round(float(np.min(q)), 4)
    q_max = round(float(np.max(q)), 4)

    return (
        {"q": q.tolist(), "I": I.tolist(), "sigma": sigma.tolist() if sigma is not None else None, "unit": unit},
        # {"q_min": q_min, "q_max": q_max},
        # q_min,
        # q_max,
        None,   # ← qrange-store starts empty, meaning "no filter applied yet"
        _build_store(q, I, sigma, unit),
        fig_qxy,
    )


def _build_store(q, I, sigma, unit):
    return {
        "q": q.tolist(),
        "I": I.tolist(),
        "sigma": sigma.tolist() if sigma is not None else None,
        "unit": unit,
    }


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

    q     = np.array(q_data["q"])
    I     = np.array(q_data["I"])
    sigma = np.array(q_data["sigma"]) if q_data["sigma"] is not None else None
    unit  = q_data.get("unit", unit)

    if q_range and q_range.get("q_min") is not None and q_range.get("q_max") is not None:
        mask = (q >= q_range["q_min"]) & (q <= q_range["q_max"])
    else:
        mask = np.ones_like(q, dtype=bool)   # no filter — show full range

    q_plot = q[mask]
    I_plot = I[mask]
    s_plot = sigma[mask] if sigma is not None else None

    fig = go.Figure()
    if s_plot is not None:
        fig.add_trace(go.Scatter(
            x=q_plot, y=I_plot,
            error_y=dict(type="data", array=s_plot, visible=True, thickness=1),
            mode="lines", name="I(q) ± σ", line=dict(width=1.5),
        ))
    else:
        fig.add_trace(go.Scatter(
            x=q_plot, y=I_plot,
            mode="lines", name="I(q)", line=dict(width=1.5),
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
        xaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
        yaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
    )
    return fig



# ─────────────────────────────────────────────────────────────────────────────
# 3.5.5.  Apply Q Range callback
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-qrange-store", "data", allow_duplicate=True),
    Input("scat-apply-qrange-btn", "n_clicks"),
    State("scat-qrange-min", "value"),
    State("scat-qrange-max", "value"),
    prevent_initial_call=True,
)
def apply_q_range(n_clicks, q_min, q_max):
    if q_min is None or q_max is None:
        raise PreventUpdate
    return {"q_min": q_min, "q_max": q_max}


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
    State("scat-tilt", "value"),
    State("scat-tilt-rot", "value"),
    State("scat-npts", "value"),
    State("scat-unit-dropdown", "value"),
    State("scat-mask-low", "value"),
    State("scat-mask-high", "value"),
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    prevent_initial_call=True,
)
def run_cake(
    n_clicks,
    image_data,
    distance_mm, wl_or_e, wavelength_A, energy_keV,
    bcx, bcy, px_x_um, px_y_um,
    tilt, tilt_rot,
    n_pts, unit,
    mask_low, mask_high,
    colorscale, log_scale,
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
        ai = build_integrator(
            detector_distance_m=float(distance_mm) * 1e-3,
            wavelength_m=wl_A * 1e-10,
            beam_center_x=float(bcx),
            beam_center_y=float(bcy),
            pixel_size_x=float(px_x_um) * 1e-6,
            pixel_size_y=float(px_y_um) * 1e-6,
            tilt=float(tilt or 0),
            tilt_plane_rotation=float(tilt_rot or 0),
        )
    except Exception as exc:
        return _error_figure(f"Integrator error: {exc}")

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)

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
    if log_scale and "log" in (log_scale or []):
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)
        cb_title = "log₁₀(I)"
    else:
        cb_title = "Intensity"

    fig = go.Figure(
        go.Heatmap(
            x=q_ax,
            y=chi_ax,
            z=display,
            colorscale=colorscale or "Viridis",
            colorbar=dict(title=cb_title),
            hovertemplate=f"{_UNIT_LABELS.get(unit, unit)}: %{{x:.4g}}<br>χ: %{{y:.1f}}°<br>I: %{{z:.3g}}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title=_UNIT_LABELS.get(unit, unit or "q (Å⁻¹)"),
        yaxis_title="Azimuthal angle χ (°)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="scat-cake",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
        yaxis=dict(showgrid=True, gridcolor="#e5e5e5", linecolor="black", mirror=True),
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
    if not n_clicks or store is None:
        raise PreventUpdate

    q   = store["q"]
    I   = store["I"]
    sigma = store["sigma"]
    unit  = store.get("unit", "q")

    header = f"{unit},I"
    rows   = [f"{qi:.6g},{Ii:.6g}" for qi, Ii in zip(q, I)]

    if sigma is not None:
        header += ",sigma"
        rows = [f"{r},{s:.6g}" for r, s in zip(rows, sigma)]

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
# 7.  Live beam-centre overlay on the 2-D image
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("scat-2d-graph", "figure", allow_duplicate=True),
    Input("scat-show-beam-centre", "value"),
    Input("scat-bcx", "value"),
    Input("scat-bcy", "value"),
    State("scat-2d-graph", "figure"),
    prevent_initial_call=True,
)

def overlay_beam_centre(show, bcx, bcy, current_fig):
    """
    Add (or remove) a crosshair marker at the beam centre position
    without re-rendering the full heatmap.
    """
    if current_fig is None:
        raise PreventUpdate

    import plotly.graph_objects as go   # local re-import is fine here

    fig = go.Figure(current_fig)

    # Drop any previously added beam-centre traces
    fig.data = tuple(
        t for t in fig.data if getattr(t, "name", "") != "Beam centre"
    )

    if show and "show" in show and bcx is not None and bcy is not None:
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
# 8.  
# ─────────────────────────────────────────────────────────────────────────────





# ─────────────────────────────────────────────────────────────────────────────
# 9.  
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _error_figure(message: str) -> go.Figure:
    """Return a blank figure with an error annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="red"),
    )
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    return fig


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
    Output("scat-tilt",       "value"),
    Output("scat-tilt-rot",   "value"),
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
        return (no_update,) * 9 + (f"✘ Could not decode file: {exc}",)

    
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
        return (no_update,) * 9 + (f"✘ pyFAI could not parse poni: {exc}",)
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

        # Beam centre via getFit2D (pixels)
        fit2d = ai.getFit2D()
        bcx   = round(fit2d["centerX"], 2)
        bcy   = round(fit2d["centerY"], 2)
        # tilt      = round(fit2d["tilt"], 4)
        # tilt_rot  = round(fit2d["tiltPlanRotation"], 4)

        # Pixel sizes μm
        px_x_um = round(ai.detector.pixel2 * 1e6, 4)   # pixel2 → X
        px_y_um = round(ai.detector.pixel1 * 1e6, 4)   # pixel1 → Y

        status = (
            f"✔ Loaded '{filename}' — "
            f"{ai.detector.__class__.__name__}, "
            f"SDD={distance_mm:.1f} mm, "
            f"E={energy_keV:.4f} keV"
        )

    except Exception as exc:
        return (no_update,) * 9 + (f"✘ Error reading geometry: {exc}",)

    return (
        distance_mm,
        energy_keV,
        wavelength_A,
        bcx,
        bcy,
        px_x_um,
        px_y_um,
        0, #tilt,
        0, #tilt_rot,
        status,
    )