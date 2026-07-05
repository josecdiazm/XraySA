
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
from utils.batch_utils import (
    list_folder_images,
    filter_excluded,
    process_file_1d,
    process_file_2d_png,
    process_file_1d_gi_csv,
    process_file_2d_gi_png,
    process_file_energy_series_1d,
)
from utils.resonant_utils import compute_nexafs_series, write_nexafs_csv
from callbacks._shared import register_folder_browse_callback, stage_dropped_files

register_folder_browse_callback("batch-folder-input")
register_folder_browse_callback("batch-output-folder")


# ─────────────────────────────────────────────────────────────────────────────
# 0.  Toggle sections by integrator mode — Resonant Scattering bypasses this
#     tab's own folder/file list entirely, reusing whatever's loaded on the
#     Resonant Scattering tab instead.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("batch-folder-section", "style"),
    Output("batch-files-card", "style"),
    Output("batch-mode-section", "style"),
    Output("batch-resonant-output-section", "style"),
    Input("batch-integrator-mode", "value"),
)
def toggle_integrator_sections(integrator_mode):
    is_resonant = integrator_mode == "resonant"
    hidden = {"display": "none"}
    shown = {}
    return (
        hidden if is_resonant else shown,
        hidden if is_resonant else shown,
        hidden if is_resonant else shown,
        shown if is_resonant else hidden,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 0.5.  Drag-and-drop files → stage into a temp folder, reusing the existing
#       folder-path pipeline unchanged (apply_exclusion_filter, run_batch).
#       This is what lets someone without files already on this machine (a
#       different computer, an OS with no native folder-browse support) use
#       Batch SWAXS the same way as typing a local path.
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("batch-all-files", "data", allow_duplicate=True),
    Output("batch-folder-input", "value", allow_duplicate=True),
    Output("batch-folder-status", "children", allow_duplicate=True),
    Output("batch-upload-tempdir-store", "data"),
    Input("batch-upload-files", "contents"),
    State("batch-upload-files", "filename"),
    State("batch-upload-tempdir-store", "data"),
    prevent_initial_call=True,
)
def handle_dropped_files(contents_list, filenames_list, prev_tempdir):
    if not contents_list or not filenames_list:
        raise PreventUpdate

    tempdir = stage_dropped_files(contents_list, filenames_list, prev_tempdir,
                                   prefix="xraysa_batch_upload_")
    files = list_folder_images(tempdir)
    if not files:
        return no_update, tempdir, "✘ None of the dropped files were a supported image format.", tempdir

    status = f"✔ Received {len(files)} dropped file(s) — staged in a temporary folder for this session."
    return files, tempdir, status, tempdir


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
        State("batch-integrator-mode", "value"),
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
        # Q Range
        State("scat-qrange-min", "value"),
        State("scat-qrange-max", "value"),
        # Display options
        State("scat-colorscale-dropdown", "value"),
        State("scat-log-toggle", "value"),
        # Grazing-incidence-specific geometry/regions (only used when
        # batch-integrator-mode == "gisaxs")
        State("gi-incident-angle", "value"),
        State("gi-tilt-angle", "value"),
        State("gi-sample-orientation", "value"),
        State("gi-npt-ip", "value"),
        State("gi-npt-oop", "value"),
        State("gi-display-qxy-min", "value"),
        State("gi-display-qxy-max", "value"),
        State("gi-display-qz-min", "value"),
        State("gi-display-qz-max", "value"),
        State("gi-azimuth-regions-store", "data"),
        State("gi-vert-regions-store", "data"),
        State("gi-horiz-regions-store", "data"),
        State("gi-qrange-min", "value"),
        State("gi-qrange-max", "value"),
        # Resonant-Scattering-specific (only used when
        # batch-integrator-mode == "resonant"); this tab's own folder/file
        # checklist is bypassed entirely in that mode.
        State("batch-resonant-output-mode", "value"),
        State("reson-file-store", "data"),
        State("reson-folder-input", "value"),
        State("reson-roi-store", "data"),
        State("reson-energy-region-select", "value"),
        State("reson-energy-start-idx", "value"),
        State("reson-energy-end-idx", "value"),
        State("reson-energy-step", "value"),
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
    integrator_mode,
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
    q_range_min, q_range_max,
    colorscale,
    log_scale,
    gi_incident_angle_deg, gi_tilt_angle_deg, gi_sample_orientation, gi_npt_ip, gi_npt_oop,
    gi_display_qxy_min, gi_display_qxy_max, gi_display_qz_min, gi_display_qz_max,
    gi_azimuth_regions, gi_vert_regions, gi_horiz_regions,
    gi_qrange_min, gi_qrange_max,
    resonant_output_mode, reson_entries, reson_folder_path, reson_rois,
    reson_region_choice, reson_start_idx, reson_end_idx, reson_step,
):
    if not output_folder:
        return 0, "", "Select an output folder first.", ""

    os.makedirs(output_folder, exist_ok=True)

    if integrator_mode == "resonant":
        return _run_resonant_batch(
            set_progress, output_folder, resonant_output_mode,
            reson_entries, reson_folder_path, reson_rois,
            reson_region_choice, azimuth_regions,
            reson_start_idx, reson_end_idx, reson_step,
            distance_mm, bcx, bcy, px_x_um, px_y_um, rot1_deg, rot2_deg, rot3_deg,
            n_pts, unit, mask_low, mask_high,
        )

    if not selected_files or not folder_path:
        return 0, "", "Select files and an input folder first.", ""

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

    is_log = bool(log_scale and "log" in log_scale)
    is_gisaxs = integrator_mode == "gisaxs"

    gi_incident_angle_rad = np.deg2rad(float(gi_incident_angle_deg or 0))
    gi_tilt_angle_rad = np.deg2rad(float(gi_tilt_angle_deg or 0))
    gi_sample_orientation = int(gi_sample_orientation or 1)

    total = len(selected_files)
    log_lines = []
    start = time.time()

    for i, fname in enumerate(selected_files, start=1):
        file_path = os.path.join(folder_path, fname)
        try:
            if mode == "2d":
                if is_gisaxs:
                    out_path = process_file_2d_gi_png(
                        file_path, ai,
                        sample_orientation=gi_sample_orientation,
                        incident_angle_rad=gi_incident_angle_rad,
                        tilt_angle_rad=gi_tilt_angle_rad,
                        n_ip=int(gi_npt_ip or 500), n_oop=int(gi_npt_oop or 500),
                        mask_low=mask_low, mask_high=mask_high,
                        cbar_min=cbar_min, cbar_max=cbar_max,
                        display_qxy_min=gi_display_qxy_min, display_qxy_max=gi_display_qxy_max,
                        display_qz_min=gi_display_qz_min, display_qz_max=gi_display_qz_max,
                        colorscale=colorscale, log_scale=is_log,
                        output_dir=output_folder,
                    )
                else:
                    out_path = process_file_2d_png(
                        file_path, ai,
                        n_points=int(n_pts or 500),
                        mask_low=mask_low, mask_high=mask_high,
                        cbar_min=cbar_min, cbar_max=cbar_max,
                        colorscale=colorscale, log_scale=is_log,
                        output_dir=output_folder,
                    )
            else:
                if is_gisaxs:
                    out_path = process_file_1d_gi_csv(
                        file_path, ai,
                        sample_orientation=gi_sample_orientation,
                        incident_angle_rad=gi_incident_angle_rad,
                        tilt_angle_rad=gi_tilt_angle_rad,
                        n_ip=int(gi_npt_ip or 500), n_oop=int(gi_npt_oop or 500),
                        n_points_1d=int(n_pts or 1000),
                        mask_low=mask_low, mask_high=mask_high,
                        azimuth_regions=gi_azimuth_regions,
                        vert_regions=gi_vert_regions,
                        horiz_regions=gi_horiz_regions,
                        q_min=gi_qrange_min, q_max=gi_qrange_max,
                        output_dir=output_folder,
                    )
                else:
                    out_path = process_file_1d(
                        file_path, ai,
                        n_points=int(n_pts or 1000),
                        unit=unit or "q_A^-1",
                        mask_low=mask_low, mask_high=mask_high,
                        azimuth_regions=azimuth_regions,
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


# ─────────────────────────────────────────────────────────────────────────────
# 3.5.  Resonant Scattering batch export — bypasses this tab's own folder/file
#       list, reusing whatever's loaded/configured on the Resonant
#       Scattering tab instead.
# ─────────────────────────────────────────────────────────────────────────────

def _run_resonant_batch(
    set_progress, output_folder, resonant_output_mode,
    entries, folder_path, rois,
    region_choice, azimuth_regions,
    start_idx, end_idx, step,
    distance_mm, bcx, bcy, px_x_um, px_y_um, rot1_deg, rot2_deg, rot3_deg,
    n_pts, unit, mask_low, mask_high,
):
    if not entries or not folder_path:
        return 0, "", "Load a folder on the Resonant Scattering tab first.", ""

    if resonant_output_mode == "nexafs":
        if not rois:
            return 0, "", "Define at least one ROI on the Resonant Scattering tab first.", ""

        total = len(entries)
        start_time = time.time()

        def _progress(i, _total):
            elapsed = time.time() - start_time
            pct = int(i / total * 100)
            set_progress((pct, f"{i}/{total}", f"{i}/{total} files — elapsed {elapsed:.1f}s", ""))

        nexafs_data = compute_nexafs_series(
            entries, folder_path, rois,
            mask_low=mask_low, mask_high=mask_high,
            progress_cb=_progress,
        )
        out_path = os.path.join(output_folder, "nexafs.csv")
        write_nexafs_csv(nexafs_data, out_path)

        final_text = f"Done — NEXAFS CSV written for {total} energies in {time.time() - start_time:.1f}s"
        return 100, f"{total}/{total}", final_text, f"✔ Wrote {os.path.basename(out_path)}"

    # resonant_output_mode == "energy_series"
    ai = build_integrator(
        detector_distance_m=float(distance_mm) * 1e-3,
        wavelength_m=1e-10,  # placeholder — overridden per file below
        beam_center_x=float(bcx),
        beam_center_y=float(bcy),
        pixel_size_x=float(px_x_um) * 1e-6,
        pixel_size_y=float(px_y_um) * 1e-6,
        rot1=np.deg2rad(float(rot1_deg or 0)),
        rot2=np.deg2rad(float(rot2_deg or 0)),
        rot3=np.deg2rad(float(rot3_deg or 0)),
    )

    start_idx = max(0, int(start_idx or 0))
    end_idx = int(end_idx) if end_idx is not None else len(entries) - 1
    end_idx = min(end_idx, len(entries) - 1)
    step = max(1, int(step or 1))
    indices = list(range(start_idx, end_idx + 1, step))
    if not indices:
        return 0, "", "No files in the selected index range.", ""

    az_range = None
    if region_choice != "full" and azimuth_regions:
        region = azimuth_regions[int(region_choice)]
        az_range = (region["az_min"], region["az_max"])

    total = len(indices)
    log_lines = []
    start_time = time.time()

    for i, idx in enumerate(indices, start=1):
        entry = entries[idx]
        file_path = os.path.join(folder_path, entry["filename"])
        try:
            out_path = process_file_energy_series_1d(
                file_path, ai,
                energy_eV=entry["energy"],
                n_points=int(n_pts or 1000),
                unit=unit or "q_A^-1",
                mask_low=mask_low, mask_high=mask_high,
                azimuth_range=az_range,
                output_dir=output_folder,
            )
            log_lines.append(f"✔ {entry['filename']} → {os.path.basename(out_path)}")
        except Exception as exc:
            log_lines.append(f"✘ {entry['filename']}: {exc}")

        elapsed = time.time() - start_time
        pct = int(i / total * 100)
        set_progress((pct, f"{i}/{total}", f"{i}/{total} files — elapsed {elapsed:.1f}s", "\n".join(log_lines)))

    final_text = f"Done — {total}/{total} files in {time.time() - start_time:.1f}s"
    return 100, f"{total}/{total}", final_text, "\n".join(log_lines)
