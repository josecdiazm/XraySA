
"""
Dash callbacks for the Batch SWAXS tab.
"""

from __future__ import annotations
import os
import time
import numpy as np

from dash import Input, Output, State, callback, no_update
from dash.exceptions import PreventUpdate

from utils.scattering_utils import build_integrator, energy_to_wavelength
from utils.batch_utils import list_folder_images, filter_excluded, process_file_1d, process_file_2d_png
from callbacks._shared import register_folder_browse_callback

register_folder_browse_callback("batch-folder-input")
register_folder_browse_callback("batch-output-folder")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Load folder → list all matching image files
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("batch-all-files", "data"),
    Output("batch-folder-status", "children"),
    Input("batch-load-folder-btn", "n_clicks"),
    State("batch-folder-input", "value"),
    prevent_initial_call=True,
)
def load_folder(n_clicks, folder_path):
    if not n_clicks:
        raise PreventUpdate

    try:
        files = list_folder_images(folder_path)
    except Exception as exc:
        return [], f"✘ {exc}"

    if not files:
        return [], f"No supported image files found in '{folder_path}'."

    return files, f"✔ Found {len(files)} file(s) in '{folder_path}'."


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Apply exclusion keywords → populate checklist
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("batch-file-checklist", "options"),
    Output("batch-file-checklist", "value"),
    Output("batch-file-count", "children"),
    Input("batch-all-files", "data"),
    Input("batch-exclude-input", "value"),
)
def apply_exclusion_filter(all_files, exclude_text):
    if not all_files:
        return [], [], "No files loaded yet."

    keywords = (exclude_text or "").split(",")
    kept = filter_excluded(all_files, keywords)

    options = [{"label": f, "value": f} for f in kept]
    count_text = f"{len(kept)} of {len(all_files)} file(s) selected."
    return options, kept, count_text


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Run the batch job with live progress
# ─────────────────────────────────────────────────────────────────────────────

_PROGRESS_OUTPUTS = [
    Output("batch-progress", "value"),
    Output("batch-progress", "label"),
    Output("batch-progress-text", "children"),
    Output("batch-log", "children"),
]


@callback(
    output=_PROGRESS_OUTPUTS,
    inputs=Input("batch-run-btn", "n_clicks"),
    state=[
        State("batch-file-checklist", "value"),
        State("batch-folder-input", "value"),
        State("batch-output-folder", "value"),
        State("batch-mode", "value"),
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
        State("scat-azimuth-min", "value"),
        State("scat-azimuth-max", "value"),
        State("scat-error-model", "value"),
        # Q Range
        State("scat-qrange-min", "value"),
        State("scat-qrange-max", "value"),
        # Display options
        State("scat-colorscale-dropdown", "value"),
        State("scat-log-toggle", "value"),
    ],
    background=True,
    progress=_PROGRESS_OUTPUTS,
    running=[(Output("batch-run-btn", "disabled"), True, False)],
    prevent_initial_call=True,
)
def run_batch(
    set_progress,
    n_clicks,
    selected_files,
    folder_path,
    output_folder,
    mode,
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
    az_min, az_max,
    error_model,
    q_range_min, q_range_max,
    colorscale,
    log_scale,
):
    if not selected_files or not folder_path or not output_folder:
        return 0, "", "Select files, an input folder, and an output folder first.", ""

    os.makedirs(output_folder, exist_ok=True)

    if wl_or_e == "energy":
        wl_A = energy_to_wavelength(float(energy_keV))
    else:
        wl_A = float(wavelength_A)

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

    az_range = None
    if az_min is not None and az_max is not None:
        az_range = (float(az_min), float(az_max))

    is_log = bool(log_scale and "log" in log_scale)

    total = len(selected_files)
    log_lines = []
    start = time.time()

    for i, fname in enumerate(selected_files, start=1):
        file_path = os.path.join(folder_path, fname)
        try:
            if mode == "2d":
                out_path = process_file_2d_png(
                    file_path, ai,
                    n_points=int(n_pts or 500),
                    mask_low=mask_low, mask_high=mask_high,
                    colorscale=colorscale, log_scale=is_log,
                    output_dir=output_folder,
                )
            else:
                out_path = process_file_1d(
                    file_path, ai,
                    n_points=int(n_pts or 1000),
                    unit=unit or "q_A^-1",
                    mask_low=mask_low, mask_high=mask_high,
                    azimuth_range=az_range,
                    error_model=error_model or None,
                    q_min=q_range_min, q_max=q_range_max,
                    output_dir=output_folder,
                )
            log_lines.append(f"✔ {fname} → {os.path.basename(out_path)}")
        except Exception as exc:
            log_lines.append(f"✘ {fname}: {exc}")

        elapsed = time.time() - start
        avg = elapsed / i
        remaining = avg * (total - i)
        pct = int(i / total * 100)
        progress_text = (
            f"{i}/{total} files — elapsed {elapsed:.1f}s — "
            f"est. remaining {remaining:.1f}s"
        )

        set_progress((pct, f"{i}/{total}", progress_text, "\n".join(log_lines)))

    total_elapsed = time.time() - start
    final_text = f"Done — {total}/{total} files in {total_elapsed:.1f}s"
    return 100, f"{total}/{total}", final_text, "\n".join(log_lines)
