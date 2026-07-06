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

**macOS / Linux:**

```bash
git clone https://github.com/josecdiazm/XraySA.git
cd XraySA
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/josecdiazm/XraySA.git
cd XraySA
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Notes for Windows:
- If `Activate.ps1` fails because script execution is disabled, run
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once, then
  retry the activation line.
- If `python` isn't recognized, or points to an unexpected install (e.g.
  MSYS2/Git Bash's Python instead of a normal Windows one), check
  `Get-Command python -All` to see every `python.exe` on your PATH, and
  either reorder PATH or invoke the correct one directly by its full path,
  e.g. `& "C:\Users\<you>\AppData\Local\Programs\Python\Python3xx\python.exe" -m venv venv`.
- The clone URL above uses HTTPS, not SSH — it works with no GitHub login
  or SSH key needed, since this repo is public. If you get a
  `Permission denied (publickey)` error, you're likely using an
  `git@github.com:...`-style SSH URL instead; switch to the HTTPS one shown
  here.

## Running

```bash
python app.py
```

The app runs at [http://127.0.0.1:8050](http://127.0.0.1:8050).

## Updating

If you cloned this repo with `git`, pull the latest changes and reinstall
dependencies (in case new ones were added):

```bash
cd XraySA
git pull
pip install -r requirements.txt
```

If you instead downloaded a ZIP of the repo rather than using `git clone`,
there's no update command — download a fresh ZIP from
[the repo's main branch](https://github.com/josecdiazm/XraySA/archive/refs/heads/main.zip)
and replace the old folder. If you expect to update regularly, it's worth
switching to `git clone` once so future updates are just `git pull`.

## Notes

- Built on [pyFAI](https://pyfai.readthedocs.io/) for detector calibration/azimuthal integration and [fabio](https://fabio.readthedocs.io/) for reading detector image formats (edf, cbf, tif, etc.), in addition to `.npy`/`.npz`.
- Batch SWAXS uses Dash's background callbacks (`dash[diskcache]`) for progress bars on long-running batch jobs.
- Folder inputs (Batch SWAXS, SWAXS Merging) can be filled via a native folder-picker dialog, cross-platform through tkinter, run in a subprocess to avoid freezing the app.
- File inputs (Resonant Scattering, SWAXS Merging, Batch SWAXS) also support drag-and-drop as an alternative to browsing.
- This is a local-only tool (server and browser on the same machine) — it is not hardened for exposure on a network.
