
"""
Utility functions for the Resonant Scattering tab: scanning an energy-series
folder, parsing each file's energy from its filename, and summing
region-of-interest (ROI) intensity for NEXAFS-style analysis.
"""

from __future__ import annotations
import os
import re
import numpy as np

from utils.batch_utils import list_folder_images, filter_excluded, load_image_from_disk
from utils.scattering_utils import apply_threshold_mask, build_pixel_mask

DEFAULT_ENERGY_PATTERN = r"_energy([\d.]+)_"


def _natural_key(text: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def parse_energy_from_filename(filename: str, pattern: str = DEFAULT_ENERGY_PATTERN) -> float | None:
    """Extract an energy value (eV) from a filename using *pattern*'s first capture group."""
    match = re.search(pattern, filename)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except (ValueError, IndexError):
        return None


def list_and_sort_by_energy(
    folder_path: str,
    exclude_keywords: list[str],
    energy_pattern: str = DEFAULT_ENERGY_PATTERN,
) -> list[dict]:
    """
    Scan folder_path for supported detector images, drop filenames matching
    exclude_keywords, natural-sort them, parse an energy value out of each
    filename, drop any file where the pattern didn't match, then re-sort the
    remaining files by that energy ascending — mirrors the notebook's
    natural_keys sort followed by the "re-sort together by energy" fix.

    Returns a list of {"filename": str, "energy": float} dicts.
    """
    files = list_folder_images(folder_path)
    files = filter_excluded(files, exclude_keywords)
    files = sorted(files, key=_natural_key)

    entries = []
    for f in files:
        energy = parse_energy_from_filename(f, energy_pattern)
        if energy is not None:
            entries.append({"filename": f, "energy": energy})

    entries.sort(key=lambda e: e["energy"])
    return entries


def compute_roi_sums(arr: np.ndarray, rois: list[dict]) -> dict[str, float]:
    """
    rois: list of {"name", "row_min", "row_max", "col_min", "col_max"}.
    Returns {name: summed intensity} for one already-masked array.
    """
    sums = {}
    for roi in rois:
        r0, r1 = int(roi["row_min"]), int(roi["row_max"])
        c0, c1 = int(roi["col_min"]), int(roi["col_max"])
        sums[roi["name"]] = float(np.sum(arr[r0:r1, c0:c1]))
    return sums


def compute_nexafs_series(
    entries: list[dict],
    folder_path: str,
    rois: list[dict],
    *,
    mask_low=None,
    mask_high=None,
    pixel_mask_regions=None,
    progress_cb=None,
) -> dict:
    """
    Loop every entry, sum each ROI's intensity (threshold + hot-pixel
    masking applied first), returning {"energies": [...], "roi_sums":
    {name: [...]}} — the NEXAFS series shared by both the interactive
    Resonant Scattering plot and the Batch SWAXS XANES/NEXAFS export.

    progress_cb(i, total), if given, is called after each file so the
    caller can report its own progress.
    """
    roi_names = [roi["name"] for roi in rois]
    roi_sums = {name: [] for name in roi_names}
    energies = []
    total = len(entries)

    for i, entry in enumerate(entries, start=1):
        energies.append(entry["energy"])
        try:
            arr = load_image_from_disk(os.path.join(folder_path, entry["filename"]))
            mask = apply_threshold_mask(arr, low=mask_low, high=mask_high)
            mask |= build_pixel_mask(arr.shape, pixel_mask_regions)
            display = arr.copy()
            display[mask] = 0
            sums = compute_roi_sums(display, rois)
        except Exception:
            sums = {name: None for name in roi_names}

        for name in roi_names:
            roi_sums[name].append(sums.get(name))

        if progress_cb is not None:
            progress_cb(i, total)

    return {"energies": energies, "roi_sums": roi_sums}


def write_nexafs_csv(nexafs_data: dict, out_path: str) -> None:
    """Write a NEXAFS series ({"energies", "roi_sums"}) as one CSV: energy,ROI_1,ROI_2,..."""
    energies = nexafs_data["energies"]
    roi_sums = nexafs_data["roi_sums"]
    names = list(roi_sums.keys())

    header = "energy," + ",".join(names)
    rows = []
    for i, e in enumerate(energies):
        cells = [f"{e:g}"]
        for name in names:
            v = roi_sums[name][i]
            cells.append(f"{v:.6g}" if v is not None else "")
        rows.append(",".join(cells))

    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))
