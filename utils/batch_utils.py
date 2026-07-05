
"""
Utility functions for batch processing a folder of detector images:
scanning/filtering files on disk, and running 1-D or 2-D q-space
processing on each one, writing results directly to an output folder.
"""

from __future__ import annotations
import os
import numpy as np
import plotly.graph_objects as go

import plotly.io as pio

from utils.scattering_utils import (
    HAS_FABIO,
    integrate_1d,
    integrate_2d_qxy,
    apply_threshold_mask,
    build_pixel_mask,
    build_fiber_integrator,
    integrate_2d_grazing_incidence,
    integrate_1d_grazing_incidence,
    power_of_ten_ticks,
    cbar_zrange,
    horiz_side_ranges,
    vert_side_ranges,
    energy_to_wavelength,
)

# Matches the scale set on the interactive plots' camera-export button
# (toImageButtonOptions in tabs/tab_scattering_2d.py, tab_gisaxs.py,
# tab_resonant.py), so batch-exported PNGs hold up to zooming just as well.
PNG_EXPORT_SCALE = 4

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


def write_multi_curve_csv(curves: list[dict], out_path: str, q_min=None, q_max=None) -> None:
    """
    Write several possibly-different-length XY curves side by side in one
    CSV, each as its own (x, I[, sigma]) column group headed by the curve's
    name — used whenever a batch job has multiple line cuts (several
    azimuthal wedges, or GI's azimuthal + vertical + horizontal regions)
    per file, rather than one file per curve.

    curves: list of {"x": array-like, "y": array-like, "sigma": array-like
            or None, "name": str}. An optional [q_min, q_max] trims each
            curve's x independently before writing. Shorter columns are
            padded with blank cells past their own length.
    """
    prepared = []
    for curve in curves:
        x = np.asarray(curve["x"], dtype=float)
        y = np.asarray(curve["y"], dtype=float)
        sigma = curve.get("sigma")
        sigma = np.asarray(sigma, dtype=float) if sigma is not None else None

        if q_min is not None and q_max is not None:
            keep = (x >= q_min) & (x <= q_max)
            x, y = x[keep], y[keep]
            if sigma is not None:
                sigma = sigma[keep]

        label = str(curve.get("name", "curve")).replace(",", ";")
        prepared.append((label, x, y, sigma))

    max_len = max((len(x) for _, x, _, _ in prepared), default=0)

    header_cells = []
    for label, _, _, sigma in prepared:
        header_cells += [f"{label}_x", f"{label}_I"]
        if sigma is not None:
            header_cells.append(f"{label}_sigma")
    header = ",".join(header_cells)

    rows = []
    for i in range(max_len):
        cells = []
        for _, x, y, sigma in prepared:
            if i < len(x):
                cells.append(f"{x[i]:.6g}")
                cells.append(f"{y[i]:.6g}")
                if sigma is not None:
                    cells.append(f"{sigma[i]:.6g}")
            else:
                cells.append("")
                cells.append("")
                if sigma is not None:
                    cells.append("")
        rows.append(",".join(cells))

    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))


def process_file_1d(file_path: str, ai, *, n_points, unit, mask_low, mask_high,
                     azimuth_regions=None, error_model, q_min=None, q_max=None,
                     output_dir: str) -> str:
    """
    Integrate one file to a 1-D profile per azimuthal region (columns in
    one CSV), or a single unrestricted integration when azimuth_regions is
    empty/None — mirrors the Scattering 2D & 1D tab's Integrate 1-D
    fallback. Returns the output path.
    """
    arr = load_image_from_disk(file_path)
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)

    curves = []
    if azimuth_regions:
        for region in azimuth_regions:
            q, I, sigma = integrate_1d(
                arr, ai,
                n_points=n_points,
                unit=unit,
                mask=mask,
                azimuth_range=(region["az_min"], region["az_max"]),
                error_model=error_model,
            )
            curves.append({
                "x": q, "y": I, "sigma": sigma,
                "name": f"Azimuthal [{region['az_min']:.1f},{region['az_max']:.1f}]",
            })
    else:
        q, I, sigma = integrate_1d(
            arr, ai,
            n_points=n_points,
            unit=unit,
            mask=mask,
            azimuth_range=None,
            error_model=error_model,
        )
        curves.append({"x": q, "y": I, "sigma": sigma, "name": unit})

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_1D.csv")
    write_multi_curve_csv(curves, out_path, q_min=q_min, q_max=q_max)

    return out_path


def process_file_2d_png(file_path: str, ai, *, n_points, mask_low, mask_high,
                         cbar_min=None, cbar_max=None,
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

    zmin, zmax = cbar_zrange(cbar_min, cbar_max, log_scale)

    colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if log_scale:
        tickvals, ticktext = power_of_ten_ticks(display, vmin=zmin, vmax=zmax)
        if tickvals is not None:
            colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            x=qx, y=qy, z=display,
            zmin=zmin, zmax=zmax,
            colorscale=colorscale or "Viridis",
            colorbar=colorbar,
        )
    )
    fig.update_layout(
        xaxis_title="q<sub>x</sub> (Å⁻¹)",
        yaxis_title="q<sub>y</sub> (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
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
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        width=800,
        height=700,
    )

    # Unlike the interactive q-space plot, this PNG's width/height are fixed,
    # so the axis domain Plotly will actually render (after scaleanchor +
    # constrain="domain" shrink one axis to keep pixels square) is fully
    # knowable here — resolve it and snap the colorbar to the real image
    # edge instead of leaving a gap for non-square detectors.
    full = pio.full_figure_for_development(fig, warn=False)
    xdom = full.layout.xaxis.domain
    ydom = full.layout.yaxis.domain
    fig.data[0].colorbar.x = xdom[1] + 0.02
    fig.data[0].colorbar.y = (ydom[0] + ydom[1]) / 2
    fig.data[0].colorbar.len = ydom[1] - ydom[0]
    fig.data[0].colorbar.yanchor = "middle"

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_qspace.png")
    fig.write_image(out_path, scale=PNG_EXPORT_SCALE)

    return out_path


def process_file_2d_gi_png(file_path: str, ai, *,
                            sample_orientation, incident_angle_rad, tilt_angle_rad,
                            n_ip, n_oop, mask_low, mask_high, pixel_mask_regions=None,
                            cbar_min=None, cbar_max=None,
                            display_qxy_min=None, display_qxy_max=None,
                            display_qz_min=None, display_qz_max=None,
                            colorscale, log_scale, output_dir: str) -> str:
    """
    Integrate one file to a grazing-incidence qxy/qz remapped image and
    save a PNG, styled identically to the interactive GI-SWAXS 2-D plot
    (no wedge/region overlays — this is the plain heatmap). Returns the
    output path.
    """
    arr = load_image_from_disk(file_path)
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    fi = build_fiber_integrator(ai)
    I2d, qxy, qz = integrate_2d_grazing_incidence(
        arr, fi,
        sample_orientation=sample_orientation,
        incident_angle_rad=incident_angle_rad,
        tilt_angle_rad=tilt_angle_rad,
        n_ip=n_ip, n_oop=n_oop,
        mask=mask,
    )

    qxy_min_full, qxy_max_full = float(qxy.min()), float(qxy.max())
    qz_min_full, qz_max_full = float(qz.min()), float(qz.max())

    display = I2d.copy()
    if log_scale:
        with np.errstate(divide="ignore", invalid="ignore"):
            display = np.where(display > 0, np.log10(display), np.nan)

    zmin, zmax = cbar_zrange(cbar_min, cbar_max, log_scale)

    colorbar = dict(
        title=dict(text="Scattering Intensity (a.u.)", side="right"),
        x=1.02, thickness=20, len=1, lenmode="fraction",
        ticks="outside",
        outlinecolor="black", outlinewidth=1,
    )
    if log_scale:
        tickvals, ticktext = power_of_ten_ticks(display, vmin=zmin, vmax=zmax)
        if tickvals is not None:
            colorbar.update(tickvals=tickvals, ticktext=ticktext)

    fig = go.Figure(
        go.Heatmap(
            x=qxy, y=qz, z=display,
            zmin=zmin, zmax=zmax,
            colorscale=colorscale or "Viridis",
            colorbar=colorbar,
        )
    )

    # Display range (like matplotlib's set_xlim/set_ylim) — a blank field
    # falls back to the full computed extent for that side, same as the
    # interactive GI 2-D display-range panel.
    xaxis_range = [
        float(display_qxy_min) if display_qxy_min is not None else qxy_min_full,
        float(display_qxy_max) if display_qxy_max is not None else qxy_max_full,
    ]
    yaxis_range = [
        float(display_qz_min) if display_qz_min is not None else qz_min_full,
        float(display_qz_max) if display_qz_max is not None else qz_max_full,
    ]

    fig.update_layout(
        xaxis_title="q<sub>xy</sub> (Å⁻¹)",
        yaxis_title="q<sub>z</sub> (Å⁻¹)",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            range=xaxis_range,
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
            range=yaxis_range,
            autorange=False,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="outside", tickcolor="black", linecolor="black", mirror=True,
            minor=dict(ticks="outside", tickcolor="black"),
        ),
        plot_bgcolor="black",
        paper_bgcolor="white",
        font=dict(family="Arial", size=14, color="black"),
        width=800,
        height=700,
    )

    # Same fixed-size colorbar-domain fix as process_file_2d_png.
    full = pio.full_figure_for_development(fig, warn=False)
    xdom = full.layout.xaxis.domain
    ydom = full.layout.yaxis.domain
    fig.data[0].colorbar.x = xdom[1] + 0.02
    fig.data[0].colorbar.y = (ydom[0] + ydom[1]) / 2
    fig.data[0].colorbar.len = ydom[1] - ydom[0]
    fig.data[0].colorbar.yanchor = "middle"

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_gispace.png")
    fig.write_image(out_path, scale=PNG_EXPORT_SCALE)

    return out_path


def process_file_1d_gi_csv(file_path: str, ai, *,
                            sample_orientation, incident_angle_rad, tilt_angle_rad,
                            n_ip, n_oop, n_points_1d,
                            mask_low, mask_high, pixel_mask_regions=None,
                            azimuth_regions=None, vert_regions=None, horiz_regions=None,
                            q_min=None, q_max=None, output_dir: str) -> str:
    """
    Integrate one file's azimuthal + vertical + horizontal GI regions (or
    a single unrestricted azimuthal integration when none are defined) and
    write every resulting curve as its own column group in one CSV —
    mirrors the GI-SWAXS tab's combined 1-D plot. Returns the output path.
    """
    arr = load_image_from_disk(file_path)
    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    fi = build_fiber_integrator(ai)

    I2d, qxy, qz = integrate_2d_grazing_incidence(
        arr, fi,
        sample_orientation=sample_orientation,
        incident_angle_rad=incident_angle_rad,
        tilt_angle_rad=tilt_angle_rad,
        n_ip=n_ip, n_oop=n_oop,
        mask=mask,
    )
    qxy_min_full, qxy_max_full = float(qxy.min()), float(qxy.max())
    qz_min_full, qz_max_full = float(qz.min()), float(qz.max())

    curves = []

    if azimuth_regions:
        for region in azimuth_regions:
            q, I, _sigma = integrate_1d(
                arr, ai, n_points=n_points_1d, unit="q_A^-1", mask=mask,
                azimuth_range=(region["az_min"], region["az_max"]),
            )
            keep = I > 0
            if keep.any():
                curves.append({
                    "x": q[keep], "y": I[keep], "sigma": None,
                    "name": f"Azimuthal [{region['az_min']:.1f},{region['az_max']:.1f}]",
                })
    else:
        q, I, _sigma = integrate_1d(
            arr, ai, n_points=n_points_1d, unit="q_A^-1", mask=mask, azimuth_range=None,
        )
        keep = I > 0
        if keep.any():
            curves.append({"x": q[keep], "y": I[keep], "sigma": None, "name": "Azimuthal (full)"})

    for region in (vert_regions or []):
        for label_suffix, oop_range, mirror in vert_side_ranges(
            region.get("side", "upper"), qz_min_full, qz_max_full
        ):
            qz_x, I = integrate_1d_grazing_incidence(
                arr, fi,
                sample_orientation=sample_orientation,
                incident_angle_rad=incident_angle_rad,
                tilt_angle_rad=tilt_angle_rad,
                ip_range=(region["qxy_min"], region["qxy_max"]),
                oop_range=oop_range,
                vertical_integration=True,
                n_points=n_points_1d,
                mask=mask,
            )
            keep = I > 0
            if not keep.any():
                continue
            x_vals = -qz_x[keep] if mirror else qz_x[keep]
            curves.append({
                "x": x_vals, "y": I[keep], "sigma": None,
                "name": (
                    f"Vertical qxy=[{region['qxy_min']:.3g},{region['qxy_max']:.3g}]{label_suffix}"
                ),
            })

    for region in (horiz_regions or []):
        for label_suffix, ip_range, mirror in horiz_side_ranges(
            region.get("side", "right"), qxy_min_full, qxy_max_full
        ):
            qxy_x, I = integrate_1d_grazing_incidence(
                arr, fi,
                sample_orientation=sample_orientation,
                incident_angle_rad=incident_angle_rad,
                tilt_angle_rad=tilt_angle_rad,
                ip_range=ip_range,
                oop_range=(region["qz_min"], region["qz_max"]),
                vertical_integration=False,
                n_points=n_points_1d,
                mask=mask,
            )
            keep = I > 0
            if not keep.any():
                continue
            x_vals = -qxy_x[keep] if mirror else qxy_x[keep]
            curves.append({
                "x": x_vals, "y": I[keep], "sigma": None,
                "name": (
                    f"Horizontal qz=[{region['qz_min']:.3g},{region['qz_max']:.3g}]{label_suffix}"
                ),
            })

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_gi1D.csv")
    write_multi_curve_csv(curves, out_path, q_min=q_min, q_max=q_max)

    return out_path


def process_file_energy_series_1d(file_path: str, ai, *, energy_eV, n_points, unit,
                                   mask_low, mask_high, pixel_mask_regions=None,
                                   azimuth_range=None, output_dir: str) -> str:
    """
    Integrate one Resonant Scattering energy-series file to a single I(q)
    profile, with ai.wavelength overridden from that file's own filename-
    parsed energy right before integrating — mirrors the interactive tab's
    per-file wavelength override. Writes a plain two-column (q, I) CSV,
    one file per energy (not combined, unlike the GI/Scattering batch
    exports). Returns the output path.
    """
    arr = load_image_from_disk(file_path)

    wl_A = energy_to_wavelength(energy_eV / 1000.0)
    ai.wavelength = wl_A * 1e-10

    mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
    mask |= build_pixel_mask(arr.shape, pixel_mask_regions)

    q, I, _sigma = integrate_1d(
        arr, ai,
        n_points=n_points,
        unit=unit,
        mask=mask,
        azimuth_range=azimuth_range,
    )

    stem = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{stem}_energyseries_1D.csv")

    header = f"{unit},I"
    rows = [f"{qi:.6g},{Ii:.6g}" for qi, Ii in zip(q, I)]
    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))

    return out_path
