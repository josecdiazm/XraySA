
"""
Utility functions for the Resonant Scattering tab: scanning an energy-series
folder, parsing each file's energy from its filename, and summing
region-of-interest (ROI) intensity for NEXAFS-style analysis.
"""

from __future__ import annotations
import re
import numpy as np

from utils.batch_utils import list_folder_images, filter_excluded, load_image_from_disk

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
