
"""
Dash callbacks for the Grazing Incidence (GI-SWAXS) tab.

Geometry, the uploaded image, and masking are all reused live from the
Scattering 2D & 1D tab's `scat-*` components via cross-tab State/Input,
the same pattern callbacks_batch_swaxs.py already uses. Only the
grazing-incidence-specific geometry and the three integration schemes
(azimuthal, vertical-region, horizontal-region) are new here.
"""

from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, ALL, callback, ctx, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from utils.scattering_utils import (
    apply_threshold_mask,
    build_pixel_mask,
    build_integrator,
    build_fiber_integrator,
    integrate_1d,
    integrate_2d_grazing_incidence,
    integrate_1d_grazing_incidence,
    energy_to_wavelength,
    power_of_ten_ticks,
    cbar_zrange,
)
from callbacks._shared import wedge_overlay_trace, error_figure

# ── Constants ─────────────────────────────────────────────────────────────────
_VERT_COLORS    = ["#1f77b4", "#17becf", "#2ca02c", "#8c564b", "#9467bd"]
_HORIZ_COLORS   = ["#ff7f0e", "#d62728", "#e377c2", "#bcbd22", "#7f7f7f"]
_AZIMUTH_COLORS = ["magenta", "gold", "cyan", "orchid", "chartreuse"]

_PALETTES = {"vert": _VERT_COLORS, "horiz": _HORIZ_COLORS, "azimuth": _AZIMUTH_COLORS}


def _region_color(regions_kind: str, index: int) -> str:
    palette = _PALETTES[regions_kind]
    return palette[index % len(palette)]


def _side_ranges(side: str, pos_label: str, neg_label: str, lo_full: float, hi_full: float):
    """
    Split a sweep range [lo_full, hi_full] into a positive-side (0, hi_full)
    and/or negative-side (lo_full, 0) sub-range depending on *side*, so a
    feature straddling zero (direct-beam streak, specular horizon, …)
    doesn't get averaged across it by default.

    A candidate side is dropped if it's degenerate for this geometry (e.g.
    lo_full >= 0 means there's no negative side at all) — callers should
    treat an empty return as "nothing to integrate on that side", not an
    error, and report it rather than silently plotting nothing.

    Returns a list of (label_suffix, (lo, hi), mirror) tuples. mirror=True
    for the negative-side entry — its x-values need negating before
    plotting, since they're otherwise invisible whenever the shared 1-D
    plot's x-axis is log-scaled (log of a negative number is undefined,
    so Plotly/matplotlib just drop those points silently).
    """
    both = side == "both"
    candidates = []
    if side in ("right", "upper", "both"):
        candidates.append((f" ({pos_label})" if both else "", (0.0, hi_full), False))
    if side in ("left", "lower", "both"):
        candidates.append((f" ({neg_label})" if both else "", (lo_full, 0.0), True))
    return [(label, r, mirror) for label, r, mirror in candidates if r[0] < r[1]]


def _horiz_side_ranges(side: str, qxy_min_full: float, qxy_max_full: float):
    """qxy sweep range for a horizontal region's I(qxy) profile."""
    return _side_ranges(side, "right", "left", qxy_min_full, qxy_max_full)


def _vert_side_ranges(side: str, qz_min_full: float, qz_max_full: float):
    """qz sweep range for a vertical region's I(qz) profile."""
    return _side_ranges(side, "upper", "lower", qz_min_full, qz_max_full)


# ─────────────────────────────────────────────────────────────────────────────
# 0.  Azimuthal-region accumulator (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-azimuth-regions-store", "data"),
    Input("gi-azimuth-add-btn", "n_clicks"),
    Input("gi-azimuth-clear-btn", "n_clicks"),
    Input({"type": "gi-azimuth-remove", "index": ALL}, "n_clicks"),
    State("gi-azimuth-min", "value"),
    State("gi-azimuth-max", "value"),
    State("gi-wedge-qmin", "value"),
    State("gi-wedge-qmax", "value"),
    State("gi-azimuth-regions-store", "data"),
    prevent_initial_call=True,
)
def manage_azimuth_regions(add_clicks, clear_clicks, remove_clicks,
                            az_min, az_max, q_min, q_max, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "gi-azimuth-clear-btn":
        return []

    if trigger == "gi-azimuth-add-btn":
        if az_min is None or az_max is None or q_min is None or q_max is None:
            raise PreventUpdate
        regions.append({
            "az_min": float(az_min), "az_max": float(az_max),
            "q_min": float(q_min), "q_max": float(q_max),
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "gi-azimuth-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("gi-azimuth-list", "children"),
    Input("gi-azimuth-regions-store", "data"),
)
def render_azimuth_list(regions):
    if not regions:
        return html.Div(
            "No azimuthal regions defined.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, region in enumerate(regions):
        color = _region_color("azimuth", i)
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
            dbc.Button("✕", id={"type": "gi-azimuth-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Vertical-region accumulator (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-vert-regions-store", "data"),
    Input("gi-vert-add-btn", "n_clicks"),
    Input("gi-vert-clear-btn", "n_clicks"),
    Input({"type": "gi-vert-remove", "index": ALL}, "n_clicks"),
    State("gi-vert-qxy-min", "value"),
    State("gi-vert-qxy-max", "value"),
    State("gi-vert-side", "value"),
    State("gi-vert-regions-store", "data"),
    prevent_initial_call=True,
)
def manage_vert_regions(add_clicks, clear_clicks, remove_clicks, qxy_min, qxy_max, side, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "gi-vert-clear-btn":
        return []

    if trigger == "gi-vert-add-btn":
        if qxy_min is None or qxy_max is None:
            raise PreventUpdate
        regions.append({
            "qxy_min": float(qxy_min), "qxy_max": float(qxy_max),
            "side": side or "upper",
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "gi-vert-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("gi-vert-list", "children"),
    Input("gi-vert-regions-store", "data"),
)
def render_vert_list(regions):
    if not regions:
        return html.Div(
            "No vertical regions defined.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, region in enumerate(regions):
        color = _region_color("vert", i)
        rows.append(html.Div([
            html.Span(style={
                "display": "inline-block", "width": "10px", "height": "10px",
                "backgroundColor": color, "borderRadius": "2px", "marginRight": "6px",
            }),
            html.Span(
                f"qxy=[{region['qxy_min']:.3g}, {region['qxy_max']:.3g}] "
                f"({region.get('side', 'upper')})",
                style={"fontSize": "0.85rem"},
            ),
            dbc.Button("✕", id={"type": "gi-vert-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Horizontal-region accumulator (add / remove / clear)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-horiz-regions-store", "data"),
    Input("gi-horiz-add-btn", "n_clicks"),
    Input("gi-horiz-clear-btn", "n_clicks"),
    Input({"type": "gi-horiz-remove", "index": ALL}, "n_clicks"),
    State("gi-horiz-qz-min", "value"),
    State("gi-horiz-qz-max", "value"),
    State("gi-horiz-side", "value"),
    State("gi-horiz-regions-store", "data"),
    prevent_initial_call=True,
)
def manage_horiz_regions(add_clicks, clear_clicks, remove_clicks, qz_min, qz_max, side, regions):
    regions = list(regions or [])
    trigger = ctx.triggered_id

    if trigger == "gi-horiz-clear-btn":
        return []

    if trigger == "gi-horiz-add-btn":
        if qz_min is None or qz_max is None:
            raise PreventUpdate
        regions.append({
            "qz_min": float(qz_min), "qz_max": float(qz_max),
            "side": side or "right",
        })
        return regions

    if isinstance(trigger, dict) and trigger.get("type") == "gi-horiz-remove":
        idx = trigger["index"]
        if 0 <= idx < len(regions):
            regions.pop(idx)
        return regions

    raise PreventUpdate


@callback(
    Output("gi-horiz-list", "children"),
    Input("gi-horiz-regions-store", "data"),
)
def render_horiz_list(regions):
    if not regions:
        return html.Div(
            "No horizontal regions defined.",
            style={"color": "#6c757d", "fontStyle": "italic", "fontSize": "0.85rem"},
        )

    rows = []
    for i, region in enumerate(regions):
        color = _region_color("horiz", i)
        rows.append(html.Div([
            html.Span(style={
                "display": "inline-block", "width": "10px", "height": "10px",
                "backgroundColor": color, "borderRadius": "2px", "marginRight": "6px",
            }),
            html.Span(
                f"qz=[{region['qz_min']:.3g}, {region['qz_max']:.3g}] "
                f"({region.get('side', 'right')})",
                style={"fontSize": "0.85rem"},
            ),
            dbc.Button("✕", id={"type": "gi-horiz-remove", "index": i},
                       color="danger", outline=True, size="sm",
                       style={"padding": "0px 6px", "fontSize": "0.75rem"}),
        ], style={
            "display": "flex", "alignItems": "center", "justifyContent": "space-between",
            "marginBottom": "4px", "padding": "4px 8px",
            "backgroundColor": "#ffffff", "borderRadius": "4px", "border": "1px solid #dee2e6",
        }))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Integrate: build the qxy/qz image + compute all requested 1-D profiles
#
#     The 1-D plot itself is NOT built here — it's built by
#     render_gi_1d_plot below, from the curves/notes this callback stores,
#     so applying a Q Range trim doesn't require re-running any pyFAI calls.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-2d-graph", "figure"),
    Output("gi-integration-store", "data"),
    Input("gi-integrate-btn", "n_clicks"),
    # Reused geometry / image / mask (Scattering 2D & 1D is the reference tab)
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
    State("scat-mask-low", "value"),
    State("scat-mask-high", "value"),
    State("scat-pixel-mask-store", "data"),
    # Reused display options
    State("scat-colorscale-dropdown", "value"),
    State("scat-log-toggle", "value"),
    State("scat-cbar-min", "value"),
    State("scat-cbar-max", "value"),
    State("scat-show-beam-centre", "value"),
    # GI-specific geometry
    State("gi-incident-angle", "value"),
    State("gi-tilt-angle", "value"),
    State("gi-sample-orientation", "value"),
    State("gi-npt-ip", "value"),
    State("gi-npt-oop", "value"),
    # Region accumulators
    State("gi-azimuth-regions-store", "data"),
    State("gi-vert-regions-store", "data"),
    State("gi-horiz-regions-store", "data"),
    State("scat-npts", "value"),
    prevent_initial_call=True,
)
def run_gi_integration(
    n_clicks,
    image_data,
    distance_mm, wl_or_e, wavelength_A, energy_keV,
    bcx, bcy, px_x_um, px_y_um,
    rot1_deg, rot2_deg, rot3_deg,
    mask_low, mask_high, pixel_mask_regions,
    colorscale, log_scale, cbar_min, cbar_max, show_beam_centre,
    incident_angle_deg, tilt_angle_deg, sample_orientation, npt_ip, npt_oop,
    azimuth_regions, vert_regions, horiz_regions,
    n_pts_1d,
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
            rot1=np.deg2rad(float(rot1_deg or 0)),
            rot2=np.deg2rad(float(rot2_deg or 0)),
            rot3=np.deg2rad(float(rot3_deg or 0)),
        )
        fi = build_fiber_integrator(ai)
    except Exception as exc:
        empty = error_figure(f"Integrator error: {exc}")
        return empty, {"curves": [], "notes": [f"Integrator error: {exc}"]}

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    incident_angle_rad = np.deg2rad(float(incident_angle_deg or 0))
    tilt_angle_rad = np.deg2rad(float(tilt_angle_deg or 0))
    sample_orientation = int(sample_orientation or 1)

    try:
        I2d, qxy, qz = integrate_2d_grazing_incidence(
            arr, fi,
            sample_orientation=sample_orientation,
            incident_angle_rad=incident_angle_rad,
            tilt_angle_rad=tilt_angle_rad,
            n_ip=int(npt_ip or 500),
            n_oop=int(npt_oop or 500),
            mask=mask,
        )
    except Exception as exc:
        empty = error_figure(f"GI 2-D integration error: {exc}")
        return empty, {"curves": [], "notes": [f"GI 2-D integration error: {exc}"]}

    qxy_min_full, qxy_max_full = float(qxy.min()), float(qxy.max())
    qz_min_full, qz_max_full = float(qz.min()), float(qz.max())

    # ── 2-D figure ──────────────────────────────────────────────────────────
    display = I2d.copy()
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

    fig2d = go.Figure(
        go.Heatmap(
            x=qxy, y=qz, z=display,
            zmin=zmin, zmax=zmax,
            colorscale=colorscale or "Viridis",
            colorbar=colorbar,
            hovertemplate="q<sub>xy</sub>: %{x:.4g} Å⁻¹<br>q<sub>z</sub>: %{y:.4g} Å⁻¹<br>I: %{z:.3g}<extra></extra>",
        )
    )
    fig2d.update_layout(
        xaxis_title="q<sub>xy</sub> (Å⁻¹)",
        yaxis_title="q<sub>z</sub> (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="gi-2d",
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        xaxis=dict(
            range=[qxy_min_full, qxy_max_full],
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
            range=[qz_min_full, qz_max_full],
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
    )

    # Wedge overlays — drawn directly in (qxy, qz) coordinates. This is a
    # deliberate simplification: qxy/qz isn't a true polar remap of the
    # detector, so the wedge here is geometrically approximate, matching
    # what was agreed rather than adding a second, geometrically-exact
    # qx/qy panel just to host it.
    for i, region in enumerate(azimuth_regions or []):
        wedge = wedge_overlay_trace(
            region["az_min"], region["az_max"], region["q_min"], region["q_max"],
            color=_region_color("azimuth", i),
        )
        if wedge is not None:
            fig2d.add_trace(wedge)

    for i, region in enumerate(vert_regions or []):
        side_ranges = _vert_side_ranges(region.get("side", "upper"), qz_min_full, qz_max_full)
        for _label, (y0, y1), _mirror in side_ranges:
            fig2d.add_shape(
                type="rect",
                x0=region["qxy_min"], x1=region["qxy_max"],
                y0=y0, y1=y1,
                fillcolor=_region_color("vert", i),
                opacity=0.35, line=dict(width=0), layer="above",
            )

    for i, region in enumerate(horiz_regions or []):
        side_ranges = _horiz_side_ranges(region.get("side", "right"), qxy_min_full, qxy_max_full)
        for _label, (x0, x1), _mirror in side_ranges:
            fig2d.add_shape(
                type="rect",
                x0=x0, x1=x1,
                y0=region["qz_min"], y1=region["qz_max"],
                fillcolor=_region_color("horiz", i),
                opacity=0.35, line=dict(width=0), layer="above",
            )

    if show_beam_centre and "show" in show_beam_centre:
        fig2d.add_trace(go.Scatter(
            x=[0.0], y=[0.0],
            mode="markers",
            marker=dict(symbol="circle", size=5, color="red", line=dict(color="red", width=0)),
            name="Origin",
            showlegend=False,
            hovertemplate="Origin<br>qxy=0, qz=0<extra></extra>",
        ))

    # ── 1-D integrations ────────────────────────────────────────────────────
    # Only curves + notes are produced here; render_gi_1d_plot below turns
    # them into the actual figure, so a Q Range trim can re-filter and
    # redraw without re-running any of this.
    n_pts_1d = int(n_pts_1d or 1000)
    curves = []
    notes = []

    for i, region in enumerate(azimuth_regions or []):
        try:
            q, I, _sigma = integrate_1d(
                arr, ai,
                n_points=n_pts_1d,
                unit="q_A^-1",
                mask=mask,
                azimuth_range=(region["az_min"], region["az_max"]),
            )
            keep = I > 0
            if not keep.any():
                notes.append(
                    f"Azimuthal region {i}: no valid (unmasked, positive) pixels in this range."
                )
            else:
                curves.append({
                    "x": q[keep].tolist(), "y": I[keep].tolist(),
                    "name": f"Azimuthal [{region['az_min']:.1f}°, {region['az_max']:.1f}°]",
                    "color": _region_color("azimuth", i),
                })
        except Exception as exc:
            notes.append(f"Azimuthal region {i} error: {exc}")

    for i, region in enumerate(vert_regions or []):
        side = region.get("side", "upper")
        side_ranges = _vert_side_ranges(side, qz_min_full, qz_max_full)
        if not side_ranges:
            notes.append(f"Vertical region {i} ({side}): no qz data on that side for this geometry.")
            continue
        for label_suffix, oop_range, mirror in side_ranges:
            try:
                qz_x, I = integrate_1d_grazing_incidence(
                    arr, fi,
                    sample_orientation=sample_orientation,
                    incident_angle_rad=incident_angle_rad,
                    tilt_angle_rad=tilt_angle_rad,
                    ip_range=(region["qxy_min"], region["qxy_max"]),
                    oop_range=oop_range,
                    vertical_integration=True,
                    n_points=n_pts_1d,
                    mask=mask,
                )
                keep = I > 0
                if not keep.any():
                    notes.append(
                        f"Vertical region {i}{label_suffix}: no valid (unmasked, positive) "
                        "pixels in this range."
                    )
                    continue
                # The lower/negative side is otherwise invisible whenever the
                # shared x-axis is log-scaled (log of a negative number is
                # undefined) — mirror it to positive, matching how the
                # original notebook plots -qxy_1d_left_filtered.
                x_vals = -qz_x[keep] if mirror else qz_x[keep]
                curves.append({
                    "x": x_vals.tolist(), "y": I[keep].tolist(),
                    "name": (
                        f"Vertical qxy=[{region['qxy_min']:.3g}, {region['qxy_max']:.3g}] "
                        f"→ I(qz){label_suffix}"
                    ),
                    "color": _region_color("vert", i),
                })
            except Exception as exc:
                notes.append(f"Vertical region {i}{label_suffix} error: {exc}")

    for i, region in enumerate(horiz_regions or []):
        side = region.get("side", "right")
        side_ranges = _horiz_side_ranges(side, qxy_min_full, qxy_max_full)
        if not side_ranges:
            notes.append(f"Horizontal region {i} ({side}): no qxy data on that side for this geometry.")
            continue
        for label_suffix, ip_range, mirror in side_ranges:
            try:
                qxy_x, I = integrate_1d_grazing_incidence(
                    arr, fi,
                    sample_orientation=sample_orientation,
                    incident_angle_rad=incident_angle_rad,
                    tilt_angle_rad=tilt_angle_rad,
                    ip_range=ip_range,
                    oop_range=(region["qz_min"], region["qz_max"]),
                    vertical_integration=False,
                    n_points=n_pts_1d,
                    mask=mask,
                )
                keep = I > 0
                if not keep.any():
                    notes.append(
                        f"Horizontal region {i}{label_suffix}: no valid (unmasked, positive) "
                        "pixels in this range."
                    )
                    continue
                # Mirror the left side to positive x — otherwise invisible
                # whenever the shared x-axis is log-scaled, same reasoning
                # as the vertical region's lower side above.
                x_vals = -qxy_x[keep] if mirror else qxy_x[keep]
                curves.append({
                    "x": x_vals.tolist(), "y": I[keep].tolist(),
                    "name": (
                        f"Horizontal qz=[{region['qz_min']:.3g}, {region['qz_max']:.3g}] "
                        f"→ I(qxy){label_suffix}"
                    ),
                    "color": _region_color("horiz", i),
                })
            except Exception as exc:
                notes.append(f"Horizontal region {i}{label_suffix} error: {exc}")

    return fig2d, {"curves": curves, "notes": notes}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Render the combined 1-D plot from stored curves, applying the Q Range
#     trim live — no pyFAI re-run needed, mirrors update_1d_plot in
#     callbacks_scattering_2d.py.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-1d-graph", "figure"),
    Input("gi-integration-store", "data"),
    Input("gi-qrange-store", "data"),
    Input("scat-log-y-toggle", "value"),
    Input("scat-log-x-toggle", "value"),
    prevent_initial_call=True,
)
def render_gi_1d_plot(store_data, q_range, log_y, log_x):
    if not store_data:
        raise PreventUpdate

    curves = store_data.get("curves", [])
    notes = store_data.get("notes", [])

    q_min = q_range.get("q_min") if q_range else None
    q_max = q_range.get("q_max") if q_range else None

    fig1d = go.Figure()
    for curve in curves:
        x = np.array(curve["x"])
        y = np.array(curve["y"])
        if q_min is not None and q_max is not None:
            keep = (x >= q_min) & (x <= q_max)
            x, y = x[keep], y[keep]
        fig1d.add_trace(go.Scatter(
            x=x.tolist(), y=y.tolist(),
            mode="lines",
            name=curve["name"],
            line=dict(width=1.5, color=curve["color"]),
        ))

    for note_i, note in enumerate(notes):
        fig1d.add_annotation(
            text=note,
            xref="paper", yref="paper", x=0.5, y=1.05 + 0.05 * note_i, showarrow=False,
            font=dict(size=11, color="red"),
        )

    ytype = "log" if (log_y and "log" in log_y) else "linear"
    xtype = "log" if (log_x and "log" in log_x) else "linear"
    fig1d.update_layout(
        xaxis_title="q / q<sub>xy</sub> / q<sub>z</sub> (Å⁻¹)",
        xaxis_type=xtype,
        yaxis_title="Intensity (a.u.)",
        yaxis_type=ytype,
        margin=dict(l=10, r=10, t=30, b=10),
        uirevision="gi-1d",
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


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Apply Q Range
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("gi-qrange-store", "data", allow_duplicate=True),
    Input("gi-qrange-apply-btn", "n_clicks"),
    State("gi-qrange-min", "value"),
    State("gi-qrange-max", "value"),
    prevent_initial_call=True,
)
def apply_gi_qrange(n_clicks, q_min, q_max):
    if q_min is None or q_max is None:
        raise PreventUpdate
    return {"q_min": q_min, "q_max": q_max}
