
"""
Utility functions for the SWAXS Merging tab: averaging repeated 1-D
scans, computing a profile's currently-displayed (q-trimmed,
scaled/offset) view, subtracting/merging/scaling profiles, and writing
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


def apply_view(profile: dict, qmin_idx: int, qmax_idx: int, scale: float, offset: float) -> dict:
    """
    Return the currently-displayed view of *profile*: intensity scaled and
    offset (always computed from the untouched raw arrays, never
    cumulative), then trimmed to the inclusive index range
    [qmin_idx, qmax_idx]. Never mutates *profile*.
    """
    I = profile["I"] * scale + offset
    sigma = profile["sigma"] * scale if profile.get("sigma") is not None else None

    lo, hi = qmin_idx, qmax_idx + 1
    return {
        "q": profile["q"][lo:hi],
        "I": I[lo:hi],
        "sigma": sigma[lo:hi] if sigma is not None else None,
        "unit": profile["unit"],
    }


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
    return {"q": ref_q, "I": I_avg, "sigma": None, "unit": unit}


def subtract_profiles(base: dict, other: dict) -> dict:
    """
    Subtract *other* from *base*, interpolating *other* onto *base*'s q
    grid if they don't already match. Propagates sigma in quadrature when
    both profiles have it (and their q grids already match, so no
    interpolated-uncertainty guesswork is needed).
    """
    if np.array_equal(base["q"], other["q"]):
        I_other = other["I"]
        sigma_other = other.get("sigma")
    else:
        I_other = np.interp(base["q"], other["q"], other["I"])
        sigma_other = None

    sigma = None
    if base.get("sigma") is not None and sigma_other is not None:
        sigma = np.sqrt(base["sigma"] ** 2 + sigma_other ** 2)

    return {"q": base["q"], "I": base["I"] - I_other, "sigma": sigma, "unit": base["unit"]}


def merge_profiles(lo: dict, hi: dict, splice_q: float) -> dict:
    """
    Splice *lo* (q <= splice_q) and *hi* (q > splice_q) into one profile,
    sorted by q. Assumes both profiles share the same q unit and are
    already scaled to match in the splice region.
    """
    lo_mask = lo["q"] <= splice_q
    hi_mask = hi["q"] > splice_q

    q = np.concatenate([lo["q"][lo_mask], hi["q"][hi_mask]])
    I = np.concatenate([lo["I"][lo_mask], hi["I"][hi_mask]])

    order = np.argsort(q)
    return {"q": q[order], "I": I[order], "sigma": None, "unit": lo["unit"]}


def merge_profiles_pairwise(base: dict, others: list[dict], splice_q: float) -> dict:
    """
    Fold *others* into *base* one at a time, lowest-q profile first,
    splicing each pair at *splice_q* via merge_profiles(). Directionality
    (which of the pair is "lo" vs "hi") is decided per-pair by comparing
    minimum q, so it doesn't matter whether *base* itself is the lower- or
    higher-q member.
    """
    if not others:
        return {"q": base["q"], "I": base["I"], "sigma": None, "unit": base["unit"]}

    current = base
    for other in sorted(others, key=lambda p: float(np.min(p["q"]))):
        if float(np.min(current["q"])) <= float(np.min(other["q"])):
            current = merge_profiles(current, other, splice_q)
        else:
            current = merge_profiles(other, current, splice_q)
    return current


def write_1d_csv(profile: dict, output_dir: str, filename: str) -> str:
    """Write a 1-D profile dict to *filename* inside *output_dir*. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)

    sigma = profile.get("sigma")
    if sigma is not None:
        header = f"{profile['unit']},I,sigma"
        rows = [f"{qi:.6g},{Ii:.6g},{si:.6g}" for qi, Ii, si in zip(profile["q"], profile["I"], sigma)]
    else:
        header = f"{profile['unit']},I"
        rows = [f"{qi:.6g},{Ii:.6g}" for qi, Ii in zip(profile["q"], profile["I"])]

    with open(out_path, "w") as fh:
        fh.write(header + "\n" + "\n".join(rows))

    return out_path
