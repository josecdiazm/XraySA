
"""
Utility functions for the SWAXS Merging tab: averaging repeated 1-D
scans, scaling/merging averaged SAXS and WAXS profiles, and writing
results to disk.
"""

from __future__ import annotations
import os
import numpy as np

PROFILE_EXTENSIONS = (".csv", ".txt")


def list_csv_files(folder_path: str) -> list[str]:
    """Return sorted CSV/TXT profile filenames in *folder_path*."""
    if not folder_path or not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    names = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(PROFILE_EXTENSIONS) and os.path.isfile(os.path.join(folder_path, f))
    ]
    return sorted(names)


def _split_line(line: str) -> list[str]:
    return line.split(",") if "," in line else line.split()


def read_1d_csv(file_path: str) -> dict:
    """
    Read a 1-D profile (q/unit,I[,sigma]) from a CSV or whitespace-delimited
    TXT file. Non-numeric lines (headers/comments) are skipped; the first
    such line's first token is used as the q-unit label.
    """
    with open(file_path) as fh:
        raw_lines = [line.strip() for line in fh if line.strip()]

    unit = "q"
    data_rows = []
    for line in raw_lines:
        parts = _split_line(line)
        try:
            q_val, I_val = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            if not data_rows and parts:
                unit = parts[0].lstrip("#").strip() or unit
            continue
        data_rows.append(parts)

    if not data_rows:
        raise ValueError(f"No numeric data found in '{os.path.basename(file_path)}'.")

    q = np.array([float(r[0]) for r in data_rows])
    I = np.array([float(r[1]) for r in data_rows])
    sigma = np.array([float(r[2]) for r in data_rows]) if len(data_rows[0]) > 2 else None

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
