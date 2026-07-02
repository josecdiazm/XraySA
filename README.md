# XraySA

X-ray Spectroscopy & Scattering Tools — a Dash web app with tabs for:

- **PTable** — periodic table element lookup
- **XAS Calculations** — X-ray absorption spectroscopy
- **Scattering 2D & 1D** — 2D/1D scattering data processing
- **Grazing Incidence (GI-SWAXS)** — grazing-incidence scattering
- **Resonant Scattering**
- **SAXS/WAXS Merging**

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
