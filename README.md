# XraySA

X-ray Scattering Analysis Tools — a Dash web app for reducing and analyzing fixed-energy and resonant X-ray scattering (SAXS/WAXS/GI-SWAXS) data from synchrotron beamlines.

## Tabs

- **PTable** — periodic table element lookup
- **XAS Calculations** — sample-stack transmission/attenuation calculations across an energy range, via [XrayDB](https://xraypy.github.io/XrayDB/)
- **Scattering 2D & 1D** — the core scattering tool: upload a detector image (and optionally a `.poni` calibration file), set up pyFAI geometry, and run azimuthal integration
  - Live 2-D views in both pixel space and remapped qx/qy space, plus 1-D I(q) and cake (q vs. χ) plots
  - Hot-pixel masking (square/circular regions by center + size), independent of intensity thresholding
  - An accumulating azimuthal wedge region list (add/remove/clear), each drawn on the q-space image and producing its own I(q) curve
  - Q-range filtering, multiple output units, and CSV export
- **Grazing Incidence (GI-SWAXS)** — promotes the shared pyFAI integrator to a `FiberIntegrator` for grazing-incidence geometry (incident/tilt angle, sample orientation)
  - qxy/qz detector image with an adjustable display range, azimuthal wedges, and accumulating vertical/horizontal line-cut regions (each mirrorable about qxy=0/qz=0)
  - Combined 1-D plot overlaying every azimuthal/vertical/horizontal curve, with its own Q-range trim
- **Resonant Scattering** — load a folder of detector images spanning an energy series (energy parsed from each filename); per-file 2-D/1-D preview with the wavelength overridden from that file's own energy, an ROI accumulator on the pixel-space image, a background NEXAFS job (ROI intensity vs. energy), and a background energy-colored 1-D overlay across the whole series
- **Batch SWAXS** — run 1-D and/or 2-D q-space processing over a whole folder of detector images in the background (with a live progress bar); choose either the Scattering 2D & 1D (azimuthal) or Grazing Incidence (fiber) integrator, reusing that tab's geometry/regions
- **SWAXS Merging** — average multiple integrated profiles and merge/splice two averaged profiles together

## Setup

Requires Python 3.

```bash
git clone git@github.com:josecdiazm/XraySA.git
cd XraySA
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

The app runs at [http://127.0.0.1:8050](http://127.0.0.1:8050).

## Notes

- Built on [pyFAI](https://pyfai.readthedocs.io/) for detector calibration/azimuthal integration and [fabio](https://fabio.readthedocs.io/) for reading detector image formats (edf, cbf, tif, etc.), in addition to `.npy`/`.npz`.
- Batch SWAXS uses Dash's background callbacks (`dash[diskcache]`) for progress bars on long-running batch jobs.
- Folder inputs (Batch SWAXS, SWAXS Merging) can be filled via a native folder-picker dialog, cross-platform through tkinter, run in a subprocess to avoid freezing the app.
- File inputs (Resonant Scattering, SWAXS Merging, Batch SWAXS) also support drag-and-drop as an alternative to browsing.
- This is a local-only tool (server and browser on the same machine) — it is not hardened for exposure on a network.
