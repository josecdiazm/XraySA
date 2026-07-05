
"""
Small callback helpers shared across callback modules.
"""

import os
import base64
import shutil
import tempfile

import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback
from dash.exceptions import PreventUpdate

from utils.native_dialog import pick_folder


def register_folder_browse_callback(input_id: str):
    """Wire a folder_picker()'s Browse button to a native Finder dialog."""

    @callback(
        Output(input_id, "value"),
        Input(f"{input_id}-browse-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def browse(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        path = pick_folder()
        if path is None:
            raise PreventUpdate
        return path


def wedge_overlay_trace(az_min, az_max, q_min, q_max, *, color="beige"):
    """
    Build a Plotly Scatter trace outlining an azimuthal wedge — an annular
    sector between q_min/q_max radii and az_min/az_max angles (degrees,
    standard azimuthal-integration convention: 0° = +x axis, increasing
    clockwise when displayed, matching ai.integrate1d's azimuth_range).

    Drawn directly in whatever (x, y) plane the caller's plot uses — for
    the ordinary qx/qy image this is geometrically exact; for GI-SWAXS's
    qxy/qz remap it's a deliberate simplification (that space isn't a true
    polar remap of the detector), but reuses the same overlay shape.

    Returns None if any bound is missing (nothing to draw).
    """
    if any(v is None for v in (az_min, az_max, q_min, q_max)):
        return None

    ang_min = np.deg2rad(-float(az_max))
    ang_max = np.deg2rad(-float(az_min))
    arc_angles = np.linspace(ang_min, ang_max, 120)

    q_min_w = float(q_min)
    q_max_w = float(q_max)

    outer_x = q_max_w * np.cos(arc_angles)
    outer_y = q_max_w * np.sin(arc_angles)
    inner_x = q_min_w * np.cos(arc_angles[::-1])
    inner_y = q_min_w * np.sin(arc_angles[::-1])

    wedge_x = np.concatenate([outer_x, inner_x, [outer_x[0]]])
    wedge_y = np.concatenate([outer_y, inner_y, [outer_y[0]]])

    return go.Scatter(
        x=wedge_x,
        y=wedge_y,
        mode="lines",
        line=dict(color=color, width=1.5, dash="2px,2px"),
        fill="none",
        name="Wedge",
        showlegend=False,
        hovertemplate=(
            f"az: [{az_min:.1f}°, {az_max:.1f}°]<br>"
            f"q: [{q_min_w:.3g}, {q_max_w:.3g}] Å⁻¹<extra></extra>"
        ),
    )


AZIMUTH_COLORS = ["magenta", "gold", "cyan", "orchid", "chartreuse"]
DEFAULT_1D_COLOR = "#1f77b4"


def azimuth_color(index: int) -> str:
    """Cycle through AZIMUTH_COLORS — shared so every tab's azimuthal wedges/
    curves use the same palette instead of drifting out of sync."""
    return AZIMUTH_COLORS[index % len(AZIMUTH_COLORS)]


def stage_dropped_files(contents_list, filenames_list, prev_tempdir, *, prefix="xraysa_upload_") -> str:
    """
    Decode dcc.Upload's dropped-file contents into a fresh temp folder
    (removing the previous one first, if any, so a session doesn't
    accumulate one temp dir per drop), returning that folder's path.

    Callers point their existing folder-path pipeline at the returned
    directory instead of adding a second, upload-aware file-handling path —
    this is what lets Batch SWAXS / SWAXS Merging / Resonant Scattering's
    drag-and-drop reuse 100% of their tested folder-based processing code.
    """
    if prev_tempdir and os.path.isdir(prev_tempdir):
        shutil.rmtree(prev_tempdir, ignore_errors=True)

    tempdir = tempfile.mkdtemp(prefix=prefix)

    for contents, filename in zip(contents_list, filenames_list):
        try:
            _header, b64data = contents.split(",", 1)
            raw = base64.b64decode(b64data)
            with open(os.path.join(tempdir, filename), "wb") as fh:
                fh.write(raw)
        except Exception:
            continue

    return tempdir


def error_figure(message: str) -> go.Figure:
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
