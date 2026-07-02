from dash import html
import dash_bootstrap_components as dbc

layout = dbc.Container(
    className="mt-4",
    children=[
        dbc.Row(
            dbc.Col(html.H4("Resonant Scattering"))
        ),
        dbc.Row(
            dbc.Col(html.P("Content coming soon."))
        ),
    ],
)