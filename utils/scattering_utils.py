
"""
Utility functions for 2D → 1D azimuthal integration using pyFAI.
All geometry is handled here; the callback layer stays thin.
"""

from __future__ import annotations
import io
import base64
import numpy as np

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


# ── Azimuthal integration ─────────────────────────────────────────────────────

def build_integrator(
    *,
    detector_distance_m: float,
    wavelength_m: float,
    beam_center_x: float,
    beam_center_y: float,
    pixel_size_x: float,
    pixel_size_y: float,
    tilt: float = 0.0,
    tilt_plane_rotation: float = 0.0,
) -> "AzimuthalIntegrator":
    """
    Instantiate and return a pyFAI AzimuthalIntegrator from physical parameters.

    Parameters
    ----------
    detector_distance_m  : sample-to-detector distance in **metres**
    wavelength_m         : X-ray wavelength in **metres**
    beam_center_x/y      : beam centre in **pixels** (x = col, y = row)
    pixel_size_x/y       : pixel pitch in **metres**
    tilt                 : detector tilt angle in degrees
    tilt_plane_rotation  : rotation of the tilt plane in degrees
    """
    if not HAS_PYFAI:
        raise RuntimeError("pyFAI is not installed.")

    ai = AzimuthalIntegrator(
        dist=detector_distance_m,
        poni1=beam_center_y * pixel_size_y,   # metres from top edge
        poni2=beam_center_x * pixel_size_x,   # metres from left edge
        rot1=np.deg2rad(tilt),
        rot2=np.deg2rad(tilt_plane_rotation),
        rot3=0.0,
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