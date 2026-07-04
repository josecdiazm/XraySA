
"""
Utility functions for 2D → 1D azimuthal integration using pyFAI.
All geometry is handled here; the callback layer stays thin.
"""

from __future__ import annotations
import io
import base64
import numpy as np

_SUPERSCRIPT_MAP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def power_of_ten_ticks(display: np.ndarray, vmin: float | None = None, vmax: float | None = None):
    """
    Build (tickvals, ticktext) for a colorbar whose underlying data has
    already been log10-transformed, so it reads as "10ⁿ" (matching the
    1-D plot's power-of-10 axis notation) instead of the raw exponent.

    vmin/vmax (already in log10 space) override the data-derived range,
    so the ticks follow a user-set Cbar min/max instead of the array's
    own extent.
    """
    if vmin is not None and vmax is not None:
        lo = int(np.floor(vmin))
        hi = int(np.ceil(vmax))
    else:
        finite = display[np.isfinite(display)]
        if finite.size == 0:
            return None, None
        lo = int(np.floor(finite.min()))
        hi = int(np.ceil(finite.max()))
    if hi <= lo:
        hi = lo + 1
    exps = list(range(lo, hi + 1))
    ticktext = [f"10{str(e).translate(_SUPERSCRIPT_MAP)}" for e in exps]
    return exps, ticktext


def cbar_zrange(cbar_min, cbar_max, is_log: bool):
    """
    Convert user-facing Cbar min/max (always entered in raw intensity
    units, like matplotlib's imshow vmin/vmax) into the zmin/zmax a
    heatmap trace needs. When the log toggle is on, the displayed array
    is already log10-transformed, so the bounds must be too.
    """
    def _conv(v):
        if v is None:
            return None
        v = float(v)
        if is_log:
            return np.log10(v) if v > 0 else None
        return v
    return _conv(cbar_min), _conv(cbar_max)

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import fabio
    HAS_FABIO = True
except ImportError:
    HAS_FABIO = False

try:
    import pyFAI
    try:
        from pyFAI.integrator.azimuthal import AzimuthalIntegrator
    except ImportError:
        from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False

# ── Image loading ─────────────────────────────────────────────────────────────

def decode_upload(contents: str, filename: str) -> np.ndarray:
    """
    Decode a Dash upload component's base64 string into a 2-D numpy array.
    Supports: .npy, .npz, and any format fabio can read (edf, cbf, tif, …).
    """
    content_type, content_string = contents.split(",", 1)
    raw = base64.b64decode(content_string)

    fname_lower = filename.lower()

    if fname_lower.endswith(".npy"):
        return np.load(io.BytesIO(raw))

    if fname_lower.endswith(".npz"):
        npz = np.load(io.BytesIO(raw))
        key = list(npz.files)[0]
        return npz[key]

    if HAS_FABIO:
        buf = io.BytesIO(raw)
        buf.name = filename          # fabio uses the name to pick the reader
        img = fabio.open(buf)
        return img.data.astype(float)

    raise RuntimeError(
        f"Cannot read '{filename}': fabio is not installed and the file is "
        "not .npy / .npz."
    )


# ── Mask helpers ──────────────────────────────────────────────────────────────

def apply_threshold_mask(
    data: np.ndarray,
    low: float | None = None,
    high: float | None = None,
) -> np.ndarray:
    """
    Return a boolean mask (True = pixel is INVALID / masked).
    Pixels below *low* or above *high* are masked.
    """
    mask = np.zeros(data.shape, dtype=bool)
    if low is not None:
        mask |= data < low
    if high is not None:
        mask |= data > high
    return mask


def build_pixel_mask(
    shape: tuple[int, int],
    regions: list[dict] | None,
) -> np.ndarray:
    """
    Build a boolean mask (True = pixel is INVALID / masked) from a list of
    user-defined hot-pixel regions, e.g. for masking known hot/dead pixels
    that aren't caught by a simple intensity threshold.

    Each region dict has keys:
        shape : "square" or "circle"
        row   : centre row (pixel)
        col   : centre column (pixel)
        size  : half-width in pixels for "square", radius in pixels for "circle"
    """
    mask = np.zeros(shape, dtype=bool)
    if not regions:
        return mask

    ny, nx = shape
    Y, X = np.ogrid[:ny, :nx]

    for region in regions:
        row, col, size = region.get("row"), region.get("col"), region.get("size")
        if row is None or col is None or not size:
            continue

        if region.get("shape") == "circle":
            mask |= (X - col) ** 2 + (Y - row) ** 2 <= size ** 2
        else:
            r0 = max(int(round(row - size)), 0)
            r1 = min(int(round(row + size)) + 1, ny)
            c0 = max(int(round(col - size)), 0)
            c1 = min(int(round(col + size)) + 1, nx)
            mask[r0:r1, c0:c1] = True

    return mask


# ── Azimuthal integration ─────────────────────────────────────────────────────

def build_integrator(
    *,
    detector_distance_m: float,
    wavelength_m: float,
    beam_center_x: float,
    beam_center_y: float,
    pixel_size_x: float,
    pixel_size_y: float,
    rot1: float = 0.0,
    rot2: float = 0.0,
    rot3: float = 0.0,
) -> "AzimuthalIntegrator":
    """
    Instantiate and return a pyFAI AzimuthalIntegrator from physical parameters.

    Parameters
    ----------
    detector_distance_m  : sample-to-detector distance in **metres**
    wavelength_m         : X-ray wavelength in **metres**
    beam_center_x/y      : beam centre in **pixels** (x = col, y = row)
    pixel_size_x/y       : pixel pitch in **metres**
    rot1/rot2/rot3        : detector rotations in **radians** (pyFAI/poni convention)
    """
    if not HAS_PYFAI:
        raise RuntimeError("pyFAI is not installed.")

    ai = AzimuthalIntegrator(
        dist=detector_distance_m,
        poni1=beam_center_y * pixel_size_y,   # metres from top edge
        poni2=beam_center_x * pixel_size_x,   # metres from left edge
        rot1=rot1,
        rot2=rot2,
        rot3=rot3,
        wavelength=wavelength_m,
    )
    ai.detector.pixel1 = pixel_size_y
    ai.detector.pixel2 = pixel_size_x
    return ai


def integrate_1d(
    data: np.ndarray,
    ai: "AzimuthalIntegrator",
    *,
    n_points: int = 1000,
    unit: str = "q_A^-1",
    mask: np.ndarray | None = None,
    azimuth_range: tuple[float, float] | None = None,
    error_model: str | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """
    Perform 1-D azimuthal integration.

    Returns
    -------
    q       : scattering vector array (in chosen *unit*)
    I       : integrated intensity
    sigma   : uncertainty array or None
    """
    kwargs: dict = dict(
        npt=n_points,
        unit=unit,
        correctSolidAngle=True,
        safe=False,
    )
    if mask is not None:
        kwargs["mask"] = mask.astype(np.int8)
    if azimuth_range is not None:
        kwargs["azimuth_range"] = azimuth_range
    if error_model:
        kwargs["error_model"] = error_model

    result = ai.integrate1d(data, **kwargs)
    q = result.radial
    I = result.intensity
    sigma = getattr(result, "sigma", None)
    return q, I, sigma


def integrate_2d(
    data: np.ndarray,
    ai: "AzimuthalIntegrator",
    *,
    n_radial: int = 500,
    n_azimuth: int = 360,
    unit: str = "q_A^-1",
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Perform 2-D (q, chi) integration (cake plot).

    Returns
    -------
    I2d   : 2-D intensity array  shape (n_azimuth, n_radial)
    q     : radial axis
    chi   : azimuthal axis in degrees
    """
    kwargs: dict = dict(
        npt_rad=n_radial,
        npt_azim=n_azimuth,
        unit=unit,
        correctSolidAngle=True,
        safe=False,
    )
    if mask is not None:
        kwargs["mask"] = mask.astype(np.int8)

    result = ai.integrate2d(data, **kwargs)
    return result.intensity, result.radial, result.azimuthal


def integrate_2d_qxy(
    data: np.ndarray,
    ai: "AzimuthalIntegrator",
    *,
    n_points: int = 500,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Remap detector image onto a regular qx/qy grid using pyFAI.

    PyFAI handles all the geometry internally when given the
    unit=("qx_nm^-1", "qy_nm^-1") argument.

    Returns
    -------
    I2d   : 2-D intensity array  shape (n_points, n_points)
    qx    : qx axis in Å⁻¹
    qy    : qy axis in Å⁻¹
    """
    kwargs: dict = dict(
        npt_rad=n_points,
        npt_azim=n_points,
        unit=("qx_nm^-1", "qy_nm^-1"),
        method="bbox",
        correctSolidAngle=True,
        safe=False,
    )
    if mask is not None:
        kwargs["mask"] = mask.astype(np.int8)

    result = ai.integrate2d(data, **kwargs)

    # Convert axes from nm⁻¹ to Å⁻¹ (divide by 10)
    qx = result.radial / 10.0
    qy = -result.azimuthal / 10.0   # sign flip matches your original code

    return result.intensity, qx, qy


# ── Grazing-incidence (fiber) integration ─────────────────────────────────────

def build_fiber_integrator(ai: "AzimuthalIntegrator"):
    """
    Promote a standard AzimuthalIntegrator to a pyFAI FiberIntegrator, which
    adds the grazing-incidence geometry (incident/tilt angle, sample
    orientation) needed for GI-SWAXS integration.
    """
    if not HAS_PYFAI:
        raise RuntimeError("pyFAI is not installed.")
    return ai.promote(type_="pyFAI.integrator.fiber.FiberIntegrator")


def integrate_2d_grazing_incidence(
    data: np.ndarray,
    fi,
    *,
    sample_orientation: int,
    incident_angle_rad: float,
    tilt_angle_rad: float = 0.0,
    n_ip: int = 500,
    n_oop: int = 500,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Remap a grazing-incidence detector image onto a regular qxy (in-plane) /
    qz (out-of-plane) grid using pyFAI's FiberIntegrator.

    Returns
    -------
    I2d  : 2-D intensity array, shape (n_oop, n_ip)
    qxy  : in-plane axis in Å⁻¹
    qz   : out-of-plane axis in Å⁻¹
    """
    kwargs: dict = dict(
        npt_ip=n_ip,
        npt_oop=n_oop,
        unit_ip="qip_A^-1",
        unit_oop="qoop_A^-1",
        sample_orientation=sample_orientation,
        incident_angle=incident_angle_rad,
        tilt_angle=tilt_angle_rad,
        correctSolidAngle=True,
        method="splitpix",
    )
    if mask is not None:
        kwargs["mask"] = mask.astype(np.int8)

    intensity, qxy, qz = fi.integrate2d_grazing_incidence(data, **kwargs)
    return intensity, qxy, qz


def integrate_1d_grazing_incidence(
    data: np.ndarray,
    fi,
    *,
    sample_orientation: int,
    incident_angle_rad: float,
    tilt_angle_rad: float = 0.0,
    ip_range: tuple[float, float],
    oop_range: tuple[float, float],
    vertical_integration: bool,
    n_points: int = 1000,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    1-D grazing-incidence line-cut integration, restricted to an in-plane
    (qxy) window and an out-of-plane (qz) window.

    vertical_integration=True  -> integrated over the ip_range window, x = qz
    vertical_integration=False -> integrated over the oop_range window, x = qxy

    A "vertical region" (a user-picked qxy band) should be passed as
    ip_range with vertical_integration=True; a "horizontal region" (a
    user-picked qz band) should be passed as oop_range with
    vertical_integration=False. The other range should span the full
    detector extent so it doesn't additionally clip the profile.

    Returns
    -------
    x : qz (vertical_integration=True) or qxy (False) axis, Å⁻¹
    I : integrated intensity
    """
    kwargs: dict = dict(
        npt_ip=n_points,
        npt_oop=n_points,
        unit_ip="qip_A^-1",
        unit_oop="qoop_A^-1",
        sample_orientation=sample_orientation,
        incident_angle=incident_angle_rad,
        tilt_angle=tilt_angle_rad,
        ip_range=ip_range,
        oop_range=oop_range,
        vertical_integration=vertical_integration,
        correctSolidAngle=True,
    )
    if mask is not None:
        kwargs["mask"] = mask.astype(np.int8)

    x, I = fi.integrate1d_grazing_incidence(data, **kwargs)
    return x, I


# ── Unit conversion helpers ───────────────────────────────────────────────────

def q_to_twotheta(q: np.ndarray, wavelength_A: float) -> np.ndarray:
    """Convert q [Å⁻¹] → 2θ [degrees]."""
    sin_theta = q * wavelength_A / (4 * np.pi)
    sin_theta = np.clip(sin_theta, -1, 1)
    return 2 * np.degrees(np.arcsin(sin_theta))


def twotheta_to_q(twotheta_deg: np.ndarray, wavelength_A: float) -> np.ndarray:
    """Convert 2θ [degrees] → q [Å⁻¹]."""
    return (4 * np.pi / wavelength_A) * np.sin(np.deg2rad(twotheta_deg / 2))


def energy_to_wavelength(energy_keV: float) -> float:
    """Return wavelength in Å given photon energy in keV."""
    return 12.398 / energy_keV


def wavelength_to_energy(wavelength_A: float) -> float:
    """Return photon energy in keV given wavelength in Å."""
    return 12.398 / wavelength_A