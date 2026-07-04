
"""
Utility functions for batch processing a folder of detector images:
scanning/filtering files on disk, and running 1-D or 2-D q-space
processing on each one, writing results directly to an output folder.
"""

from __future__ import annotations
import os
import numpy as np
import plotly.graph_objects as go

from utils.scattering_utils import (
    HAS_FABIO,
    integrate_1d,
    integrate_2d_qxy,
    apply_threshold_mask,
    power_of_ten_ticks,
)

if HAS_FABIO:
    import fabio

# ── Supported detector image extensions ────────────────────────────────────────
IMAGE_EXTENSIONS = (".tif", ".tiff", ".cbf", ".edf", ".mar", ".npy", ".npz")


def list_folder_images(folder_path: str) -> list[str]:
    """Return sorted filenames in *folder_path* matching supported image extensions."""
    if not folder_path or not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    names = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(IMAGE_EXTENSIONS) and os.path.isfile(os.path.join(folder_path, f))
    ]
    return sorted(names)


def filter_excluded(filenames: list[str], exclude_keywords: list[str]) -> list[str]:
    """Drop any filename containing one of the (case-insensitive) exclude keywords."""
    keywords = [k.strip().lower() for k in exclude_keywords if k.strip()]
    if not keywords:
        return list(filenames)
    return [f for f in filenames if not any(k in f.lower() for k in keywords)]


def load_image_from_disk(file_path: str) -> np.ndarray:
    """Load a detector image directly from a filesystem path into a 2-D numpy array."""
    lower = file_path.lower()

    if lower.endswith(".npy"):
        return np.load(file_path).astype(float)

    if lower.endswith(".npz"):
        npz = np.load(file_path)
        key = list(npz.files)[0]
        return npz[key].astype(float)

    if not HAS_FABIO:
        raise RuntimeError("fabio is not installed; cannot read this file format.")

    return fabio.open(file_path).data.astype(float)


def process_file_1d(file_path: str, ai, *, n_points, unit, mask_low, mask_high,
                     azimuth_range, error_model, q_min=None, q_max=None,
                     output_dir: str) -> str:
    """Integrate one file to a 1-D profile and save it as CSV. Returns the output path."""
    arr = load_image_from_disk(file_path)
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)

    q, I, sigma = integrate_1d(
        arr, ai,
        n_points=n_points,
        unit=unit,
        mask=mask,
        azimuth_range=azimuth_range,
        error_model=error_model,
    )

    if q_min is not None and q_max is not None:
        keep = (q >= q_min) & (q <= q_max)
        q, I = q[keep], I[keep]
        if sigma is not None:
            sigma = sigma[keep]

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_1D.csv")

    header = f"{unit},I"
    rows = [f"{qi:.6g},{Ii:.6g}" for qi, Ii in zip(q, I)]
    if sigma is not None:
        header += ",sigma"
        rows = [f"{r},{s:.6g}" for r, s in zip(rows, sigma)]

    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))

    return out_path


def process_file_2d_png(file_path: str, ai, *, n_points, mask_low, mask_high,
                         colorscale, log_scale, output_dir: str) -> str:
    """Integrate one file to a qx/qy remapped image and save a PNG. Returns the output path."""
    arr = load_image_from_disk(file_path)
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)

    I_qxy, qx, qy = integrate_2d_qxy(arr, ai, n_points=n_points, mask=mask)

    display = I_qxy.copy()
    if mask_low is not None or mask_high is not None:
        qxy_mask = apply_threshold_mask(I_qxy, low=mask_low, high=mask_high)
        display[qxy_mask] = np.nan

    if log_scale:
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)

    colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
    )
    if log_scale:
        tickvals, ticktext = power_of_ten_ticks(display)
        if tickvals is not None:
            colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            x=qx, y=qy, z=display,
            colorscale=colorscale or "Viridis",
            colorbar=colorbar,
        )
    )
    fig.update_layout(
        xaxis_title="qx (Å⁻¹)",
        yaxis_title="qy (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            range=[float(qx.min()), float(qx.max())],
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
            range=[float(qy.min()), float(qy.max())],
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
        ),
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        width=800,
        height=700,
    )

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_qspace.png")
    fig.write_image(out_path)

    return out_path
