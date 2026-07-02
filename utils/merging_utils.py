
"""
Utility functions for the SWAXS Merging tab: averaging repeated 1-D
scans, scaling/merging averaged SAXS and WAXS profiles, and writing
results to disk.
"""

from __future__ import annotations
import os
import csv
import numpy as np

CSV_EXTENSION = ".csv"


def list_csv_files(folder_path: str) -> list[str]:
    """Return sorted CSV filenames in *folder_path*."""
    if not folder_path or not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    names = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(CSV_EXTENSION) and os.path.isfile(os.path.join(folder_path, f))
    ]
    return sorted(names)


def read_1d_csv(file_path: str) -> dict:
    """Read a 1-D profile CSV (q/unit,I[,sigma]) into arrays."""
    with open(file_path, newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = [row for row in reader if row]

    unit = header[0]
    has_sigma = len(header) > 2

    q = np.array([float(r[0]) for r in rows])
    I = np.array([float(r[1]) for r in rows])
    sigma = np.array([float(r[2]) for r in rows]) if has_sigma else None

    return {"q": q, "I": I, "sigma": sigma, "unit": unit}


def average_profiles(profiles: list[dict]) -> dict:
    """Average multiple 1-D profiles onto the first profile's q grid."""
    if not profiles:
        raise ValueError("No profiles to average.")

    ref_q = profiles[0]["q"]
    unit = profiles[0]["unit"]

    stack = []
    for p in profiles:
        if np.array_equal(p["q"], ref_q):
            stack.append(p["I"])
        else:
            stack.append(np.interp(ref_q, p["q"], p["I"]))

    I_avg = np.mean(np.vstack(stack), axis=0)
    return {"q": ref_q, "I": I_avg, "unit": unit}


def scale_profile(profile: dict, factor: float) -> dict:
    """Return a copy of *profile* with intensity multiplied by *factor*."""
    return {"q": profile["q"], "I": profile["I"] * factor, "unit": profile["unit"]}


def merge_profiles(saxs: dict, waxs: dict, splice_q: float) -> dict:
    """
    Splice SAXS (q <= splice_q) and WAXS (q > splice_q) into one profile,
    sorted by q. Assumes both profiles share the same q unit.
    """
    saxs_mask = saxs["q"] <= splice_q
    waxs_mask = waxs["q"] > splice_q

    q = np.concatenate([saxs["q"][saxs_mask], waxs["q"][waxs_mask]])
    I = np.concatenate([saxs["I"][saxs_mask], waxs["I"][waxs_mask]])

    order = np.argsort(q)
    return {"q": q[order], "I": I[order], "unit": saxs["unit"]}


def write_1d_csv(profile: dict, output_dir: str, filename: str) -> str:
    """Write a 1-D profile dict to *filename* inside *output_dir*. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)

    header = f"{profile['unit']},I"
    rows = [f"{qi:.6g},{Ii:.6g}" for qi, Ii in zip(profile["q"], profile["I"])]

    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))

    return out_path
