
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

# ── Tab layouts ───────────────────────────────────────────────────────────────
from tabs.tab_ptable import layout as ptable_layout
from tabs.tab_transmission import layout as transmission_layout
from tabs.tab_scattering_2d import layout as scattering_layout
from tabs.tab_resonant import layout as resonant_layout
from tabs.tab_gisaxs import layout as gisaxs_layout
from tabs.tab_merging import layout as merging_layout

# ── Register callbacks ────────────────────────────────────────────────────────
import callbacks.callbacks_scattering_2d
import callbacks.callbacks_ptable
import callbacks.callbacks_transmission

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True
)

app.title = "X-Ray Spectroscopy & Scattering Tools"

app.layout = dbc.Container(
    fluid=True,
    className="pb-4",
    children=[
        dbc.Row(
            dbc.Col(
                html.H2(
                    "X-Ray Spectroscopy & Scattering Tools",
                    className="text-center my-3"
                )
            )
        ),
        dbc.Tabs(
            id="main-tabs",
            active_tab="tab-ptable",
            children=[
                dbc.Tab(label="PTable",                      tab_id="tab-ptable",       children=ptable_layout),
                dbc.Tab(label="XAS Calculations",            tab_id="tab-transmission", children=transmission_layout),
                dbc.Tab(label="Scattering 2D & 1D",          tab_id="tab-scattering",   children=scattering_layout),
                dbc.Tab(label="Grazing Incidence (GI-SWAXS)",tab_id="tab-gisaxs",       children=gisaxs_layout),
                dbc.Tab(label="Resonant Scattering",         tab_id="tab-resonant",     children=resonant_layout),
                dbc.Tab(label="SAXS/WAXS Merging",           tab_id="tab-merging",      children=merging_layout),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=8050)