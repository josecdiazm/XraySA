from dash import html
import dash_bootstrap_components as dbc

layout = dbc.Container(
    className="mt-4",
    children=[
        dbc.Row(
            dbc.Col(html.H4("Grazing Incidence Scattering (GISAXS/GIWAXS)"))
        ),
        dbc.Row(
            dbc.Col(html.P("Content coming soon."))
        ),
    ],
)