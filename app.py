
import diskcache
import dash
from dash import DiskcacheManager
import dash_bootstrap_components as dbc
from dash import dcc, html

# ── Tab layouts ───────────────────────────────────────────────────────────────
from tabs.tab_ptable import layout as ptable_layout
from tabs.tab_transmission import layout as transmission_layout
from tabs.tab_scattering_2d import layout as scattering_layout
from tabs.tab_resonant import layout as resonant_layout
from tabs.tab_gisaxs import layout as gisaxs_layout
from tabs.tab_batch_swaxs import layout as batch_swaxs_layout
from tabs.tab_merging import layout as merging_layout

# ── Register callbacks ────────────────────────────────────────────────────────
import callbacks.callbacks_scattering_2d
import callbacks.callbacks_ptable
import callbacks.callbacks_transmission
import callbacks.callbacks_batch_swaxs
import callbacks.callbacks_merging
import callbacks.callbacks_gisaxs

# ── Background callback manager (for batch progress) ──────────────────────────
_cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(_cache)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
    background_callback_manager=background_callback_manager,
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
                dbc.Tab(label="Resonant Scattering",         tab_id="tab-resonant",     children=resonant_layout),
                dbc.Tab(label="Grazing Incidence (GI-SWAXS)",tab_id="tab-gisaxs",       children=gisaxs_layout),
                dbc.Tab(label="Batch SWAXS",                 tab_id="tab-batch-swaxs",  children=batch_swaxs_layout),
                dbc.Tab(label="SWAXS Merging",                tab_id="tab-merging",      children=merging_layout),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=8050)